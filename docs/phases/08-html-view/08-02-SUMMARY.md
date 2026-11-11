# 08-02 SUMMARY: enrich.view_semantic

Plan 08-02 (wave 1) | status: done | VIEW-05, D-02, D-08

## Built
- `enrich.file_input(graph, root, path, _kids=None)` (Q5): `_kids` is passed to
  `outputs.file_outline(..., _kids=_kids)`, so a caller building many inputs makes the contains index once.
  Output is identical either way; all existing enrich tests pass unchanged.
- `enrich.view_semantic(root, graph) -> dict | None`: the `sem` object of the Embedded-JSON contract.
  - None iff `.reaper/semantic.json` does not exist; otherwise `load_semantic` (JSONDecodeError propagates).
  - files: `{path: {summary, role, model, stale}}` only for paths that are file nodes now; input_sha not
    shipped; stale = `input_sha != cache_key(model, file_input(graph, root, path, kids))`, OSError -> stale.
    `outputs._children(graph)` is built once per call.
  - groups: `{gid: {name, summary, members, model, stale}}`; members = stored members that are file nodes
    now, order kept; stale = `gid not in plan or not _fresh(entry, members, text)` with
    `plan = {gid: (members, text) for gid, members, _, text in _group_plan(graph, sem)}`.
  - architecture: None when the stored section is empty, else `{overview, patterns, decisions, model,
    stale, dropped}`; patterns/decisions via `_clean_items` against current node ids; dropped =
    sorted(stored dropped_evidence + newly dropped); stale via `arch_input` + `ARCH_PROMPT_VERSION`,
    NotReady -> stale.
  - Missing keys -> None (overview -> "", lists -> []). Reads only, never writes a file (tests compare a
    path+mtime snapshot of the repo before/after). LLM text is passed through raw; escaping stays in
    outputs/template (VIEW-07).
- reaper/outputs.py does not import enrich (no change there; cli 08-03 passes the dict in).

## Files
- modified: reaper/enrich.py (file_input `_kids`; new section "view (graph.html)": `_dict`, `view_semantic`,
  `_view_architecture`)
- created: tests/test_view_semantic.py (10 tests)
- created: docs/phases/08-html-view/08-02-SUMMARY.md

## Tests (all written first, seen failing, then implemented)
08-02-1: test_file_input_kids_same_output, test_view_semantic_absent_is_none,
test_view_semantic_files_staleness, test_view_semantic_missing_source_is_stale,
test_view_semantic_builds_children_once.
08-02-2: test_view_semantic_groups_staleness (hand values g1 = [__init__, models, repository, service, utils],
fresh; g2 members [] stale; changing models.py's summary makes g1 stale).
08-02-3: test_view_semantic_architecture, test_view_semantic_partial_entries,
test_view_semantic_empty_architecture_is_null (passed at once by design while architecture was still a
None stub: regression guard for the empty-section case), test_view_semantic_malformed_entries (Rule 2).

## Decisions honoured
D-02 (no CLI change; sem built in enrich, handed over as a plain dict), D-05 (no new dependency),
D-08 (graph.json/semantic.json formats unchanged; view_semantic only reads).

## Deviations
- [Rule 2] Malformed semantic.json entries (hand edits): a non-dict file/group/architecture entry, non-list
  members/dropped_evidence, non-str overview read as missing keys (None / [] / "", stale True) instead of
  crashing; the group/architecture inputs see only dict entries. Covered by
  test_view_semantic_malformed_entries.
- [Rule 2] `arch_input` can raise KeyError when a current group entry has a matching input_sha but no
  name/summary (hand edit); caught with NotReady -> architecture stale True.
- None of Rule 4 (no format, CLI or dependency change).

## Notes
- Shared tree: during the run, the full suite twice showed failures only in 08-01's files
  (tests/test_html_data.py, tests/test_outputs.py::test_html_large_graph_opens_file_level) plus one
  transient collection error while outputs.py was mid-edit; not touched here. My files and the
  enrich/cli suites stayed green (`pytest -q tests/test_view_semantic.py tests/test_enrich.py
  tests/test_enrich_groups.py tests/test_cli.py` -> 59 passed).

## Verify
`conda run -n repo-reaper pytest -q tests/test_view_semantic.py` -> 10 passed
`conda run -n repo-reaper pytest -q` -> 164 passed in 1.78s

Self-Check: PASSED (all listed files exist; full suite 164 passed)
