"""Semantic passes over graph.json with a local LLM; results go to <repo>/.reaper/semantic.json.

semantic.json = {files: {path: {summary, role, input_sha, model}},
                 groups: {id: {name, summary, members, input_sha, model}},
                 architecture: {overview, patterns, decisions, dropped_evidence, input_sha, model}}

Every answer is cached under input_sha = sha256(model, prompt version, input text), so an input
is asked again only when it, the model or the prompt changes.

Files pass: one call per code file (files with a file node). Input = the file's TREE outline plus
its source (whole when <= 300 lines, else the first 150). Work goes most-connected file first and
semantic.json is saved after every answer, so an interrupted run (or --limit) keeps what it
finished and the next run picks up the rest.

Groups pass: groups = Louvain communities (seed 42) of the file graph (files linked by their
imports/inherits/calls edges, weight = edge count). A file with no link to another file gives
Louvain nothing to go on, so it joins the group holding most files of its own directory (isolated
files of a directory no group reaches form one group). One call per group: member paths + file
summaries, capped at 12k chars -> {name, summary}. Ids g1, g2, ... go largest group first; a
cached answer is found by input_sha, so it survives an id shift.

Architecture pass: one call over the group summaries, cross-group edge counts and most-connected
nodes -> {overview, patterns, decisions}. Needs a current answer for every group. Evidence ids
not in graph.json are dropped. Writes <repo>/.reaper/ARCHITECTURE.md, marked LLM-generated.
"""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

import networkx as nx

from reaper import llm, outputs
from reaper.graph import graph_path

DEFAULT_MODELS = {"files": "devstral-small-2:24b", "groups": "qwen3-coder:30b",
                  "architecture": "qwen3-coder:30b"}
SECTIONS = ("files", "groups", "architecture")

MAX_WHOLE_LINES = 300  # longer files are cut to their first HEAD_LINES lines
HEAD_LINES = 150

# Bump FILES_PROMPT_VERSION whenever FILES_SYSTEM, ROLES or the input layout change: it is part
# of every cache key, so the bump makes the next run ask about every file again.
FILES_PROMPT_VERSION = "files-1"
ROLES = ("entrypoint", "api", "service", "model", "data-access", "utility", "config", "test",
         "script", "package", "other")
FILES_SYSTEM = """\
You describe one source file of a software repository for a code map.
You get the file's path, an outline of its classes and functions with line numbers, and its \
source (possibly cut off).
Reply with a JSON object:
- "summary": at most 2 sentences on what the file does and its key classes or functions. \
Start with a verb, e.g. "Parses ...". Be concrete.
- "role": the file's main role, one of: entrypoint (CLI, main, app startup), api (routes, \
handlers, public interface), service (business logic, orchestration), model (data structures, \
domain types, schemas), data-access (storage, databases, file formats, network clients), \
utility (generic helpers), config (settings, constants), test (tests, fixtures), script \
(build, deploy, one-off tooling), package (package init, re-exports), other.
Describe only what the given text shows; do not guess about other files."""
FILES_SCHEMA = {"type": "object",
                "properties": {"summary": {"type": "string"},
                               "role": {"type": "string", "enum": list(ROLES)}},
                "required": ["summary", "role"]}


# ---------------------------------------------------------------- semantic.json

def semantic_path(root: str | os.PathLike) -> Path:
    return graph_path(root).parent / "semantic.json"


def load_semantic(root: str | os.PathLike) -> dict:
    path = semantic_path(root)
    sem = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for section in SECTIONS:
        sem.setdefault(section, {})
    return sem


