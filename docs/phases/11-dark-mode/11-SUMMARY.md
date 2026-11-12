# Phase 11 SUMMARY: dark mode for graph.html

Status: built and tested; waiting for the user's browser checklist (below) before the tick.

## User decisions (2026-11-12)
- Theme select now (Auto / Light / Dark, localStorage key "reaper-theme"), not later.
- External colour #bab0ac -> #79706e in both modes (method #72b7b2 vs external: CVD dE 1.0 -> 17.7).
- Phase 8 test test_template_physics_never_back_on changed as approved: the one theme
  setOptions({...look, groups}) is allowed and must not mention physics.

## Changes (reaper/templates/graph.html only; graph.json, semantic.json, CLI, outputs.py unchanged)
- CSS tokens on :root (light = the old literals) + dark blocks (@media prefers dark unless
  data-theme="light", and data-theme="dark"), color-scheme: dark, vis tooltip rule, legend classes.
- JS INKS {light, dark} -> vis node font (label ink + halo), chosen (dark: white ring 3 px, hover 2 px),
  Tree folder boxes, contains/branch colour, LLM group colours (4 dark variants), no-group grey, swatches.
- applyTheme() restyles live: positions written back, setOptions on both networks, edge/node updates.
- Changed vs plan: light chosen is {node: true, label: true}, not true. vis copies a node's object options
  when it creates the node, so after dark -> light the dark ring stayed (seen in a pixel diff); an object is
  updated in place. Same look as true.

## Tests
New tests/test_html_theme.py (8): tokens, select and legend hooks, CSS = JS kind colours, light default
in node, OS dark, saved choice beats OS, live switch on both networks, nothing extra at start.
REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q -> 238 passed.

## Checks done (headless Chrome, this repo + a synthetic 400-module repo)
- Light Tree, with and without a selection: canvas pixel-identical to commit 48661d1; only the Theme select
  and the external legend swatch differ. (Graph layout is random per run, so it is not pixel-diffable; its
  light options equal vis defaults.)
- Switch dark -> light and light -> dark: pixel-identical to a page opened in that theme; positions kept.
- dataviz validator, dark surface #1a1a19: 14 group colours and 5 kind colours all >= 3:1 (no 14-colour set
  passes the all-pairs CVD checks, as expected). Text inks >= 4.8:1; branch lines 2.68:1 on purpose.

## Browser checklist (user)
Open .reaper/graph.html (this repo) and the synthetic page
/tmp/claude-1000/-home-keyward-Rajiv-personal-repo-reaper/60779f51-465c-4141-86b1-87a354d71865/scratchpad/synth.html
1. OS light, Theme Auto: looks as before; Theme select at the top right; externals darker grey.
2. Theme Dark (or OS dark): Graph and Tree readable; labels light with a dark halo; folder boxes dark.
3. Search "run_gr", pick run_groups: white ring; panel, badges, stale badge and LLM block readable.
4. Hover a node and an edge: dark tooltip.
5. Untick and tick LLM layer in dark: kind colours <-> group colours; group swatches follow.
6. Switch Light / Dark / Auto: camera, focus and positions stay; reload keeps the choice.
7. Synthetic page in dark: Graph file-level view, Tree, double-click a file to expand.
