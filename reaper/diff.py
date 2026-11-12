"""What changed since a commit: the working tree (staged, unstaged, untracked) against `base`.

diff(root, graph, base) -> {
  base, commit, branch,
  files:  {path: added|modified|deleted}       every changed file, parsed or not
  stats:  {path: [lines added, lines removed]} (None for binary files)
  nodes:  {id: added|modified|deleted}         files and symbols (and ext: packages)
  extra_nodes: [node]                          nodes the current graph lacks: deleted ones as
                                               they were at the base, and changed unparsed files
  edges:  {added: [[src, dst, kind]], removed: [edge as it was at the base]}
}
- A file's status comes from git: in the tree now but not at the base = added, the other way
  round = deleted, in both and different = modified. Untracked files count (git's ignore rules
  and discover's skipped folders apply, as for the graph).
- A symbol is added / deleted when its id exists only now / only at the base. It is modified
  when a changed, non-blank line falls inside it and inside no deeper symbol: the lines git
  reports on the new side (checked against today's spans) and on the old side (against the
  base's spans). So a changed method marks the method, not its class.
- Links: the graph at the base is rebuilt from the base's version of the changed files plus the
  unchanged files as they are now, then compared with the current graph by (src, dst, kind).
"""

from __future__ import annotations

import os
import subprocess
from collections import defaultdict
from pathlib import Path

from reaper.discover import _skipped, language
from reaper.graph import EXTRACTED_LANGS, _inside, extract_source
from reaper.resolve import KIND_ORDER, STRENGTH, resolve

ADDED, MODIFIED, DELETED = "added", "modified", "deleted"
LETTER = {ADDED: "A", MODIFIED: "M", DELETED: "D"}
MAX_SYMBOLS_PER_FILE = 10
FILE_MODES = ("100644", "100755")  # regular files; symlinks and submodules are not mapped


class DiffError(Exception):
    """The comparison cannot be made (not a git repo, unknown base)."""


def _git(root: Path, *args: str) -> bytes:
    try:
        return subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=root,
                              capture_output=True, check=True).stdout
    except FileNotFoundError as e:
        raise DiffError("git is not installed") from e
    except subprocess.CalledProcessError as e:
        raise DiffError(e.stderr.decode(errors="replace").strip() or "git failed") from e


def _text(data: bytes) -> list[str]:
    return data.decode("utf-8", "replace").splitlines()


def _hunks(root: Path, commit: str, paths: list[str]) -> dict[str, tuple[set[int], set[int]]]:
    """{path: (changed lines at the base, changed lines now)} from `git diff -U0`."""
    out: dict[str, tuple[set[int], set[int]]] = {}
    if not paths:
        return out
    raw = _git(root, "diff", "-U0", "--no-renames", "--no-color", "--no-ext-diff", "--relative",
               "--src-prefix=a/", "--dst-prefix=b/", commit, "--", *paths)
    current = None
    for line in raw.decode("utf-8", "replace").splitlines():
        if line.startswith("+++ "):
            name = line[4:]
            current = name[2:] if name.startswith("b/") else None
            if current is not None:
                out.setdefault(current, (set(), set()))
        elif line.startswith("@@ ") and current is not None:
            old, new = line.split(" ")[1:3]  # "-a,b" "+c,d"
            for side, spec in ((0, old[1:]), (1, new[1:])):
                start, _, count = spec.partition(",")
                n = int(count) if count else 1
                out[current][side].update(range(int(start), int(start) + n))
    return out


def _innermost(spans: list[tuple[int, int, str]], line: int) -> str | None:
    """The deepest symbol whose lines contain `line` (smallest span wins)."""
    best = None
    for start, end, node_id in spans:
        if start <= line <= end and (best is None or end - start < best[0]):
            best = (end - start, node_id)
    return best[1] if best else None


def _spans(nodes: list[dict]) -> dict[str, list[tuple[int, int, str]]]:
    out = defaultdict(list)
    for n in nodes:
        if n.get("end_line") is not None:
            out[n["file"]].append((n["line"], n["end_line"], n["id"]))
    return out


