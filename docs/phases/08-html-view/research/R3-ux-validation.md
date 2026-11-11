# R3: UX + validation research, Phase 8 (interactive HTML view)

Scope: UI behaviour to copy from other tools (within 08-CONTEXT D-01..D-08), pitfalls, and how to validate
VIEW-01..VIEW-07. Tags: [VERIFIED] = checked in this repo's source/data or by running it; [CITED: url];
[ASSUMED] = design judgement or unchecked browser/library behaviour. Deferred items (path tracing, hulls,
dark mode, inlined library, precomputed layout, compact arrays) are not recommended anywhere below.

Facts used throughout [VERIFIED, computed with the conda env]:
- Fixture: 25 nodes (5 file, 4 class, 4 function, 10 method, 2 external), 39 edges (18 contains, 8 imports,
  1 inherits, 12 calls; 4 calls INFERRED, 0 AMBIGUOUS). AMBIGUOUS needs the tests/test_resolve.py
  `test_last_name_matching` mini repo (A.go -> B.save is AMBIGUOUS).
- This repo: 346 nodes, 860 edges (under the ~1500/5000 budget -> full view). "run_gr" matches
  `reaper/enrich.py::run_groups` (name "run_groups") and `reaper/enrich.py::run_groups.store` (name "store").
  run_groups callers: reaper/cli.py::_enrich_groups, tests/test_enrich_groups.py::groups (both EXTRACTED).
- semantic.json here: files (summary, role, input_sha, model), groups g1..g6 (name, summary, members,
  input_sha, model), architecture (overview, patterns[name, explanation, evidence], decisions[decision,
  rationale, evidence], dropped_evidence, input_sha, model).
- `_vis_node` emits only id/label/group/title: search on name/signature and the panel need ADDED fields
  (name, kind, signature, file, line, doc, deg) - allowed by D-04.

## A. What to copy

### A1. Sourcetrail [CITED: https://github.com/CoatiSoftware/Sourcetrail/blob/master/DOCUMENTATION.md]
Copy:
- Search popup that lists matches as you type, matched text visible, node type shown on the right of each
  row; arrow keys move, Enter picks (VIEW-01). Sourcetrail's docs do not state a ranking, so ours is A6.
- Picking a symbol makes it "active": graph shows it plus everything it relates to (VIEW-02, VIEW-03).
- Depth control for the trail (their slider; ours = hop buttons 1/2/3, VIEW-03).
- Bundled edges drawn thicker with the bundled count on hover (VIEW-06 aggregated file edges: width = count,
  title "service.py -> models.py: 3 edges (imports 1, calls 2)").
- Legend reachable from the graph (VIEW-04; ours is always visible, see A5).
Do NOT copy: fuzzy skip-character matching (rank becomes hard to predict/test); code view with snippets
(needs source text in the payload); "custom trail to target" (= path tracing, deferred); full-text search.

### A2. Nx graph [CITED: https://nx.dev/docs/features/explore-graph]
Copy:
- Focus a node, then reshape with sidebar controls ("proximity and group by folder") - our hop buttons sit
  next to the focus state (VIEW-03). That "proximity" means hop count is [ASSUMED]; the page does not say.
- Composite nodes "expanded in place" to show members and their dependencies -> double-click a file in the
  level-of-detail view (VIEW-06).
- Clicking an edge tells "which file(s) created the dependency" -> click an aggregated edge: status line
  lists its kind/confidence counts (VIEW-06).
- Sidebar search = substring on names (VIEW-01, our tier 3-4).
Do NOT copy: trace path between two projects (deferred); PNG export; manual per-node hide list.

### A3. dependency-cruiser [CITED: https://github.com/sverweij/dependency-cruiser/blob/main/doc/cli.md]
Copy:
- `--focus` = node plus direct dependencies and dependents; `--focus-depth` default 1 (0 = infinite) ->
  hop focus is undirected, default 1, capped at 3 (VIEW-03).
- `--collapse` summarises modules to folder level -> our file level (VIEW-06); ddot "summarises modules on
  folder level" confirms aggregated edges are the norm.
- Filters are composable options -> kind, edge-kind, confidence and focus combine (VIEW-04).
Do NOT copy: `--reaches` / `--affected` (directional transitive impact) - a new feature; if wanted it goes
to <deferred>. Folder-level collapse (only file level is in D-03).

