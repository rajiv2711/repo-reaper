# HANDOFF
Phase 8 (inserted: interactive HTML view) | status: partial | current step: verify (Step 6 of the continue prompt)

## Done this session
- Docs: inserted Phase 8 in AGENTS.md, tree-sitter renumbered to Phase 9 (commit f3105d7).
- Discuss -> 08-CONTEXT.md; research R1-R3 + 08-RESEARCH.md; plan 08-PLAN.md (3 checker rounds, last = pass).
- Execute: plans 08-01..08-06 done, all 6 SUMMARY files say Self-Check: PASSED. reaper/templates/graph.html (package
  data), outputs payload + LOD file_edges + one-pass fill, enrich.view_semantic, cli export reads semantic.json,
  search/panel/hop focus/filters/legend/LLM toggle/architecture tab/deep link. No Rule 4 stop.

## Key decisions (docs/phases/08-html-view/08-CONTEXT.md)
D-01 vis-network 9.1.9 (unpkg) | D-02 export reads semantic.json, LLM layer hideable via one toggle, labelled
LLM-generated/stale | D-03 level of detail (file view + aggregated edges, dblclick expand) | D-04 node/edge objects
only gain fields | D-05 no new Python deps | D-06 exact-version CDN scripts | D-07 no innerHTML | D-08 formats unchanged.
User: no payload ceiling for huge repos (always embed everything).

## Deviations (details in 08-0*-SUMMARY.md)
- test_html_large_graph_shows_files_only replaced by test_html_large_graph_opens_file_level (D-03).
- Canvas click = pick(id, false), no fit (dblclick would miss the file); edge width = log2 clamp (D-03 discretion).
- [Rule 2] cli tolerates a semantic.json that is not a JSON object; root-cause fix in enrich.load_semantic proposed in 08-03-SUMMARY.
- node >= 18 (/usr/bin/node, not in environment.yml) is an optional test-time tool for test_js_*; without it they skip
  with a reason; REAPER_REQUIRE_NODE=1 makes them fail. Not a Python dependency (D-05 holds).

## Exact next step
Step 6: spawn a FRESH verifier (inputs: AGENTS.md Phase 8 entry, 08-CONTEXT.md, 08-PLAN.md must_haves, git diff
HEAD~1 + new files) -> docs/phases/08-html-view/08-VERIFICATION.md; then human UAT checklist (9 items), then Step 7.
## Blockers: none

## Verify
REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q   -> 196 passed
