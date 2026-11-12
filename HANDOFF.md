# HANDOFF
Phase 12 (Tree overview) | status: partial (built and tested; waiting for the user's browser checklist)

## Done this session
- Phase 11 closed: the user's tick and verified summary committed (fbaa0be).
- Phase 12 decision: (a) collapsible folders (over (b) zoom-driven, (c) folder bands); refined so files
  with symbols close too and externals do not count in the auto-close budget (12-PLAN.md).
- reaper/templates/graph.html only: state.closed, standIn, treeView (folder bundles "d:<from> -> <to>"),
  closable, toggleClosed (double-click), autoClosed (TREE_ROWS 60), reveal on pick, fitIds via stand-ins,
  closed labels/tooltips, status ", N closed". Graph mode, graph.json, semantic.json, CLI unchanged.
- tests/test_html_tree_overview.py (7 new). Docs: docs/phases/12-tree-overview/12-PLAN.md, 12-SUMMARY.md.
- Headless Chrome, 0 console messages: this repo opens as folders -> files (45 closed); dark pick reveals;
  synthetic repo opens as "pkg/ (400)".

## Exact next step
Get the user's answer on the 7-item browser checklist in 12-SUMMARY.md. All pass -> tick Phase 12 in
AGENTS.md, set 12-SUMMARY status to verified, commit "Phase 12: ...". A failed item -> fix in Phase 12.
Then Phase 13 (UI/UX polish): ask the user what to polish before planning.

## Open notes
- Screenshots: force light/dark with --blink-settings=preferredColorScheme=1/0; one --user-data-dir per run.
  Helpers (shot.py, build_pages.py, synth.py) are in this session's scratchpad (see 12-SUMMARY path).
- Phase 12 limits: externals not foldable; closed state not kept on reload or in deep links; one auto
  depth for the whole tree. Mixed-kind bundles keep #888 in dark (from Phase 11).
- Not in Phases 12-13: monorepo workspace packages resolve as external; Phase 10 limits.

## Blockers: none

## Verify
REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q   -> 245 passed
