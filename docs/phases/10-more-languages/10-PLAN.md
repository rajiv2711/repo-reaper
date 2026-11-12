# Phase 10 plan: JavaScript + TypeScript extraction

Decisions (user, 2026-11-11): official grammars `tree-sitter` + `tree-sitter-javascript` + `tree-sitter-typescript`
(bundled wheels, offline), not tree-sitter-language-pack (1.x downloads parser binaries at runtime). Languages: JS + TS.

## Contract (same as extract_py: pure, one file in, nodes + raw refs out)
- `reaper/extract_js.py`: `module_name(path)`, `extract(path, source, module)`. Grammar by extension:
  .ts -> typescript, .tsx -> tsx, .js .jsx .mjs .cjs -> javascript. Parse error -> file node only
  (changed while executing: ERROR subtrees are skipped, the rest is extracted; see 10-SUMMARY).
- Module name: drop extension (.d.ts too), "/" -> ".", drop trailing ".index", drop leading "src.".
- Nodes: class (class, abstract class, `const X = class`, TS interface), function (function declaration,
  `const f = () => {}` / `= function`), method (class methods, arrow-function class fields); nested like Python.
  Signature "name(params): Ret" (async prefix), class "User extends Entity implements Named",
  interface "interface Named"; doc = first line of the `/** */` comment directly above; file doc = leading `/** */`.
- Refs, written in the resolver's dotted form:
  import  `import d from './m'` -> m.default/d; `{a as b}` -> m.a/b; `* as ns` -> m/ns; `import './m'` -> m/None;
          `export {a} from`, `export * from` (alias *), `require('m')` (declarator binds alias), `import('m')`;
          `export default foo` / `export {a as b}` -> self-alias ref (target <own module>.foo, alias default|b),
          so the resolver's re-export chase finds default and renamed exports. Asset imports (.css, .svg, ...) skipped.
          Relative paths become dotted repo module names; packages: 'react-dom/client' -> react-dom.client,
          '@scope/pkg/x' -> @scope/pkg.x.
  call    call/new/JSX-component (<Button/>; lowercase tags skipped) text: "this.save", "utils.clean",
          "super.constructor" for super(...), "Admin().x"; results-of-calls and subscripts give no ref.
  inherit extends + implements (classes), extends (interfaces).
- graph.extract_file dispatches javascript/typescript to extract_js. graph.json format and CLI unchanged.

## Resolver (small, language-neutral where possible)
- Rule 1 also accepts `this.x` and `super.x`.
- Rule 4 uses JS globals (console, JSON, Map, Error, ...) for .js/.jsx/.mjs/.cjs/.ts/.tsx files.
- Import refs with alias None bind no name.
- symbol(): an exact module hit (no rest) also tries the parent module's name (JS index re-exports:
  `import {UserCard} from './components'` -> components/index.ts -> ./UserCard default).

## Tests (expected values by hand from the fixture, before coding)
- tests/fixtures/sample_js/src: models.ts, utils.js, repository.js, service.ts, components/{UserCard.tsx,index.ts},
  app.jsx (base/sub class, interface, default/named/namespace/require imports, re-exports, JSX, same name in 2 files).
- tests/test_extract_js.py: module names, node counts by kind, signatures/docs/lines, refs, parse error.
- tests/test_resolve_js.py: every expected non-contains edge with confidence; update with no change = same graph;
  export TREE.txt lists TS symbols. All earlier tests unchanged.

Accept: pytest green; `reaper map` + `export` on the fixture works.
