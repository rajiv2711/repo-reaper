# HANDOFF
Phase 9 (Tree mode) | status: done | ticked in AGENTS.md (user browser checklist 1-8: all pass)

## Done this session
- First attempt (tree layout replacing Graph) dropped at the user's request: main reset to 21ba424, old Phase 9
  tag deleted; one clean main branch. Not pushed.
- graph.html: Graph | Tree toggle buttons. Graph = Phase 8 network, default, unchanged except one user-approved bug
  fix (LLM group colours were lost on the first refresh; llmColour(id) now sent with every position update).
  Tree = second vis network (physics off, treeLayout positions, page-only folders, branch vs relation curves),
  sharing selection, search, panel, hop focus, filters, LLM layer, Collapse all and deep links.
- Tests: 15 new in tests/test_html_tree.py; Phase 5/8 test files unchanged. Docs: docs/phases/09-tree-mode/
  09-PLAN.md, 09-SUMMARY.md.

## Exact next step
Phase 10 (optional): more languages via tree-sitter-language-pack, same extract contract. It needs a new
dependency, so first propose it in HANDOFF.md (AGENTS.md Stack rule), then plan it.

## Open notes
- Deep links (#node=<id>&hops=N) always open in Graph; possible follow-up: &view=tree.
- Known Tree behaviour (09-SUMMARY.md): folders not in legend counts; hop focus hangs a symbol with a hidden file
  under its folder; long relation curves bulge in Fit view; plain A-Z file order.
- node >= 18 (/usr/bin/node) is an optional test-time tool for test_js_*; REAPER_REQUIRE_NODE=1 makes them fail
  instead of skip. Not a Python dependency.
- Proposal from 08-03-SUMMARY still open: root-cause non-object semantic.json in enrich.load_semantic.

## Blockers: none

## Verify
REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q   -> 213 passed
