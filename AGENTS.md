# repo-reaper: guide for contributors and coding agents

What the tool does and how to use it: [README.md](README.md). This file covers how the code is
built and the rules for changing it.

## Architecture (do not break)
discover -> extract -> resolve -> outputs -> enrich
- **extract** is per file and pure: one file in, nodes + raw refs out, no cross-file knowledge.
- **resolve** is global: it rebuilds ALL edges from all nodes + raw refs, every time.
- **Incremental update** = re-extract added/changed files (sha256 differs), keep the rest, resolve again.
  An update must give the same graph as a full build.
- **Structure first, LLM second.** The LLM only adds meaning on top of the deterministic graph,
  never sees the whole repo (one bounded chunk per call), and must cite node ids that exist.
- **Confidence on every edge:** EXTRACTED (proven by the code), INFERRED (one guess), AMBIGUOUS
  (several candidates).

## Layout
reaper/cli.py           `reaper` entry point (argparse); every command but scan takes `--out DIR`
reaper/discover.py      list files (`git ls-files -co --exclude-standard`, else os.walk), language, sha256
reaper/extract_py.py    Python extraction (ast)
reaper/extract_js.py    JavaScript/TypeScript extraction (tree-sitter)
reaper/resolve.py       raw refs -> edges
reaper/graph.py         build/update/load/save graph.json; `out_dir()` decides where outputs go
reaper/outputs.py       TREE.txt, SUMMARY.md, graph.html, query
reaper/legend.py        what the labels mean; written into every output (keep it in step with resolve.py),
                        and the agent block `reaper rules` prints (trust rule + query line)
reaper/templates/graph.html   the whole page (HTML, CSS, JS), package data
reaper/llm.py           Ollama client (stdlib urllib)
reaper/enrich.py        LLM passes: files, groups, architecture; semantic layer for graph.html
tests/fixtures/sample_py, sample_js   small known repos used by the tests

## Data contract
Outputs live in `<repo>/.reaper/` or the `--out` dir.
- graph.json (format version 2; another version means `update` does a full build):
  `meta {version, generated_at}`, `legend` (reaper/legend.py), `files {path: {lang, sha256, lines}}`,
  `nodes [{id, kind, name, file, line, signature, doc}]` (kind file|class|function|method|external),
  `refs [{src, kind, target, alias, file, line}]` (raw, per file; kind import|call|inherit),
  `edges [{src, dst, kind, confidence, lines}]` (kind contains|imports|calls|inherits; `lines` =
  source lines in src's file that made the edge, absent on contains). A (src, dst, kind) pair has
  one edge per confidence among its lines, each line only on its strongest one.
- Node ids: file = relative path `app/service.py`; symbol = `app/service.py::UserService.create`;
  external = `ext:requests`. Module name of a file: drop `.py`, `/` -> `.`, drop a trailing
  `.__init__`, drop a leading `src.`.
- semantic.json: `{legend, files: {path: {summary, role, input_sha, model}}, groups: {id: {name,
  summary, members, input_sha, model}}, architecture: {...}}` (`legend` is dropped on load). Cache key = sha256(model + prompt version + input).

## Rules worth knowing before you change something
- **Precision first.** A wrong edge costs more than a missing one: agents stop trusting the graph
  and grep everything. Never add a rule that links by name alone; a call that cannot be resolved
  gets no edge (query lists it as "not linked"). tests/test_resolve_rules.py holds the cases.
- **Call resolution order** (resolve.py docstring has the details):
  1. `self.x` inside a class: own method (EXTRACTED), else a base-class method (INFERRED), else that
     method in subclasses (1 INFERRED, 2-5 AMBIGUOUS), else no edge.
  2. Through the file's import aliases (EXTRACTED). An alias pointing outside the repo gives no edge.
  3. A same-file name (EXTRACTED).
  4. Builtins, and `x.m()` where m is a built-in type's method (PY_TYPE_METHODS, JS_PROTO_METHODS),
     give no edge.
  5. Last name part, among candidates the file can see (`x.m()`: classes defined, imported or
     re-exported there and their bases; bare Python names: none; bare JS names: all top-level
     functions): 1 candidate INFERRED, 2-5 AMBIGUOUS (one edge each), more gives no edge.
- **imports** go to the repo file with the longest module-name prefix match; a Python import that
  matches none tries the importing file's own folder (EXTRACTED without `__init__.py`, else
  INFERRED); otherwise `ext:<top package>`.
- **LLM calls** (llm.py): POST /api/chat, stream false, `format` = JSON schema, temperature 0,
  one retry on invalid JSON. Never send num_ctx.
- **enrich**: `--limit` picks the most-connected files first. Groups are Louvain communities
  (seed 42) on the file graph. The architecture pass drops evidence ids not in graph.json.
- **graph.html**:
  - Data text reaches the DOM only via textContent. The template is filled in one pass, and `<` is
    escaped in the embedded JSON.
  - Above 1,500 nodes or 5,000 edges the page opens at file level.
  - vis-network 9.1.9 from unpkg, jsDelivr as fallback. No other JS library or CDN.

## Working rules
- Environment: conda env `repo-reaper` (environment.yml). Run everything through it:
  `conda run -n repo-reaper reaper ...`, `conda run -n repo-reaper python ...`.
- Tests: `REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q` must pass before every commit.
  The variable makes the page-JS tests fail instead of skip when Node 18+ is missing.
- Expected test values are written by hand from the fixtures, before the code. Never edit an
  expected value just to make a test pass: fix the code.
- New behaviour needs new tests. Never claim something works without showing the command output.
- Don't change the data format, the CLI or graph.html behaviour without the owner's OK.
- No new dependencies without a note saying why. The stack today: Python 3.11+ stdlib, networkx,
  tree-sitter (+ javascript, typescript grammars); pytest for tests.
- If the same failure survives 3 fix attempts, stop and report it instead of trying more.

## Gotchas
- `conda run` drops stdin: a heredoc piped into `conda run ... python` silently does nothing.
  Write a script file instead.
- Headless Chrome reports dark mode. For graph.html screenshots, force a theme with
  `--blink-settings=preferredColorScheme=1` (light) or `=0` (dark), and use one `--user-data-dir`
  per parallel run.
- Read big files in ranges (`grep -n`, `sed -n 'a,bp'`), and never print .reaper/ outputs in full.

## History
The project was built in 13 phases. Their plans, research and summaries were removed from the
tree but are kept under the git tag `phases-archive`:

    git show phases-archive:docs/phases/08-html-view/08-CONTEXT.md

Labels in comments and tests such as "Phase 8", "D-02", "VIEW-05" or "08-03-1" refer to those docs.
