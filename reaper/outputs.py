"""Human-facing outputs of graph.json: TREE.txt, SUMMARY.md, graph.html, and `reaper query`.

All functions take a loaded graph dict and return text (or result dicts); export() writes the
three files to <repo>/.reaper/. Nothing here changes the graph.

"Most-connected" degree counts imports, inherits and calls edges; contains edges (pure
ownership) and external packages (listed separately) are left out.
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

from reaper.discover import count_by_language
from reaper.graph import graph_path

NODE_KINDS = ("file", "class", "function", "method", "external")
EDGE_KINDS = ("contains", "imports", "inherits", "calls")
CONFIDENCES = ("EXTRACTED", "INFERRED", "AMBIGUOUS")
TOP_N = 10
MAX_LISTED_FILES = 5
MAX_HTML_NODES = 3000  # above this, graph.html shows files + external packages only
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
          f"Structural graph from .reaper/graph.json, generated {generated}. "
          "Edges marked INFERRED or AMBIGUOUS are best guesses, not proven by the code.", "",
          "## Stats", ""]
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

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>repo-reaper graph</title>
<script src="__VIS__"></script>
<style>
  html, body { margin: 0; height: 100%; font: 14px system-ui, sans-serif; background: #fff; }
  #bar { padding: 6px 10px; border-bottom: 1px solid #ddd; display: flex; gap: 14px;
         flex-wrap: wrap; align-items: center; }
  #net { position: absolute; top: 44px; bottom: 0; left: 0; right: 0; }
  #info { color: #555; }
  .k { display: inline-block; width: 18px; border-top: 3px solid; vertical-align: middle; }
  .d { border-top-style: dashed; }
</style>
</head>
<body>
<div id="bar">
  <strong>repo-reaper</strong>
  <label><input type="checkbox" data-kind="contains" checked> <span class="k" style="border-color:#b0b0b0"></span> contains</label>
  <label><input type="checkbox" data-kind="imports" checked> <span class="k" style="border-color:#4c78a8"></span> imports</label>
  <label><input type="checkbox" data-kind="inherits" checked> <span class="k" style="border-color:#b279a2"></span> inherits</label>
  <label><input type="checkbox" data-kind="calls" checked> <span class="k" style="border-color:#f58518"></span> calls</label>
  <span><span class="k d" style="border-color:#555"></span> not EXTRACTED (INFERRED / AMBIGUOUS)</span>
  <input id="find" placeholder="find node..." size="24">
  <span id="info"></span>
</div>
<div id="net"></div>
<script id="graph-data" type="application/json">__DATA__</script>
<script>
const data = JSON.parse(document.getElementById("graph-data").textContent);
const nodes = new vis.DataSet(data.nodes);
const edges = new vis.DataSet(data.edges);
const shown = {contains: true, imports: true, inherits: true, calls: true};
const view = new vis.DataView(edges, {filter: e => shown[e.kind]});
const big = data.nodes.length > 300;
const net = new vis.Network(document.getElementById("net"), {nodes, edges: view}, {
  layout: {improvedLayout: !big},
  physics: {solver: "forceAtlas2Based", stabilization: {iterations: big ? 100 : 300}},
  edges: {arrows: {to: {enabled: true, scaleFactor: 0.5}}, smooth: false},
  nodes: {shape: "dot", size: 10, font: {size: 12}},
  groups: {
    file: {color: "#4c78a8", size: 16, shape: "box", font: {color: "#fff"}},
    class: {color: "#b279a2"}, function: {color: "#54a24b"}, method: {color: "#72b7b2"},
    external: {color: "#bab0ac", shape: "diamond"}
  },
  interaction: {hover: true, tooltipDelay: 150}
});
document.getElementById("info").textContent =
  data.nodes.length + " nodes, " + data.edges.length + " edges" + (data.note ? " - " + data.note : "");
document.querySelectorAll("input[data-kind]").forEach(cb => cb.addEventListener("change", () => {
  shown[cb.dataset.kind] = cb.checked; view.refresh();
}));
document.getElementById("find").addEventListener("keydown", ev => {
  if (ev.key !== "Enter") return;
  const q = ev.target.value.trim().toLowerCase();
  const hit = data.nodes.find(n => n.id.toLowerCase() === q)
           || data.nodes.find(n => n.id.toLowerCase().includes(q));
  if (hit) { net.selectNodes([hit.id]); net.focus(hit.id, {scale: 1.2, animation: true}); }
});
</script>
</body>
</html>
"""


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


