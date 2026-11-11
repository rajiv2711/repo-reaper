# R2 - Integration: how this repo changes for Phase 8

Scope: Python side of graph.html (signatures, staleness, JSON contract, template fill, level of
detail, tests, packaging). Locked decisions D-01..D-08 of 08-CONTEXT.md are followed. Measurements
were taken on a scratch copy: `cp -r repo <scratch>/r2/repo && reaper map && reaper export`.
Tags: [VERIFIED] checked in source or run, [CITED: url], [ASSUMED].

## 0. Prior findings, checked

| Claim | Verdict |
|---|---|
| export() never reads semantic.json | [VERIFIED] outputs.py l.307-317. outputs imports only discover and graph (l.19-20), never enrich |
| details only in the hover title | [VERIFIED] _vis_node l.266-278; the template has no click handler. vis 9.1.9 shows a string title with `this.frame.innerText=g` (grep of the unpkg file), so it is plain text [VERIFIED] |
| only edge kinds can be toggled | [VERIFIED] l.219-222, 250-252 |
| search needs Enter, takes the first substring match | [VERIFIED] l.253-258. Also: it matches **ids only**, not name or signature |
| physics never turned off | [VERIFIED] the code never sets physics:false and has no `stabilized` handler (l.236-247). Whether vis keeps simulating once stable is [ASSUMED] (it stops at minVelocity, but large graphs can jitter) |
| >3000 nodes: files + externals, only import edges | [VERIFIED] l.293-301 + test l.196-204. On this repo only (file,file,imports) 36 and (file,external,imports) 70 have both ends at file level |
| ~260 KB for 346 nodes / 860 edges; every edge repeats color/title/dashes | [VERIFIED] 260,708 B (blob 257,444 B, template 3,264 B); about 236 B per node and 201 B per edge |
| #net top:44px overlaps a wrapped toolbar | [VERIFIED] CSS l.208-210 (flex-wrap + absolute top:44px). The overlap itself is [ASSUMED], not rendered |
| 33 files, 346 nodes, 860 edges | **Corrected:** the committed .reaper/graph.json has 33 `files`. A fresh map of the working tree gives **34**, because the untracked docs/phases/08-html-view/08-CONTEXT.md is now included. Only 25 are code files (= 25 file nodes). Nodes 346 (function 242, method 43, file 25, external 24, class 12) and edges 860 (calls 455, contains 297, imports 106, inherits 2; EXTRACTED 852, INFERRED 8, AMBIGUOUS 0) [VERIFIED] |
| semantic.json: 25 files, 6 groups, 0 dropped | [VERIFIED] Also 3 patterns and 3 decisions; all 7 evidence ids exist in the graph, and every entry was fresh |

## 1. Signatures and module boundaries

- `outputs.graph_html(graph: dict, sem: dict | None = None) -> str`
- `outputs.export(root, graph: dict, sem: dict | None = None) -> list[Path]`: sem goes only to
  graph_html. TREE.txt and SUMMARY.md stay unchanged.
- `outputs.file_edges(graph: dict) -> list[dict]`: aggregated file-level edges (see 6).
- `enrich.view_semantic(root, graph: dict) -> dict | None`: None when .reaper/semantic.json does
  not exist. `load_semantic` cannot signal that, because it returns empty sections (l.80-85), so
  check `semantic_path(root).exists()` first.
- Import direction [VERIFIED]: enrich imports outputs (enrich.py l.40), and outputs does not import
  enrich, so keep it that way. cli already imports enrich at module top (cli.py l.11). Module-level
  code in enrich.py and llm.py is constants plus `class NotReady` only (no I/O, no Ollama call), so
  the import has no side effects [VERIFIED].

cmd_export, before -> after (cli.py l.52-58):
```python
# before
    for path in outputs.export(args.repo, graph):
# after
    sem = enrich.view_semantic(args.repo, graph)   # None when semantic.json is absent
    for path in outputs.export(args.repo, graph, sem):
```
Optional: an unreadable semantic.json (json.JSONDecodeError) makes cmd_export print a warning to
stderr and export with sem=None, so "export still works" holds.

## 2. Staleness via existing helpers (exact code)