def save_semantic(root: str | os.PathLike, sem: dict) -> Path:
    """Write semantic.json atomically (temp file + rename); return its path."""
    path = semantic_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(sem, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


# ---------------------------------------------------------------- files pass

def ranked_files(graph: dict) -> list[str]:
    """Code files (file nodes), most-connected first: sum of the non-contains degree
    (outputs.degrees) of every node in the file; ties by path."""
    file_of = {n["id"]: n["file"] for n in graph["nodes"]}
    score = Counter()
    for node_id, (d_in, d_out) in outputs.degrees(graph).items():
        score[file_of[node_id]] += d_in + d_out
    files = [n["id"] for n in graph["nodes"] if n["kind"] == "file"]
    return sorted(files, key=lambda f: (-score[f], f))


def file_input(graph: dict, root: str | os.PathLike, path: str,
               _kids: dict | None = None) -> str:
    """The user message for one file: path, TREE outline, source (cut when long).

    _kids = outputs._children(graph), passed in by callers that build many inputs so the
    contains index is built once; the text is the same either way."""
    text = (Path(root) / path).read_bytes().decode("utf-8", errors="replace")
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    if len(lines) > MAX_WHOLE_LINES:
        head = f"Source (first {HEAD_LINES} of {len(lines)} lines):"
        text = "\n".join(lines[:HEAD_LINES]) + "\n"
    else:
        head = "Source:"
    outline = outputs.file_outline(graph, path, _kids=_kids)
    return f"File: {path}\n\nOutline:\n{outline}\n\n{head}\n{text}"


def cache_key(model: str, text: str, version: str = FILES_PROMPT_VERSION) -> str:
    return hashlib.sha256(f"{model}\n{version}\n{text}".encode("utf-8")).hexdigest()


def first_sentences(text: str, n: int) -> str:
    """At most the first n sentences, whitespace collapsed."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", " ".join(text.split()))
    return " ".join(parts[:n])


def two_sentences(text: str) -> str:
    return first_sentences(text, 2)


def run_files(root: str | os.PathLike, graph: dict, model: str = DEFAULT_MODELS["files"],
              limit: int | None = None, dry_run: bool = False,
              progress: Callable[[str], None] | None = None) -> dict:
    """Summarize every code file whose cached answer is stale; return a report.

    report = {model, todo (paths to ask, after --limit), called, cached (count), failed
    {path: reason}, pruned (entries of files gone from the graph), tokens and max_tokens
    (approx input tokens of the todo calls, chars / 4)}. dry_run computes the report and
    writes nothing. An invalid reply skips that file; llm.LLMError otherwise (Ollama down,
    unknown model) stops the run, keeping the answers saved so far.
    """
    say = progress or (lambda _msg: None)
    sem = load_semantic(root)
    cache = sem["files"]
    ranked = ranked_files(graph)
    todo, cached, failed = [], 0, {}
    for path in ranked:
        try:
            text = file_input(graph, root, path)
        except OSError as e:
            failed[path] = f"cannot read: {e}"
            continue
        key = cache_key(model, text)
        if cache.get(path, {}).get("input_sha") == key:
            cached += 1
        else:
            todo.append((path, text, key))
    if limit is not None:
        todo = todo[:limit]
    chars = [len(FILES_SYSTEM) + len(text) for _, text, _ in todo]
    report = {"model": model, "todo": [p for p, _, _ in todo], "called": [], "cached": cached,
              "failed": failed, "pruned": sorted(set(cache) - set(ranked)),
              "tokens": sum(chars) // 4, "max_tokens": max(chars, default=0) // 4}
    if dry_run:
        return report

    for path in report["pruned"]:
        del cache[path]
    if report["pruned"]:
        save_semantic(root, sem)
    for i, (path, text, key) in enumerate(todo, 1):
        messages = [{"role": "system", "content": FILES_SYSTEM}, {"role": "user", "content": text}]
        try:
            reply = llm.chat(model, messages, FILES_SCHEMA)
        except llm.InvalidResponse as e:
            failed[path] = str(e)
            say(f"[{i}/{len(todo)}] {path}: FAILED {e}")
            continue
        cache[path] = {"summary": two_sentences(reply["summary"]), "role": reply["role"],
                       "input_sha": key, "model": model}
        save_semantic(root, sem)
        report["called"].append(path)
        say(f"[{i}/{len(todo)}] {path}: {reply['role']}")
    return report


# ---------------------------------------------------------------- groups

LOUVAIN_SEED = 42
GROUP_MAX_CHARS = 12000      # cap on one group's input
GROUP_TAIL_RESERVE = 40      # room kept under the cap for the "(N more files not shown)" line
MAX_SUMMARY_CHARS = 1000     # one file summary in a group input

# Bump GROUPS_PROMPT_VERSION whenever GROUPS_SYSTEM or the group_input layout change.
GROUPS_PROMPT_VERSION = "groups-1"
GROUPS_SYSTEM = """\
You describe one group of related source files of a software repository for a code map. The \
group was found by clustering files on their imports and calls.
You get each member's path and, when known, its role and a short summary, most-connected first \
(the list may be cut off).
Reply with a JSON object:
- "name": 2 to 5 words naming what the group is responsible for, e.g. "Graph resolution" or \
"CLI and output writers".
- "summary": at most 3 sentences on what the group does as a whole and how its files work \
together. Be concrete; mention key files by path.
Describe only what the given text shows; do not guess about other files."""
GROUPS_SCHEMA = {"type": "object",
                 "properties": {"name": {"type": "string"}, "summary": {"type": "string"}},
                 "required": ["name", "summary"]}


def _file_links(graph: dict) -> Counter:
    """(file a, file b) with a < b -> number of imports/inherits/calls edges between them."""
    file_of = {n["id"]: n["file"] for n in graph["nodes"] if n["kind"] != "external"}
    links = Counter()
    for e in graph["edges"]:
        if e["kind"] == "contains":
            continue
        a, b = file_of.get(e["src"]), file_of.get(e["dst"])
        if a and b and a != b:
            links[(min(a, b), max(a, b))] += 1
    return links


def communities(graph: dict) -> list[list[str]]:
    """Groups of code files (each sorted), largest first, ties by first path.

    Louvain (seed 42) on the files that have a link to another file. Each other file joins
    the Louvain group with most files in its directory (first such group on a tie); isolated
    files of a directory no group reaches form one group per directory.
    """
    g = nx.Graph()
    for (a, b), weight in sorted(_file_links(graph).items()):
        g.add_edge(a, b, weight=weight)
    found = (nx.community.louvain_communities(g, weight="weight", seed=LOUVAIN_SEED)
             if g.number_of_nodes() else [])
    groups = sorted((sorted(c) for c in found), key=lambda m: (-len(m), m[0]))
    dirs = [Counter(posixpath.dirname(p) for p in m) for m in groups]
    extra = defaultdict(list)  # group index or directory -> isolated files joining it
    for path in sorted(n["id"] for n in graph["nodes"] if n["kind"] == "file"):
        if path in g:
            continue
        d = posixpath.dirname(path)
        best = max(range(len(groups)), key=lambda i: dirs[i][d], default=None)
        extra[best if best is not None and dirs[best][d] else d].append(path)
    for i, m in enumerate(groups):
        m.extend(extra.pop(i, []))
    groups += extra.values()
    return sorted((sorted(m) for m in groups), key=lambda m: (-len(m), m[0]))


def group_input(members: list[str], files: dict) -> str:
    """The user message for one group: members in the given order (most-connected first) with
    role and summary from semantic.json's files section, cut to GROUP_MAX_CHARS."""
    head = f"Group of {outputs._plural(len(members), 'file')}, most-connected first:\n"
    used, lines = len(head), []
    for path in members:
        entry = files.get(path) or {}
        summary = entry.get("summary")
        if summary:
            if len(summary) > MAX_SUMMARY_CHARS:
                summary = summary[:MAX_SUMMARY_CHARS - 1] + "…"
            role = f" [{entry['role']}]" if entry.get("role") else ""
            line = f"- {path}{role}: {summary}\n"
        else:
            line = f"- {path}: (no summary yet)\n"
        if used + len(line) > GROUP_MAX_CHARS - GROUP_TAIL_RESERVE:
            break
        lines.append(line)
        used += len(line)
    text = head + "".join(lines)
    if len(lines) < len(members):
        text += f"({outputs._plural(len(members) - len(lines), 'more file')} not shown)\n"
    return text


def _group_plan(graph: dict, sem: dict) -> list[tuple[str, list[str], list[str], str]]:
    """[(id, members sorted, members most-connected first, input text)] for the graph now."""
    rank = {p: i for i, p in enumerate(ranked_files(graph))}
    plan = []
    for i, members in enumerate(communities(graph), 1):
        ordered = sorted(members, key=rank.__getitem__)
        plan.append((f"g{i}", members, ordered, group_input(ordered, sem["files"])))
    return plan


def run_groups(root: str | os.PathLike, graph: dict, model: str = DEFAULT_MODELS["groups"],
               limit: int | None = None, dry_run: bool = False,
               progress: Callable[[str], None] | None = None) -> dict:
    """Name and summarize every group whose cached answer is stale; return a report.

    report = {model, groups (count), todo (ids to ask, after --limit), called, cached (count),
    failed {id: reason}, missing_summaries (member files without a file summary), tokens,
    max_tokens}. The groups section is rebuilt: groups that no longer exist are dropped.
    Same failure handling as run_files.
    """
    say = progress or (lambda _msg: None)
    sem = load_semantic(root)
    old = {e.get("input_sha"): e for e in sem["groups"].values()}
    plan = _group_plan(graph, sem)
    entries, todo = {}, []
    for gid, members, _, text in plan:
        key = cache_key(model, text, GROUPS_PROMPT_VERSION)
        hit = old.get(key)
        if hit:
            entries[gid] = {"name": hit["name"], "summary": hit["summary"], "members": members,
                            "input_sha": key, "model": model}
        else:
            todo.append((gid, members, text, key))
    if limit is not None:
        todo = todo[:limit]
    chars = [len(GROUPS_SYSTEM) + len(text) for _, _, text, _ in todo]
    report = {"model": model, "groups": len(plan), "todo": [gid for gid, *_ in todo],
              "called": [], "cached": len(entries), "failed": {},
              "missing_summaries": sorted(p for _, members, _, _ in plan for p in members
                                          if not (sem["files"].get(p) or {}).get("summary")),
              "tokens": sum(chars) // 4, "max_tokens": max(chars, default=0) // 4}
    if dry_run:
        return report

    def store() -> None:
        sem["groups"] = {gid: entries[gid] for gid, *_ in plan if gid in entries}
        save_semantic(root, sem)

    store()
    for i, (gid, members, text, key) in enumerate(todo, 1):
        messages = [{"role": "system", "content": GROUPS_SYSTEM},
                    {"role": "user", "content": text}]
        try:
            reply = llm.chat(model, messages, GROUPS_SCHEMA)
        except llm.InvalidResponse as e:
            report["failed"][gid] = str(e)
            say(f"[{i}/{len(todo)}] {gid}: FAILED {e}")
            continue
        entries[gid] = {"name": " ".join(reply["name"].split()),
                        "summary": first_sentences(reply["summary"], 3), "members": members,
                        "input_sha": key, "model": model}
        store()
        report["called"].append(gid)
        say(f"[{i}/{len(todo)}] {gid} ({outputs._plural(len(members), 'file')}): "
            f"{entries[gid]['name']}")
    return report


# ---------------------------------------------------------------- architecture

ARCH_TOP_NODES = 15          # most-connected nodes in the input
ARCH_TOP_LINKS = 30          # cross-group pairs in the input
ARCH_GROUP_FILES = 10        # member paths listed per group
ARCH_GROUPS_MAX_CHARS = 16000

# Bump ARCH_PROMPT_VERSION whenever ARCH_SYSTEM or the arch_input layout change.
ARCH_PROMPT_VERSION = "architecture-1"
ARCH_SYSTEM = """\
You describe the architecture of a software repository from a code map.
You get the repository's groups of files (each with a name, a summary and its main files), \
how many imports/inherits/calls edges go from one group to another, and the most-connected \
nodes (files and symbols) with their edge counts.
Reply with a JSON object:
- "overview": 3 to 6 sentences on what the system is for, its main parts and how data or \
control flows between them.
- "patterns": architectural or design patterns the code shows, each {"name", "explanation" \
(1 to 2 sentences on where and how it is used), "evidence" (node ids)}.
- "decisions": notable design decisions, each {"decision", "rationale" (1 to 2 sentences on \
why it was likely made and its trade-off), "evidence" (node ids)}.
Evidence must be node ids copied exactly from the input: file paths like "pkg/mod.py" or \
symbol ids like "pkg/mod.py::Class.method". Never invent ids; group ids like "g1" are not \
node ids. Describe only what the given text supports; prefer few well-supported items."""
_EVIDENCE = {"type": "array", "items": {"type": "string"}}
ARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "overview": {"type": "string"},
        "patterns": {"type": "array", "items": {
            "type": "object", "required": ["name", "explanation", "evidence"],
            "properties": {"name": {"type": "string"}, "explanation": {"type": "string"},
                           "evidence": _EVIDENCE}}},
        "decisions": {"type": "array", "items": {
            "type": "object", "required": ["decision", "rationale", "evidence"],
            "properties": {"decision": {"type": "string"}, "rationale": {"type": "string"},
                           "evidence": _EVIDENCE}}},
    },
    "required": ["overview", "patterns", "decisions"],
}


