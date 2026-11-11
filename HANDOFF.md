# HANDOFF
Phase 8 (interactive HTML view) | status: done | ticked in AGENTS.md

## Done this session
- Verify step: fresh verifier wrote docs/phases/08-html-view/08-VERIFICATION.md (status: passed, 18/18 truths,
  no D-xx violated; Phase 5 html tests unchanged except the logged D-03 replacement).
- Closed verifier gaps (tests written first, seen failing):
  G1 cli._view_semantic: unreadable semantic.json (OSError) -> warning + structural page, not a traceback.
  G2 enrich.group_input: non-string summary -> "(no summary yet)", not a TypeError (well-formed text/cache keys unchanged).
  Tests: test_export_unreadable_semantic_warns, test_export_non_string_summary_does_not_crash.
- Headless Chrome pre-check (no console errors on 4 pages; CDN fallback + both-blocked error message seen).
- User ran the 9-item browser checklist: "all pass" (incl. log2 bundle width for D-03).

## Exact next step
Phase 9 (optional): more languages via tree-sitter-language-pack, same extract contract. It needs a new
dependency, so first propose it in HANDOFF.md (AGENTS.md Stack rule), then start its discuss step.

## Open notes (not defects; contract behaviour, see 08-VERIFICATION.md Notes)
- After "Collapse all" the selected symbol stays drawn alone; hop BFS walks through hidden node kinds.
- node >= 18 (/usr/bin/node, not in environment.yml) is an optional test-time tool for test_js_*; without it they
  skip with a reason; REAPER_REQUIRE_NODE=1 makes them fail. Not a Python dependency (D-05 holds).
- Proposal from 08-03-SUMMARY still open: root-cause non-object semantic.json in enrich.load_semantic.

## Blockers: none

## Verify
REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q   -> 198 passed
