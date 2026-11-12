# Phase 13 PLAN: UI/UX polish of graph.html

User decision (2026-11-12): all 4 proposed items. reaper/templates/graph.html only (+ tests, docs); graph.json,
semantic.json, CLI, outputs.py unchanged; Graph and Tree stay; no new library; data text via textContent; light and
dark built from the existing Phase 11 tokens (token sets unchanged).

## 1. Toolbar + status
- Buttons and the Theme select styled from --chip, --chip-line, --hover, --fg; active stays #4c78a8; segmented
  groups [Graph|Tree] [Hops 1 2 3] [Fit, Clear focus, Collapse all, Re-layout]; :focus-visible ring in --link.
- Re-layout hidden in Tree (setMode); Tree nodes are not draggable (dragNodes false), so nothing needs putting
  back. relayout() itself unchanged (Phase 9 test).
- Status text as before minus the file-level note, which becomes a "file-level view" tag (#lod-note, tooltip =
  D.note). Status stays on one row (nowrap, ellipsis, full text in its tooltip); the CDN error still wraps.

## 2. Compact LLM groups
- Group = <details class="grp"><summary>swatch, name (one line, ellipsis, full name as tooltip), stale,
  "N files"</summary> summary</details>, closed at load; "no group" stays a plain row.

## 3. Details panel + keys
- Signature, ids, file:line and relation links in monospace 12px.
- Empty panel (renderHome at start): hint, "Most connected" = topNodes(10) (deg desc, then id; deg 0 left out)
  as links that pick, and the key list.
- onKey (document keydown): "/" focuses search, g Graph, t Tree, f Fit; not while typing in a field or with
  Ctrl/Alt/Meta. Esc clears focus as before. Button tooltips name their keys.
- searchKey: Up/Down move the highlighted result (clamped), Enter picks it (first one if the list is stale).

## 4. Calmer Tree edges
- calm(e): every Tree edge that is not a branch (relations, file and folder bundles) goes into tedges at width 1
  and opacity x CALM_OPACITY (0.3; AMBIGUOUS keeps its half); its own width and opacity are kept in STRONG.
- Tree network edges.chosen = treeEdgeChosen: an edge that is selected or hovered (vis does this for a node's
  edges with the node) gets its STRONG width and opacity, +1 width when selected. treeEdgeItems(), bundleStyle()
  and Graph mode unchanged (Phase 8/9/12 tests).

## Tests first (tests/test_html_polish.py; expected values by hand from tests/fixtures/sample_py)
1. topNodes(10): UserService.create (6); repository.py, service.py (4); utils.py (3); then deg 2 by id:
   models.py, User, User.label, UserRepository.save, normalize, validate; 11th Entity (externals: no deg).
2. Status: fixture text unchanged; file-level view: no note in the status, #lod-note shown, title = D.note.
3. Keys (fake vis): t -> Tree, g -> Graph, f -> fit, "/" focuses search; ignored in an INPUT or with Ctrl.
   Re-layout hidden in Tree, shown in Graph; Tree dragNodes false.
4. Search: Down twice -> highlight 2, Up from 0 stays 0, Enter picks the highlighted id.
5. Calm: create -> log in tedges = {color {#f58518, 0.3}, width 1}, AMBIGUOUS 0.15, bundle f3 width 1 with
   STRONG width 1 + log2(3); branches unchanged; treeEdgeChosen restores width / opacity.
6. Template: <details> groups, .mono, CSS uses only the Phase 11 tokens. Phase 5/8/9/11/12 tests unchanged.

## Check
pytest; headless Chrome light + dark: this repo and the 400-module synthetic repo, Graph and Tree, 0 console
messages; browser checklist in 13-SUMMARY.md.
