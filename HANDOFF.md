# HANDOFF
Phase 2 | status: done

## Done this session
- tests/test_extract_py.py written FIRST (expected values by hand from the fixture), then reaper/extract_py.py:
  module_name(path) per spec (+ drops .pyi); extract(path, source: str|bytes, module) -> (nodes, refs), pure.
- Nodes: file node (name = module, signature None, doc = module docstring line 1) + class/function/method, nested
  ones too ("a.py::A.run.helper"). Class signature "User(Entity)"; function "__init__(self, repo=None)", "async "
  prefix, " -> T" return. Duplicate qualname (property + setter): first wins. Absent doc/signature/alias = null.
- Refs: src = innermost enclosing class/function id, else file id. import alias = the text that refers to target
  (`import a.b` -> alias "a.b"; `from a import *` -> target "a", alias "*"); __future__ imports skipped.
  call target = dotted text ("self.repo.save", "super().__init__", "name.strip().lower"); nameless callees skipped.
  Decorators/defaults/annotations belong to the enclosing scope. inherit: Generic[T] -> "Generic", metaclass= ignored.
  Syntax error / null bytes -> file node only.
- reaper/graph.py: graph_path, new_graph (meta {version: 1, generated_at}), extract_file (dispatch by lang), build,
  save (atomic), load. `files` holds ALL discovered files; only python files get nodes (README.md: none).
- `reaper map <repo>` in cli.py. Fixture totals: nodes file 5/class 4/method 10/function 4; refs import 9/call 25/inherit 1.
- Robustness: build() on the whole CPython stdlib (2936 files) in 3.7s, no crash, no duplicate ids.

## Exact next step
Phase 3: write tests/test_resolve.py FIRST listing every expected non-contains fixture edge + confidence, then
reaper/resolve.py resolve(nodes, refs) -> edges, and replace the `edges=[]` TODO in graph.build() with it.
Hints: per-file aliases = import refs grouped by ref["file"]; "super().x" calls -> base-class method;
external nodes (ext:<top package>) are created by resolve.

## Blockers: none (note: AGENTS.md Phase 3 lists rule "(3) same-file name" twice; treat as one rule)

## Verify
conda run -n repo-reaper pytest -q                -> 44 passed
conda run -n repo-reaper reaper map .             -> 23 files, 100 nodes, 341 refs, 0 edges -> .reaper/graph.json
