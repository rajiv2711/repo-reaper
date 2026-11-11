# Phase 9 - Tree mode: summary

What changed (reaper/templates/graph.html only; outputs.py, graph.json, semantic.json, CLI and embedded data unchanged)
- Toolbar Graph | Tree buttons. Graph = the Phase 8 network, default, untouched: of the Phase 8 template exactly one
  line changed (the approved bug fix below); everything else is added. Tree is enabled once Graph's first layout is done.
- Tree = a second vis network in the same grid cell (the hidden one: visibility hidden, keeps size, camera and
  positions), own DataSets built on first use, physics off. `net` = the shown network, so pick, Fit and deep links
  act on it; refresh() starts with `if (mode === "tree") return refreshTree();`; Re-layout in Tree re-applies the
  tree positions; leaving Graph switches its physics off (stops a running Re-layout). Shared: selection, search,
  panel, hop focus, filters + legend, LLM layer, Collapse all, file-level expand, deep links.
- treeLayout(V): pure; folders, then files A-Z (case-insensitive), symbols in source order; x = depth * 260,
  y = row * 40; hidden parent -> nearest shown ancestor; externals after a blank row. Page-only folder nodes
  "dir:<path>/" and branches "b:<child>". Look: contains + branches grey cubicBezier (horizontal), no arrow;
  relations and bundles curvedCW 0.25 with the Phase 8 colours/dashes. Labels: folder name, file basename, symbols
  as in Phase 8. First Tree open: top of the tree at 100% (or the focus, if something is selected).
- Phase 8 bug fixed (user-approved): vis re-applies the group style to a node updated without a colour, so Graph's
  refresh() turned LLM group colours into kind colours on the first click/filter. llmColour(id) now travels with
  every position update in both modes. Seen in headless Chrome: 21ba424 "load #d62728 | after refresh #4c78a8";
  now "#d62728" after refresh, filter off/on, LLM on; "#4c78a8" with LLM off.

Tests: tests/test_html_tree.py, 15 new (fixture order written by hand before coding; mode tests run the real
start() with a fake vis that records calls per network). Phase 5/8 test files unchanged
(`git diff 21ba424 -- tests/test_html_template.py tests/test_outputs.py` is empty). Own-test corrections during the
work (not expected-value tweaks to pass code): two node-count slips (fixture has 25 nodes), the AMB repo needed its
own folder, a colour check that tested vis items instead of what vis draws was replaced by the update-order check.
Result: REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q -> 213 passed. Headless Chrome: 0 console
messages, Graph and Tree, on this repo (448 nodes) and the synthetic repo (7201 nodes, file-level view).

Known behaviour: folders are page-only (not in legend counts); under hop focus in Tree a symbol whose file is
hidden hangs under its folder; long relation curves bulge (0.25 x length) in Tree's Fit view; file order is plain
A-Z (m1, m10, m100, m2); the mode is not part of the deep link (links open in Graph).

Browser checklist (this repo, then the synthetic repo)
1. Opens in Graph exactly as before (force layout, group colours); Graph highlighted; Tree enabled once laid out.
2. Clicking a node or a filter in Graph keeps the group colours (the fixed bug).
3. Tree: top of the tree at 100%: reaper -> __init__.py, cli.py, ... -> cli.py functions in source order; group
   colours; grey branch curves without arrows; relations bend over the tree; INFERRED dashed.
4. Search "run_gr" -> run_groups in Tree: panel + compact focus. Graph: run_groups selected, focus fitted, the other
   nodes where you left them. Back to Tree: same tree.
5. In Tree: hops 1-3 and the filters compact the tree, legend counts match; "class" off -> methods under their
   file; "contains" off -> no branch lines.
6. Tree: drag a node, Re-layout puts it back. Graph: Re-layout runs the force layout as before. Fit fits the shown mode.
7. LLM toggle recolours both modes; Architecture chips focus nodes in the shown mode; #node=...&hops=2 deep link works.
8. Synthetic repo: Graph file-level view as before; Tree: pkg -> files; double-click m0.py inserts its symbols;
   in Graph they sit on a ring around m0.py; Collapse all; CPU idle.
