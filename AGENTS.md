# repo-reaper

## Core concept
A lightweight tool that maps any code repository into a graph, combining:
- Structural analysis (no LLM): files, imports, classes, functions, calls, inheritance.
- Semantic analysis (local LLM via Ollama): what each file does, how modules relate, architectural patterns, design decisions, system purpose.

## Key ideas
1. Structure first, LLM second. The structural graph is deterministic and cheap; the LLM only adds meaning on top of it.
2. Context management: the LLM never sees the whole repo. Each call gets one bounded chunk (one file's outline + source, or the summaries of one group of files), so any repo size fits.
3. Two models: devstral-small-2:24b for the fast per-file pass, qwen3-coder:30b for group and architecture analysis. Run each pass to completion with one model (Ollama swaps models slowly).
4. Incremental: every file's sha256 is stored in JSON. Re-runs re-parse only changed files and re-ask the LLM only for inputs whose hash changed.
5. Honesty: every edge has a confidence: EXTRACTED (proven by the code), INFERRED (single best guess), AMBIGUOUS (several candidates). LLM claims must cite node ids that exist in the graph.

## Architecture (do not break)
discover -> extract (per file and pure: one file in, nodes + raw refs out, no cross-file knowledge) -> resolve (global: rebuilds ALL edges from nodes + raw refs) -> outputs -> enrich (LLM).
Incremental update = re-extract changed files, then resolve again.

## Stack
Python 3.11+ stdlib (ast, json, hashlib, argparse, subprocess, urllib), networkx, pytest. No other dependencies without a note in HANDOFF.md.
Always use the conda env `repo-reaper` (defined in environment.yml; create with `conda env create -f environment.yml`): conda run -n repo-reaper python, conda run -n repo-reaper pytest -q, conda run -n repo-reaper reaper

## Layout
reaper/cli.py          `reaper` entry point (argparse)
reaper/discover.py     list files, language, sha256
reaper/extract_py.py   Python AST extraction
reaper/resolve.py      raw refs -> edges
reaper/graph.py        load/save .reaper/graph.json
reaper/outputs.py      tree, summary, html, query
reaper/templates/graph.html  graph.html page template (package data)
reaper/llm.py          Ollama client
reaper/enrich.py       semantic passes
tests/fixtures/sample_py/   small known repo used by all tests
docs/phases/NN-slug/   GSD-style phase docs (Phase 8+): NN-CONTEXT, NN-RESEARCH, NN-PLAN, NN-*-SUMMARY, NN-VERIFICATION

## Data format (output dir: <repo>/.reaper/)
graph.json:
  meta:  {version, generated_at}
  files: {path: {lang, sha256, lines}}
  nodes: [{id, kind, name, file, line, signature, doc}]   kind: file|class|function|method|external
  refs:  [{src, kind, target, alias, file, line}]          raw, per file; kind: import|call|inherit
  edges: [{src, dst, kind, confidence}]                    kind: contains|imports|calls|inherits
Node ids: file = relative path "app/service.py"; symbol = "app/service.py::UserService.create"; external = "ext:requests".
Module name of a file: drop ".py", "/" -> ".", drop trailing ".__init__", drop leading "src.".
semantic.json: {files: {path: {summary, role, input_sha, model}}, groups: {id: {name, summary, members, input_sha, model}}, architecture: {...}}

## CLI
reaper scan <repo>                    file counts per language
reaper map <repo>                     full structural build -> graph.json
reaper update <repo>                  incremental structural update
reaper export <repo>                  TREE.txt, SUMMARY.md, graph.html
reaper query <repo> callers|callees|deps NAME [--json]
reaper enrich <repo> --pass files|groups|architecture [--model M] [--limit N] [--dry-run]
Typical use: map -> export -> enrich --pass files --model devstral-small-2:24b -> enrich --pass groups, then --pass architecture, both with --model qwen3-coder:30b.
## Phases (one per session; tick [x] only when acceptance passes)
- [x] Phase 1: Scaffold + discovery
  pyproject.toml (console script `reaper`), .gitignore (.venv/, __pycache__/, .reaper/, *.egg-info/), venv with pytest + networkx, reaper/cli.py, reaper/discover.py.
  discover: `git ls-files -co --exclude-standard` inside a git repo, else os.walk; skip .git node_modules .venv venv __pycache__ dist build .reaper; language by extension; sha256 + line count.
  Fixture tests/fixtures/sample_py/app/ (4-5 small files): module docstrings, `import os`, `from x import y`, a base class and a subclass, self.method() calls, cross-file function calls, one 
function name defined in two files.
  Accept: `reaper scan tests/fixtures/sample_py` prints the python file count; pytest passes (tests copy the fixture to tmp_path first).
- [x] Phase 2: Python structure
  extract_py.extract(path, source, module) -> nodes + raw refs via `ast`. Classes, functions, methods with line, signature like "create(self, name)", first docstring line. Refs: imports (absolute 
target + local alias; relative imports made absolute), calls (dotted callee text like "self.repo.save"), class bases. Syntax error -> file node only. `reaper map` writes graph.json.
  Accept: tests assert node counts by kind and specific refs on the fixture. Write expected values by hand from the fixture source BEFORE implementing.
- [x] Phase 3: Resolution
  resolve.py rebuilds all edges. contains: parent -> child. imports: file -> repo file (longest module-name prefix match), else -> ext:<top package>. inherits: base resolved via imports or same 
file. calls, in order:
  (1) self.x inside a class -> own method EXTRACTED, else base-class method INFERRED
  (2) via the file's import aliases -> EXTRACTED; alias pointing outside the repo -> no edge
  (3) same-file name -> EXTRACTED
  (3) same-file name -> EXTRACTED
  (4) builtins -> no edge
  (5) else match by last name part: 1 candidate INFERRED, 2-5 AMBIGUOUS (one edge each), otherwise no edge
  Accept: a test lists every expected non-contains edge of the fixture with its confidence.
- [x] Phase 4: Incremental update
  `reaper update`: compare sha256s; re-extract added/changed, drop deleted, skip unchanged, then resolve. Return {added, changed, deleted, unchanged}.
  Accept: a no-change run gives an identical graph; editing one file, deleting one and adding one gives correct counts and edges.
- [x] Phase 5: Outputs + query
  TREE.txt (per file: classes/functions with signatures and line numbers), SUMMARY.md (stats, most-connected nodes, import cycles via networkx, external deps), graph.html (single file, vis-network
9.1.9 from unpkg, dashed edges when not EXTRACTED), `reaper query`.
  Accept: tests check key strings in each output and query results on the fixture.
- [x] Phase 6: Semantic pass, files (fast model)
  llm.py: POST {OLLAMA_HOST or http://localhost:11434}/api/chat with stream false, format = JSON schema, temperature 0; retry once on invalid JSON; never send num_ctx. enrich --pass files: input 
per file = TREE outline + source (whole if <= 300 lines, else first 150) -> {summary (max 2 sentences), role}. Cache key = sha256(model + prompt version + input), stored in semantic.json. --limit 
picks most-connected files first. --dry-run prints call count and approx tokens (chars/4).
  Accept: tests mock llm (no real Ollama); a second run makes 0 calls.
- [x] Phase 7: Semantic pass, groups + architecture (full model)
  Groups = networkx Louvain communities (seed=42) on the file graph. groups pass: per group, input = member paths + file summaries (cap 12k chars) -> {name, summary}. architecture pass: input = 
group summaries + cross-group edge counts + most-connected nodes -> {overview, patterns: [{name, explanation, evidence: [node ids]}], decisions: [...]}. Drop evidence ids not in graph.json. Write 
ARCHITECTURE.md marked "LLM-generated".
  Accept: mocked tests, including a fake evidence id being dropped; a manual run on this repo works.
- [x] Phase 8: Interactive HTML view (GSD-style; docs in docs/phases/08-html-view/)
  Goal: graph.html becomes the way to explore a mapped repo: find any symbol, see what it is, what touches it and what the LLM layer says about it, on repos of any size.
  Depends on: Phase 5 (graph.html), Phase 7 (semantic.json). Locked decisions: docs/phases/08-html-view/08-CONTEXT.md (D-xx); later steps never contradict them.
  Requirements: VIEW-01 search (id, name, signature; ranked list as you type). VIEW-02 click -> side panel (kind, signature, file:line, doc, file summary + role, callers/callees/imports/imported-by/bases with confidence, all clickable).
  VIEW-03 focus on a node's 1-3 hop neighbourhood. VIEW-04 filters by node kind, edge kind and confidence (INFERRED and AMBIGUOUS drawn differently), plus a legend with counts.
  VIEW-05 semantic layer when .reaper/semantic.json exists: group colours, summaries, architecture tab whose evidence ids focus their nodes, stale entries marked. Without semantic.json the page is the structural view and shows no LLM text.
  VIEW-06 big repos: level of detail (file-level view with aggregated edges, expand a file) instead of the all-or-nothing files-only cut; the layout stops after it stabilizes. VIEW-07 safety: data text reaches the DOM only via textContent, template filled in one pass, a visible message when the CDN script fails.
  Success (must be TRUE):
    1. On this repo, typing "run_gr" lists reaper/enrich.py::run_groups; picking it focuses the node, and the panel shows its signature, doc, file summary and clickable callers/callees.
    2. Hop focus (1-3) and the node-kind, edge-kind and confidence filters combine, and the legend counts match what is shown.
    3. With semantic.json, nodes are coloured by group and every architecture evidence id focuses its node. With semantic.json absent, `reaper export` still works and the page has no LLM text.
    4. A synthetic repo above the size budget opens as a file-level view with aggregated edges; a file expands to its symbols; the CPU goes idle once the layout settles.
    5. A docstring or summary containing "<b>x</b></script>" is shown as plain text.
  Accept: pytest checks on the generated HTML pass (data contract, UI hooks, escaping, degrade mode, with and without semantic.json); the Phase 5 html tests are unchanged unless a locked decision replaces them; 08-VERIFICATION.md says status: passed; the user confirmed the browser checklist.
  Workflow: discuss -> research -> plan -> execute -> verify. Each step writes its file in docs/phases/08-html-view/; a resumed session continues at the first missing file.
- [ ] Phase 9 (optional): More languages via tree-sitter-language-pack, same extract contract. (was Phase 8; renumbered when Phase 8 "Interactive HTML view" was inserted)

## Session protocol
Start: read HANDOFF.md; run `git log --oneline -5` and `conda run -n repo-reaper pytest -q`; say "This session: Phase N". Work on the phase HANDOFF.md marks partial, else the first unchecked phase. Only that 
phase.
During:
- Small steps; run tests after each. Never claim something works without showing the command output.
- Read big files in ranges (grep -n, sed -n 'a,bp'). Never print .reaper/ outputs in full.
- Don't change the data format or CLI; propose changes in HANDOFF.md instead.
- Never edit expected test values just to make tests pass; fix the code.
- Same failure after 3 fix attempts: stop and record it as a blocker.
End (phase done, blocked, or about 40 tool calls in):
1. Run `conda run -n repo-reaper pytest -q` and show the summary line.
2. Tick the phase above only if its acceptance passed.
3. Rewrite HANDOFF.md from scratch, max 30 lines: Phase N | status (done/partial/blocked) | done this session | exact next step | blockers | verify command + result.
4. `git add -A && git commit -m "Phase N: <summary>"`
5. Tell the user: "Start a fresh session and paste the continue prompt." Then stop.