class NotReady(RuntimeError):
    """The architecture pass needs a current groups pass first."""


def _fresh(entry: dict | None, members: list[str], text: str) -> bool:
    return bool(entry) and entry.get("members") == members and entry.get("input_sha") == \
        cache_key(entry.get("model", ""), text, GROUPS_PROMPT_VERSION)


def _arch_parts(graph: dict, sem: dict) -> tuple[list, list[str], list[str]]:
    """(plan, cross-group lines, most-connected lines); NotReady unless every current group
    has an answer for its current input."""
    plan = _group_plan(graph, sem)
    if not plan:
        raise NotReady("the graph has no code files, so there are no groups")
    stale = [gid for gid, members, _, text in plan if not _fresh(sem["groups"].get(gid), members,
                                                                 text)]
    if stale:
        raise NotReady(f"{len(stale)} of {len(plan)} groups have no current answer "
                       f"({outputs._listed(stale)}); run `reaper enrich <repo> --pass groups` "
                       "first")
    order = {gid: i for i, (gid, *_) in enumerate(plan)}
    group_of = {p: gid for gid, members, *_ in plan for p in members}
    file_of = {n["id"]: n["file"] for n in graph["nodes"] if n["kind"] != "external"}
    cross = defaultdict(Counter)
    for e in graph["edges"]:
        a, b = file_of.get(e["src"]), file_of.get(e["dst"])
        if e["kind"] != "contains" and a and b and group_of[a] != group_of[b]:
            cross[(group_of[a], group_of[b])][e["kind"]] += 1
    pairs = sorted(cross.items(), key=lambda kv: (-sum(kv[1].values()), order[kv[0][0]],
                                                  order[kv[0][1]]))
    cross_lines = [f"- {a} -> {b}: {sum(c.values())} ("
                   + ", ".join(f"{kind} {n}" for kind, n in sorted(c.items())) + ")"
                   for (a, b), c in pairs[:ARCH_TOP_LINKS]]
    if len(pairs) > ARCH_TOP_LINKS:
        cross_lines.append(f"({len(pairs) - ARCH_TOP_LINKS} more group pairs not shown)")
    node_lines = [f"- {i}: in {d_in}, out {d_out}"
                  for i, d_in, d_out in outputs.most_connected(graph, ARCH_TOP_NODES)]
    return plan, cross_lines or ["- none"], node_lines or ["- none"]


