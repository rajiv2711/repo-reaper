# HANDOFF
Phase 4 | status: done

## Done this session
- tests/test_update.py written FIRST (7 tests): mutation = edit app/utils.py (drop `import os` + data_dir, add
  slugify), delete app/repository.py, add app/store.py. Hand-written: changes dict, node/ref/edge counts, every
  non-contains edge after the mutation (MUTATED_EDGES), which files get re-extracted (spy on extract_file).
- reaper/graph.py: update(root) -> (graph, changes); changes = {added, changed, deleted, unchanged}, sorted path
  lists. build() and update() share _assemble(root, previous): unchanged sha256 -> reuse old nodes/refs (grouped
  by "file"; ext nodes rebuilt by resolve), else re-extract; then resolve(). Same file order as build, so
  update == full build except meta.generated_at (tested). No graph.json or other meta.version -> full build.
  update() does not save; the caller does (like build).
- reaper/cli.py: `reaper update <repo>` prints "1 added, 1 changed, 1 deleted, 4 unchanged" + totals line.
- Mutation check: making update ignore sha256 fails 4 of the 7 tests.
- Real repo: CPython stdlib copy (2936 files): map 6.6s, no-change update 3.6s; edit+delete+add -> update ==
  full build.

## Exact next step
Phase 5: write tests first for TREE.txt, SUMMARY.md, graph.html, `reaper query` on the fixture, then
reaper/outputs.py + `reaper export` / `reaper query` in cli.py.

## Blockers: none
Note: an import of a deleted module resolves to its longest existing prefix (`from .repository import X`
-> app/__init__.py) per the Phase 3 rule; kept as-is, asserted in test_update.py.

## Verify
conda run -n repo-reaper pytest -q        -> 57 passed
conda run -n repo-reaper reaper update .  -> 0 added, 0 changed, 0 deleted, 26 unchanged (161 nodes, 353 edges)
