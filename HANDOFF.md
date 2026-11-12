# HANDOFF
Phase 11 (dark mode for graph.html) | status: partial (built and tested; waiting for the user's browser checklist)

## Done this session
- AGENTS.md: Phases 11-13 added (commit efd043f).
- User decisions: Theme select now (Auto / Light / Dark, localStorage "reaper-theme"); external #bab0ac ->
  #79706e in both modes (CVD vs method); Phase 8 test test_template_physics_never_back_on changed (approved)
  to allow the one theme setOptions({...look, groups}).
- reaper/templates/graph.html only: CSS tokens + dark blocks, legend classes, vis tooltip rule; INKS (label
  halo, white selection ring, dark folders, quiet branches, 4 dark group colours); applyTheme() restyles live.
- tests/test_html_theme.py (8 tests). Docs: docs/phases/11-dark-mode/11-PLAN.md, 11-SUMMARY.md.
- Headless Chrome: light Tree canvas pixel-identical to 48661d1 (only the select and external swatch differ);
  dark <-> light switch pixel-identical to a page opened in that theme; positions kept.

## Exact next step
Get the user's answer on the 7-item browser checklist in 11-SUMMARY.md. All pass -> tick Phase 11 in
AGENTS.md, set 11-SUMMARY status to verified, commit "Phase 11: ...". A failed item -> fix in Phase 11.
Then Phase 12: ask the semantic-zoom decision (a/b/c) before building.

## Open notes
- Screenshots: headless Chrome here reports dark; force light with --blink-settings=preferredColorScheme=1
  (dark =0); one --user-data-dir per parallel run. Graph layout is random per run (no pixel diffs).
- Mixed-kind bundles keep #888 in dark (4.9:1, louder than imports 3.8:1); revisit in Phase 12 if noisy.
- Not in Phases 11-13: monorepo workspace packages resolve as external; Phase 10 limits (dotted package
  names, tsconfig paths other than "src/", CommonJS exports).
- Earlier: Tree mode limits (09-SUMMARY), deep links open in Graph, enrich.load_semantic non-object (08-03).

## Blockers: none

## Verify
REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q   -> 238 passed