def arch_input(graph: dict, sem: dict) -> str:
    """The user message for the architecture pass (NotReady when groups are missing/stale)."""
    plan, cross_lines, node_lines = _arch_parts(graph, sem)
    blocks, used = [], 0
    for gid, members, ordered, _ in plan:
        e = sem["groups"][gid]
        block = (f"{gid}: {e['name']} ({outputs._plural(len(members), 'file')})\n{e['summary']}\n"
                 f"Files: {outputs._listed(ordered, ARCH_GROUP_FILES)}\n")
        if blocks and used + len(block) > ARCH_GROUPS_MAX_CHARS:
            break
        blocks.append(block)
        used += len(block)
    text = f"Groups ({len(plan)}):\n\n" + "\n".join(blocks)
    if len(blocks) < len(plan):
        text += f"\n({outputs._plural(len(plan) - len(blocks), 'more group')} not shown)\n"
    return (text + "\nCross-group edges (from -> to: count by kind):\n"
            + "".join(line + "\n" for line in cross_lines)
            + "\nMost-connected nodes (in/out edges over imports, inherits, calls):\n"
            + "".join(line + "\n" for line in node_lines))


def _clean_items(items, title: str, text: str, known: set[str], dropped: set[str]) -> list[dict]:
    """Keep well-formed {title, text, evidence} items; evidence = known node ids only
    (backticks and spaces stripped, duplicates removed); unknown ids go to `dropped`."""
    out = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get(title), str) \
                or not item[title].strip():
            continue
        body = item.get(text)
        evidence = []
        refs = item.get("evidence")
        for ref in refs if isinstance(refs, list) else []:
            if not isinstance(ref, str):
                continue
            ref = ref.strip().strip("`").strip()
            if ref in known:
                if ref not in evidence:
                    evidence.append(ref)
            elif ref:
                dropped.add(ref)
        out.append({title: " ".join(item[title].split()),
                    text: " ".join(body.split()) if isinstance(body, str) else "",
                    "evidence": evidence})
    return out


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def architecture_md(graph: dict, sem: dict) -> str:
    """ARCHITECTURE.md from semantic.json's architecture and groups sections."""
    a = sem["architecture"]
    plan, cross_lines, _ = _arch_parts(graph, sem)
    dropped = len(a["dropped_evidence"])
    lines = ["# Architecture", "",
             f"> LLM-generated by {a['model']} (`reaper enrich --pass architecture`) from the "
             "group summaries and graph.json; reaper does not verify these claims. Evidence "
             f"lists only node ids that exist in graph.json "
             f"({outputs._plural(dropped, 'evidence id')} not found there were dropped).",
             "", "## Overview", "", a["overview"], ""]

    def evidence(ids: list[str]) -> str:
        return "Evidence: " + (", ".join(f"`{i}`" for i in ids) if ids else "none")

    for heading, items, title, text in (("Patterns", a["patterns"], "name", "explanation"),
                                        ("Design decisions", a["decisions"], "decision",
                                         "rationale")):
        lines += [f"## {heading}", ""]
        for item in items:
            lines += [f"### {item[title]}", ""]
            if item[text]:
                lines += [item[text], ""]
            lines += [evidence(item["evidence"]), ""]
        if not items:
            lines += ["None given.", ""]
    lines += ["## Groups", "", "| Group | Name | Files | Summary |", "|---|---|--:|---|"]
    for gid, members, _, _ in plan:
        e = sem["groups"][gid]
        lines.append(f"| {gid} | {_cell(e['name'])} | {len(members)} | {_cell(e['summary'])} |")
    lines += ["", "## Cross-group edges", "", *cross_lines, ""]
    return "\n".join(lines)


