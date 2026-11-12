"""Human-facing outputs of graph.json: TREE.txt, SUMMARY.md, graph.html, and `reaper query`.

All functions take a loaded graph dict and return text (or result dicts); export() writes the
three files next to graph.json (<repo>/.reaper/ or the --out dir). Nothing here changes the graph.

"Most-connected" degree counts imports, inherits and calls edges; contains edges (pure
ownership) and external packages (listed separately) are left out.
"""

from __future__ import annotations

import importlib.resources
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

from reaper import legend
from reaper.discover import count_by_language, language
from reaper.graph import graph_path
from reaper.resolve import BUILTINS as PY_BUILTINS, JS_GLOBALS, JS_PROTO_METHODS, PY_TYPE_METHODS

NODE_KINDS = ("file", "class", "function", "method", "external")
EDGE_KINDS = ("contains", "imports", "inherits", "calls")
CONFIDENCES = ("EXTRACTED", "INFERRED", "AMBIGUOUS")
TOP_N = 10
MAX_LISTED_FILES = 5
# Level-of-detail budget: above either, graph.html opens a file-level view (bundled
# file -> file edges) and the user expands files one by one. Read at call time.
MAX_HTML_NODES = 1500
MAX_HTML_EDGES = 5000
VIS_NETWORK_URL = "https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _listed(items: list[str], cap: int = MAX_LISTED_FILES) -> str:
    text = ", ".join(items[:cap])
    return text + f", ... (+{len(items) - cap} more)" if len(items) > cap else text


def _children(graph: dict) -> dict[str, list[dict]]:
    """Parent id -> child nodes (via contains edges), in source-line order."""
    by_id = {n["id"]: n for n in graph["nodes"]}
    kids = defaultdict(list)
    for e in graph["edges"]:
        if e["kind"] == "contains" and e["dst"] in by_id:
            kids[e["src"]].append(by_id[e["dst"]])
    for lst in kids.values():
        lst.sort(key=lambda n: (n["line"] or 0, n["id"]))
    return kids


# ---------------------------------------------------------------- TREE.txt

def _symbol_line(n: dict) -> str:
    sig = n["signature"] or n["name"]
    if language(n["file"] or "") in ("javascript", "typescript"):
        if n["kind"] == "class":
            text = sig if sig.startswith("interface ") else f"class {sig}"
        elif n["kind"] == "function":
            text = f"async function {sig[len('async '):]}" if sig.startswith("async ") else f"function {sig}"
        else:
            text = sig  # methods read as in the class body
        return f"{text}  # L{n['line']}"
    if n["kind"] == "class":
        text = f"class {sig}"
    elif sig.startswith("async "):
        text = f"async def {sig[len('async '):]}"
    else:
        text = f"def {sig}"
    return f"{text}  # L{n['line']}"


def file_outline(graph: dict, path: str, _kids: dict | None = None) -> str:
    """One file's block of TREE.txt: header plus nested classes/functions (no trailing newline)."""
    kids = _children(graph) if _kids is None else _kids
    lines = graph["files"].get(path, {}).get("lines", 0)
    out = [f"{path} ({_plural(lines, 'line')})"]

    def walk(node_id: str, depth: int) -> None:
        for child in kids.get(node_id, []):
            out.append("  " * depth + _symbol_line(child))
            walk(child["id"], depth + 1)

    walk(path, 1)
    return "\n".join(out)


TREE_HEADER = [
    "# repo-reaper TREE.txt: every parsed file (Python, JavaScript, TypeScript) with its classes,",
    "# functions and methods. A file is `path (N lines)`; each symbol below it is one indented line,",
    "# its signature then `# L<line>`. The links between symbols (calls, imports, inherits) are in",
    "# graph.json: ask `reaper query <repo> callers|callees|subclasses|deps NAME`.",
    "#",
]


def tree_file(graph: dict) -> str:
    """TREE.txt: a header that explains the format and the labels, then tree_text()."""
    return "\n".join(TREE_HEADER + legend.plain("# ")) + "\n\n" + tree_text(graph)


def tree_text(graph: dict) -> str:
    """Every extracted file (sorted by path) with its classes/functions, signatures, lines."""
    kids = _children(graph)
    files = sorted(n["id"] for n in graph["nodes"] if n["kind"] == "file")
    return "".join(file_outline(graph, f, kids) + "\n" + ("\n" if i < len(files) - 1 else "")
                   for i, f in enumerate(files))