def _edge_map(edges: list[dict]) -> dict[tuple[str, str, str], dict]:
    """One edge per (src, dst, kind): the strongest of a split pair."""
    out = {}
    for e in edges:
        key = (e["src"], e["dst"], e["kind"])
        if key not in out or STRENGTH[e["confidence"]] > STRENGTH[out[key]["confidence"]]:
            out[key] = e
    return out


def diff(root: str | os.PathLike, graph: dict, base: str = "HEAD",
         out: str | os.PathLike | None = None) -> dict:
    """Compare the working tree with `base`; `graph` is the current graph (see module doc)."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise DiffError(f"not a git repository: {root}")
    try:
        inside = _git(root, "rev-parse", "--is-inside-work-tree").strip() == b"true"
    except DiffError:
        inside = False
    if not inside:
        raise DiffError(f"not a git repository: {root}")
    try:
        commit = _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}").decode().strip()
    except DiffError:
        commit = ""
    if not commit:
        raise DiffError(f"unknown base: {base}")
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD").decode().strip()
    prefix = _git(root, "rev-parse", "--show-prefix").decode().strip()
    excluded = tuple(d.rstrip("/") + "/" for d in _inside(root, out))

    base_files = set()
    for entry in _git(root, "ls-tree", "-r", "-z", "--full-tree", commit).split(b"\0"):
        if not entry:
            continue
        meta, _, path = entry.decode("utf-8", "surrogateescape").partition("\t")
        if meta.split()[0] not in FILE_MODES or not path.startswith(prefix):
            continue
        rel = path[len(prefix):]
        if not _skipped(rel) and not rel.startswith(excluded):
            base_files.add(rel)

    stats: dict[str, list[int] | None] = {}
    numstat = _git(root, "diff", "--numstat", "-z", "--no-renames", "--relative", commit)
    for entry in numstat.split(b"\0"):
        if entry:
            plus, minus, path = entry.decode("utf-8", "surrogateescape").split("\t", 2)
            stats[path] = None if plus == "-" else [int(plus), int(minus)]

    now = graph["files"]
    files = {p: ADDED for p in now if p not in base_files}
    files.update({p: DELETED for p in base_files if p not in now})
    files.update({p: MODIFIED for p in base_files & now.keys() if p in stats})
    files = dict(sorted(files.items()))
    stats = {p: stats.get(p) if p in stats else [now[p]["lines"], 0] for p in files}

    # the graph at the base: changed files as they were, the rest as they are now
    parsed = lambda p: language(p) in EXTRACTED_LANGS  # noqa: E731
    old_src = {p: _git(root, "show", f"{commit}:{prefix}{p}")
               for p, s in files.items() if s != ADDED and parsed(p)}
    by_file_nodes, by_file_refs = defaultdict(list), defaultdict(list)
    for n in graph["nodes"]:
        if n["kind"] != "external":
            by_file_nodes[n["file"]].append(n)
    for r in graph["refs"]:
        by_file_refs[r["file"]].append(r)
    base_nodes, base_refs = [], []
    for p in sorted(base_files):  # same order as a full build
        if p in old_src:
            n, r = extract_source(p, language(p), old_src[p])
        else:
            n, r = by_file_nodes[p], by_file_refs[p]
        base_nodes.extend(n)
        base_refs.extend(r)
    base_nodes, base_edges = resolve(base_nodes, base_refs)

    cur = {n["id"]: n for n in graph["nodes"]}
    old = {n["id"]: n for n in base_nodes}
    nodes = {i: ADDED for i in cur if i not in old}
    nodes.update({i: DELETED for i in old if i not in cur})
    cur_spans, old_spans = _spans(graph["nodes"]), _spans(base_nodes)
    hunks = _hunks(root, commit, [p for p, s in files.items() if s == MODIFIED and parsed(p)])
    for p, (old_lines, new_lines) in hunks.items():
        new_text = _text((root / p).read_bytes())
        old_text = _text(old_src.get(p, b""))
        hit = set()
        for line in new_lines:
            if 0 < line <= len(new_text) and new_text[line - 1].strip():
                hit.add(_innermost(cur_spans[p], line))
        for line in old_lines:
            if 0 < line <= len(old_text) and old_text[line - 1].strip():
                hit.add(_innermost(old_spans[p], line))
        for i in hit:
            if i is not None and i in cur and i not in nodes:
                nodes[i] = MODIFIED
    for p, s in files.items():  # file nodes, parsed or not
        nodes.setdefault(p, s)

    extra = [old[i] for i in sorted(nodes) if nodes[i] == DELETED and i in old]
    extra += [{"id": p, "kind": "file", "name": p.rpartition("/")[2], "file": p, "line": 1,
               "signature": None, "doc": None}
              for p in files if p not in cur and p not in old]
    extra.sort(key=lambda n: n["id"])

    now_edges, old_edges = _edge_map(graph["edges"]), _edge_map(base_edges)
    added = [list(k) for k in sorted(now_edges.keys() - old_edges.keys())]
    removed = [old_edges[k] for k in sorted(old_edges.keys() - now_edges.keys())]
    return {"base": base, "commit": commit, "branch": None if branch == "HEAD" else branch,
            "files": files, "stats": stats, "nodes": dict(sorted(nodes.items())),
            "extra_nodes": extra, "edges": {"added": added, "removed": removed}}


def _stat(st: list[int] | None) -> str:
    if st is None:
        return "binary"
    return " ".join(t for t in (f"+{st[0]}" if st[0] else "", f"-{st[1]}" if st[1] else "") if t)


def format_diff(d: dict, graph: dict) -> str:
    """The terminal answer of `reaper diff`; `graph` is the current graph (for symbol lines)."""
    where = f"{d['commit'][:7]}, branch {d['branch']}" if d["branch"] else d["commit"][:7]
    if not d["files"]:
        return f"no changes since {d['base']} ({where})"
    count = {s: sum(1 for v in d["files"].values() if v == s) for s in (ADDED, MODIFIED, DELETED)}
    n = len(d["files"])
    out = [f"changes since {d['base']} ({where}): {n} file{'s' * (n != 1)}: "
           f"{count[ADDED]} added, {count[MODIFIED]} modified, {count[DELETED]} deleted"]
    nodes = {n["id"]: n for n in d["extra_nodes"]}
    nodes.update((n["id"], n) for n in graph["nodes"])
    symbols = defaultdict(list)
    for i, s in d["nodes"].items():
        if "::" in i:
            n = nodes.get(i, {})
            symbols[i.partition("::")[0]].append((n.get("line") or 0, i.partition("::")[2], s))
    for p, s in d["files"].items():
        st = _stat(d["stats"].get(p))
        out.append(f"  {LETTER[s]}  {p}" + (f"  {st}" if st else ""))
        rows = sorted(symbols.get(p, []))
        for line, qual, sym in rows[:MAX_SYMBOLS_PER_FILE]:
            out.append(f"       {LETTER[sym]}  {qual}  (line {line})")
        if len(rows) > MAX_SYMBOLS_PER_FILE:
            out.append(f"       ... {len(rows) - MAX_SYMBOLS_PER_FILE} more")
    plus, minus = defaultdict(int), defaultdict(int)
    for _, _, kind in d["edges"]["added"]:
        plus[kind] += 1
    for e in d["edges"]["removed"]:
        minus[e["kind"]] += 1
    kinds = sorted((set(plus) | set(minus)) - {"contains"}, key=KIND_ORDER.get)
    if kinds:
        parts = [k + "".join(f" {sign}{c[k]}" for sign, c in (("+", plus), ("-", minus)) if c[k])
                 for k in kinds]
        out.append(f"links: {sum(plus[k] for k in kinds)} new, {sum(minus[k] for k in kinds)} "
                   f"removed ({', '.join(parts)})")
    else:
        out.append("links: none new or removed")
    return "\n".join(out)
