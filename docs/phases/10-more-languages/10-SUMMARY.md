# Phase 10 summary: JavaScript + TypeScript

Status: done. `REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q` -> 230 passed (213 before + 17 new).

## Changes
- New dependency (user choice): tree-sitter 0.26.1, tree-sitter-javascript 0.25.0, tree-sitter-typescript 0.23.2
  (pyproject `dependencies`; environment.yml installs them through `-e .`). Not tree-sitter-language-pack:
  its 1.x downloads parser binaries at runtime.
- reaper/extract_js.py: same contract as extract_py (contract in its docstring). graph.extract_file dispatches
  javascript/typescript files to it. graph.json format and CLI unchanged.
- reaper/resolve.py: rule 1 accepts this.x / super.x; rule 4 uses JS globals + test-runner globals for JS/TS
  files; import refs with alias None bind no name; an exact module hit also tries the parent module's name
  (index.ts re-exports); rule 2: a bare imported repo name that is no class/function -> no edge (was a rule-5 guess).
- reaper/outputs.py: TREE.txt uses "class" / "interface" / "function" / bare method lines for JS/TS files.
  Python lines unchanged.

## Changed while executing (vs 10-PLAN)
- Parse errors: a read-only build of a 6654-file TS/TSX repo had 355 files (5%) with tree-sitter ERROR nodes,
  the 6 sampled at valid code the grammar misreads (`export type * from`, styled-component generics in context).
  Whole-file drop lost their symbols, so
  ERROR subtrees are skipped and the rest is extracted; a file that does not parse at all keeps its file node only.
- Bare "src/..." specifiers are repo paths (module names already drop "src."): 1964 imports moved from ext:src
  to repo files on that repo.
- Rule 2 no-guess + test globals: AMBIGUOUS calls on that repo 17573 -> 11663; INFERRED 5598 -> 4838.
  Python fixture edges unchanged.
- Methods and class fields become nodes only inside a class node (anonymous `module.exports = class {..}`
  methods were wrongly top-level functions; found via a broken-code test).

## Tests
- tests/fixtures/sample_js/src: 7 files (models.ts, utils.js, repository.js, service.ts, app.jsx,
  components/UserCard.tsx, components/index.ts).
- tests/test_extract_js.py (12): module names, node counts/ids/details, import/call/inherit refs, more forms,
  parse error, ERROR subtree skipped, anonymous class methods, "src/" specifier.
- tests/test_resolve_js.py (5): all 35 non-contains fixture edges with confidence, update no-change, packages +
  globals, imported value / test globals give no guess, TREE.txt keywords.

## Known limits
- Package names with dots (chart.js) give ext:chart; tsconfig `paths` aliases other than "src/" stay external;
  workspace packages (@scope/pkg in a monorepo) are external.
- A JS file and a Python file with the same module name (app/util.js, app/util.py): the smaller path wins.
- `import {X} from "./dir"` draws its imports edge to dir/X.ts when that file exists (longest module prefix).
- CommonJS `module.exports = ...` is not modelled; named imports of such files resolve only when the name is a node.
