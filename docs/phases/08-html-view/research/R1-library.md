# R1 - vis-network 9.1.9 API for Phase 8 (VIEW-01..07)

Method: downloaded the real 9.1.9 files (`standalone/umd/vis-network.min.js`, non-minified `vis-network.js`
(41,851 lines), `package.json`) and the official docs pages, then read/grepped them (never executed).
GitHub release notes and issues via api.github.com. Line refs `L1234` = non-minified `vis-network.js` 9.1.9.
Tags: [VERIFIED] read in 9.1.9 source/docs or checked by command; [CITED: url]; [ASSUMED] not checked.
Nothing was run in a browser, so runtime claims are from reading the source.

## 0. Delivery and CDN failure (VIEW-07, D-01, D-06)
- URL `https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js`: 688,911 bytes (~689 kB),
  ~162 kB gzipped, header says `@version 9.1.9 @date 2023-11-03`. Served `cache-control: max-age=31536000`
  with CORS `*`. [VERIFIED curl]
- jsDelivr `https://cdn.jsdelivr.net/npm/vis-network@9.1.9/standalone/umd/vis-network.min.js` serves the same
  bytes (sha256 f53f833d...a1a2e5), CORS `*`, so it works as a fallback.
  SRI = `sha384-yxKDWWf0wwdUj/gPeuL11czrnKFQROnLgY8ll7En9NYoXibgg3C6NK/UDHNtUgWJ`. [VERIFIED]
- The UMD sets `global.vis = global.vis || {}` and exports `DataSet, DataView, Network, data, ...` (L41838-48).
  The standalone build bundles vis-data and injects its own CSS (`div.vis-tooltip`). [VERIFIED]
- Do NOT add `onerror` or `integrity` to the existing tag. `test_html_loads_vis_network_and_embeds_graph`
  checks the exact substring `<script src="...vis-network.min.js">`. [VERIFIED tests/test_outputs.py]
  The tag is parser-blocking, so an inline script placed after it already knows whether the library loaded. [ASSUMED: standard HTML]
```js
// keep: <script src="__VIS__"></script>   (unchanged)
if (typeof vis === "undefined" || typeof vis.Network !== "function") {
  const m = document.getElementById("cdn-error");          // static element, text set via textContent
  m.textContent = "Could not load vis-network from unpkg.com (offline or blocked): the graph cannot be drawn.";
  m.hidden = false;
} else { start(); }
```
  Pitfall: never give a DOM element `id="vis"`. Named element access would make `window.vis` an element, so
  the `typeof` check would pass even when the CDN failed. [ASSUMED: HTML named-access rule]
  Optional fallback: `document.createElement("script")` with the jsDelivr src + `integrity` + `crossOrigin =
  "anonymous"`, then `onload = start` and `onerror = showError`.

## 1. DataSet / DataView: filters and level of detail (VIEW-04, VIEW-06)
- `new vis.DataView(ds, {filter})`: the filter gets the full item, `filter(item) -> bool` (getIds L18112). [VERIFIED]
- `view.refresh()` runs the filter again over the whole DataSet. It sends one `add` event for newly matching
  ids and one `remove` event for ids that stopped matching (L18706-18760). [VERIFIED] Updates to the DataSet go
  through the view on their own: an `update` that changes a filter result becomes add/remove (L18927). [VERIFIED]
- `view.length`, `view.getIds()`, `view.get(id)` (returns null when the item is filtered out). Use these for legend counts. [VERIFIED]
- **Edges of filtered-out nodes:** `_updateVisibleIndices` (L41439) only draws edges whose two endpoint nodes
  exist and are not hidden. `EdgesHandler._updateState` (L27803) also removes edges with a missing endpoint
  from the network body, then on every data change adds them back from the view and removes them again.
  So the drawing is correct, but `edgesView.length` still counts those edges and there is O(E) churn.
  **Fix:** put the endpoint test in the edge filter so that view length = edges drawn (VIEW-04 truth 2). [VERIFIED]