**Files.** run_files computes `key = cache_key(model, text)` from `text = file_input(graph, root, path)`
(l.157-161) and stores `{"input_sha": key, "model": model}` (l.187-188). cache_key's default
`version=FILES_PROMPT_VERSION` (l.125-126) is the same in both places. So
`stale = e.get("input_sha") != cache_key(e.get("model", ""), file_input(graph, root, path))`
reproduces it exactly. Count as stale: OSError on read (file gone), and a missing model or
input_sha [VERIFIED].
**Groups.** Ids are rebuilt every run from `_group_plan` (l.285-292: Louvain, then
`group_input(ordered, sem["files"])`). Freshness is `_fresh` (l.399-401):
```python
def _fresh(entry, members, text):
    return bool(entry) and entry.get("members") == members and entry.get("input_sha") == \
        cache_key(entry.get("model", ""), text, GROUPS_PROMPT_VERSION)
```
In the view: `stale = gid not in plan or not _fresh(sem["groups"][gid], *plan[gid])`. Group input
depends on the stored file summaries, not on source, so editing a source file stales that file
only. Editing a summary stales its group [VERIFIED by experiment].
**Architecture.** run_architecture is fresh when `sem["architecture"]["input_sha"] ==
cache_key(model, arch_input(graph, sem), ARCH_PROMPT_VERSION)` (l.532-534). arch_input raises
NotReady when any group is missing or stale (l.410-415). In the view, stale = NotReady or a key
mismatch against `a.get("model", "")`.
**Evidence.** Re-run `_clean_items(items, title, text, known, dropped)` (l.457-480) against the
current graph's ids, because the graph may have changed since enrich. Expose the newly dropped ids.

A prototype `view_semantic` (scratch only; ~35 lines; uses only the helpers above) ran in 5 ms on
this repo [VERIFIED]: 0 stale, 6 groups fresh, arch fresh, 0 dropped. After appending a line to
reaper/llm.py and running `reaper update`, exactly reaper/llm.py became stale. After editing the
summary of reaper/graph.py in semantic.json, g2 and the architecture became stale [VERIFIED].
Partial entries (test_semantic_json_other_sections_kept writes
`{"groups": {"g0": {"name": "core"}}, "architecture": {"overview": "x"}}`) must not crash: use
`.get` everywhere [VERIFIED shape].

**Cost pitfall.** file_input calls `outputs.file_outline(graph, path)` without `_kids`, so each
call rebuilds `_children(graph)`, which is O(F x (N+E)). Synthetic 401 files / 6,801 nodes: 1.6
ms per file, 0.6 s in total [VERIFIED]. 100k-node repos with full summaries would take minutes
[ASSUMED extrapolation]. Fix (output unchanged):
```python
# before  def file_input(graph, root, path) ... outputs.file_outline(graph, path)
# after   def file_input(graph, root, path, _kids=None) ... outputs.file_outline(graph, path, _kids)
```
view_semantic computes `kids = outputs._children(graph)` once and passes it in.

## 3. Embedded-JSON contract (D-04: only add)

Kept as is: `_vis_node` -> {id, label, group (= kind), title} and `_vis_edge` -> {from, to, kind,
confidence, dashes, color, title}. Wrap them rather than editing them.

| Where | Added key | Value |
|---|---|---|
| node | kind, name, file, line, signature, doc | copied from the graph.json node (null kept: externals have file/line/signature/doc null [VERIFIED]) |
| edge | id | `"e<i>"`, the index in graph["edges"]. Stable DataSet ids for expand/collapse. Today vis invents random ids |
| top | note | kept: "" in full view (asserted); LOD: explanation text |
| top | lod | bool |
| top | budget | {nodes: MAX_HTML_NODES, edges: MAX_HTML_EDGES} |
| top | meta | {generated_at (from graph.json, so deterministic), files, nodes, edges} counts |
| top | file_edges | [{id "f<i>", from, to, kind, count, conf {EXTRACTED: n, INFERRED: n, AMBIGUOUS: n}}] |
| top | sem | null, or {files: {path: {summary, role, model, stale}}, groups: {gid: {name, summary, members, model, stale}}, architecture: null or {overview, patterns: [{name, explanation, evidence}], decisions: [{decision, rationale, evidence}], model, stale, dropped: [ids]}} |

- Semantic group membership lives only in `sem.groups[*].members`. JS maps file -> gid, and a
  symbol takes its file's group via node.file. Node objects are then identical with and without
  sem, and toggling LLM off only restores the default node colours.
- No "files" list is needed: file and external nodes are already in `nodes`, and JS filters them by
  kind.
- input_sha is not shipped.
- Avoid vis option names for new data keys (`level`, `value`, `hidden`, `width`, `x`, `y`,
  `physics`) unless the vis behaviour is wanted [ASSUMED from the vis docs].
- What html_data and the kept tests require [VERIFIED test_outputs.py l.168-211]:
  - the regex `<script id="graph-data" type="application/json">(.*?)</script>`: one blob, exact
    opening tag;
  - nodes 25 and edges 39 on the fixture, so file_edges must never be appended to `edges`;
  - `note == ""`;
  - `sum(dashes) == 4`;
  - `nodes[0]["title"]` starts with "evil.py", so keep graph order and title.

