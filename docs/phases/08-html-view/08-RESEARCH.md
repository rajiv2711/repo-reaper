# Phase 8: Interactive HTML view - RESEARCH (synthesis of R1-R3)

Inputs: 08-CONTEXT.md (locked) + research/R1-library.md, R2-integration.md, R3-ux-validation.md. Tags: [VERIFIED],
[CITED: url], [ASSUMED]; "(R1 §n)" = origin. [VERIFIED: synthesis run] = run here on scratch copies (fixture copy,
`git archive HEAD` copy of this repo, synthetic 400-module repo), never on the repo's own .reaper/.

## User Constraints

From 08-CONTEXT.md `<decisions>`, verbatim:

- D-01 Library: stay on vis-network 9.1.9 from unpkg
  (https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js). User said "choose for me"; chosen
  because the Phase 5 tests pin it, it draws dashed edges natively and it covers every VIEW-xx.
- D-02 Semantic layer: `reaper export` reads .reaper/semantic.json when present, with NO CLI change. User
  addition: the LLM layer must be HIDEABLE in the page: one toggle hides all LLM text (summaries, roles,
  group names, architecture tab) and switches group colours back to the structural colouring. LLM text is
  always labelled "LLM-generated"; stale entries are marked "stale". Without semantic.json the page shows no
  LLM text and no toggle.
- D-03 Big repos: level of detail. Above a nodes+edges budget the page opens a file-level view with aggregated
  file->file edges (width = count); double-clicking a file expands it in place to its symbols. The file-level
  data is precomputed in Python. This replaces today's files-only cut, so
  tests/test_outputs.py::test_html_large_graph_shows_files_only may be replaced (log it in SUMMARY); all other
  Phase 5 html tests stay unchanged.
- D-04 Embedded JSON: keep today's node and edge objects (as produced by _vis_node/_vis_edge) and only ADD
  fields/keys, so the Phase 5 html tests (html_data helper) stay untouched. No compact-array payload.
- D-05 No new Python dependencies (stdlib + networkx only; numpy is not in the env).
- D-06 Scripts only from unpkg or jsdelivr, with exact versions.
- D-07 Data or LLM text enters the DOM only via textContent / createElement, never innerHTML (nor
  outerHTML, insertAdjacentHTML, document.write).
- D-08 graph.json and semantic.json formats unchanged.

### Claude's discretion
- UI layout (toolbar, side panel, tabs), colours, the exact level-of-detail budget (roughly 1500 nodes or
  5000 edges as a starting point), hop default, debounce timing.
- Whether HTML_TEMPLATE moves to its own file (e.g. reaper/templates/graph.html). If it does, ship it as
  package data (pyproject.toml) and load it with importlib.resources.