# ---------------------------------------------------------------- SUMMARY.md

def degrees(graph: dict) -> dict[str, tuple[int, int]]:
    """Node id -> (in, out) over imports/inherits/calls edges, externals left out."""
    kinds = {n["id"]: n["kind"] for n in graph["nodes"]}
    deg = defaultdict(lambda: [0, 0])
    for e in graph["edges"]:
        if e["kind"] == "contains":
            continue
        if kinds.get(e["src"]) not in (None, "external"):
            deg[e["src"]][1] += 1
        if kinds.get(e["dst"]) not in (None, "external"):
            deg[e["dst"]][0] += 1
    return {k: (v[0], v[1]) for k, v in deg.items()}


def most_connected(graph: dict, n: int = TOP_N) -> list[tuple[str, int, int]]:
    """[(id, in, out)] by total degree desc, then id; nodes with no such edge left out."""
    ranked = sorted(degrees(graph).items(), key=lambda kv: (-sum(kv[1]), kv[0]))
    return [(i, a, b) for i, (a, b) in ranked[:n]]


def import_cycles(graph: dict) -> list[tuple[list[str], list[str]]]:
    """[(cycle, component)] per strongly connected group of files in the import graph.

    cycle = a shortest cycle through the component's smallest path, as a closed list
    [a, b, ..., a]; component = all its files, sorted. Self-imports are not cycles.
    """
    files = {n["id"] for n in graph["nodes"] if n["kind"] == "file"}
    g = nx.DiGraph()
    g.add_edges_from((e["src"], e["dst"]) for e in graph["edges"]
                     if e["kind"] == "imports" and e["dst"] in files and e["src"] != e["dst"])
    result = []
    for comp in nx.strongly_connected_components(g):
        if len(comp) < 2:
            continue
        sub = g.subgraph(comp)
        start = min(comp)
        paths = [nx.shortest_path(sub, start, p) for p in sub.predecessors(start)]
        best = min(paths, key=lambda p: (len(p), p))
        result.append(([*best, start], sorted(comp)))
    return sorted(result)


def _table(header: tuple[str, ...], rows: list[tuple], align: str) -> list[str]:
    return ["| " + " | ".join(header) + " |", "|" + "|".join(align) + "|",
            *("| " + " | ".join(str(c) for c in row) + " |" for row in rows)]


