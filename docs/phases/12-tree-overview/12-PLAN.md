# Phase 12 PLAN: Tree overview (collapsible folders)

User decision (2026-11-12): option (a) collapsible folders, over (b) zoom-driven detail and (c) folder
bands. Goal: in Tree mode a reader relates every import/call/inherit to the folder tree at any zoom.

## Scope (reaper/templates/graph.html only; graph.json, semantic.json, CLI, outputs.py, Graph mode unchanged)
- state.closed = set of page-only folder ids ("dir:<path>/") closed in Tree. Graph mode ignores it.
- standIn(id): the outermost closed folder above id, else id. treeLayout(V) hangs a node's stand-in, so
  a closed folder is a leaf row; branches into it stay, branches inside it go.
- treeView(V) (pure): the drawn sets. Nodes inside a closed folder are not drawn. An edge or file-level
  bundle whose two ends fall in the same closed folder is hidden; one with a closed folder at either
  end joins a page-only folder bundle "d:<from> -> <to>" with counts by kind and confidence, drawn and
  styled like a Phase 8 file-level bundle (width = count, colour = kind, dashes = confidence).
- Closed folder label "name/ (N)" (N = files below it in the graph); tooltip says double-click to open.
- Refined after the first browser check (this repo opened as 2 folders + 36 externals): files with
  symbols close too (label "name (N symbols)"; not in the file-level view, where double-click expands),
  auto close counts tree depth over folders and files, and externals are not counted in TREE_ROWS.
- Double-click a folder in Tree: close / open it (focus kept). Files keep the Phase 8 double-click.
- First Tree build: autoClosed(V) closes every folder at depth >= d for the largest d whose tree has at
  most TREE_ROWS = 60 rows (top-level folders are depth 0; nothing fits -> all folders closed). The
  fixture (26 rows) opens fully expanded, exactly as in Phase 9.
- pick() (search, panel links, architecture chips, deep link, click) opens the folders on the way to
  the picked node (reveal). Fit and pick fit a node inside a closed folder as that folder.
- Legend counts and the status line count what Tree draws: folder bundles add their edges like file
  bundles; nodes inside closed folders are not counted (folders never are, as in Phase 9).

## Tests first (tests/test_html_tree_overview.py, expected values by hand from tests/fixtures/sample_py)
1. Fixture, "dir:app/" closed: rows dir:app/ (0,0), ext:json (0,2), ext:os (0,3); no branches; bundles
   app/ -> ext:json imports EXTRACTED 1 and app/ -> ext:os imports EXTRACTED 2; everything else hidden.
2. NEST repo, "dir:pkg/sub/" closed: sub/ is a leaf at (1,1), files below move up two rows,
   b:pkg/sub/a.py gone. autoClosed: budget 14 -> none, 13/12 -> {pkg/sub/}, 11 or less -> all three.
3. Fake-vis modes: fixture Tree opens with nothing closed (Phase 9 rows); double-click dir:app/ closes
   it (label "app/ (5)", bundle edges shown, legend lines 2), again opens it (Phase 9 rows back); pick
   reveals; Fit with a focus inside a closed folder fits the folder; Graph view unchanged meanwhile.
4. Phase 5/8/9/11 tests unchanged.

## Check
pytest; headless Chrome on this repo and the 400-module synthetic repo (Tree Fit view, light + dark);
user browser checklist in 12-SUMMARY.md.