- Deep link (#node=<id>&hops=N) - optional, nice to have.

Deferred (never built): path tracing, group hulls, dark mode, inlined vis copy, precomputed layout, compact arrays.

## Summary

- Python: `graph_html(graph, sem=None)` embeds ALL nodes+edges plus added keys `lod`, `budget`, `meta`, `file_edges`,
  `sem`; `enrich.view_semantic(root, graph)` builds `sem` (None without semantic.json) from existing staleness
  helpers; cli passes it to `export`. Template -> reaper/templates/graph.html, filled in ONE `re.sub` pass.
- JS (plain): one `applyView()` derives visible sets from filters, hop focus, LOD expansion and selection; two
  DataViews filter by them; the legend counts the same sets. 5-tier search; DOM only via createElement+textContent.
- LOD above 1500 nodes or 5000 edges: file+external nodes with per-pair `file_edges`; double-click expands a file
  in a ring; a bundle gives way to raw edges only when BOTH ends are expanded. Physics off after stabilization.
- LLM layer: `body.llm-off .llm {display:none}` + recolour by kind; toggle hidden unless `data.sem` is non-null.
- One Phase 5 test is replaced (files-only cut); every other existing test stays byte-for-byte.

## Standard Stack

| Item | Exact value | Notes |
|---|---|---|
| vis-network | `https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js` | 688,911 B, ~162 kB gz, CORS `*`, `max-age=31536000` [VERIFIED curl, R1 §0]. Tag stays byte-identical `<script src="...">` (no onerror/integrity) because test_html_loads asserts that substring [VERIFIED]. |
| jsDelivr fallback (optional, see Open Q2) | `https://cdn.jsdelivr.net/npm/vis-network@9.1.9/standalone/umd/vis-network.min.js`, `integrity="sha384-yxKDWWf0wwdUj/gPeuL11czrnKFQROnLgY8ll7En9NYoXibgg3C6NK/UDHNtUgWJ"`, `crossOrigin="anonymous"` | Same bytes as unpkg [VERIFIED R1 §0]. Consistent with D-06 (jsdelivr, exact version) and with the pinned-tag test, because it is injected by the inline script with `document.createElement("script")` only after `typeof vis === "undefined"`; the static unpkg tag is untouched. |
| Python | stdlib `json`, `re`, `collections.Counter`, `importlib.resources`; `tomllib` in one test | D-05: no new deps. networkx unchanged (only via existing enrich helpers). |
| Tests | pytest (env `repo-reaper`) | 140 passing at phase start [VERIFIED R2 §7]. Optional: node v18 at /usr/bin/node (not in env) and headless Chrome for smoke checks [VERIFIED R3 C3]. |

## Architecture Patterns

### P1. Module boundaries and signatures (R2 §1)
- `outputs.graph_html(graph: dict, sem: dict | None = None) -> str`; `outputs.export(root, graph, sem=None)`:
  sem goes only to graph_html; TREE.txt/SUMMARY.md unchanged. `outputs.file_edges(graph) -> list[dict]`.
- `enrich.view_semantic(root, graph) -> dict | None`: None iff `semantic_path(root)` does not exist
  (load_semantic cannot signal absence) [VERIFIED enrich.py l.80-85]. outputs NEVER imports enrich [VERIFIED].
- `cli.cmd_export`: `sem = enrich.view_semantic(args.repo, graph)`; JSONDecodeError -> stderr warning, sem=None.
- Constants (read at call time so monkeypatch works): `MAX_HTML_NODES = 1500` (was 3000), `MAX_HTML_EDGES = 5000`;
  `lod = len(nodes) > MAX_HTML_NODES or len(edges) > MAX_HTML_EDGES`. This repo (346/860) -> full view;
  synthetic 7,201/12,800 -> LOD [VERIFIED: synthesis run].
- Template: reaper/templates/graph.html, `[tool.setuptools.package-data] reaper = ["templates/*.html"]`, loaded once
  into `outputs.HTML_TEMPLATE` via `importlib.resources.files("reaper").joinpath("templates/graph.html")`. A scratch
  wheel omitted the file without package-data; editable install hides that, so add a tomllib guard test [VERIFIED R2 §8].
  Starts with `<!DOCTYPE html>`, no BOM. AGENTS.md Layout gains one line.

### P2. Embedded-JSON contract (ONE reconciled version; D-04: only additions)
Serialised with `json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))`, then
`"<"` -> `\u003c`, U+2028 -> `\u2028`, U+2029 -> `\u2029`. Lists keep graph order; no `now()` [R2 §4, R3 B].

Top-level keys:
| Key | Status | Value |
|---|---|---|
| `nodes` | kept | ALL graph nodes, graph order, in BOTH modes (fixture 25) - expand and evidence need them [R2 §6, R3 VIEW-06] |
| `edges` | kept | ALL graph edges, graph order, both modes (fixture 39); `file_edges` never appended here |
| `note` | kept | `""` when `lod` is false (asserted by test_html_loads). LOD: `f"file-level view: graph has {N} nodes and {E} edges (budget {MAX_HTML_NODES} nodes, {MAX_HTML_EDGES} edges); double-click a file to expand it"` |
| `lod` | added | bool |
| `budget` | added | `{"nodes": MAX_HTML_NODES, "edges": MAX_HTML_EDGES}` |
| `meta` | added | `{"generated_at": graph["meta"].get("generated_at"), "files": len(graph["files"]), "nodes": N, "edges": E}` (from graph.json, so deterministic) |
| `file_edges` | added | `[]` when `lod` is false; else the per-pair list below |
| `sem` | added | `null`, or the object below |

Node object = `_vis_node` output unchanged `{id, label, group (= kind), title}` + added
`kind, name, file, line, signature, doc` (copied; externals have file/line/signature/doc null [VERIFIED R2 §3])
+ `deg` = in+out from `outputs.degrees(graph).get(id, (0, 0))` (search tie-break; externals 0).
`title` stays structural only: no LLM text in any title/label (the toggle cannot hide tooltips) [R3 A9].

Edge object = `_vis_edge` output unchanged `{from, to, kind, confidence, dashes (bool), color (str), title}`
+ added `id: "e<i>"` (index in graph["edges"]; stable DataSet ids for expand/collapse) [R2 §3].

`file_edges` item (LOD only): `{"id": "f<i>", "from": file-or-ext id, "to": file-or-ext id, "count": int,
"counts": {kind: {confidence: n}}}`, one per (from, to) pair, `contains` skipped, same-file pairs dropped,
sorted by (from, to), `i` = position. Map each endpoint with `node["file"] or node["id"]` (externals map to
themselves, so file->ext imports ARE aggregated and ext nodes ARE LOD nodes). No vis option names
(`value`, `width`, `hidden`, `level`, `x`, `y`) as data keys [ASSUMED R2 §3]; JS derives width/dashes/colour/title.

`sem` object (built only by view_semantic; `.get` everywhere so partial entries never crash [VERIFIED R2 §2]):
```
{"files":  {path: {"summary", "role", "model", "stale": bool}},          # only paths that are file nodes now
 "groups": {gid:  {"name", "summary", "members": [paths], "model", "stale": bool}},
 "architecture": null | {"overview", "patterns": [{"name", "explanation", "evidence": [ids]}],
                  "decisions": [{"decision", "rationale", "evidence": [ids]}],
                  "model", "stale": bool, "dropped": [ids]}}               # null when the section is empty
```
input_sha is not shipped. Group membership lives only in `sem.groups[*].members`; JS maps file -> gid, a symbol
uses its `node.file`, so node objects are identical with and without sem [R2 §3]. Evidence is re-cleaned with
`_clean_items` against the CURRENT graph ids, so every shipped evidence id exists (truth 3); `dropped` =
sorted(stored `dropped_evidence` + newly dropped) [VERIFIED helpers, enrich.py l.457-480, l.548-555].
Staleness (exact helpers, R2 §2): files `e.get("input_sha") != cache_key(e.get("model",""), file_input(graph, root, path))`
(OSError or missing keys -> stale); groups `gid not in plan or not _fresh(entry, members, text)` with
`plan = {gid: (members, text) for gid, members, _, text in _group_plan(graph, sem)}`; architecture stale on
`NotReady` from `arch_input` or `input_sha != cache_key(a.get("model",""), arch_input(graph, sem), ARCH_PROMPT_VERSION)`.

**Reconciliation (a): fixture file_edges.** R2's "12" counts (src, dst, kind) keys; R3's "8" counts (src, dst)
pairs. Both are right for their key [VERIFIED: synthesis run]. Chosen: **per pair with a kind x confidence
breakdown**, because (1) with `smooth: false` two edges of one pair are drawn on the same straight line and hide
each other [ASSUMED], (2) fewer lines: this repo 106 pairs vs 141 keys, synthetic 1,200 vs 2,400 [VERIFIED: synthesis run],
(3) one edge per pair still lets JS recount per enabled kind/confidence. Exact fixture values (sum of counts 15 =
39 edges - 18 contains - 6 same-file; 6 dropped same-file: User->Entity inherits, User.__init__->Entity.__init__ and
User.label->Entity.describe calls INFERRED, save->validate, create->log, utils.validate->normalize calls) [VERIFIED: synthesis run]:

| id | from | to | count | counts |
|---|---|---|---|---|
| f0 | app/repository.py | app/models.py | 1 | imports {EXTRACTED 1} |
| f1 | app/repository.py | app/utils.py | 2 | calls {EXTRACTED 1}, imports {EXTRACTED 1} |
| f2 | app/repository.py | ext:json | 1 | imports {EXTRACTED 1} |
| f3 | app/service.py | app/models.py | 3 | calls {EXTRACTED 1, INFERRED 1}, imports {EXTRACTED 1} |
| f4 | app/service.py | app/repository.py | 3 | calls {EXTRACTED 1, INFERRED 1}, imports {EXTRACTED 1} |
| f5 | app/service.py | app/utils.py | 3 | calls {EXTRACTED 2}, imports {EXTRACTED 1} |
| f6 | app/service.py | ext:os | 1 | imports {EXTRACTED 1} |
| f7 | app/utils.py | ext:os | 1 | imports {EXTRACTED 1} |
LOD start nodes = kind file|external = `["app/__init__.py", M, R, S, U, "ext:json", "ext:os"]` (app/__init__.py is isolated).

### P3. One view function (VIEW-03/04/06; R1 §1, R3 A7)
State S = {nodeKinds, edgeKinds, confs, focus (Set|null), hops (default 1), selected, expanded (Set), lod}.
`applyView()` is pure over S + data and returns {nodes, raw, agg} sets; DataView filters are membership tests;
the legend reads the same sets (so counts cannot drift, truth 2). Rules (reconciliation e1, LOD edges):
- node visible = `id === selected` OR (kind on AND (no focus OR in focus) AND (not lod OR kind is file|external OR
  `expanded.has(node.file)`)). The selected node is always shown (status "shown although its kind is filtered") [R3 A7].
- raw edge visible = kind on AND conf on AND both ends visible AND (not lod OR both `fileOf(end)` expanded),
  `fileOf(id) = node.file || node.id`.
- agg edge visible = lod AND NOT (from expanded AND to expanded) AND both ends visible AND enabled count > 0.
  So every cross-file edge is drawn exactly once: bundled while either side is collapsed, raw when both are
  expanded; same-file edges appear when their file expands. (R1 hid the bundle when EITHER side expanded,
  which loses cross-file links; R3 re-derived symbol->file edges at runtime, which needs synthetic edge ids. This
  rule needs neither.)
- Legend counts = edges represented (raw shown + sum of enabled counts in shown bundles), plus "N lines drawn" [R3 B].
- Before each `refresh()`: `net.getPositions()` -> `nodes.update(...)`; never `storePositions()` (throws with a filtering DataView) [VERIFIED R1 §1 + CITED: https://github.com/visjs/vis-network/issues/1129].

### P4. Hop focus (VIEW-03) - reconciliation e2
Undirected BFS on an adjacency built once from `data.edges` (`getConnectedNodes` sees loaded edges only [VERIFIED
R1 §3]) over edges passing the edge-kind AND confidence filters, never through `contains` (R3 A7; R1's snippet
did not skip it, so a file would pull in all its symbols); contains edges are still drawn inside the set. Fixture:
create hops=1 -> 7 ids (itself, models.User, User.label, UserRepository.save, UserService.log, utils.normalize,
utils.validate), hops=2 -> 10, hops=3 -> 10 [VERIFIED: synthesis run]. In LOD, focus also expands the files of
focused symbols [R1 §3]. Pick (search row, canvas click, panel link, evidence chip) = select + Details + hop focus
+ `net.fit`; [Clear]/Esc drops focus, keeps selection (R3 A7; Open Q1).

### P5. Edge style (VIEW-04) - reconciliation (b)
Python keeps `dashes: bool` (test pins `dashes is True` and `sum(dashes) == 4` [VERIFIED tests/test_outputs.py l.183-190]).
JS at load: `DASH = {INFERRED: [8, 6], AMBIGUOUS: [2, 4]}` (R1's pair, canvas `[dash, gap]` order [VERIFIED R1 §5];
R3's [8,5] looks the same). AMBIGUOUS also gets `color: {color, opacity: 0.5}` [CITED: https://visjs.github.io/vis-network/docs/network/edges.html];
panel rows carry a text badge. Bundles: solid if any enabled EXTRACTED, else INFERRED dash, else AMBIGUOUS dash;
colour EDGE_COLORS[kind] when one enabled kind, else `#888`; `width = Math.min(8, 1 + Math.log2(count))` (stable
across filters, unlike R3's `value`+`scaling` [VERIFIED R1 §5]); title `app/service.py -> app/models.py: 3 edges
(calls 2: EXTRACTED 1, INFERRED 1; imports 1)`. Keep `smooth: false` (dynamic adds a physics node per edge [VERIFIED R1 §5]).

### P6. Layout and idle CPU (VIEW-06) - reconciliation (c)
- Force layout only (`forceAtlas2Based`, as today). **Hierarchical layout is not built** in Phase 8: it re-places
  every loaded node on each data change (breaks expand-in-place and filter stability), forces its own solver,
  and has cycle gaps fixed only in 9.1.12 [VERIFIED R1 §9 + CITED: https://github.com/visjs/vis-network/releases/tag/v9.1.12].
- `layout.improvedLayout` only when the initially visible node count <= 150 (clustering + O(k^3) above)
  [VERIFIED R1 §9]. Stabilization iterations: keep today's 300 / 100 (big) as a start [ASSUMED; tune in check 7].
- `net.once("stabilizationIterationsDone", () => net.setOptions({physics: {enabled: false}}))`; always pass `enabled:
  false` (omitting it re-enables physics) [VERIFIED R1 §4]; progress via `stabilizationProgress`; `hideEdgesOnDrag/Zoom` in LOD.
- Expand = ring placement BEFORE refresh, no physics (R1 §2, R3 A10). Optional [Re-layout]: physics on until
  `stabilized` or a 3 s hard cap (R1 said 1.5 s, R3 10 s) [ASSUMED].

### P7. LLM layer and toggle (VIEW-05, D-02) - reconciliation (d)
Single mechanism: every element that shows LLM-derived content (file summary + role block, LLM stale badges,
group legend section, group names, Architecture tab button AND its pane, dropped-evidence note) is created with
class `llm`; CSS `body.llm-off .llm {display: none !important}`; the toggle does
`document.body.classList.toggle("llm-off", !on)`, recolours with ONE `nodes.update` (group palette <-> kind
colours from the same map as `options.groups`; explicit colours both ways, R3 A9; `color: null` also works
per R1 §6) and switches to Details if Architecture was active. No LLM text in node titles/labels, search rows or
status, so the class rule covers all of it. Toggle markup `<label id="llm-toggle" hidden>`, unhidden only when
`data.sem !== null`; with sem null no `.llm` element is ever created. Add `[hidden]{display:none !important}`.
Labels: tab "Architecture (LLM-generated)", block "File summary - LLM-generated, model X", badge "stale".
Group palette indexed by numeric gid order (sort_keys gives g1, g10, g2) [R2 §4]; files in no group grey "(no group)".

### P8. Search (VIEW-01; R3 A6)
Precompute lower-case name/id/signature once. Tiers: 1 name == q, 2 name startsWith q, 3 name includes q, 4 id
includes q, 5 signature includes q; tie-break `deg` desc then id; cap 30 rows; debounce 120 ms; rows built in a
DocumentFragment with textContent. "run_gr" -> run_groups (tier 2) above run_groups.store (tier 4) [VERIFIED
R3 + synthesis run]. Search covers all nodes; picking a hidden one reveals it (expand file / selected exemption).
Programmatic `selectNodes` emits no event, so pick() renders the panel itself [VERIFIED R1 §8].

### P9. Page layout (R3 A5, [ASSUMED design])
Grid `auto 1fr / 260px minmax(0,1fr) 340px`: bar (toggle, hops, Clear, Fit, Collapse all, `#status`) | search +
legend-filters | `#net` (`min-height:0`) | tabs Details/Architecture. Replaces `#net{top:44px}` [VERIFIED outputs.py].

## Don't Hand-Roll

| Need | Use | Not |
|---|---|---|
| Drawing, physics, zoom, tooltips | vis-network 9.1.9 | own canvas code |
| Filtering what is drawn | `vis.DataView` + `refresh()` | manual add/remove or `hidden` (hidden nodes still simulate [VERIFIED R1 §1]) |
| LOD bundling | Python `file_edges` | vis `cluster()` (full rebuild per call, ~2 s at 1k nodes [CITED: https://github.com/visjs/vis-network/issues/1879]) |
| Staleness | `cache_key`, `file_input`, `_fresh`, `_group_plan`, `arch_input`, `_clean_items` | re-implemented hashing |
| Degrees | `outputs.degrees` | a new counter |
| Escaping | `json.dumps` + `<` replace + `JSON.parse`; DOM via `textContent` | HTML-escape helpers, innerHTML |
| Template fill | one `re.sub(r"__([A-Z]+)__", fn, TEMPLATE)` | chained `.replace`, `str.format`, `string.Template` |
| Package data | `importlib.resources` | paths relative to `__file__` |

## Common Pitfalls

| Pitfall | Mitigation |
|---|---|
| Chained `.replace` substitutes placeholders inside data | one `re.sub` with a FUNCTION replacement (a string replacement raises `bad escape \u` on the blob [VERIFIED R2 §5]); unknown slot -> KeyError |
| `</script>`, `<!--` in data | `<` -> `\u003c` in the blob [VERIFIED R2 §5, R3 B; CITED: https://html.spec.whatwg.org/multipage/scripting.html#restrictions-for-contents-of-script-elements] |
| Adding `onerror`/`integrity` to the vis tag breaks test_html_loads | detect with `typeof vis === "undefined" \|\| typeof vis.Network !== "function"` in the inline script [VERIFIED R1 §0] |
| An element `id="vis"` makes `window.vis` truthy | never use that id [ASSUMED R1 §0] |
| `storePositions()` throws with a filtering DataView | `getPositions()` -> `nodes.update` [VERIFIED R1 §1] |
| `selectNodes`/`fit`/`focus` on a not-loaded id throw or log | reveal (expand file, selected exemption) + `applyView()` first [VERIFIED R1 §8] |
| New nodes appear at random far away | give x/y in a ring before refresh [VERIFIED R1 §2] |
| `setOptions({physics:{...}})` silently re-enables physics | always `enabled: false` [VERIFIED R1 §4] |
| Double-click fires 2 clicks first | click = idempotent select+panel; expand only on `doubleClick` [VERIFIED R1 §8] |
| Edge view counts edges with hidden ends | endpoint test inside the edge rule (P3) [VERIFIED R1 §1] |
| Overlapping animated `focus` calls glitch in 9.1.9 | debounce search-driven focus [CITED: https://github.com/visjs/vis-network/releases/tag/v10.1.4; impact ASSUMED] |
| JS regex escapes in a non-raw Python string | template in its own .html file [VERIFIED R2 §8] |
| Each DataSet call = one network rebuild | always pass arrays [VERIFIED R1 §1] |
| `font.multi` interprets markup in labels | never set it [CITED: https://visjs.github.io/vis-network/docs/network/nodes.html] |
| CSS `display` overrides the `hidden` attribute | `[hidden]{display:none !important}` [ASSUMED: CSS cascade] |
| "No LLM text" tested as absence of the words "LLM-generated" | test `data["sem"] is None` and absence of semantic CONTENT; the template contains the labels [R2 §4, R3 B] |
| `file_input` rebuilds `_children` per file (O(F x (N+E))) | add `_kids=None` to `file_input`, compute `outputs._children(graph)` once in view_semantic [VERIFIED R2 §2] |
| Payload size grows ~210 B per node+edge | sort_keys + compact separators (~7% smaller); LLM text once per file [VERIFIED R2 §4/§6] |

## Code Examples

Python, `graph_html` (before -> after):
```python
# before: nodes cut to files above MAX_HTML_NODES; chained replace
blob = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
return HTML_TEMPLATE.replace("__VIS__", VIS_NETWORK_URL).replace("__DATA__", blob)
# after
deg = degrees(graph)
nodes = [{**_vis_node(n), **{k: n[k] for k in ("kind", "name", "file", "line", "signature", "doc")},
          "deg": sum(deg.get(n["id"], (0, 0)))} for n in graph["nodes"]]
edges = [{**_vis_edge(e), "id": f"e{i}"} for i, e in enumerate(graph["edges"])]
lod = len(nodes) > MAX_HTML_NODES or len(edges) > MAX_HTML_EDGES
data = {"nodes": nodes, "edges": edges, "note": _lod_note(graph) if lod else "", "lod": lod,
        "budget": {"nodes": MAX_HTML_NODES, "edges": MAX_HTML_EDGES}, "meta": {...},
        "file_edges": file_edges(graph) if lod else [], "sem": sem}
blob = (json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        .replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))
return re.sub(r"__([A-Z]+)__", lambda m: {"VIS": VIS_NETWORK_URL, "DATA": blob}[m.group(1)], HTML_TEMPLATE)
```
Python, `file_edges`:
```python
def file_edges(graph):
    file_of = {n["id"]: n["file"] or n["id"] for n in graph["nodes"]}   # ext:x -> itself
    agg = {}
    for e in graph["edges"]:
        a, b = file_of.get(e["src"], e["src"]), file_of.get(e["dst"], e["dst"])
        if e["kind"] != "contains" and a != b:
            agg.setdefault((a, b), {}).setdefault(e["kind"], Counter())[e["confidence"]] += 1
    return [{"id": f"f{i}", "from": a, "to": b, "count": sum(sum(c.values()) for c in k.values()),
             "counts": {kind: dict(c) for kind, c in k.items()}} for i, ((a, b), k) in enumerate(sorted(agg.items()))]
```
Python, cli (before -> after): `outputs.export(args.repo, graph)` -> `outputs.export(args.repo, graph, enrich.view_semantic(args.repo, graph))`.

JS, load + CDN check + edge styles (dash before: every non-EXTRACTED edge `[5,5]`; after: per confidence):
```js
const D = JSON.parse(document.getElementById("graph-data").textContent);
if (typeof vis === "undefined" || typeof vis.Network !== "function") {
  status.textContent = "Could not load vis-network 9.1.9 from unpkg.com (offline or blocked): the graph cannot be drawn.";
} else start();
const DASH = {INFERRED: [8, 6], AMBIGUOUS: [2, 4]};
D.edges.forEach(e => { if (DASH[e.confidence]) e.dashes = DASH[e.confidence];
  if (e.confidence === "AMBIGUOUS") e.color = {color: e.color, opacity: 0.5}; });
```
JS, view sets (P3) and toggle (P7):
```js
const fileOf = id => byId.get(id).file || id;
const nodeOn = n => n.id === S.selected || (S.kinds.has(n.kind) && (!S.focus || S.focus.has(n.id))
  && (!D.lod || n.kind === "file" || n.kind === "external" || S.expanded.has(n.file)));
const rawOn = (e, vn) => S.ekinds.has(e.kind) && S.conf.has(e.confidence) && vn.has(e.from) && vn.has(e.to)
  && (!D.lod || (S.expanded.has(fileOf(e.from)) && S.expanded.has(fileOf(e.to))));
const aggOn = (f, vn) => D.lod && !(S.expanded.has(f.from) && S.expanded.has(f.to))
  && vn.has(f.from) && vn.has(f.to) && enabledCount(f) > 0;
function setLLM(on) { document.body.classList.toggle("llm-off", !on);
  nodes.update(D.nodes.map(n => ({id: n.id, color: on ? groupColor(n) : KIND_COLOR[n.kind]})));
  if (!on && activeTab === "arch") showTab("details"); }
```
BFS (P4) and expand/stabilize: as in R1 §3 (add `if (e.kind === "contains") continue;`), R1 §2, R1 §4.

Synthetic repo for check 7 (7,201 nodes / 12,800 edges, 1,200 file pairs, maps in 1.4 s [VERIFIED: synthesis run]):
```python
import os, random, sys   # python gen.py <dir> 400; then reaper map <dir> && reaper export <dir>
root, n = sys.argv[1], int(sys.argv[2]); random.seed(1)
os.makedirs(f"{root}/pkg", exist_ok=True); open(f"{root}/pkg/__init__.py", "w").close()
for i in range(n):
    deps = random.sample([j for j in range(n) if j != i], 3)
    src = [f'"""Module {i}."""'] + [f"from pkg import m{j}" for j in deps]
    for c in range(3):
        src += [f"class C{c}:"] + [f"    def f{k}(self):\n        return m{deps[k % 3]}.g{k % 2}()" for k in range(4)]
    open(f"{root}/pkg/m{i}.py", "w").write("\n".join(src + [f"def g{k}():\n    return {k}" for k in range(2)]) + "\n")
```

## Assumptions Log

| # | Assumption (origin) | How it will be checked |
|---|---|---|
| A1 | Parser-blocking vis tag: the inline script after it knows whether vis loaded (R1 §0) | manual check 1 with unpkg blocked in DevTools request blocking |
| A2 | `id="vis"` would shadow `window.vis` (R1 §0) | avoided; pytest asserts `id="vis"` not in template |
| A3 | DataView refresh costs only node re-create, cheap (R1 §1) | manual check 4 + 7 (DevTools Performance on filter toggles) |
| A4 | forceAtlas2Based is the better solver here (R1 §4) | manual check 7; switch to barnesHut only if profiling says so |
| A5 | 9.1.9 overlapping animated focus glitches (R1 §8) | debounce; manual check 2 (fast typing + Enter) |
| A6 | Budget 1500 nodes / 5000 edges is workable; smooth up to a few thousand (R1 §10-11) | manual check 7 on the synthetic repo, also with the budget raised |
| A7 | vis may keep simulating once stable (R2 §0) | moot (physics disabled); manual checks 1 + 7: CPU idle |
| A8 | Wrapped toolbar overlaps `#net` (R2 §0) | moot (grid layout); manual check 1 |
| A9 | 100k-node repos: file_input cost would take minutes (R2 §2) | `_kids` fix; optional timing of view_semantic on the synthetic repo |
| A10 | Data keys must avoid vis option names (R2 §3) | contract uses none; pytest asserts node/edge key sets |
| A11 | Payload ~85 MB at 100k nodes + 300k edges; ~17 MB at 20k+60k (R2 §6, R3 B) | Open Q3; measure html size of the synthetic repo in SUMMARY |
| A12 | Nx "proximity" = hop count (R3 A2) | not needed for the build |
| A13 | Hiding (not dimming) cuts render cost (R3 A4) | manual check 4 / 7 |
| A14 | Page layout A5 is usable (R3 A5) | manual check 1 |
| A15 | Re-layout cap: 3 s (R1 1.5 s, R3 10 s) | manual check 7 |
| A16 | Re-added nodes need saved x/y (R3 B; R1 VERIFIED in source) | manual check 4 "nodes keep their places" |
| A17 | Linear search over 20k nodes stays in ms (R3 B) | manual check 7: type in search on the synthetic repo |
| A18 | Deep-link behaviour (R3 B) | manual check 8, only if built |
| A19 | Node-based JS unit test worth it only if C1 is thin (R3 C3) | planner choice |
| A20 | Straight parallel edges of one pair overlap with smooth:false (synthesis, reason for per-pair bundles) | manual check 7 |
| A21 | SRI + crossOrigin on a file:// page works with jsDelivr (synthesis) | manual check 1 variant: unpkg blocked, page still draws |
| A22 | 300/100 stabilization iterations are enough before physics freezes (synthesis) | manual checks 1 + 7: layout readable after freeze |
| A23 | Bundle-until-both-expanded is understandable UX (synthesis) | manual check 7 |
| A24 | `[hidden]` needs `!important` against author `display` (synthesis) | manual checks 5 + 6 |
| A25 | Louvain re-run inside view_semantic is fast enough for export (synthesis) | time `reaper export` on this repo with semantic.json |

## Open Questions

1. Canvas click: select + panel + hop focus (R3 A7, chosen default) or select + panel only? changes scope: no.
2. Build the jsDelivr fallback (~10 lines, D-06 allows it; message names both CDNs if both fail)? Recommended yes. changes scope: no.
3. Hard payload ceiling for huge repos (R2: e.g. > 40k nodes embed files only, expand disabled)? Re-introduces a
   files-only cut that D-03 replaced; not needed for truth 4. Recommended: do not build; record measured size. changes scope: yes.
   RESOLVED 2026-11-11 by the user: no ceiling (always embed everything; record measured sizes).
4. Deep link `#node=<id>&hops=N` (discretion): build last if time allows. changes scope: no.
5. `enrich.file_input(graph, root, path, _kids=None)` (internal signature, output unchanged) for view_semantic speed. changes scope: no.
6. LOD: should expanding ONE file also draw symbol -> collapsed-file links (R3 re-derive) instead of bundles (P3)? changes scope: no.

## Validation Architecture

pytest checks on the HTML string (tests/test_outputs.py; `html_data` helper and the 4 kept html tests unchanged;
M, R, S, U as in the test module). Fixture facts [VERIFIED: synthesis run]: 25 nodes, 39 edges, 4 INFERRED, 0 AMBIGUOUS.
| Req | Checks |
|---|---|
| VIEW-01 | hooks `id="search"`, `id="results"`; node `S::UserService.create` has kind "method", name "create", file "app/service.py", line 15, signature "create(self, entity_id, name)", doc "Validate, build and save a new user.", deg 6; deg of R = 4, `U::validate` = 2, `R::validate` = 1, `ext:os` = 0; node keys == {id,label,group,title,kind,name,file,line,signature,doc,deg} |
| VIEW-02 | hooks `id="panel"`, `id="tab-details"`; edge ids are "e0".."e38", unique; calls into `U::validate` = [`S::UserService.create`] (other in-edge is contains) |
| VIEW-03 | hooks `data-hops="1"`, `"2"`, `"3"`, `id="clear-focus"`; template contains `"contains"` skip in BFS; optional node test: create hops=1 -> the 7 ids of P4, hops=2 -> 10 |
| VIEW-04 | one input per kind: `data-node-kind="<5 kinds>"`, `data-edge-kind="<4 kinds>"`, `data-conf="<3>"`, `id="legend"`; template has `[8, 6]` and `[2, 4]`; test_resolve `test_last_name_matching` mini repo: edge A.go -> B.save confidence "AMBIGUOUS", `dashes` True |
| VIEW-05 | no semantic.json: `data["sem"] is None`, `<label id="llm-toggle" hidden>` in html, `reaper export` returns 0, html == `graph_html(load(repo))` (byte identity). With a hand-written semantic.json: summary `"Makes users <b>x</b></script>"` round-trips and `"</script><b>"` not in html; input_sha "x" -> stale True; `cache_key("m", file_input(...))` -> stale False; fresh group via `_group_plan` -> stale False (fixture = one group g1); evidence `[S::UserService.create, "app/ghost.py::nope"]` -> evidence == first only, "app/ghost.py::nope" in `dropped`; partial `{"groups": {"g0": {"name": "core"}}, "architecture": {"overview": "x"}}` does not crash; no node title contains summary text; template has `body.llm-off .llm` |
| VIEW-06 | replace `test_html_large_graph_shows_files_only` (log in SUMMARY): MAX_HTML_NODES=24 -> `lod` True, 25 nodes, 39 edges, note == LOD text for 25/39/24/5000, `file_edges` == the 8 rows of P2, sum of counts 15; twin MAX_HTML_EDGES=38 -> `lod` True; default -> `lod` False and `file_edges == []`; template contains `stabilizationIterationsDone`, `doubleClick`, `enabled: false` |
| VIEW-07 | template has none of `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval(`, `multi:`, `id="vis"`; exact vis tag present; `typeof vis` and static `id="status"` loading text present; exactly one `<script id="graph-data"`; docstring `"""__VIS__ __DATA__ __X__"""` survives verbatim in html_data; blob has no raw `<`, U+2028, U+2029 |
| infra | outputs.py source has no import of enrich; pyproject package-data has `templates/*.html` (tomllib); template file starts with `<!DOCTYPE html>`, no BOM; `graph_html(g) == graph_html(g, None)` |

Manual browser checklist (R3 C2; this repo unless noted; `reaper map . && reaper export .`):
1. Open .reaper/graph.html: no console errors; layout settles, then stops (CPU idle in the task manager). Variant: block unpkg -> CDN message (or jsDelivr fallback draws).
2. Type "run_gr": the list shows reaper/enrich.py::run_groups first; picking it focuses the node and opens the panel.
3. Panel shows signature, file:line, doc, file summary + role (marked LLM-generated, and stale if so), and
   callers/callees with confidence badges; each entry is clickable and moves the selection.
4. Hop focus 1/2/3 and [Clear] work; node-kind, edge-kind and confidence filters combine with focus; INFERRED
   (dashed) and AMBIGUOUS (dotted, faded) look different (use a repo that has AMBIGUOUS edges); legend counts
   follow every filter change; nodes keep their places when filters are toggled back.
5. Nodes are coloured by group; each architecture evidence chip focuses its node; the LLM toggle hides all LLM
   text (summaries, roles, group names, Architecture tab) and restores kind colours.
6. A copy without semantic.json (`reaper export` on a fresh map) shows no LLM text and no toggle.
7. A synthetic repo above the budget (gen.py above) opens file-level with weighted edges; double-click expands
   a file in place, double-click again collapses it; CPU idle afterwards.
8. Deep link `#node=<encodeURIComponent(id)>&hops=2` survives a reload (only if deep links are planned).
9. A docstring/summary `<b>x</b></script>` shows as literal text in panel, tooltip and search row.

## Sources

- 08-CONTEXT.md; research/R1-library.md, R2-integration.md, R3-ux-validation.md; AGENTS.md; pyproject.toml
- reaper/outputs.py (l.27-28, 90-100, 199-317), reaper/enrich.py (l.76-128, 285-293, 399-416, 457-480, 521-560),
  reaper/cli.py (l.52-58), reaper/graph.py, tests/test_outputs.py (l.168-211)
- https://visjs.github.io/vis-network/docs/network/ (edges, nodes, physics, layout, interaction pages); vis-network
  release notes v9.0.0, v9.1.12, v10.1.4; issues 131, 680, 1129, 1879, 2257 (github.com/visjs/vis-network)
- https://html.spec.whatwg.org/multipage/scripting.html#restrictions-for-contents-of-script-elements
- UX (R3): Sourcetrail DOCUMENTATION.md, https://nx.dev/docs/features/explore-graph, dependency-cruiser doc/cli.md,
  https://github.com/glato/emerge
