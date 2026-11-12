# Phase 11 PLAN: dark mode for graph.html

Goal: graph.html follows the OS dark setting, with a toolbar Theme select (Auto / Light / Dark) kept in
localStorage. Light mode keeps today's look except the two changes the user approved on 2026-11-12:
the Theme select itself, and the external colour fix for both modes.

User decisions (2026-11-12): add the toggle now (not later); fix method #72b7b2 vs external #bab0ac
(CVD dE 1.0) in both modes -> external #79706e (dE 17.7, and >= 3:1 on both surfaces). Method stays,
because tests/test_html_tree.py asserts #72b7b2.

## Changes (reaper/templates/graph.html only; graph.json, semantic.json, CLI and outputs.py unchanged)
1. CSS tokens on :root with today's light values; dark values under
   `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) }` and `:root[data-theme="dark"]`,
   with `color-scheme: dark`. Every hard-coded CSS colour reads a token. Legend inline styles become
   classes. `html div.vis-tooltip` reads tip tokens whose light values equal vis 9.1.9's defaults.
2. JS: `INKS = {light, dark}`. INK is light unless "dark" is saved, or "auto" (the default) and
   matchMedia says dark. Node tests have no matchMedia and no localStorage, so they get light.
   Light INK: label #343434, halo 0 (vis defaults), branch #b0b0b0, noGroup #c7c7c7, GROUP_COLORS,
   folder #eeeeee/#9e9e9e/#222, chosen {node: true, label: true} (= vis default; an object so a switch updates it in place).
   Dark INK: surface #1a1a19, label #f0efec, halo 3 in the surface colour, branch #5f5e5a,
   noGroup #6b6a65, groups with #8c564b->#c49c94, #393b79->#6b6ecf, #843c39->#d6616b and
   #7b4173->#ce6dbd, folder #2c2c2a/#6b6a65/#f0efec, and a selection ring (selected 3 px #ffffff,
   hover 2 px #c3c2b7).
3. INK feeds: the vis node font (Graph and Tree), chosen, Tree folder boxes, the contains/branch
   colour (D.edges contains colour set in the page; BRANCH_EDGES), nodeColor and the group legend swatches.
4. Theme select in #bar (right end). A change, or an OS change while on Auto, calls applyTheme():
   it sets data-theme, writes the positions back to both DataSets, calls setOptions({nodes: {font, chosen}, groups})
   on both networks (the groups option makes vis re-read every node) and updates the contains/branch
   edges, the LLM colours and the legend swatches. Nothing runs at start, so the Phase 8/9 update logs stay as they are.
   Dark inks: text #e8e6e0, muted #c3c2b7, faint #898781, error #ff6b7f, link #7ab4f0, all >= 4.8:1 on #1a1a19.

## Tests (new tests/test_html_theme.py; expected values written by hand first)
- template: dark media block, data-theme rules, color-scheme dark, tooltip rule, legend has no inline style,
  light token values equal the old CSS literals, no innerHTML (existing test).
- js (node): default = light INK and the same light constants as before; matchMedia dark gives dark INK,
  dark contains colour on D.edges, dark noGroup in nodeColor; saved "light" beats the OS setting
  and saved "dark" applies on a light OS; a switch to dark and back on FAKE_VIS restyles both networks
  (setOptions font/chosen/groups, contains colour, LLM colours) and keeps the positions.
- Phase 5/8/9 tests unchanged.

## Verify
REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q; headless Chrome screenshots of this repo light/dark x
Graph/Tree, LLM on/off, selection, tooltip, and a big-repo file view; light Tree before/after pixel diff
(only the toolbar, external diamonds and legend swatch may differ); dataviz validator on the dark palettes.
