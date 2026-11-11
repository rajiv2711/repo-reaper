# Phase 9 - Tree mode: summary (user browser checklist 1-8: all pass, 2026-11-11)

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
- Phase 8 bug fixed (user-approved): vis re-applies the group style on colourless node updates, so Graph lost its
  LLM colours on the first refresh (21ba424: #d62728 -> #4c78a8). llmColour(id) now rides every position update.

Tests: tests/test_html_tree.py, 15 new (fixture order hand-written first; mode tests run the real start() with a
fake vis recording calls per network). Phase 5/8 test files unchanged (git diff 21ba424 on them is empty). Fixed in
my own new tests: two node-count slips (25 nodes), AMB repo folder, a colour test that checked items, not drawing.
Result: REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q -> 213 passed. Headless Chrome: 0 console
messages, Graph and Tree, on this repo (448 nodes) and the synthetic repo (7201 nodes, file-level view).

Known behaviour: folders not in legend counts; in Tree under hop focus a symbol with a hidden file hangs under its
folder; long relation curves bulge in Tree's Fit view; plain A-Z (m1, m10, m100); deep links open in Graph.

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
