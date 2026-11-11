# 08-03 cli wiring - SUMMARY

Plan 08-03 of Phase 8 (interactive HTML view), wave 2. Status: done.

## Built
- `reaper export` now reads `.reaper/semantic.json` when it exists and passes the semantic layer to
  graph.html: `cmd_export` calls the new `cli._view_semantic(repo, graph)` and then
  `outputs.export(args.repo, graph, sem)`.
- `_view_semantic` returns `enrich.view_semantic(repo, graph)` (None when semantic.json does not exist).
  When the file cannot be read it prints a warning to stderr, returns None, and export still writes the
  structural page (exit 0):
  - invalid JSON (ValueError): `warning: <path>/semantic.json is not valid JSON (<err>); graph.html has no semantic layer`
    (the exact text the plan pins)
  - valid JSON that is not an object: `warning: <path>/semantic.json is not a JSON object; graph.html has no semantic layer`
- Without semantic.json, graph.html is byte-identical to `outputs.graph_html(graph)` (structural view, `sem` null).
  TREE.txt and SUMMARY.md never depend on semantic.json. Export never rewrites graph.json or semantic.json.

## Files
- Modified: reaper/cli.py (new `_view_semantic`, `cmd_export` passes `sem`)
- Created: tests/test_export_semantic.py (6 tests), docs/phases/08-html-view/08-03-SUMMARY.md

## Tests added (tests/test_export_semantic.py)
- 08-03-1: test_export_without_semantic_is_byte_identical (passed before the change: the default is
  already sem=None), test_export_with_semantic_embeds_view, test_export_corrupt_semantic_warns
  (both failed first, then passed), test_export_non_object_semantic_warns ([Rule 2], failed first, then passed).
- 08-03-2 (regression guards, passed at once by design): test_export_leaves_inputs_untouched,
  test_export_tree_summary_unchanged_by_semantic.

## Decisions honoured
- D-02: no CLI option or parser change; the semantic layer reaches graph.html only, as a plain dict built in
  enrich and passed in by cli (outputs still never imports enrich).
- D-05: no new dependency. D-07: LLM text is passed as data only; the test checks that `<b>x</b>` never
  appears raw in the html and that no node title holds summary text.
- D-08: graph.json and semantic.json are only read, never written (byte-identical regression guard).

## Deviations
- [Rule 2] Now that export reads semantic.json, a file holding valid JSON that is not an object (`[]`,
  `null`) crashed `reaper export` with an AttributeError from `enrich.load_semantic` (`sem.setdefault`).
  Handled in cli.py (my file): catch AttributeError, warn "is not a JSON object", export the structural page.
  Test: test_export_non_object_semantic_warns. Root cause stays in enrich.load_semantic (not this plan's
  file). Suggested follow-up there, for `enrich` too: raise ValueError when the loaded JSON is not a dict.
  Before: `sem = json.loads(...) if path.exists() else {}`
  After:  same, plus `if not isinstance(sem, dict): raise ValueError(f"{path} is not a JSON object")`.

## Result
- `conda run -n repo-reaper pytest -q` -> 170 passed
- Self-Check: PASSED (reaper/cli.py, tests/test_export_semantic.py and this file exist; the full suite passes)