def graph_html(graph: dict) -> str:
    """Single-file interactive view (vis-network from unpkg); dashed edges = not EXTRACTED.

    Above MAX_HTML_NODES nodes the browser cannot lay the graph out usefully, so only file
    and external nodes (and the edges between them) are drawn, with a note saying so.
    """
    nodes, note = graph["nodes"], ""
    if len(nodes) > MAX_HTML_NODES:
        nodes = [n for n in nodes if n["kind"] in ("file", "external")]
        note = (f"files only: {len(graph['nodes']) - len(nodes)} symbols hidden "
                f"(graph has {len(graph['nodes'])} nodes, limit {MAX_HTML_NODES})")
    keep = {n["id"] for n in nodes}
    data = {"note": note, "nodes": [_vis_node(n) for n in nodes],
            "edges": [_vis_edge(e) for e in graph["edges"]
                      if e["src"] in keep and e["dst"] in keep]}
    # "<" escaped so no source text (e.g. a docstring with "</script>") can end the data block
    blob = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    return HTML_TEMPLATE.replace("__VIS__", VIS_NETWORK_URL).replace("__DATA__", blob)


def export(root: str | os.PathLike, graph: dict) -> list[Path]:
    """Write TREE.txt, SUMMARY.md and graph.html next to graph.json; return their paths."""
    out_dir = graph_path(root).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, text in (("TREE.txt", tree_text(graph)), ("SUMMARY.md", summary_md(graph)),
                       ("graph.html", graph_html(graph))):
        path = out_dir / name
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


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


def _entry(by_id: dict, node_id: str, confidence: str | None = None) -> dict:
    n = by_id.get(node_id, {})
    entry = {"id": node_id, "kind": n.get("kind"), "file": n.get("file"), "line": n.get("line")}
    if confidence is not None:
        entry["confidence"] = confidence
    return entry


def query(graph: dict, mode: str, name: str) -> list[dict]:
    """Results per matched node, sorted by id.

    callers / callees: [{node, callers|callees: [{id, kind, file, line, confidence}]}]
    deps: [{node, imports: [...], imported_by: [...]}] for the file of each match
          (a symbol means its file; an external package has only imported_by).
    """
    by_id = {n["id"]: n for n in graph["nodes"]}
    matches = find_nodes(graph, name)
    results = []
    if mode in ("callers", "callees"):
        calls = [e for e in graph["edges"] if e["kind"] == "calls"]
        for n in matches:
            if mode == "callers":
                hits = [(e["src"], e["confidence"]) for e in calls if e["dst"] == n["id"]]
            else:
                hits = [(e["dst"], e["confidence"]) for e in calls if e["src"] == n["id"]]
            results.append({"node": n["id"],
                            mode: [_entry(by_id, i, c) for i, c in sorted(hits)]})
    elif mode == "deps":
        imports = [e for e in graph["edges"] if e["kind"] == "imports"]
        targets = sorted({n["id"] if n["kind"] == "external" else n["file"] for n in matches})
        for t in targets:
            results.append({
                "node": t,
                "imports": [_entry(by_id, e["dst"]) for e in
                            sorted(imports, key=lambda e: e["dst"]) if e["src"] == t],
                "imported_by": [_entry(by_id, e["src"]) for e in
                                sorted(imports, key=lambda e: e["src"]) if e["dst"] == t],
            })
    else:
        raise ValueError(f"unknown query mode: {mode}")
    return results


def format_query(mode: str, results: list[dict]) -> str:
    out = []
    for res in results:
        out.append(f"{mode} of {res['node']}")
        if mode == "deps":
            for key, label in (("imports", "imports"), ("imported_by", "imported by")):
                out.append(f"  {label}:")
                out += [f"    {d['id']}" for d in res[key]] or ["    (none)"]
        else:
            out += [f"  {r['confidence']:<9}  {r['id']}  (line {r['line']})"
                    for r in res[mode]] or ["  (none)"]
    return "\n".join(out) + "\n"
