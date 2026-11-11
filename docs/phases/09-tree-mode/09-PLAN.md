# Phase 9 - Tree mode: plan

Goal (AGENTS.md Phase 9): toolbar toggle buttons Graph | Tree. Graph = the Phase 8 view, unchanged and the default.
Tree = the same graph laid out left to right like an editor's project tree. First attempt replaced Graph; dropped.
User choices kept from it: Phase 8 node look, ROW 40 px; labels folder name / file basename / symbols as Phase 8;
Tree first opens at the top of the tree at 100% zoom.

Design: two vis networks in the same grid cell; the hidden one gets class "off" (visibility: hidden, keeps its
size, camera and positions). Graph code, DataSets (nodes, edges, shown, placed) and options stay as in Phase 8.
Tree has its own DataSets (tnodes, tedges, tshown) built lazily on the first click on Tree, physics off.
`net` = the active network, so the shared Phase 8 code (pick, Fit, deep link) acts on the shown mode; refresh()
starts with `if (mode === "tree") return refreshTree();`. Leaving Graph switches its physics off (stops a running
Re-layout); Tree is disabled until Graph's first layout is done (so the Phase 8 stabilization handler always runs on
the Graph network). Re-layout in Tree re-applies the tree positions. Selection, search, panel, hop focus, filters,
legend, LLM layer, Collapse all and deep links are shared state.

Tree model (pure, from the first attempt): DIRS ("dir:<path>/" page-only folders), parentOf, treeLayout(V) ->
{pos, dirs, branches}: x = depth * 260, y = row * 40, folders then files A-Z then symbols by line; hidden parent ->
nearest shown ancestor; externals in one block after a blank row; branches "b:<child>" folder -> subfolder / file.

Tasks (test first; after each `REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q`; one commit each)
1. Tree model: DIRS, parentOf, treeKey, treeLayout. Tests: test_js_tree_layout_fixture (fixture order written by hand:
   dir:app/ d0; 5 files d1 A-Z; classes/functions d2 in source order; methods d3; ext:json, ext:os after a blank
   row), test_js_tree_layout_folders (nested repo: folders first, root files d0), test_js_tree_layout_compacts
   (class filter off; file-level view + expand), test_template_tree_strings. `pytest -q -k tree_layout`
2. Tree look as data, Graph data untouched: treeNodeItems (tree labels, folders, LLM colours), treeEdgeItems
   (contains + branches = grey cubicBezier horizontal, no arrow; relations + bundles = curvedCW 0.25, Phase 8
   colours/dashes). Tests: test_js_tree_edge_styles, test_js_tree_labels, test_js_graph_data_untouched (D.nodes /
   D.edges keep the Phase 8 labels and styles), test_template_tree_styles. `pytest -q -k "tree_ or graph_data"`
3. Modes: buttons #mode-graph / #mode-tree, #tree container, setMode, startTree, refreshTree, placeTree, topView,
   relayout guard, setLLM also colours tnodes. Tests (fake vis in node): test_js_mode_switch (Tree locked until the
   graph layout is done; Tree positions = treeLayout; Graph positions, camera calls and physics untouched by Tree
   work; back to Graph syncs filters), test_js_mode_pick (pick/Fit act on the shown network), test_js_tree_relayout,
   test_template_modes (Phase 8 Graph options still in start()). `pytest -q tests/test_html_tree.py`
4. Check + docs: `git diff 21ba424 -- tests/test_html_template.py tests/test_outputs.py` empty (Phase 5/8 tests
   unchanged); `reaper export .`; synthetic 400-module repo (08-RESEARCH.md l.310); headless Chrome on both,
   Graph (default) and Tree: no console errors, #status, screenshots. 09-SUMMARY.md with a <= 8 item checklist.