## 4. Byte identity and determinism

cmd_export passes view_semantic's None when the file is absent, so `graph_html(g)`,
`graph_html(g, None)` and the "absent" case are byte-identical by construction. Test it with an
export without semantic.json, then `read_text() == outputs.graph_html(load(repo))`.

Use `json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))`. Key order and
spacing are irrelevant to the tests, which parse JSON. Lists keep graph order. view_semantic
iterates `sorted()` paths. file_edges is sorted by (from, to, kind). Never embed now().

Two effects of sort_keys:
- Group ids sort as g1, g10, g2, so the page should order groups numerically or by size.
- It saves about 7% with compact separators (this repo 364 -> 341 KB; synthetic 5.88 -> 5.40 MB)
  [VERIFIED].

"No LLM text" must be tested as `data["sem"] is None`, not as the absence of the literal
"LLM-generated": the template's JS will contain that label string.

## 5. Template fill and escaping

Today (l.303-304):
```python
blob = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
return HTML_TEMPLATE.replace("__VIS__", VIS_NETWORK_URL).replace("__DATA__", blob)
```
This chain is safe only because DATA is replaced last. Any later placeholder would also be
substituted inside a docstring. One pass:
```python
_SLOT = re.compile(r"__([A-Z]+)__")
return _SLOT.sub(lambda m: {"VIS": VIS_NETWORK_URL, "DATA": blob}[m.group(1)], HTML_TEMPLATE)
```
- The replacement **must be a function**. A string replacement processes backslashes, and
  `re.sub("X", "\\u003c", "X")` raises `re.error: bad escape \u` [VERIFIED].
- An unknown slot raises KeyError, which is a fail-fast.
- `__proto__` does not match, because the pattern only takes uppercase.
- Test with a docstring `"__VIS__ __DATA__"`: it must come back unchanged in `data`.