### A4. Emerge [CITED: https://github.com/glato/emerge]
Copy:
- "Node colors are based on Louvain modularity" with a step to make colouring deterministic -> colour by the
  stored semantic.json groups (g1..gN), palette indexed by group order, so colours are stable (VIEW-05).
- Live search highlighting as you type (VIEW-01).
- Selection plus "fading unselected nodes" -> dim instead of hide is an option; we hide (A7) because hiding
  also cuts render cost on big repos [ASSUMED].
- Generated from Python into an HTML app (same model as ours).
Do NOT copy: concave hulls (deferred), dark mode (deferred), heatmaps, git metrics, TF-IDF search.

### A5. Page layout (one plain-JS template, CSS grid, no build step) [ASSUMED design]
```
+--------------------------------------------------------------------------------------------+
| #bar: repo-reaper | [LLM layer x] (only with semantic) | Focus: [1][2][3] [Clear] | [Fit]   |
|       [Collapse all] (LOD only) | #status: "346 nodes, 860 edges" / CDN / LOD message       |
+----------------------+----------------------------------------------+----------------------+
| #side (260px)        | #net (minmax(0,1fr), min-height:0)           | #panel (340px)       |
| [#search..........]  |                                              | [Details][Architecture|
| #results (<= 30)     |               vis-network canvas             |  (LLM-generated)]    |
| #legend:             |                                              | tab content, scrolls |
|  Node kinds  x n/N   |                                              |                      |
|  Edge kinds  x n/N   |                                              |                      |
|  Confidence  x n/N   |                                              |                      |
|  Groups (LLM) swatch |                                              |                      |
+----------------------+----------------------------------------------+----------------------+
```
`body{height:100vh;display:grid;grid-template:auto 1fr / 260px minmax(0,1fr) 340px}`, `#bar` spans all
columns, side and panel `overflow:auto`. The legend IS the filter list (swatch + checkbox + "shown/total"),
so counts and filters cannot disagree. Columns have fixed widths, so the canvas size changes only on window
resize, which vis handles (autoResize default true) [CITED: https://visjs.github.io/vis-network/docs/network/].

### A6. Search ranking rule (VIEW-01)
Case-insensitive; query trimmed; tiers, first match wins per node:
1 name == q; 2 name starts with q; 3 name contains q; 4 id contains q (covers "UserService.create",
"app/service.py"); 5 signature contains q. Tie-break: deg (in+out from outputs.degrees, precomputed field)
desc, then id. Cap 30 rows; row = label + kind badge + file:line (all textContent). Debounce 120 ms.
Example [VERIFIED data]: "run_gr" -> run_groups (tier 2) above run_groups.store (tier 4); "valid" ->
app/utils.py::validate (deg 2) above app/repository.py::validate (deg 1). Search covers ALL nodes, including
ones hidden by filters or inside collapsed files; picking one reveals it (A7, A10).
Keys: "/" focuses search, Up/Down move, Enter picks, Esc clears focus.

### A7. Hop focus (VIEW-03) and the focus/filter rule
- Picking a node (search row, canvas click, panel link, evidence chip) = select + open Details + focus with
  the current hop value (default 1). Buttons 1/2/3 change the depth; [Clear] / Esc restores the full view
  and keeps the selection. `net.fit({nodes: focusSet})` after each change.
- Focus set = undirected BFS from the selected node over edges that pass the edge-kind AND confidence
  filters, never through `contains` (a file contains everything, 2 hops would be the whole file plus its
  imports). Contains edges are still drawn between nodes already in the set when that filter is on.
  Fixture check: create, hops=1 -> 7 nodes (itself + User, User.label, UserRepository.save,
  UserService.log, utils.normalize, utils.validate) [VERIFIED from the edge list].
- One function `applyView()` computes visibleNodes = kindOn && (no focus || in focusSet), visibleEdges =
  kindOn && confOn && both ends visible; the selected node is always visible (status: "shown although its
  kind is filtered"). DataView refresh + legend counts come from these same sets.

### A8. Filters, legend, INFERRED vs AMBIGUOUS (VIEW-04)
- Three checkbox groups (node kind x5, edge kind x4, confidence x3), each "shown/total".
- Edge styles applied in JS at load, JSON unchanged (`dashes: true` must stay for INFERRED - the Phase 5 test
  asserts `is True` [VERIFIED tests/test_outputs.py]): EXTRACTED solid; INFERRED long dash [8,5];
  AMBIGUOUS dotted [2,4] + `color.opacity` 0.5. Dash arrays and opacity are vis edge options
  [CITED: https://visjs.github.io/vis-network/docs/network/edges.html]. Panel rows carry a text badge
  (EXTRACTED / INFERRED / AMBIGUOUS), so colour/dash is never the only cue.
- Node kinds by shape too (file box, external diamond, class/function/method dots of different size), so the
  LLM group colouring (A9) does not lose the kind.

### A9. LLM layer (D-02, VIEW-05)
- Toggle `#llm-toggle` exists in the bar but stays `hidden` unless `data.semantic` is non-null. Default on.
- Every LLM element is created with class `llm`; one CSS rule `body.llm-off .llm{display:none}` hides
  summaries, roles, group names, the Architecture tab button and the group legend. Toggle off also recolours
  nodes by kind (explicit colours both ways via `nodes.update`) and switches to the Details tab.
- Keep ALL LLM text out of node `title`/`label` (tooltips cannot be hidden by the toggle); it lives once in
  `data.semantic` (files by path, groups, architecture) and is rendered only in panel/legend.
- Labels: tab "Architecture (LLM-generated)"; panel block "File summary - LLM-generated, model X".
- Stale: badge "stale" + text "source changed since this was generated; re-run reaper enrich" for files
  (input_sha mismatch), groups (_fresh false) and architecture (any group stale or its input changed). Stale
  groups still colour nodes (legend "g3 Name (stale)"); files in no stored group are grey "(no group)".
  Optional: dashed node border for stale files (`shapeProperties.borderDashes`)
  [CITED: https://visjs.github.io/vis-network/docs/network/nodes.html].
- Architecture tab: overview, patterns (name, explanation), decisions (decision, rationale), each with
  evidence chips (buttons, textContent = id). Click = pick (A7) but the tab stays on Architecture so the next
  chip is one click away. An id no longer in the graph -> disabled chip "(not in graph)".

### A10. Level of detail (D-03, VIEW-06)
- Over budget (Python decides, e.g. nodes > 1500 or edges > 5000): `data.lod = true`, `data.file_edges`
  precomputed = cross-file non-contains edges aggregated to (file or ext id) pairs with per "kind|confidence"
  counts, so JS can recompute width/dash when filters change. Fixture result [VERIFIED]: 8 pairs, e.g.
  service.py -> models.py {imports|EXTRACTED 1, calls|EXTRACTED 1, calls|INFERRED 1}; 6 intra-file edges vanish.
- Opens with file + external nodes only; `#status` says "file-level view: N nodes / M edges over budget;
  double-click a file to expand". Edge width = enabled count (vis `value` + `scaling`) [CITED: edges.html].
- Double-click a file: add its symbols in a ring around the file position, re-derive its edges by mapping each
  endpoint to itself (expanded file) or its file (collapsed). Double-click again / panel button "Collapse
  file" / bar [Collapse all] restore. Picking a symbol in a collapsed file auto-expands that file.
- Note vis fires two `click` events before `doubleClick` [CITED: network docs]: click handler must be
  idempotent (select + panel), doubleClick does the expand.

## B. Pitfalls and mitigations
| Pitfall | Mitigation |
|---|---|
| JSON ending the `<script>` block ("</script", "<!--") | Keep `json.dumps(...).replace("<", "\\u003c")`: blob has no raw "<" for a docstring with `<!--` and `</script>` [VERIFIED by running graph_html]. Keep `type="application/json"` + `JSON.parse`. |
| U+2028/2029 | `json.dumps(ensure_ascii=False)` keeps them raw [VERIFIED]; harmless for JSON.parse, fatal only if the blob were ever inlined as a JS literal. Also replace them with ` `/` ` (cheap). Docstrings already cut at them (first line) [VERIFIED], LLM summaries are not. |
| Data reaching the DOM as HTML | D-07: createElement + textContent only; clear lists with `el.replaceChildren()` or `textContent = ""`, never `innerHTML = ""`. vis 9 renders string titles as text ("Titles are now interpreted literary, not as HTML") [CITED: https://github.com/visjs/vis-network/releases/tag/v9.0.0]; never pass Element titles; never set `font.multi` (true/'html' interprets markup in labels) [CITED: nodes.html]. |
| Template filled in several passes | One `re.sub(r"__([A-Z]+)__", lambda m: values[m.group(1)], TEMPLATE)`; inserted text is not rescanned [VERIFIED: "__A__"->"__B__" stays "__B__"]. Avoid `string.Template` (`${}` in JS) and `str.format` (braces in CSS/JS). |
| CDN down / blocked | Do NOT add `onerror`/`integrity` to the script tag: the Phase 5 test asserts the exact text `<script src="...vis-network.min.js">` [VERIFIED]. Static `#status` text "Loading vis-network from unpkg..." in HTML; inline script wrapped in a function that starts `if (typeof vis === "undefined")` -> textContent "Could not load vis-network 9.1.9 from unpkg.com (offline or blocked)". |
| Physics never stopping (CPU) | On `stabilizationIterationsDone` set `physics: {enabled: false}`; stabilization can end at the iteration cap, not at rest [CITED: network docs]. `stopSimulation()` alone is undone by data changes, i.e. every filter refresh [CITED]. Expand uses ring placement, no physics; optional [Re-layout] turns physics on, then off on `stabilized` or after a 10 s guard [ASSUMED timings]. `hideEdgesOnDrag`/`hideEdgesOnZoom` when big [CITED: interaction.html]. |
| Positions lost when nodes leave/re-enter the DataView | With physics off, re-added nodes need x/y: snapshot `net.getPositions()` into the DataSet before each `applyView()` [ASSUMED vis behaviour; manual check 4]. |
| Payload size | This repo: 257 KB JSON, ~237 chars/node, ~201/edge; `separators=(",", ":")` saves ~6% [VERIFIED]. 20k nodes + 60k edges ~ 17 MB [estimate]. Keep LLM text once (per file), not per node; LOD keeps the DataSet small. |
| Toolbar over the canvas | Today `#net{position:absolute;top:44px}` under a `flex-wrap` bar [VERIFIED outputs.py]; a wrapped bar covers the canvas. Use the grid in A5; `#net` needs `min-height:0`. |
| Search on thousands of nodes | Precompute lower-case name/id/signature once; debounce 120 ms; cap 30 rows; build rows in a DocumentFragment. Linear scan over 20k nodes stays in milliseconds [ASSUMED]. |
| Focus + filter interplay | Rule in A7 (BFS over filter-visible edges; selected node forced visible; search ignores filters). `selectNode` is not fired by programmatic `selectNodes` [CITED], so pick() opens the panel itself. |
| Legend counts drift | Counts derived from the sets `applyView()` just computed, never incremented by handlers. In LOD, edge counts = underlying edges represented (sum of enabled bundle counts); status adds "N lines drawn". |
| Deep links with "/" ":" "." | `#node=` + `encodeURIComponent(id)` + `&hops=2`; read with `new URLSearchParams(location.hash.slice(1))`; write with `history.replaceState`; unknown id -> status "node not in graph" [ASSUMED]. |
| "No LLM text" test vs template strings | The template itself contains "LLM-generated"/"Architecture"; tests must assert absence of the semantic CONTENT and `data["semantic"] is None`, not absence of those words. |
| Import cycle | outputs never imports enrich (CONTEXT): test it with a source grep. |

## C. Validation architecture

### C1. pytest checks on the generated HTML string (tests/test_outputs.py, html_data helper unchanged)
Field/key names (`semantic`, `lod`, `file_edges`, `deg`) are proposals; the plan fixes them.
| Req | Checks (hand values from the fixture unless noted) |
|---|---|
| VIEW-01 | Hooks `id="search"`, `id="results"`. Node `f"{S}::UserService.create"` has name "create", kind "method", signature "create(self, entity_id, name)", file "app/service.py", line 15, doc "Validate, build and save a new user.", deg 6; `f"{R}"` (app/repository.py) deg 4. Phase 5 counts unchanged: 25 nodes, 39 edges, note "". |
| VIEW-02 | Hooks `id="panel"`, `id="tab-details"`. Edges keep from/to/kind/confidence (relations derive from them); sources of kind "calls" edges into `f"{U}::validate"` = [`f"{S}::UserService.create"`] (its other in-edge is contains from app/utils.py) [VERIFIED]. Panel builder has no `innerHTML` (VIEW-07 grep). |
| VIEW-03 | Hooks `data-hops="1"`, `"2"`, `"3"`, `id="clear-focus"`. (BFS itself: manual item 4, or optional C3 node test: create hops=1 -> 7 ids.) |
| VIEW-04 | One filter input per NODE_KINDS, EDGE_KINDS, CONFIDENCES (e.g. `data-conf="AMBIGUOUS"`); `id="legend"`. Ambiguous mini repo: edge A.go -> B.save has confidence "AMBIGUOUS", `dashes` True; existing INFERRED assertions untouched. |
| VIEW-05 | Without semantic.json: `data["semantic"] is None`, `id="llm-toggle"` carries `hidden`, `reaper export` returns 0. With a hand-written semantic.json in tmp: file summary `"Makes users <b>x</b></script>"` round-trips via html_data and `"</script><b>"` is not in html; fake input_sha -> stale True; input_sha from `enrich.cache_key(model, enrich.file_input(graph, root, path))` -> stale False; group members map to colour indexes; evidence ["app/service.py::UserService.create", "app/ghost.py::nope"] -> first in node ids, second flagged missing. Toggle on: no summary text in any node title. |
| VIEW-06 | monkeypatch budget below 25 nodes (replaces `test_html_large_graph_shows_files_only`, log in SUMMARY): `lod` True, `file_edges` == the 8 pairs (A10), service.py -> models.py counts {imports|EXTRACTED: 1, calls|EXTRACTED: 1, calls|INFERRED: 1}, nodes still 25 (expand needs them). Default budget: `lod` False. Template contains `stabilizationIterationsDone` and `doubleClick` handlers. |
| VIEW-07 | Template has none of `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval(`, `multi:`. Exact vis script tag still present; template contains `typeof vis` and static `id="status"` loading text. One pass: docstring `"""__VIS__ __DATA__ __SEMANTIC__"""` (every marker) survives verbatim in html_data, and html has exactly one embedded data block. Blob contains no raw `<`, ` `, ` `. `reaper/outputs.py` source has no `enrich` import. |

### C2. Manual browser checklist (on this repo unless noted; `reaper map . && reaper export .`)
1. Open .reaper/graph.html: no console errors; layout settles, then stops (CPU idle in the task manager).
2. Type "run_gr": the list shows reaper/enrich.py::run_groups first; picking it focuses the node and opens
   the panel.
3. Panel shows signature, file:line, doc, file summary + role (marked LLM-generated, and stale if so), and
   callers/callees with confidence badges; each entry is clickable and moves the selection.
4. Hop focus 1/2/3 and [Clear] work; node-kind, edge-kind and confidence filters combine with focus;
   INFERRED (dashed) and AMBIGUOUS (dotted, faded) look different (use a repo that has AMBIGUOUS edges);
   legend counts follow every filter change; nodes keep their places when filters are toggled back.
5. Nodes are coloured by group; each architecture evidence chip focuses its node; the LLM toggle hides all
   LLM text (summaries, roles, group names, Architecture tab) and restores kind colours.
6. A copy without semantic.json (`reaper export` on a fresh map) shows no LLM text and no toggle.
7. A synthetic repo above the budget opens file-level with weighted edges; double-click expands a file in
   place, double-click again collapses it; CPU idle afterwards.
8. Deep link `#node=<encodeURIComponent(id)>&hops=2` survives a reload (only if deep links are planned).
9. A docstring/summary `<b>x</b></script>` shows as literal text in panel, tooltip and search row.

### C3. Optional automation (not required by acceptance)
- Headless Chrome smoke [VERIFIED it loads today's graph.html from file:// and fetches unpkg]:
  `google-chrome --headless=new --user-data-dir=<scratch> --virtual-time-budget=8000 --dump-dom
  file://.../graph.html | grep -o '<span id="status">[^<]*'` (never print the dump: it holds the data).
  Pointing VIS_NETWORK_URL at a bad URL should show the CDN message in the dump (item 1 / VIEW-07).
- node v18 is at /usr/bin/node [VERIFIED], not in the conda env: if the template keeps pure functions
  (rank, hopSet, applyView sets) in one marked block, a `skipif(shutil.which("node") is None)` test could
  run them on the fixture (create hops=1 -> 7 ids; "valid" order). Adds no Python dependency [ASSUMED worth it
  only if C1 feels too thin].
