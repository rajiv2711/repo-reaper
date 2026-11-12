# Phase 13 SUMMARY: UI/UX polish of graph.html

Status: verified (2026-11-12): the user confirmed the browser checklist below (item 1 rechecked after the toolbar restyle), all pass. Phase 13 ticked.

## User decision (2026-11-12)
All 4 proposed items: toolbar + status, compact LLM groups, details panel + keys, calmer Tree edges.

## Changes (reaper/templates/graph.html only; graph.json, semantic.json, CLI, outputs.py unchanged)
- Toolbar: buttons, select and tabs styled from the Phase 11 tokens (no new tokens): 28 px rounded buttons
  with a light shadow and hover; [Graph|Tree] and [Hops 1 2 3] as trays (--chip) whose active choice is a
  #4c78a8 pill (user's follow-up: "a bit more aesthetic"); focus ring (:focus-visible, --link). Re-layout hidden in Tree, where nodes
  can no longer be dragged (dragNodes false), so nothing needs putting back. Status on one row (ellipsis,
  full text as tooltip); the file-level note is a "file-level view" tag with the note as tooltip.
- LLM groups: one row per group (<details>, name with ellipsis + tooltip, stale, file count); click opens it.
- Details panel: signature, ids, file:line and relation links in monospace; node name as a larger title.
  Empty panel: 10 most-connected nodes (outputs.degrees: externals have none), clickable, and a key list.
- Keys: "/" search, g Graph, t Tree, f Fit (not in a field, not with Ctrl/Alt/Meta), Esc as before;
  Up/Down/Enter in the search box (highlighted row). Button tooltips name their keys.
- Tree edges: relations and bundles stored calm (1 px, 0.3 x their opacity, dashes kept); a hovered or
  selected node's edges get their own width / opacity back (vis chosen.edge). Graph mode unchanged.

## Tests
New tests/test_html_polish.py (8), expected values by hand. Phase 5/8/9/11/12 test files unchanged (the
Graph button's markup is pinned by Phase 9, so its tooltip is set in initModes).
REAPER_REQUIRE_NODE=1 pytest -q -> 253 passed.

## Checks done (headless Chrome 1600x1000, light + dark, 0 console messages in every run)
This repo: Graph (home panel, compact groups, one opened), Tree (calm edges, readable labels), Tree with
run_groups picked (its edges full strength), search "run_" with Down x2 (row 3 highlighted).
Synthetic 400-module repo: Graph (one-row toolbar, tag), Tree via "t", pkg/ opened, m5.py picked.

## Known / not changed
Long search result names still run past the sidebar edge (Phase 8). The synthetic Tree still opens as
"pkg/ (400)" with "0 nodes" in the status (Phase 12). Clear focus keeps the last node in the panel.

## Browser checklist (user)
Open .reaper/graph.html (this repo) and
/tmp/claude-1000/-home-keyward-Rajiv-personal-repo-reaper/c689fbb5-f2fe-4e4d-85b2-0dc21ea98b6c/scratchpad/synth-phase13.html
1. Toolbar: rounded buttons of one family in light and dark (Theme select); Graph|Tree and Hops are trays
   with the active choice as a blue pill; Tab moves a visible focus ring; Re-layout only shows in Graph.
2. Synthetic page: toolbar is one row; "file-level view" tag shows the full note on hover.
3. Sidebar: each LLM group is one row (long names end in "..."); clicking a row opens / closes its summary.
4. Right panel before any pick: "Most connected" list (click one -> it is picked) and the key list.
5. Pick a function: signature, id and file:line in monospace; relation links still pick.
6. Keys: "/" jumps to search; type "run_", Down/Up move the highlight, Enter picks it; g / t switch modes,
   f fits; keys do nothing while typing in the search box (except Esc and the arrows / Enter there).
7. Tree (this repo): relation edges are thin and faint; hovering a file or symbol shows its edges in full
   colour and width; a selected node keeps them full. Tree nodes cannot be dragged (drag pans).
8. Graph mode looks and behaves as before (layout, colours, double-click expand in the file-level view).
