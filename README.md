# repo-reaper

repo-reaper maps a code repository into a graph of its files, classes, functions and methods,
and of the imports, calls and inheritance between them. You can explore the graph in a browser,
query it from the shell, or hand its text outputs to a person or an AI assistant instead of the
raw source.

It works in two layers:

- **Structure** (deterministic, no LLM, seconds): Python is parsed with the standard `ast` module,
  JavaScript and TypeScript (`.js .jsx .mjs .cjs .ts .tsx`) with tree-sitter.
- **Meaning** (optional, a local LLM through [Ollama](https://ollama.com)): a two-sentence summary
  and a role for each file, named groups of related files, and an architecture overview whose
  evidence must point at real nodes in the graph.

Every edge has a confidence: **EXTRACTED** means the code proves it, **INFERRED** means one best
guess, and **AMBIGUOUS** means several candidates were equally likely. The graph only guesses
where the code leaves few options; a call it cannot resolve gets no edge, and `query` lists those
call sites instead. Re-runs are incremental: unchanged files are not parsed again, and the LLM is
only asked again when its input changed.

```
$ reaper query . callers run_groups
callers of reaper/enrich.py::run_groups  (line 301)
  2 callers: 2 EXTRACTED
  EXTRACTED  reaper/cli.py::_enrich_groups  (calls at line 129)
  EXTRACTED  tests/test_enrich_groups.py::groups  (calls at line 178)
  not linked: none
```

## Install

You need Python 3.11 or newer.

```
# with conda (creates the env "repo-reaper" and installs the package in editable mode)
conda env create -f environment.yml
conda activate repo-reaper          # or prefix each command: conda run -n repo-reaper reaper ...

# or with a plain virtualenv
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

Then `reaper --version` should print `reaper 0.1.0`.

## Quick start

```
reaper run ~/code/myapp                    # graph + TREE.txt, SUMMARY.md, graph.html in ~/code/myapp/.reaper/
xdg-open ~/code/myapp/.reaper/graph.html   # macOS: open ...
reaper query ~/code/myapp callers UserService.create
```

To keep the outputs out of the repository, add `--out DIR`, and pass the same `--out` to every
later command:

```
reaper run   ~/code/myapp --out ~/reaper-out/myapp
reaper query ~/code/myapp --out ~/reaper-out/myapp deps app/service.py
```

To add the LLM layer, start Ollama (see [LLM layer](#llm-layer-ollama)) and run
`reaper run ~/code/myapp --llm`.

## Commands

The argument `<repo>` is the root of the repository to map. Every command except `scan` takes
`--out DIR` (default: `<repo>/.reaper`).

| Command | What it does |
|---|---|
| `reaper run <repo>` | The everyday command. It updates graph.json (a full build the first time) and writes TREE.txt, SUMMARY.md and graph.html. |
| `reaper run <repo> --llm` | The same, plus the three LLM passes (files, then groups, then architecture) before the outputs are written. |
| `reaper scan <repo>` | Counts files per language. Writes nothing. |
| `reaper map <repo>` | Rebuilds graph.json from scratch. |
| `reaper update <repo>` | Updates graph.json incrementally and prints the added, changed, deleted and unchanged counts. |
| `reaper export <repo>` | Writes TREE.txt, SUMMARY.md and graph.html from graph.json. |
| `reaper query <repo> callers\|callees\|subclasses\|deps NAME` | Answers one question in one call (see [query](#query)). NAME can be a node id, a qualified name (`UserService.create`), a module name (`app.service`) or a plain name. |
| `reaper enrich <repo> --pass files\|groups\|architecture` | Runs one LLM pass, then rewrites graph.html so the page shows the new results. |

Options:
- `run --llm` and `enrich` both take:
  - `--model M`: the Ollama model. For `run`, one model for all passes; for `enrich`, the model for that pass.
  - `--limit N`: ask about at most N stale files or groups, most-connected first.
- `enrich` also takes `--dry-run`: print the number of calls and the approximate input tokens, and call nothing.

If an LLM pass fails (for example, Ollama is not running), `run --llm` skips the remaining passes,
still writes the outputs, and exits with status 1. Running it again retries only what is missing,
because finished answers are cached.

### `run` with and without `--llm`

| | `reaper run <repo>` | `reaper run <repo> --llm` |
|---|---|---|
| Needs | nothing else | Ollama running, with the models pulled |
| Time | seconds (physicsnemo, 2,000 Python files: about 6 s) | about 9 s per changed file on a 16 GB laptop GPU, plus a few calls for groups and architecture |
| Writes | graph.json, TREE.txt, SUMMARY.md, graph.html | the same, plus semantic.json and ARCHITECTURE.md |
| graph.html | structure: search, panel, focus, filters | plus group colours, a summary and role for each file, and an Architecture tab |

### query

- `callers` / `callees`: who calls a function, method or class, and what it calls. Each line gives
  the call sites (`calls at line 851, 932`).
- `subclasses`: classes that inherit from a class.
- `deps`: what a file imports and who imports it, with the import lines.
- `--depth N`: follow N hops (callers of the callers, and so on). Each node is listed once; a
  repeat says `(see above)`.
- `--budget TOKENS` (default 2000, about 4 characters per token): the text output stays under it.
  Nearer hops come first and the space is shared between parents; what does not fit is counted
  per top-level folder (`... 46 more callers (examples/ 23, test/ 23)`), and the last line names
  the `--budget` that shows everything.
- `callers` ends with **not linked**: call sites that use the same name but that the graph could
  not resolve (the object's type is unknown, or a dynamic import). Those are the only places left
  to check by hand.
- `--json` prints everything, never cut.

```
$ reaper query ~/code/physicsnemo callers _get_checkpoint_filename --depth 2
callers of physicsnemo/utils/checkpoint.py::_get_checkpoint_filename  (line 570)
  5 callers: 5 EXTRACTED; hop 2: 129 callers: 129 EXTRACTED
  EXTRACTED  examples/.../transformer_models/src/gp_utils.py::load_pretrained_model_only  (calls at line 493)
    EXTRACTED  examples/.../transformer_models/src/plot_embeddings.py::main  (calls at line 295)
  ...
  EXTRACTED  physicsnemo/utils/checkpoint.py::save_checkpoint  (calls at line 851, 932)
    ... 46 more callers (examples/ 23, test/ 23)
  (120 of 192 lines not shown; --budget 5400 shows all)
  not linked: none
```

## Outputs

All outputs go to `<repo>/.reaper/`, or to the `--out` directory.

| File | Contents |
|---|---|
| `graph.json` | The graph: `meta`, `files {path: {lang, sha256, lines}}`, `nodes`, `refs` (raw per-file imports, calls and bases), `edges` |
| `TREE.txt` | Every file with its classes, functions and methods, each with signature and line number. This file is large on big repos, so search it rather than read it whole. |
| `SUMMARY.md` | Counts, the most-connected nodes, import cycles and external dependencies |
| `graph.html` | The interactive page (see below) |
| `semantic.json` | LLM answers with their cache keys (only after an LLM pass) |
| `ARCHITECTURE.md` | The LLM's architecture overview, marked "LLM-generated" (only after the architecture pass) |

Each node is `{id, kind, name, file, line, signature, doc}` with kind `file`, `class`, `function`,
`method` or `external`. The id is the file's relative path (`app/service.py`), the symbol under
it (`app/service.py::UserService.create`), or `ext:<package>` for something outside the repo.
Each edge is `{src, dst, kind, confidence, lines}` with kind `contains`, `imports`, `calls` or
`inherits`; `lines` are the lines in src's file the edge comes from (call sites, the import, the
class line) and are absent on `contains` edges.

### How a call becomes an edge

The rules are tried in this order:
1. `self.x()` inside a class goes to the class's own method (EXTRACTED), else to a base class's
   method (INFERRED), else to that method in its subclasses (a hook: 1 is INFERRED, 2 to 5 are
   AMBIGUOUS). Otherwise there is no edge: `x` comes from a base outside the repo (such as
   PyTorch's `nn.Module`) or is an attribute.
2. A name brought in by an import of a repo file is EXTRACTED. A name imported from outside the repo gets no edge.
3. A name defined in the same file is EXTRACTED.
4. Builtins get no edge, and neither does `x.m()` when `m` is a method of a built-in type
   (`list.append`, `dict.get`, `str.split`; in JS `push`, `map`, `then`...).
5. What is left is matched by its last name part: one candidate is INFERRED, 2 to 5 are
   AMBIGUOUS (one edge each), more get no edge. The candidates are limited to what the calling
   file can see:
   - `x.m()`: methods of classes defined in the file, imported by it (also through a package's
     re-exports or an imported module), and their base classes.
   - a bare `f()`: in Python, a name that is neither defined in the file nor imported can only be
     a local variable, so there is no edge. In JS and TS it can be a script global, so it is
     matched against top-level functions and classes.

Imports go to the repo file with the longest matching module name. A Python import that matches
none is looked up in the importing file's own folder, as Python does for a script
(`from gp_utils import x` next to `gp_utils.py`): EXTRACTED in a folder without `__init__.py`,
INFERRED in a package folder.

## graph.html

Open the file in a browser; no server is needed. The page loads vis-network 9.1.9 from unpkg
(jsDelivr as fallback), so it needs internet access. If both fail, the page says so.

- **Views.** Graph is a force layout; Re-layout and Fit are in the toolbar. Tree lays the repo out
  left to right like an editor's project tree: folders, then files, then classes and functions,
  then methods. Imports, calls and inheritance are drawn as curves over it. In Tree,
  double-click a folder or file to open or close it; edges into a closed one are bundled.
- **Search** by name, id or signature. Pick a result to focus it.
- **Details panel**: kind, signature, doc, `file:line`, the LLM file summary, and clickable callers,
  callees, imports, importers and bases with their confidence. With nothing selected it lists the
  most-connected nodes.
- **Focus** on a node's 1, 2 or 3-hop neighbourhood; Clear focus leaves it. The address bar keeps a
  deep link, `graph.html#node=<id>&hops=N`.
- **Filters** by node kind, edge kind and confidence. The legend counts what is shown. INFERRED and
  AMBIGUOUS edges are drawn dashed.
- **LLM layer** (only when semantic.json exists; switch it off with the "LLM layer" box): group
  colours, group summaries and an Architecture tab whose evidence links focus their nodes.
  Entries whose inputs have changed since the LLM saw them are marked stale.
- **Big repos** (over 1,500 nodes or 5,000 edges) open as a file-level view with bundled edges;
  double-click a file to expand it, and Collapse all folds every file back.
- **Theme**: Auto (follows the OS), Light or Dark.
- **Keys**: `/` search, `Up`/`Down`/`Enter` in the results, `g` Graph, `t` Tree, `f` Fit, `Esc` clear focus.

## LLM layer (Ollama)

1. Install [Ollama](https://ollama.com) and start it (`ollama serve`, or its system service).
2. Pull the default models:
   ```
   ollama pull devstral-small-2:24b   # files pass
   ollama pull qwen3-coder:30b        # groups and architecture passes
   ```
   Any other Ollama model works with `--model`.
3. Run `reaper run <repo> --llm`, or run the passes one at a time with `reaper enrich <repo> --pass files`
   (then `groups`, then `architecture`).

repo-reaper talks to `$OLLAMA_HOST`, or to `http://localhost:11434` if that is not set. Calls use
temperature 0 and a JSON schema for the reply; an invalid reply is retried once.

Each pass sends the LLM one bounded chunk at a time, so repo size does not matter for the context
window:
- **files:** a file's outline plus its source (whole up to 300 lines, else the first 150).
- **groups:** the paths and summaries of one group of files (Louvain communities, at most 12k characters).
- **architecture:** the group summaries, cross-group link counts and most-connected nodes.

The architecture pass drops any evidence id that is not in graph.json.

Answers are cached by a hash of model, prompt version and input, so a second run asks nothing.
On a big repo, check the cost first and limit it:

```
reaper enrich ~/code/big --pass files --dry-run     # e.g. 1981 calls, ~3.2M input tokens
reaper run ~/code/big --llm --limit 200             # the 200 most-connected files first
```

## Limits

- **Languages.** Only Python, JavaScript and TypeScript get symbols. Other files are listed and
  hashed but not parsed.
- **Static resolution.** Calls are resolved statically, so dynamic dispatch, `getattr` and
  callbacks are missed or only guessed by name.
- **No type inference yet.** For `x.m()` the graph does not know what `x` is; it only narrows the
  candidates to classes the file can see. So `m = Mesh(...); m.clean()` is INFERRED rather than
  EXTRACTED, a call on an object whose class the file never imports gets no edge (`query callers`
  lists it under "not linked"), and a library method with the same name as a visible repo method
  (a tensor's `.to()` or `.clone()` next to a repo class that defines them) can still be guessed.
- **No exclude option.** Only `.gitignore` and a fixed set of folders (`.git node_modules .venv venv
  __pycache__ dist build .reaper`) are skipped, so test fixtures and examples are mapped too.
- **Monorepos.** Workspace packages resolve as external.
- **Dynamic code.** `importlib.import_module(...)`, `getattr`, registries and config files
  (Hydra `_target_`) give no edges.
- **sys.path tricks.** Folders added with `sys.path.append(...)` or `PYTHONPATH` are not followed.
- **Large outputs.** graph.html embeds the whole graph (31 MB for physicsnemo) and TREE.txt grows
  with the number of symbols (1.6 MB for physicsnemo).
- **graph.html quirks.** Long search results overflow the sidebar. A repo with one huge folder
  opens Tree as a single closed folder. Tree's open/closed state is not kept on reload. External
  nodes cannot be folded.

## Development

```
REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q
```

Some tests run the page's JavaScript with Node 18+. Without Node they are skipped;
`REAPER_REQUIRE_NODE=1` makes them fail instead, so a missing Node cannot go unnoticed. [AGENTS.md](AGENTS.md) describes the architecture, code layout and
rules for contributors and coding agents.

## License

Apache 2.0, see [LICENSE](LICENSE).