Escaping "<" as `<` is sufficient: JSON has "<" only inside strings, and JSON.parse restores
it. That kills `</script`, `<!--` and `<script` (script-data escape states), and a bare `-->` is
harmless without `<!--` [CITED: https://html.spec.whatwg.org/multipage/scripting.html#restrictions-for-contents-of-script-elements].
`&` and `>` need no escaping in a script element. U+2028 is fine in JSON text. Put no data
anywhere else in the HTML: everything goes through the blob and then textContent (D-07).

**CDN failure pitfall.** test_html_loads asserts the exact substring
`<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js">`. Adding
`onerror=` (before or after src) breaks that test. Detect the failure in the inline script instead:
`if (typeof vis === "undefined") { msg.textContent = "..."; return; }`.

## 6. Level of detail (D-03)

The budget check stays inside graph_html and reads module globals at call time, so monkeypatch
works:
```python
MAX_HTML_NODES = 1500   # was 3000; above this, or above MAX_HTML_EDGES, open at file level
MAX_HTML_EDGES = 5000
lod = len(graph["nodes"]) > MAX_HTML_NODES or len(graph["edges"]) > MAX_HTML_EDGES
```
This repo (346 / 860) stays in full view. The synthetic repo (6,801 / 19,600) uses LOD.

Aggregation, precomputed in Python (7 ms on 19.6k edges [VERIFIED]):
```python
file_of = {n["id"]: n["file"] or n["id"] for n in graph["nodes"]}  # external: file None -> own id
agg = {}
for e in graph["edges"]:
    if e["kind"] == "contains": continue
    a, b = file_of[e["src"]], file_of[e["dst"]]
    if a != b:  # drop self-loops (e.g. User->Entity inherits inside models.py)
        agg.setdefault((a, b, e["kind"]), Counter())[e["confidence"]] += 1
# -> sorted(agg.items()), one dict per key: count = sum, conf = per-confidence counts
```
- Fixture result [VERIFIED]: 12 file edges: 8 imports (count 1 each), plus calls R->U 1, S->M 2
  (EXTRACTED 1, INFERRED 1), S->R 2 (EXTRACTED 1, INFERRED 1), and S->U 2.
- This repo: 141 file edges over 106 pairs [VERIFIED].
- No dangling edges in this repo's graph [VERIFIED], but guard `file_of.get` anyway.
- Edge dashes: draw dashed when conf has no EXTRACTED member. The confidence filter recomputes
  count from the enabled confidences.

Expanding a file: **embed all nodes and edges**, in both full and LOD modes. JS builds a
node.file -> symbols index and adds those symbols and their edges on double-click. This keeps
D-04 objects and lets architecture evidence ids expand their file first (via node.file).

Measured sizes [VERIFIED]:

| Graph | Today | With the added keys + file_edges (+ sem) |
|---|---|---|
| This repo | 257 KB | 341-364 KB |
| Synthetic 401 files / 6,801 nodes / 19,600 edges | 236 KB (files-only) | 5.4-5.9 MB, of which 244 KB is file_edges |

That is about 210 B per node+edge, so 100k nodes + 300k edges would be about 85 MB [ASSUMED
linear]. An optional hard ceiling (e.g. >40k nodes: embed files only, disable expand, and say so
in note) is a planner choice; it is not required by D-03.

The template's `big = data.nodes.length > 300` (l.235) must use the visible count. After the first
`stabilizationIterationsDone` event (present in 9.1.9 [VERIFIED]), call
`setOptions({physics:false})` (VIEW-06 idle CPU).

## 7. Tests

These stay byte-for-byte untouched:
- test_html_loads_vis_network_and_embeds_graph
- test_html_dashed_when_not_extracted
- test_html_escapes_script_end_in_docs
- test_export_writes_three_files
- test_export_without_graph
- every TREE, SUMMARY and query test in test_outputs.py, and all of test_enrich*.py

The suite passes 140 tests now [VERIFIED].

**Replace** test_html_large_graph_shows_files_only (l.196-204; log it in SUMMARY). Today it does:
```python
monkeypatch.setattr(outputs, "MAX_HTML_NODES", 24)  # fixture has 25 nodes
data = html_data(outputs.graph_html(build(sample_repo)))
assert sorted(n["id"] for n in data["nodes"]) == ["app/__init__.py", M, R, S, U, "ext:json", "ext:os"]
```
The replacement, same trick:
```python
monkeypatch.setattr(outputs, "MAX_HTML_NODES", 24)
data = html_data(outputs.graph_html(build(sample_repo)))
assert data["lod"] is True and len(data["nodes"]) == 25 and len(data["edges"]) == 39
fe = {(e["from"], e["to"], e["kind"]): e for e in data["file_edges"]}
assert len(fe) == 12 and fe[(S, M, "calls")]["conf"] == {"EXTRACTED": 1, "INFERRED": 1}
```
Add an edges-only twin with `monkeypatch.setattr(outputs, "MAX_HTML_EDGES", 38)` (39 edges).

For a semantic.json fixture, use the shape of test_enrich_groups.py `mapped` (l.155-160):
`{"files": {p: {"summary", "role", "input_sha": "x", "model": "m"}}, "groups": {}, "architecture": {}}`.
`"x"` makes an entry stale. For a fresh one, use
`enrich.cache_key("m", enrich.file_input(graph, repo, p))`.
- Fresh group: loop over `enrich._group_plan(graph, sem)` and set
  `input_sha = enrich.cache_key("m", text, enrich.GROUPS_PROMPT_VERSION)`. The fixture is a single
  group g1 (test_fixture_is_one_group).
- Architecture: add evidence `[S, "ghost.py::X"]` and assert that ghost lands in
  `sem.architecture.dropped`.
- Truth 5: give a summary `"<b>x</b></script>"`, then assert `"<b>x</b>" not in html` and
  `html_data(html)["sem"]["files"][S]["summary"] == "<b>x</b></script>"`.

## 8. Move HTML_TEMPLATE to reaper/templates/graph.html?

Recommendation: **yes**.

- pyproject.toml has `[tool.setuptools] packages = ["reaper"]` and no package-data. A scratch
  wheel build **omitted** reaper/templates/graph.html. With
  `[tool.setuptools.package-data] reaper = ["templates/*.html"]` it was included [VERIFIED].
- The env uses an editable install (environment.yml `-e .`; reaper.__file__ is in the source
  tree), so tests will not catch a missing package-data entry. Add a guard test that reads
  pyproject.toml with tomllib.
- `importlib.resources.files("reaper").joinpath("templates/graph.html").read_text(encoding="utf-8")`
  works without templates/__init__.py [VERIFIED with python -S on the scratch copy].
- Keep the module name `outputs.HTML_TEMPLATE` (load it at import).
- The file must start with `<!DOCTYPE html>` and have no BOM.
- Why move it: the template grows from about 65 lines to several hundred of JS. Inside a non-raw
  Python string, a JS regex like `/\s+/` is an invalid escape (a SyntaxError under -W error on
  3.12 [VERIFIED]).
- If it stays inline, make it `r"""..."""`.
- The AGENTS.md Layout gains one line (not a data-format or CLI change).