def run_architecture(root: str | os.PathLike, graph: dict,
                     model: str = DEFAULT_MODELS["architecture"], dry_run: bool = False,
                     progress: Callable[[str], None] | None = None) -> dict:
    """One call over the groups (unless cached); write ARCHITECTURE.md; return a report.

    report = {model, todo (a call is needed), called, cached, tokens, dropped (evidence ids
    not in graph.json), path (ARCHITECTURE.md)}. NotReady when groups are missing or stale;
    llm.LLMError (including InvalidResponse) when the call fails.
    """
    say = progress or (lambda _msg: None)
    sem = load_semantic(root)
    text = arch_input(graph, sem)
    key = cache_key(model, text, ARCH_PROMPT_VERSION)
    cached = sem["architecture"].get("input_sha") == key
    report = {"model": model, "todo": not cached, "called": False, "cached": cached,
              "tokens": 0 if cached else (len(ARCH_SYSTEM) + len(text)) // 4,
              "dropped": [], "path": None}
    if dry_run:
        return report
    if cached:
        answer = sem["architecture"]
    else:
        say(f"asking {model} about {outputs._plural(len(sem['groups']), 'group')} ...")
        answer = llm.chat(model, [{"role": "system", "content": ARCH_SYSTEM},
                                  {"role": "user", "content": text}], ARCH_SCHEMA)
        report["called"] = True
    known = {n["id"] for n in graph["nodes"]}
    dropped = set(answer.get("dropped_evidence", []))
    overview = answer.get("overview")
    sem["architecture"] = {
        "overview": overview.strip() if isinstance(overview, str) else "",
        "patterns": _clean_items(answer.get("patterns"), "name", "explanation", known, dropped),
        "decisions": _clean_items(answer.get("decisions"), "decision", "rationale", known,
                                  dropped),
        "dropped_evidence": sorted(dropped), "input_sha": key, "model": model}
    save_semantic(root, sem)
    path = semantic_path(root).parent / "ARCHITECTURE.md"
    path.write_text(architecture_md(graph, sem), encoding="utf-8")
    report["dropped"], report["path"] = sem["architecture"]["dropped_evidence"], path
    return report


