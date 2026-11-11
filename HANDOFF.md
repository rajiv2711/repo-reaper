# HANDOFF
Phase 7 | status: done

## Done this session
- Tests first (tests/test_enrich_groups.py, 27, mocked llm.chat): hand-computed Louvain groups (fixture = 1 group by
  modularity; MINI repo = a/, b/, c/), 12k cap, cache, id shift, --limit, dry-run, failures, NotReady, evidence drop, CLI.
- enrich.communities(graph): Louvain (seed 42) on the file graph (cross-file imports/inherits/calls, weight = count).
  CHOICE beyond spec: files with no cross-file edge join the Louvain group holding most files of their directory; if
  none, isolated files of one directory form a group. Avoids one 30b call per empty __init__.py. Ids g1.. largest first.
- run_groups: input = member paths [role]: summary, most-connected first, cut at 12000 chars -> {name, summary<=3
  sentences}. Cache found by input_sha (survives id shifts); groups section rebuilt (gone groups dropped).
- run_architecture: input = group blocks + cross-group edge counts + top 15 nodes -> {overview, patterns, decisions}.
  Needs a fresh answer for every current group (else NotReady -> exit 1). Evidence: backticks stripped, unknown ids
  dropped -> architecture.dropped_evidence. Writes .reaper/ARCHITECTURE.md ("LLM-generated" banner, groups, edges).
- cli: enrich dispatches files/groups/architecture. Replaced test_cli_later_passes_not_ready (Phase 6 placeholder).
- 6 mutation checks (evidence kept, no cache, no cap, singletons, stale ignored, no 3-sentence cut) all caught.
- Manual run on this repo: files 24 calls 2m10s; groups 6 calls 21s; architecture 1 call 10s, 0 ids dropped; re-runs 0 calls.

## Exact next step
Phase 8: Interactive HTML view (GSD-style, docs/phases/08-html-view/). Phase 9 (optional) = tree-sitter.
## Blockers: none
Proposals only: rank tests last in --limit; resolve misses fixture imports when repo is not the fixture root (utils.py isolated here).

## Verify
conda run -n repo-reaper pytest -q                                      -> 140 passed
conda run -n repo-reaper reaper enrich . --pass architecture --dry-run  -> 0 calls (1 cached) after the manual run