- DataSet: `add(items)` throws "Cannot add item: item with id X already exists". `update(items)` updates or
  adds, with a shallow merge `{...old, ...patch}`. `remove(ids)`. An item without `id` gets a UUIDv4 written
  INTO the source object (`ensureFullItem`). [VERIFIED L18479, L17625, `_updateItem`]
  Each DataSet call is one event, which is one network `_dataChanged`, so always pass arrays.
  [VERIFIED + CITED: https://github.com/visjs/vis-network/issues/131]
```js
const D = JSON.parse(document.getElementById("graph-data").textContent);
D.edges.forEach((e, i) => { e.id = "e" + i; });                 // stable ids (or add an "id" key in Python, D-04 allows it)
const nodes = new vis.DataSet(D.nodes), edges = new vis.DataSet(D.edges.concat(D.lodEdges || []));
const S = {kinds: new Set(["file","class","function","method","external"]), ekinds: new Set([...]),
           conf: new Set(["EXTRACTED","INFERRED","AMBIGUOUS"]), focus: null, expanded: new Set(), lod: big};
const fileOf = id => id.split("::")[0];
const nodeOk = n => !!n && S.kinds.has(n.group) && (!S.focus || S.focus.has(n.id))
                   && (!S.lod || n.group === "file" || n.group === "external" || S.expanded.has(fileOf(n.id)));
const edgeOk = e => S.ekinds.has(e.kind) && S.conf.has(e.confidence)
  && (!e.agg || (!S.expanded.has(e.from) && !S.expanded.has(e.to)))  // agg file->file edge until a side expands
  && nodeOk(nodes.get(e.from)) && nodeOk(nodes.get(e.to));           // endpoint test => view length == drawn
const nodesView = new vis.DataView(nodes, {filter: nodeOk});
const edgesView = new vis.DataView(edges, {filter: edgeOk});
function apply() { savePositions(); nodesView.refresh(); edgesView.refresh(); updateLegend(); }
```
- **`hidden` flag vs DataView** [VERIFIED]:
  | | `hidden: true` | DataView filter |
  |---|---|---|
  | physics | node still simulated (docs: "will still be part of the physics simulation"; `updatePhysicsData` only checks `options.physics`) | removed from body, so no cost |
  | position | kept | lost: node re-created and placed at random (see section 2) unless x/y were saved first |
  | `selectNodes`/`fit`/`focus` on it | works | `selectNodes` throws RangeError, `fit` throws TypeError, `focus` logs an error |
  | edges | hidden automatically | removed internally (above) |
  For LOD (thousands of symbols not loaded) use DataView. Use the same DataView for kind/confidence/hop
  filters, so there is one mechanism. Physics is off after the first settle, so the extra cost of DataView
  is only the node re-create on refresh: O(n) and cheap at this size. [ASSUMED]
- **`network.storePositions()` THROWS when the nodes DataView filters anything out.** It loops over the
  whole DataSet and reads `body.nodes[id].x` (L24165). [VERIFIED + CITED: https://github.com/visjs/vis-network/issues/1129]
  Use this DataView-safe replacement:
```js
function savePositions() {                     // getPositions() with no args = loaded/visible nodes only
  const p = net.getPositions();
  nodes.update(Object.keys(p).map(id => ({id, x: p[id].x, y: p[id].y})));
}
```

## 2. Expand a file in place (D-03, VIEW-06)
- New nodes without x/y are placed by `positionInitially` at a random angle on a circle of radius (count+50)
  around the origin (L36658), not near the file. Hierarchical mode re-places everything instead (section 9). [VERIFIED]
- Physics disabled means nothing moves them, so give them coordinates near the file BEFORE refresh. Updates
  to items that are still filtered out only touch the DataSet and do not reach the network. [VERIFIED L18927]
```js
function expand(fileId) {
  const c = net.getPositions([fileId])[fileId], kids = D.nodes.filter(n => n.id.startsWith(fileId + "::"));
  const r = 60 + 8 * kids.length;
  nodes.update(kids.map((n, i) => ({id: n.id, x: c.x + r * Math.cos(2 * Math.PI * i / kids.length),
                                                y: c.y + r * Math.sin(2 * Math.PI * i / kids.length)})));
  S.expanded.add(fileId); apply();             // view diff adds symbols + their edges, drops agg edges of fileId
}
net.on("doubleClick", p => { const id = net.getNodeAt(p.pointer.DOM); if (id && nodes.get(id).group === "file") expand(id); });
```
  Optional tidy-up: `settle()` (section 4). It moves ALL loaded nodes a little, not only the new ones.

## 3. Hop focus 1-3 on the FULL data (VIEW-03)
- `net.getConnectedNodes(id, dir)` reads `body.nodes[id].edges`, so it only sees edges loaded in the network.
  It misses everything filtered out or not expanded (L24218). `dir`: `"from"` = parents (sources of incoming
  edges), `"to"` = children, anything else = both. `net.getConnectedEdges(id)` logs an error for a node that is
  not loaded. [VERIFIED + CITED: https://visjs.github.io/vis-network/docs/network/]
- So build an adjacency map once from `D.edges` (not the aggregated edges) and run BFS:
```js
const adj = new Map();
for (const e of D.edges) for (const v of [e.from, e.to]) (adj.get(v) || adj.set(v, []).get(v)).push(e);
function hood(id, hops) {
  const seen = new Set([id]); let front = [id];
  for (let h = 0; h < hops && front.length; h++) {
    const next = [];
    for (const v of front) for (const e of adj.get(v) || []) {
      if (!S.ekinds.has(e.kind) || !S.conf.has(e.confidence)) continue;   // filters combine (truth 2)
      const w = e.from === v ? e.to : e.from;
      if (!seen.has(w)) { seen.add(w); next.push(w); }
    }
    front = next;
  }
  return seen;
}
// S.focus = hood(id, hops); in LOD mode also S.expanded.add(fileOf(x)) for symbol ids in the set; apply();
```

## 4. Stabilization, then idle CPU (VIEW-06 truth 4)
- Events (all [VERIFIED] L29625-29681 + docs): `startStabilizing`; `stabilizationProgress {iterations, total}`
  fires every `updateInterval` ticks; `stabilizationIterationsDone` fires when the hidden pass ends (fit already
  done); `stabilized {iterations}` fires when velocity < `minVelocity` or after `stopSimulation()`.
- The hidden pass runs `updateInterval` ticks per `setTimeout` batch with redraw blocked. The DOM stays
  responsive between batches, but the canvas is blank until the pass ends, so show progress text. Defaults:
  `iterations: 1000, updateInterval: 50, fit: true`. [VERIFIED L28985]
- If the hidden pass ends unstable, `_finalizeStabilization` calls `startSimulation()` (a visible animation that
  runs until velocity < 0.75). Disabling physics inside `stabilizationIterationsDone` runs before that call,
  and `startSimulation` then does nothing. [VERIFIED L29669-29683]
- Trap: `setOptions({physics: {...}})` without `enabled` sets `enabled = true` (PhysicsEngine.setOptions,
  L29067). Always pass `enabled: false`, or use `physics: false`. [VERIFIED]
- `net.stabilize(n)` runs ticks even while physics is disabled. It has no enabled check and refits the view at
  the end when `stabilization.fit` is true. [VERIFIED L29580]
```js
net.on("stabilizationProgress", p => { status.textContent = "layout " + p.iterations + "/" + p.total; });
net.once("stabilizationIterationsDone", () => { net.setOptions({physics: {enabled: false}}); status.textContent = ""; });
function settle(capMs = 1500) {                 // brief re-enable after an expand; hard cap so the CPU always idles
  net.setOptions({physics: {enabled: true}});
  const stop = () => net.setOptions({physics: {enabled: false}});
  net.once("stabilized", stop); setTimeout(stop, capMs);
}
```
- Solvers: docs call `barnesHut` "the fastest, default and recommended solver for non-hierarchical layouts".
  `forceAtlas2Based` reuses the Barnes-Hut tree with linear repulsion and degree-scaled mass. Both are
  O(n log n) per tick. [CITED: https://visjs.github.io/vis-network/docs/network/physics.html]
  Keep forceAtlas2Based (it spreads hubs better). Switch to barnesHut only if profiling says so. [ASSUMED]

## 5. Edge style: dashes and width (VIEW-04, VIEW-06)
- `dashes`: `false`, `true` (= `[5,5]`), or an array passed straight to `ctx.setLineDash`, so `[dash, gap, ...]`
  in canvas order (the docs wrongly say "gap length, dash length"). [VERIFIED L25115, L25663]
- **Constraint:** `test_html_dashed_when_not_extracted` asserts `dashes is True` and `sum(e["dashes"]) == 4`.
  Keep booleans in the Python JSON and switch to arrays in JS. [VERIFIED tests/test_outputs.py:183-190]
```js
// before (outputs.py _vis_edge): "dashes": e["confidence"] != "EXTRACTED"   -> every non-EXTRACTED edge [5,5]
// after (JS, at load, Python unchanged):
const DASH = {INFERRED: [8, 6], AMBIGUOUS: [2, 4]};
D.edges.forEach(e => { if (DASH[e.confidence]) e.dashes = DASH[e.confidence]; });
```
- Width: `width` (default 1). Or `value` + `edges.scaling {min: 1, max: 15}`, which scales linearly over the
  loaded edges (defaults L27418). [VERIFIED] For aggregated counts use log + clamp, which stays stable across filters:
  `e.width = Math.min(8, 1 + Math.log2(e.count));`. The legend can show "width = edge count".
- Keep `edges.smooth: false`. The default `smooth: {type: "dynamic"}` adds one hidden physics node per edge
  (`setupSupportNode`, `"edgeId:"+id`), which roughly doubles physics work. [VERIFIED L25945]

## 6. Colours and groups (VIEW-05, D-02 toggle)
- `group: kind` + `options.groups` (as today) sets shape/colour per kind. A group name not in options gets an
  auto palette colour (`Groups.get`). [VERIFIED L14049]
- Semantic colour: set a per-node `color` (string or `{background, border}`). Toggle it off with `color: null`:
  `Node.setOptions` records `_localColor`, and `updateGroupOptions` then merges the group colour back.
  [VERIFIED L23020-23192, L23622] This keeps the file box / external diamond shapes (do not change `group`).
```js
function semantic(on) {                         // one update call = one event
  nodes.update(D.nodes.map(n => ({id: n.id, color: on && n.sgroup != null ? PALETTE[n.sgroup % PALETTE.length] : null})));
}
```

## 7. Text safety: title and label (VIEW-07, D-07, truth 5)
- `title` as a string is plain text: `Popup.setText` does `this.frame.innerText = content`. An `Element` is
  appended as-is (L10753). [VERIFIED] Breaking change in 9.0.0: "Titles are now interpreted literary,
  not as HTML". [CITED: https://github.com/visjs/vis-network/releases/tag/v9.0.0]
  If a rich tooltip is ever needed, build the Element with `createElement` + `textContent` only.
- `label` is drawn on the canvas (`ctx.fillText`). `font.multi` defaults to `false` for nodes and edges
  (L23736, L27393), so `<b>x</b>` is drawn literally. Never set `font.multi: "html"`/`"markdown"`: that changes
  the text (not XSS). [VERIFIED + CITED: docs nodes.html]
- The library itself has no `innerHTML`/`outerHTML`/`insertAdjacentHTML`/`document.write` sink (grep: one
  `innerHTML` hit, in a comment). D-07 risk is only in our own panel/search/list code. [VERIFIED]

## 8. Navigation and events (VIEW-01, VIEW-02, VIEW-05 evidence links)
- `net.focus(id, {scale, offset, locked, animation: {duration, easingFunction} | bool})`. `animation: true`
  = 1000 ms easeInOutQuad. For an id that is not loaded it logs `Node: X cannot be found.` and does nothing. [VERIFIED L32648]
- `net.fit({nodes, minZoomLevel, maxZoomLevel (default 1), animation})`. `nodes: []` means all. An id that is
  not loaded throws TypeError (`getRange`). [VERIFIED L32505, L29759]
- `net.selectNodes(ids, highlightEdges = true)` throws RangeError `Node with id "X" not found` for an id that is
  not loaded. [VERIFIED L35380]
- Programmatic `selectNodes`/`setSelection` call `commit()`, not `commitAndEmit()`, so NO
  `selectNode`/`click` event fires. Call the panel renderer yourself after a search pick. [VERIFIED]
- `click` / `doubleClick` / `selectNode` get `{nodes, edges, event, pointer: {DOM, canvas}}`; `click` also
  gets `items`. A double click fires 2 `click` events and then `doubleClick`, so keep click handling idempotent
  (open panel) and put expand on doubleClick only. [VERIFIED L33622-33642 + CITED: docs network events]
  `net.getNodeAt(p.pointer.DOM)` gives the node under the pointer. [VERIFIED L41779]
```js
function goTo(id, hops) {                       // search pick / panel link / architecture evidence id
  if (!nodesView.get(id)) reveal(id);           // expand its file, clear a focus/filter that hides it, apply()
  net.selectNodes([id]);
  net.focus(id, {scale: 1.2, animation: {duration: 400, easingFunction: "easeInOutQuad"}});
  showPanel(id);                                // selectNode is not fired for programmatic selection
}
```
- 10.1.4 fixed "finish pending view animation before starting a new one", so 9.1.9 may glitch when animated
  focus calls overlap. Debounce search-driven focus. [CITED: https://github.com/visjs/vis-network/releases/tag/v10.1.4; impact ASSUMED]

## 9. Layout options (VIEW-06)
- `layout.improvedLayout` runs only on the initial `setData` (`_dataLoaded`), not on DataView refresh or add.
  Above `clusterThreshold` (150) it clusters in up to 10 rounds, then runs Kamada-Kawai with an all-pairs
  Floyd-Warshall (O(k^3)). On dense graphs the clustering fails with console "could not be positioned ...
  disable improvedLayout". [VERIFIED L36681-36790, L40805; CITED: https://github.com/visjs/vis-network/issues/2257]
  Docs: "For networks larger than 100 nodes, clustering will be performed automatically". [CITED: layout.html]
```js
// before (HTML_TEMPLATE): const big = data.nodes.length > 300; ... layout: {improvedLayout: !big},
// after: decide on what is actually loaded
layout: {improvedLayout: nodesView.length <= 150},
```
- Hierarchical: `layout: {hierarchical: {direction: "LR", sortMethod: "directed", shakeTowards: "roots",
  levelSeparation: 200, nodeSpacing: 30}}`. The validator accepts sortMethod `hubsize|directed` only
  (L40268). [VERIFIED] Findings against using it as the default:
  (a) `setupHierarchicalLayout` runs on EVERY `_dataChanged` and re-places all loaded nodes, so each filter
  change or expand reflows the whole view and expand-in-place is lost [VERIFIED L36474, L36858-36912];
  (b) the solver is forced to `hierarchicalRepulsion` [VERIFIED + CITED: physics.html];
  (c) a mix of nodes with and without `level` throws [VERIFIED];
  (d) cyclic graphs (import cycles) get level gaps, fixed only in 9.1.12 [CITED: https://github.com/visjs/vis-network/releases/tag/v9.1.12];
  (e) very slow at about 1200 nodes / 1100 edges [CITED: https://github.com/visjs/vis-network/issues/680]
  and about 2 s per re-layout at 1k nodes [CITED: https://github.com/visjs/vis-network/issues/1879].
  Verdict: workable for a static file-level view of a few hundred nodes, but force layout should stay the
  default. At most, offer an optional "layered" toggle when no file is expanded.
- `interaction.hideEdgesOnDrag` / `hideEdgesOnZoom` exist (default false) and help on big views. [VERIFIED L31436]

## 10. Practical size limits [ASSUMED unless noted]
- No official limit is published. Each physics tick is O(n log n) (Barnes-Hut tree, [VERIFIED L27903]); each
  frame redraws every loaded edge on a 2D canvas; the hidden stabilization costs `iterations` x tick.
- With `smooth: false`, `improvedLayout: false` above 150 nodes, physics off after stabilization and
  hideEdgesOnDrag/Zoom, the CONTEXT budget (~1500 nodes or ~5000 edges loaded) is a reasonable start. Measure
  it with the synthetic repo of truth 4 (DevTools Performance: idle after `stabilizationIterationsDone`).
- vis `cluster()` is not a good LOD tool. Each call emits `_dataChanged` (full rebuild) unless
  `refreshData=false` (L30175) [VERIFIED]; opening/closing clusters took about 2 s at 1k nodes
  [CITED: issue 1879]; `storePositions` has "todo: add support for clusters" [VERIFIED]. This matches D-03
  (precompute in Python).

## 11. Prior findings: verdicts
| Prior finding | Verdict |
|---|---|
| UMD ~689 KB; v10 only repackages | Size CONFIRMED (688,911 B; 162 kB gz). "Only repackages" PARTLY WRONG: 10.0.0 = ESM+CJS rework + major vis-* deps, and 9.1.10-10.1.5 include fixes 9.1.9 lacks (hierarchical cyclic gaps 9.1.12, overlapping view animations 10.1.4). |
| DataView filters + getConnectedNodes cover focus/filters | CORRECTED: getConnectedNodes sees only loaded edges, so BFS on own adjacency from `D.edges`. Edge filter must also test endpoints for legend counts. storePositions crashes with a filtered DataView. |
| Dashes arrays INFERRED [8,6], AMBIGUOUS [2,4] | CONFIRMED in vis (canvas `[dash, gap]`), but set them in JS: a Phase 5 test pins `dashes: true/false` in the JSON. |
| Hierarchical LR usable for a few hundred file nodes | PARTLY: usable as a static view, but re-lays out every node on each data change (breaks expand/filters), cycle gaps in 9.1.9. Not the default. |
| Smooth up to a few thousand nodes+edges | UNVERIFIED [ASSUMED]: needs measurement. |
| cluster() slow; storePositions ignores clusters | CONFIRMED (source + issue 1879), plus storePositions throws with DataView (issue 1129). |
| v9 titles plain text, HTML only via Element | CONFIRMED (`innerText`; v9.0.0 breaking change). |

## 12. Pitfall checklist for the planner
1. Never `setOptions({physics: {...}})` without `enabled: false` after the first settle.
2. Call `selectNodes`/`fit`/`focus` only on ids where `nodesView.get(id)` is not null; reveal first.
3. Save positions (`getPositions` -> `nodes.update`) before each `refresh()`; never call `storePositions()`.
4. Give new symbol nodes x/y near their file before they become visible.
5. Batch every DataSet change into one array call.
6. Keep `smooth: false`; `font.multi` false; string titles only (or Elements built with textContent).
7. Leave the vis `<script src>` tag byte-identical; detect failure with `typeof vis` afterwards.