def summary_md(graph: dict) -> str:
    kinds = {n["id"]: n["kind"] for n in graph["nodes"]}
    node_counts = Counter(n["kind"] for n in graph["nodes"])
    edge_counts = Counter(e["kind"] for e in graph["edges"])
    conf_counts = Counter(e["confidence"] for e in graph["edges"])
    generated = graph.get("meta", {}).get("generated_at", "?")

    md = ["# repo-reaper summary", "",
          f"Structural graph from graph.json, generated {generated}. "
          "Edges marked INFERRED or AMBIGUOUS are best guesses, not proven by the code.", "",
          *legend.markdown(), "## Stats", ""]
    md += _table(("total", "count"), [("files", len(graph["files"])),
                                      ("nodes", len(graph["nodes"])),
                                      ("edges", len(graph["edges"]))], ("---", "---:"))
    md += [""] + _table(("language", "files"), list(count_by_language(graph["files"]).items()),
                        ("---", "---:"))
    md += [""] + _table(("node kind", "count"), [(k, node_counts[k]) for k in NODE_KINDS],
                        ("---", "---:"))
    md += [""] + _table(("edge kind", "count"), [(k, edge_counts[k]) for k in EDGE_KINDS],
                        ("---", "---:"))
    md += [""] + _table(("confidence", "edges"), [(c, conf_counts[c]) for c in CONFIDENCES],
                        ("---", "---:"))

    md += ["", "## Most-connected nodes", "",
           "Degree over imports, inherits and calls edges "
           "(contains edges and external packages left out).", ""]
    top = most_connected(graph)
    md += _table(("node", "kind", "in", "out", "total"),
                 [(f"`{i}`", kinds.get(i, "?"), a, b, a + b) for i, a, b in top],
                 ("---", "---", "---:", "---:", "---:")) if top else ["None."]

    md += ["", "## Import cycles", ""]
    cycles = import_cycles(graph)
    if not cycles:
        md.append("None.")
    else:
        md += [f"{_plural(len(cycles), 'group')} of files that import each other "
               "(one shortest cycle shown per group):", ""]
        for cycle, comp in cycles:
            line = "- " + " -> ".join(cycle)
            if len(comp) > len(cycle) - 1:
                line += f" (group of {len(comp)} files: {_listed(comp)})"
            md.append(line)

    md += ["", "## External dependencies", ""]
    importers = defaultdict(set)
    for e in graph["edges"]:
        if e["kind"] == "imports" and kinds.get(e["dst"]) == "external":
            importers[e["dst"].removeprefix("ext:")].add(e["src"])
    rows = []
    for name, srcs in sorted(importers.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        rows.append((f"`{name}`", len(srcs), _listed(sorted(srcs))))
    md += _table(("package", "importing files", "files"), rows, ("---", "---:", "---")) \
        if rows else ["None."]
    return "\n".join(md) + "\n"


# ---------------------------------------------------------------- graph.html

EDGE_COLORS = {"contains": "#b0b0b0", "imports": "#4c78a8", "inherits": "#b279a2",
               "calls": "#f58518"}

# Page template (package data); __VIS__ and __DATA__ are its only slots, filled in one pass.
_TEMPLATE_FILE = importlib.resources.files("reaper").joinpath("templates/graph.html")
HTML_TEMPLATE = _TEMPLATE_FILE.read_text(encoding="utf-8")


HTML_LEGEND = "\n".join([
    "repo-reaper graph.html: the whole graph is embedded below as JSON (script#graph-data:",
    "nodes and edges). What the labels mean (also in graph.json \"legend\" and SUMMARY.md):", "",
    *legend.plain("  ")]).replace("-->", "- ->")


def _fill(blob: str) -> str:
    """Fill the template slots in ONE pass: text put into a slot is never scanned again,
    so "__DATA__" inside the URL or "__VIS__" inside a docstring stays as it is.
    An unknown slot in the template raises KeyError."""
    slots = {"VIS": VIS_NETWORK_URL, "DATA": blob, "LEGEND": HTML_LEGEND}
    return re.sub(r"__([A-Z]+)__", lambda m: slots[m.group(1)], HTML_TEMPLATE)


def _vis_node(n: dict) -> dict:
    if n["kind"] == "file":
        label = n["id"]
    elif n["kind"] == "external":
        label = n["name"]
    else:
        label = n["id"].partition("::")[2]
    title = [n["id"]]
    if n["kind"] not in ("file", "external"):
        title.append(f"{n['kind']} {n['signature'] or n['name']}  ({n['file']}:{n['line']})")
    if n.get("doc"):
        title.append(n["doc"])
    return {"id": n["id"], "label": label, "group": n["kind"], "title": "\n".join(title)}


def _vis_edge(e: dict) -> dict:
    return {"from": e["src"], "to": e["dst"], "kind": e["kind"], "confidence": e["confidence"],
            "dashes": e["confidence"] != "EXTRACTED", "color": EDGE_COLORS.get(e["kind"], "#888"),
            "title": f"{e['kind']} ({e['confidence']})"}


def file_edges(graph: dict) -> list[dict]:
    """Non-contains edges bundled per (file, file) pair for the file-level view.

    Each end maps to its node's file (externals map to themselves); same-file pairs are left
    out. Items {id: "f<i>", from, to, count, counts: {kind: {confidence: n}}}, sorted by
    (from, to).
    """
    file_of = {n["id"]: n.get("file") or n["id"] for n in graph["nodes"]}
    counts: dict[tuple[str, str], dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    for e in graph["edges"]:
        if e["kind"] == "contains":
            continue
        a, b = file_of.get(e["src"], e["src"]), file_of.get(e["dst"], e["dst"])
        if a != b:
            counts[(a, b)][e["kind"]][e["confidence"]] += 1
    return [{"id": f"f{i}", "from": a, "to": b,
             "count": sum(sum(c.values()) for c in by_kind.values()),
             "counts": {k: dict(c) for k, c in sorted(by_kind.items())}}
            for i, ((a, b), by_kind) in enumerate(sorted(counts.items()))]


def _page_node(n: dict, deg: dict[str, tuple[int, int]]) -> dict:
    """_vis_node plus the graph fields the page searches and shows (add-only, no LLM text)."""
    return {**_vis_node(n), "kind": n["kind"], "name": n.get("name"), "file": n.get("file"),
            "line": n.get("line"), "signature": n.get("signature"), "doc": n.get("doc"),
            "deg": sum(deg.get(n["id"], (0, 0)))}


def graph_html(graph: dict, sem: dict | None = None) -> str:
    """Single-file interactive view (vis-network from unpkg); dashed edges = not EXTRACTED.

    All nodes and edges are always embedded. Above MAX_HTML_NODES nodes or MAX_HTML_EDGES
    edges ("lod") the page opens at file level with the bundled file_edges() and expands
    files on demand. `sem` is the semantic layer built by the caller (None = structural view
    only); it is passed through as data, never merged into node labels or titles.
    """
    n_nodes, n_edges = len(graph["nodes"]), len(graph["edges"])
    lod = n_nodes > MAX_HTML_NODES or n_edges > MAX_HTML_EDGES
    note = (f"file-level view: graph has {n_nodes} nodes and {n_edges} edges (budget "
            f"{MAX_HTML_NODES} nodes, {MAX_HTML_EDGES} edges); double-click a file to expand it"
            if lod else "")
    deg = degrees(graph)
    data = {"note": note, "lod": lod,
            "budget": {"nodes": MAX_HTML_NODES, "edges": MAX_HTML_EDGES},
            "meta": {"generated_at": graph["meta"].get("generated_at"),
                     "files": len(graph["files"]), "nodes": n_nodes, "edges": n_edges},
            "nodes": [_page_node(n, deg) for n in graph["nodes"]],
            "edges": [{**_vis_edge(e), "id": f"e{i}"} for i, e in enumerate(graph["edges"])],
            "file_edges": file_edges(graph) if lod else [],
            "sem": sem}
    # "<" escaped so no text (e.g. a docstring with "</script>") can end the data block;
    # U+2028/U+2029 escaped so the blob is also safe as a JS string literal.
    blob = (json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            .replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
    return _fill(blob)


def export(root: str | os.PathLike, graph: dict, sem: dict | None = None,
           out: str | os.PathLike | None = None) -> list[Path]:
    """Write TREE.txt, SUMMARY.md and graph.html next to graph.json; return their paths.

    `sem` (optional semantic layer) only reaches graph.html."""
    out_dir = graph_path(root, out).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, text in (("TREE.txt", tree_file(graph)), ("SUMMARY.md", summary_md(graph)),
                       ("graph.html", graph_html(graph, sem))):
        path = out_dir / name
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


def write_html(root: str | os.PathLike, graph: dict, sem: dict | None = None,
               out: str | os.PathLike | None = None) -> Path:
    """Rewrite only graph.html (after an enrich pass: TREE.txt and SUMMARY.md ignore `sem`)."""
    path = graph_path(root, out).parent / "graph.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(graph_html(graph, sem), encoding="utf-8")
    return path


# ---------------------------------------------------------------- query

def find_nodes(graph: dict, name: str) -> list[dict]:
    """Nodes matching `name`, first non-empty tier wins, sorted by id.

    1. exact node id ("app/utils.py::validate", "app/utils.py", "ext:os")
    2. qualified name ("UserService.create"), module.qualname ("app.utils.validate"),
       module name of a file ("app.utils"), external package name ("os")
    3. last name part of a symbol ("create") or of a file's module name ("utils")
    """
    nodes = graph["nodes"]
    exact = [n for n in nodes if n["id"] == name]
    if exact:
        return exact
    modules = {n["id"]: n["name"] for n in nodes if n["kind"] == "file"}

    def qualified(n: dict) -> bool:
        if n["kind"] in ("file", "external"):
            return n["name"] == name
        file_id, _, qual = n["id"].partition("::")
        return name in (qual, f"{modules.get(file_id)}.{qual}")

    def last_part(n: dict) -> bool:
        if n["kind"] == "file":
            return n["name"].rpartition(".")[2] == name
        return n["kind"] != "external" and n["name"] == name

    for match in (qualified, last_part):
        hits = [n for n in nodes if match(n)]
        if hits:
            return sorted(hits, key=lambda n: n["id"])
    return []


QUERY_MODES = ("callers", "callees", "subclasses", "deps")
DEFAULT_BUDGET = 2000  # tokens of text output; about 4 characters per token
MAX_UNLINKED_LISTED = 10


def _entry(by_id: dict, node_id: str, confidence: str | None = None,
           lines: list[int] | None = None) -> dict:
    n = by_id.get(node_id, {})
    entry = {"id": node_id, "kind": n.get("kind"), "file": n.get("file"), "line": n.get("line")}
    if confidence is not None:
        entry["confidence"] = confidence
    if lines is not None:
        entry["lines"] = lines
    return entry


def _neighbours(graph: dict, mode: str) -> dict[str, list[tuple[str, str, list[int]]]]:
    """node id -> [(neighbour id, confidence, lines)] for callers / callees / subclasses."""
    kind = "inherits" if mode == "subclasses" else "calls"
    out = defaultdict(list)
    for e in graph["edges"]:
        if e["kind"] != kind:
            continue
        here, there = (e["src"], e["dst"]) if mode == "callees" else (e["dst"], e["src"])
        out[here].append((there, e["confidence"], e.get("lines", [])))
    for hits in out.values():
        hits.sort()
    return out


def _tree(by_id: dict, near: dict, root: str, mode: str, depth: int) -> list[dict]:
    """Entries up to `depth` hops from root, breadth first. A node is expanded once, at its
    shallowest hop; a later repeat is marked {"repeat": True} and has no children."""
    top = [_entry(by_id, i, c, ln) for i, c, ln in near.get(root, [])]
    level, seen = top, {root} | {e["id"] for e in top}
    for _ in range(depth - 1):
        nxt = []
        for entry in level:
            kids = []
            for i, c, ln in near.get(entry["id"], []):
                kid = _entry(by_id, i, c, ln)
                if i in seen:
                    kid["repeat"] = True
                else:
                    seen.add(i)
                    nxt.append(kid)
                kids.append(kid)
            entry[mode] = kids
        level = nxt
    return top


def _unlinked(graph: dict, by_id: dict, node: dict) -> list[dict]:
    """Call sites that use the node's name but are linked to nothing of that name: the receiver's
    type was unknown, or the call went through something the graph could not follow. Calls through
    an import from outside the repo (np.save) and builtins are left out."""
    name = node["name"]
    linked = set()
    for e in graph["edges"]:
        if e["kind"] == "calls" and by_id.get(e["dst"], {}).get("name") == name:
            linked.update((e["src"], line) for line in e.get("lines", []))
    outside = {(e["src"], e["dst"][4:]) for e in graph["edges"]
               if e["kind"] == "imports" and e["dst"].startswith("ext:")}
    ext_alias = defaultdict(set)
    for r in graph["refs"]:
        if r["kind"] == "import" and r["alias"] not in (None, "*") and r["target"]:
            if (r["file"], r["target"].split(".")[0]) in outside:
                ext_alias[r["file"]].add(r["alias"].split(".")[0])
    out = []
    for r in graph["refs"]:
        if r["kind"] != "call" or r["target"].rpartition(".")[2] != name:
            continue
        if (r["src"], r["line"]) in linked:
            continue
        first = r["target"].split(".")[0].removesuffix("()")
        known = JS_GLOBALS if language(r["file"]) in ("javascript", "typescript") else PY_BUILTINS
        if first in ext_alias.get(r["file"], ()) or (r["target"] != name and first in known):
            continue
        out.append({"src": r["src"], "file": r["file"], "line": r["line"], "target": r["target"]})
    home = node["file"] or ""
    folder = home.rpartition("/")[0]
    importers = {e["src"] for e in graph["edges"] if e["kind"] == "imports" and e["dst"] == home}
    out.sort(key=lambda u: (u["file"] != home, u["file"].rpartition("/")[0] != folder,
                            u["file"] not in importers, u["file"], u["line"]))
    return out


def query(graph: dict, mode: str, name: str, depth: int = 1) -> list[dict]:
    """Results per matched node, sorted by id.

    callers / callees / subclasses: [{node, line, <mode>: [entry]}], entry =
      {id, kind, file, line, confidence, lines}; `lines` are the call sites (callers: in the
      caller's file; callees: in the queried function's file), or the class line for subclasses.
      With depth > 1 an entry has its own <mode> list; each node is expanded once (a repeat
      gets "repeat": true). callers also has `unlinked`: call sites using the same name that
      the graph linked to nothing of that name, [{src, file, line, target}].
    deps: [{node, imports: [...], imported_by: [...]}] for the file of each match
          (a symbol means its file; an external package has only imported_by); entries carry
          `lines`: where the import is, in the importing file.
    """
    if mode not in QUERY_MODES:
        raise ValueError(f"unknown query mode: {mode}")
    by_id = {n["id"]: n for n in graph["nodes"]}
    matches = find_nodes(graph, name)
    results = []
    if mode in ("callers", "callees", "subclasses"):
        near = _neighbours(graph, mode)
        for n in matches:
            res = {"node": n["id"], "line": n.get("line"),
                   mode: _tree(by_id, near, n["id"], mode, depth)}
            if mode == "callers" and n["kind"] in ("function", "method", "class"):
                res["unlinked"] = _unlinked(graph, by_id, n)
            results.append(res)
    else:
        imports = sorted((e for e in graph["edges"] if e["kind"] == "imports"),
                         key=lambda e: (e["src"], e["dst"]))
        targets = sorted({n["id"] if n["kind"] == "external" else n["file"] for n in matches})
        for t in targets:
            results.append({
                "node": t,
                "imports": [_entry(by_id, e["dst"], lines=e.get("lines", []))
                            for e in imports if e["src"] == t],
                "imported_by": [_entry(by_id, e["src"], lines=e.get("lines", []))
                                for e in imports if e["dst"] == t],
            })
    return results


_AT = {"callers": "calls at ", "callees": "called at ", "subclasses": ""}
_NOUNS = {"callers": ("caller", "callers"), "callees": ("callee", "callees"),
          "subclasses": ("subclass", "subclasses")}


def _lines_text(lines: list[int]) -> str:
    return "line " + ", ".join(map(str, lines)) if lines else ""


def _rows(mode: str, entries: list[dict], depth: int = 1, parent: int = -1,
          out: list | None = None) -> list[tuple[int, int, str, str]]:
    """(hop, parent row, text, id) per entry, depth first, children indented under their parent."""
    out = [] if out is None else out
    for e in entries:
        where = _lines_text(e.get("lines", []))
        where = f"  ({_AT[mode]}{where})" if where else ""
        repeat = "  (see above)" if e.get("repeat") else ""
        out.append((depth, parent, f"{'  ' * depth}{e['confidence']:<9}  {e['id']}{where}{repeat}", e["id"]))
        _rows(mode, e.get(mode, []), depth + 1, len(out) - 1, out)
    return out


def _budgeted(mode: str, rows: list[tuple[int, int, str, str]], room: int | None) -> list[str]:
    """Rows that fit in `room` characters, nearer hops first and shared round-robin between the
    parents of a hop (a row is only shown with its parent). Under a parent whose children did not
    all fit, and at the end for hop 1: '... N more <noun> (folder counts)'."""
    keep = set(range(len(rows)))
    if room is not None:
        rank, seen = [], Counter()
        for _, parent, _, _ in rows:
            rank.append(seen[parent])
            seen[parent] += 1
        keep, used = set(), 0
        for i in sorted(range(len(rows)), key=lambda i: (rows[i][0], rank[i], i)):
            hop, parent, text, _ = rows[i]
            if used + len(text) + 1 > room or (parent >= 0 and parent not in keep):
                continue
            keep.add(i)
            used += len(text) + 1
    cut_under = defaultdict(list)
    for i, (hop, parent, _, node_id) in enumerate(rows):
        if i not in keep and (parent in keep or parent < 0):
            cut_under[parent].append(node_id)
    noun = _NOUNS[mode][1]

    def more(p: int) -> str:
        folders = Counter(_top_folder(n) for n in cut_under[p])
        return (f"{'  ' * (rows[p][0] + 1 if p >= 0 else 1)}... {len(cut_under[p])} more {noun} ("
                + ", ".join(f"{f} {n}" for f, n in folders.most_common()) + ")")

    out = []
    for i, (_, _, text, _) in enumerate(rows):
        if i in keep:
            out.append(text)
        out += [more(p) for p in _closing(rows, i, cut_under)]
    if -1 in cut_under:
        out.append(more(-1))
    return out


def _closing(rows: list, i: int, cut_under: dict) -> list[int]:
    """Ancestors of row i whose subtree ends at row i and that had children cut, innermost first."""
    nxt = rows[i + 1][0] if i + 1 < len(rows) else 0
    out, p = [], rows[i][1]
    while p >= 0 and rows[p][0] >= nxt:
        if p in cut_under:
            out.append(p)
        p = rows[p][1]
    return out


def _count(mode: str, entries: list[dict]) -> list[str]:
    """Per hop: '5 callers: 5 EXTRACTED', then 'hop 2: 130 callers: ...' (repeats not counted)."""
    out, level, hop = [], entries, 1
    while level:
        unique = {e["id"]: e for e in level if not e.get("repeat")}
        conf = Counter(e["confidence"] for e in unique.values())
        noun = _NOUNS[mode][len(unique) != 1]
        text = (f"{len(unique)} {noun}: " + ", ".join(f"{conf[c]} {c}" for c in CONFIDENCES if conf[c])
                if unique else "no new ones")
        out.append(text if hop == 1 else f"hop {hop}: {text}")
        level = [k for e in level for k in e.get(mode, [])]
        hop += 1
    return out


def _top_folder(node_id: str) -> str:
    path = node_id.split("::")[0]
    return path.split("/")[0] + "/" if "/" in path else path


def format_query(mode: str, results: list[dict], budget: int | None = DEFAULT_BUDGET) -> str:
    """Text for an agent or a person. `budget` (tokens, ~4 characters each) caps the listed
    entries; what is cut is counted per top-level folder, with the --budget that shows it all."""
    out = []
    for res in results:
        at = f"  (line {res['line']})" if res.get("line") and mode != "deps" else ""
        out.append(f"{mode} of {res['node']}{at}")
        if mode == "deps":
            for key, label in (("imports", "imports"), ("imported_by", "imported by")):
                out.append(f"  {label}:")
                out += [f"    {d['id']}" + (f"  ({_lines_text(d['lines'])})" if d.get("lines") else "")
                        for d in res[key]] or ["    (none)"]
            continue
        if not res[mode]:
            out.append("  (none)")
        else:
            counts = _count(mode, res[mode])
            out.append("  " + "; ".join(counts))
            rows = _rows(mode, res[mode])
            head = len("\n".join(out))
            room = None if budget is None else max(budget * 4 - head, 0)
            shown = _budgeted(mode, rows, room)
            out += shown
            listed = sum(1 for line in shown if not line.lstrip().startswith("... "))
            if listed < len(rows):
                need = -(-(head + sum(len(r[2]) + 1 for r in rows) + 200) // 400) * 100
                out.append(f"  ({len(rows) - listed} of {len(rows)} lines not shown; "
                           f"--budget {need} shows all)")
        if "unlinked" in res:
            name = res["node"].rpartition("::")[2].rpartition(".")[2]
            un = res["unlinked"]
            builtin = name in PY_TYPE_METHODS or name in JS_PROTO_METHODS
            if not un:
                out.append("  not linked: none")
            else:
                note = (f"; {name} is also a built-in list/dict/str (or JS Array, String...) method, "
                        f"so most of these are probably that" if builtin else "")
                out.append(f"  not linked: {len(un)} call site{'s' * (len(un) != 1)} named {name} "
                           f"that the graph could not resolve (check only these{note}):")
                out += [f"    {u['file']}:{u['line']}  {u['target']}()  in {u['src']}"
                        for u in un[:MAX_UNLINKED_LISTED]]
                if len(un) > MAX_UNLINKED_LISTED:
                    rest = Counter(_top_folder(u["file"]) for u in un[MAX_UNLINKED_LISTED:])
                    out.append(f"    ... {len(un) - MAX_UNLINKED_LISTED} more ("
                               + ", ".join(f"{f} {n}" for f, n in rest.most_common()) + "; --json lists all)")
    if mode != "deps" and any(res.get(mode) or res.get("unlinked") for res in results):
        out += legend.query_key(mode)
    return "\n".join(out) + "\n"
