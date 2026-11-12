# HANDOFF
Phase 10 (optional: more languages) | status: done | ticked in AGENTS.md. All phases in AGENTS.md are now ticked.

## Done this session
- User decisions: official grammars (tree-sitter 0.26.1, tree-sitter-javascript 0.25.0, tree-sitter-typescript
  0.23.2; pyproject dependencies, installed via environment.yml `-e .`), languages JS + TS. tree-sitter-language-pack
  rejected: its 1.x downloads parser binaries at runtime.
- reaper/extract_js.py (same pure contract as extract_py); graph.py dispatch; resolve.py: this/super, JS + test-runner
  globals, alias None, index re-export fallback, rule 2 no-guess for imported non-nodes; TREE.txt JS keywords.
- Fixture tests/fixtures/sample_js; tests/test_extract_js.py (12), tests/test_resolve_js.py (5). Phase 2-9 tests unchanged.
- Docs: docs/phases/10-more-languages/10-PLAN.md, 10-SUMMARY.md (changes vs plan, known limits).
- Read-only check on a 6654-file TS/TSX repo: build 7.4 s; ERROR subtrees skipped instead of dropping 5% of files.

## Exact next step
No unchecked phase left. Ask the user what comes next (ideas: other languages through the same contract,
tsconfig `paths` / workspace packages, a `&view=tree` deep link).

## Open notes
- Known JS limits in 10-SUMMARY.md (dotted package names, tsconfig paths, CommonJS exports, js/py module-name clash).
- On that repo the class-scope fix moved 9 nodes from function to method (same total); not inspected.
- From earlier phases: Tree mode limits (09-SUMMARY.md); deep links always open in Graph; root-cause non-object
  semantic.json in enrich.load_semantic (08-03-SUMMARY proposal).
- node >= 18 is an optional test-time tool for test_js_*; REAPER_REQUIRE_NODE=1 makes them fail instead of skip.

## Blockers: none

## Verify
REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q   -> 230 passed
