# HANDOFF
Phase 3 | status: done

## Done this session
- tests/test_resolve.py written FIRST: every non-contains fixture edge by hand (8 imports, 1 inherits, 12 calls,
  each with confidence), 18 contains, ext nodes, idempotency/order independence, plus 2 mini repos (re-exports,
  star imports, nested scopes, grandparent methods, external-alias stop, AMBIGUOUS, >5 candidates).
- reaper/resolve.py: resolve(nodes, refs) -> (nodes, edges). Drops incoming external nodes and rebuilds them
  (ext:<top>, file/line/signature/doc null), so it is idempotent. Edges deduped per (src, dst, kind) keeping the
  strongest confidence, sorted by (kind, src, dst) -> independent of file order. graph.build() now calls it.
- Rule details beyond the AGENTS.md wording (all documented in the resolve.py docstring):
  super().x -> base method INFERRED, else no edge; self.x not on class/bases -> falls through to rules 2-5;
  aliases follow re-exports (pkg/__init__ `from .core import X`) and `from m import *` (max 5 hops);
  `import a.b` also binds `a`; alias match ignores a trailing "()" (Path().resolve -> pathlib, external);
  rule 5: bare f() matches only top-level functions/classes, dotted x.f() only methods;
  inherits via alias / same-file scope / star import; base outside the repo -> no edge.
- tests/test_graph.py: Phase 2 counts 23 -> 25 nodes (spec-mandated ext:json, ext:os), now also asserts edges.
- Robustness: CPython stdlib, 2936 files -> 129k edges in 4.4s, 0 dangling edges, no duplicate ids.

## Exact next step
Phase 4: write tests/test_update.py FIRST, then graph.update(root) -> {added, changed, deleted, unchanged} and
`reaper update` in cli.py. Keep nodes/refs of unchanged files (match on node["file"] / ref["file"]; external
nodes have file null and are rebuilt by resolve), re-extract added/changed, then nodes, edges = resolve(...).
Hints: missing graph.json -> full build; "identical graph" test should ignore meta.generated_at.

## Blockers: none (AGENTS.md Phase 3 lists "(3) same-file name" twice; treated as one rule)

## Verify
conda run -n repo-reaper pytest -q     -> 50 passed
conda run -n repo-reaper reaper map .  -> 25 files, 144 nodes, 475 refs, 294 edges -> .reaper/graph.json
