# 08-04 SUMMARY: template core (view, filters, focus, LOD)

Status: done. Requirements: VIEW-03, VIEW-04, VIEW-06, VIEW-07 (template side).

## What was built
reaper/templates/graph.html rewritten (Phase 5 page replaced, data slots unchanged):
- Layout: CSS grid `auto 1fr / 260px minmax(0,1fr) 340px` (bar | side | #net | #panel), `[hidden]` rule,
  every DOM hook of the contract (hop buttons 1-3, clear-focus, fit, collapse-all, relayout, llm-toggle,
  status, search, results, legend checkboxes per node kind / edge kind / confidence with `.count` spans,
  panel tabs, details, arch). Search, results, panel, tabs and the LLM hooks are static markup for 08-05.
- Safe boot: static `<script src="__VIS__"></script>` kept byte-identical; boot() injects the jsDelivr copy
  (createElement, SRI sha384, crossOrigin anonymous) when `typeof vis === "undefined"`; onerror or still no vis
  -> #status (class error) "Could not load vis-network 9.1.9 from unpkg.com or cdn.jsdelivr.net ...".
- Edge styles at load: INFERRED dashes [8, 6], AMBIGUOUS [2, 4] plus colour {color, opacity: 0.5}.
- Pure, node-testable logic: bundleParts, applyView (View rules), legendCounts, bfs, refocus, focusOn
  (LOD symbol centre expands the files of focused symbols), toggleExpand, bundleStyle.
- DOM/vis: refresh() (ring placement of newly expanded files' symbols, getPositions -> nodes.update, applyView,
  LOD bundles re-styled on every refresh via `edges.update(D.file_edges.map(...bundleStyle(f)))`, DataView
  refresh, legend counts + #status "N nodes, M edges shown (L lines)" + D.note); hop buttons, clear-focus,
  Esc, legend change listeners, Fit, doubleClick -> toggleExpand, Collapse all (shown only in LOD), Re-layout.
- Physics: forceAtlas2Based, smooth false, arrows to; improvedLayout only when <= 150 nodes start visible;
  300 iterations (100 above 300); hideEdgesOnDrag/Zoom in LOD; physics off at stabilizationIterationsDone;
  relayout() is the only physics-on call, switched off on "stabilized" or after RELAYOUT_MS = 3000.

## Files
- Modified: reaper/templates/graph.html, tests/test_html_template.py
- Created: docs/phases/08-html-view/08-04-SUMMARY.md

## Tests added (tests/test_html_template.py, 15 new; helper run_js + _node, fixture_html, fn_body)
- 08-04-1: test_js_parses, test_template_dom_hooks, test_template_cdn_fallback, test_template_edge_styles,
  test_html_ambiguous_is_dashed (regression guard: passed at once, Python already dashes non-EXTRACTED edges),
  test_js_edge_styles_at_load.
- 08-04-2: test_js_bfs_hops, test_js_bfs_respects_filters, test_js_view_counts, test_js_lod_focus,
  test_template_focus_strings.
- 08-04-3: test_js_lod_counts, test_js_toggle_expand, test_template_lod_strings, test_template_physics_never_back_on.
- run_js skips with "node >= 18 not found: JS behaviour test skipped (node is a test-time tool, not a Python
  dependency)" and fails instead under REAPER_REQUIRE_NODE=1 (both checked by running with node off PATH).

## Decisions honoured
D-01 vis-network 9.1.9 (unpkg tag unchanged), D-03 file-level view from precomputed file_edges + double-click
expand, D-04 Python payload untouched (JS only styles D.edges after parse), D-05 no Python dependency (node is
test-time only), D-06 only unpkg (via __VIS__) and jsDelivr exact version (SRI hash checked against the real
jsDelivr file), D-07 textContent only (no innerHTML/outerHTML/insertAdjacentHTML/document.write), D-08 no
format or CLI change. No `<deferred>` item built.

## Deviations and interpretations
- Claude's discretion under D-03: "width = count" read as "width encodes count": bundle width =
  `Math.min(8, 1 + Math.log2(count))`, count = the bundle's edges passing the current filters (08-RESEARCH P5).
- Own new test corrected before implementing: test_js_lod_counts node breakdown for expanded {S, M} was
  miscounted by hand (class 4 / method 6); the fixture gives class 3 / method 7 (Entity, User, UserService +
  7 methods). The plan pins only sizes, edge, conf and lines for that case; those were unchanged.
- Extra assertion in test_js_parses: JS EDGE_COLORS == outputs.EDGE_COLORS (contract says they are equal).
- Top-level `let shown, placed` next to net/DataSets: the DataView filters' current V and the expanded set of
  the last refresh (for ring placement). Ring placement skips symbols already loaded, so they don't jump.
- A bundle whose enabled edges are only AMBIGUOUS gets dashes [2, 4] and opacity 0.5, like raw edges.
- Not in this plan: canvas click -> pick, search, panel, LLM layer (08-05). Until 08-05 a single click does not
  focus.
- No Rule 1-4 deviations; no blockers. 08-03 files (reaper/cli.py, tests/test_export_semantic.py) not touched.

## Manual check (headless Chrome, real vis-network 9.1.9, scratch copies only)
No JS errors; physics off after stabilization; Re-layout turns it on and it is off again within 3 s; in LOD
f3 turns dashed orange "1 edge (calls 1: INFERRED 1)" with EXTRACTED off; with network blocked #status shows
the error message; with unpkg broken the jsDelivr fallback (SRI) loads and the graph draws.

## Verify
- `REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q tests/test_html_template.py` -> 20 passed in 2.02s
- `conda run -n repo-reaper pytest -q` -> 185 passed in 3.37s
- `REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q` -> 185 passed in 3.87s

Self-Check: PASSED
