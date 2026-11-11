# 08-01 SUMMARY: Python payload + template file

Plan 08-01 (wave 1) | status: done | requirements: VIEW-06, VIEW-07, D-03, D-04

## What was built
- 08-01-1: the graph.html page template moved out of outputs.py into `reaper/templates/graph.html`.
  The Phase 5 page was copied byte for byte by a script, so the page itself is unchanged. It is shipped
  as package data (`[tool.setuptools.package-data] reaper = ["templates/*.html"]`) and loaded once at
  import with `importlib.resources.files("reaper").joinpath("templates/graph.html")`. The chained
  `.replace` fill is now a single `re.sub(r"__([A-Z]+)__", ...)` pass (`_fill`), so a slot name inside the
  URL or the data is never filled again, and an unknown slot raises KeyError. AGENTS.md Layout has the new line.
  Checked separately: a wheel built from a scratch copy contains `reaper/templates/graph.html`.
- 08-01-2: the files-only cut is gone; level of detail is in. `MAX_HTML_NODES = 1500`,
  `MAX_HTML_EDGES = 5000` (read at call time), and `lod` / `budget` / `note` / `file_edges` were added.
  `file_edges(graph)` bundles non-contains edges per (file, file) pair: externals map to themselves,
  same-file pairs are skipped, and rows are sorted by (from, to) with ids f0..fN. All nodes and edges are
  always embedded.
- 08-01-3: payload fields were added without removing any (`_vis_node`/`_vis_edge` unchanged). Nodes gain
  kind, name, file, line, signature, doc and deg (`sum(degrees(graph).get(id, (0, 0)))`). Edges gain
  `id` "e<i>". New top-level keys are `meta` {generated_at, files, nodes, edges} and the `sem` slot.
  `graph_html(graph, sem=None)` and `export(root, graph, sem=None)` pass `sem` through only as data; it
  never reaches a label or title. The blob uses `sort_keys=True`, compact separators, and escapes `<`,
  U+2028 and U+2029.

## Files
Created: reaper/templates/graph.html, tests/test_html_template.py, tests/test_html_data.py,
docs/phases/08-html-view/08-01-SUMMARY.md
Modified: reaper/outputs.py, pyproject.toml, AGENTS.md, tests/test_outputs.py (one test replaced, see below)

## Tests (all written first)
- tests/test_html_template.py (5). Seen failing first: test_template_is_package_data (KeyError
  'package-data') and test_html_one_pass_fill (the blob was put into the script src). Regression guards
  that passed at once by design: test_template_slots, test_template_never_uses_innerhtml,
  test_outputs_never_imports_enrich.
- tests/test_html_data.py (9). All seen failing first: test_file_edges_fixture, test_html_lod_file_edges,
  test_html_lod_by_edges, test_html_default_not_lod, test_html_node_fields, test_html_edge_ids,
  test_html_top_level, test_html_sem_passthrough_and_escaping, test_export_passes_sem.
- tests/test_outputs.py: test_html_large_graph_opens_file_level (seen failing first). The other Phase 5
  html tests are unchanged and pass.

## D-xx honoured
D-01 (still vis-network 9.1.9 from unpkg; the page is unchanged). D-02 (no CLI change; `sem` is an
optional argument, and cli wiring is 08-03). D-03 (the file-level view replaces the files-only cut;
file_edges is precomputed in Python). D-04 (fields only added; Phase 5 html_data tests untouched).
D-05 (stdlib only: importlib.resources, re, tomllib in tests). D-06 (no new script URL). D-07 (guard
test: no innerHTML, outerHTML, insertAdjacentHTML, document.write, eval( or multi: in the template).
D-08 (graph.json and semantic.json untouched). outputs.py does not import enrich.

## Deviations
- [D-03 planned replacement] tests/test_outputs.py::test_html_large_graph_shows_files_only was REPLACED in
  place by test_html_large_graph_opens_file_level, marked with the comment
  "# Phase 8 D-03 replaced test_html_large_graph_shows_files_only". It picks file/external nodes by
  `group` (== kind), because the `kind` field only arrives in 08-01-3. No other expected value was edited.
- [Rule 1] A shell heredoc turned the ` `/` ` escapes in tests/test_html_data.py into raw
  U+2028/U+2029 characters. They were rewritten as ASCII escapes, so all touched files are ASCII-only.
- [Rule 3] The template load uses `_TEMPLATE_FILE = ...joinpath("templates/graph.html")` on one line, so
  the plan's key-link pattern matches. The fill lives in `_fill(blob)` and is the contract's re.sub with
  a dict lookup.
- One full-suite run showed 2 transient failures, and an immediate rerun was clean. They were most likely
  08-02 mid-edit on its own files; I fixed nothing outside my plan.
- Note for 08-04: the page JS is still the Phase 5 script, so until 08-04 rewrites it, a LOD page draws
  every node.

## Result
`conda run -n repo-reaper pytest -q` -> 164 passed in 1.77s (includes 08-02's tests in the shared tree)

Self-Check: PASSED