# ---------------------------------------------------------------- view (graph.html)

def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def view_semantic(root: str | os.PathLike, graph: dict) -> dict | None:
    """The `sem` object graph.html embeds; None when .reaper/semantic.json does not exist.

    files: {path: {summary, role, model, stale}} for the paths that are file nodes now
      (input_sha is not shipped); stale = the stored input_sha is not the cache key of the
      file's input now (unreadable source -> stale).
    groups: {gid: {name, summary, members, model, stale}}; members = the stored members that
      are file nodes now, order kept; stale = gid is not a group of the graph now, or its
      stored answer is not for the group's current members and input (_fresh).
    architecture: None when the stored section is empty, else {overview, patterns, decisions,
      model, stale, dropped}; evidence keeps only node ids in the graph now (_clean_items),
      dropped = stored dropped_evidence + ids dropped now, sorted; stale = the stored
      input_sha is not the cache key of arch_input now (NotReady -> stale).
    Missing keys -> None (overview -> "", lists -> []). Reads only; never writes a file.
    """
    if not semantic_path(root).exists():
        return None
    sem = load_semantic(root)
    # the group/architecture inputs read only well-formed entries; the view lists them all
    raw_files, raw_groups = _dict(sem["files"]), _dict(sem["groups"])
    sem["files"] = {p: e for p, e in raw_files.items() if isinstance(e, dict)}
    sem["groups"] = {gid: e for gid, e in raw_groups.items() if isinstance(e, dict)}
    file_nodes = {n["id"] for n in graph["nodes"] if n["kind"] == "file"}
    kids = outputs._children(graph)
    files = {}
    for path, e in raw_files.items():
        if path not in file_nodes:
            continue
        e = _dict(e)
        try:
            stale = e.get("input_sha") != cache_key(e.get("model", ""),
                                                     file_input(graph, root, path, kids))
        except OSError:
            stale = True
        files[path] = {"summary": e.get("summary"), "role": e.get("role"),
                       "model": e.get("model"), "stale": stale}
    plan = {gid: (members, text) for gid, members, _, text in _group_plan(graph, sem)}
    groups = {}
    for gid, e in raw_groups.items():
        e = _dict(e)
        stored = e.get("members")
        members = [m for m in (stored if isinstance(stored, list) else [])
                   if isinstance(m, str) and m in file_nodes]
        groups[gid] = {"name": e.get("name"), "summary": e.get("summary"), "members": members,
                       "model": e.get("model"),
                       "stale": gid not in plan or not _fresh(e, *plan[gid])}
    return {"files": files, "groups": groups, "architecture": _view_architecture(graph, sem)}


def _view_architecture(graph: dict, sem: dict) -> dict | None:
    a = _dict(sem["architecture"])
    if not a:
        return None
    known = {n["id"] for n in graph["nodes"]}
    stored = a.get("dropped_evidence")
    dropped = {d for d in (stored if isinstance(stored, list) else []) if isinstance(d, str)}
    patterns = _clean_items(a.get("patterns"), "name", "explanation", known, dropped)
    decisions = _clean_items(a.get("decisions"), "decision", "rationale", known, dropped)
    try:
        stale = a.get("input_sha") != cache_key(a.get("model", ""), arch_input(graph, sem),
                                                ARCH_PROMPT_VERSION)
    except (NotReady, KeyError):  # KeyError: a current group entry without name/summary
        stale = True
    overview = a.get("overview")
    return {"overview": overview if isinstance(overview, str) else "", "patterns": patterns,
            "decisions": decisions, "model": a.get("model"), "stale": stale,
            "dropped": sorted(dropped)}
