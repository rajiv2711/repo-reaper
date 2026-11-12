# Phase 12 SUMMARY: Tree overview (collapsible folders and files)

Status: built and tested; waiting for the user's browser checklist (below) before the tick.

## User decision (2026-11-12)
(a) collapsible folders with bundled edges, over (b) zoom-driven detail and (c) folder bands.
Refined after the first headless check (this repo opened as 2 folders + 36 externals): files with symbols
close too, auto close counts tree depth over folders and files, externals are not counted in TREE_ROWS.

## Changes (reaper/templates/graph.html only; graph.json, semantic.json, CLI, outputs.py, Graph mode unchanged)
- state.closed (Tree only). standIn(id) = outermost closed folder/file above id. treeLayout hangs stand-ins,
  so a closed one is a leaf row. treeView(V) = drawn sets: hidden inside, folder bundles "d:<from> -> <to>"
  (counts by kind and confidence, Phase 8 bundle look; tooltip names folders by path).
- closable = folders, plus files with symbols outside the file-level view (there double-click expands).
  Labels when closed: "app/ (5)" (files below), "service.py (4)" (symbols); tooltip "..., double-click to open".
- First Tree build: autoClosed() = closable at depth >= d, largest d with <= TREE_ROWS (60) non-external rows,
  computed on the whole tree (not the focus); then the selection is revealed.
- pick()/focusOn reveals (opens the folders and file above the node). fitIds fits hidden nodes as their
  stand-in. Legend counts and status count what Tree draws; status adds ", N closed (double-click to open)".

## Tests
New tests/test_html_tree_overview.py (7), expected values by hand: closed folder (rows, bundles, counts,
look), cross-folder edges, nested folder, auto close budgets, closed file, toggle + reveal + fit with fake vis,
first build. Phase 5/8/9/11 test files unchanged. REAPER_REQUIRE_NODE=1 pytest -q -> 245 passed.

## Checks done (headless Chrome, 0 console messages)
- This repo, first Tree: reaper -> 10 files, tests -> files, fixtures/ (12) closed: "45 closed", 66 nodes.
  Fit with externals unticked: whole repo on one screen, call bundles tests -> reaper files.
- Dark: pick run_groups reopens enrich.py; neighbours in closed files drawn as those files.
- Synthetic 400-module repo: Tree opens as "pkg/ (400)"; opening it gives the Phase 9 file-level tree.

## Known behaviour
Externals are not foldable (untick "external" to hide the column); closed state is not kept across reloads
or in deep links; the auto depth is one depth for the whole tree (one huge folder can close everything).

## Browser checklist (user)
Open .reaper/graph.html (this repo) and the synthetic page
/tmp/claude-1000/-home-keyward-Rajiv-personal-repo-reaper/94798072-2d95-4781-aa48-cec1774b47b0/scratchpad/synth-phase12.html
1. Graph opens exactly as before. Tree: reaper and tests with their files, "cli.py (16)" style labels,
   fixtures/ (12) closed; status ends "45 closed (double-click to open)".
2. Fit, then untick external: the whole repo fits; hover a bundle: "tests/... -> reaper/...: N edges (...)".
3. Double-click cli.py: its symbols appear and the bundles split onto them; again: closed. Double-click
   tests: "tests/ (32)" with bundles into reaper files.
4. Search "run_gr" -> run_groups: enrich.py opens; callers/callees in closed files show as those files.
5. Hops 1-3, filters, legend counts, Clear focus still work; folders stay as you left them.
6. Theme Dark: closed labels readable, bundles visible.
7. Synthetic page: Tree opens as "pkg/ (400)"; double-click -> 400 files; double-click m0.py expands it.
