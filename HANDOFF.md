# HANDOFF
Phase 5 | status: done

## Done this session
- tests/test_outputs.py written FIRST (23 tests, hand-derived values): exact TREE.txt of the fixture, SUMMARY
  stats/top-10 (in/out/total)/externals/cycles, graph.html embedded data + dashes, export + query via the CLI.
- reaper/outputs.py: tree_text / file_outline(graph, path) (one TREE block; reuse it for the Phase 6 outline),
  summary_md, degrees / most_connected (imports+inherits+calls only, no externals), import_cycles (networkx
  SCCs + one shortest cycle through the smallest path), graph_html, export, find_nodes, query, format_query.
- graph.html: vis-network 9.1.9 from unpkg, data in <script id="graph-data" type="application/json"> with "<"
  escaped, dashed = not EXTRACTED, edge-kind checkboxes, find box. Over MAX_HTML_NODES=3000 nodes it draws files
  + externals only, with a note (stdlib: 17 MB -> 816 KB). Headless Chrome render checked by eye.
- cli.py: `reaper export` (writes .reaper/TREE.txt, SUMMARY.md, graph.html), `reaper query callers|callees|deps
  NAME [--json]`; both exit 1 with "run `reaper map`" when graph.json is missing; no match -> exit 1.
- NAME lookup, first non-empty tier: exact id; qualname / module.qualname / module / external name; last name
  part (symbol name or last module part, e.g. "outputs"). deps of a symbol = deps of its file; shows both
  imports and imported_by.
- Mutation checks: no dashes, contains in degree, no "<" escape, skipping exact tier -> each fails tests.

## Exact next step
Phase 6: tests first with a mocked llm (no Ollama) for reaper/llm.py + enrich --pass files; build the per-file
input from outputs.file_outline + source; --limit can rank files with outputs.degrees.

## Blockers: none
Notes: SUMMARY lists at most 5 files per cycle group / external (", ... (+N more)").

## Verify
conda run -n repo-reaper pytest -q                          -> 80 passed
conda run -n repo-reaper reaper map . && reaper export .    -> 212 nodes, 482 edges; 3 files written
conda run -n repo-reaper reaper query . deps outputs        -> imports discover.py, graph.py + 5 ext
