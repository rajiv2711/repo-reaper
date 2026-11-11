# Phase 8: Interactive HTML view - CONTEXT (discuss step)

Locked 2026-11-11 with the user. D-xx items are non-negotiable for research, plan, execute and verify.
Items in <deferred> are never built in this phase.

<domain>
Phase boundary = the AGENTS.md "Phase 8: Interactive HTML view" entry (fixed; new ideas go to <deferred>).
Goal: graph.html becomes the way to explore a mapped repo: find any symbol, see what it is, what touches it
and what the LLM layer says about it, on repos of any size.
Requirements:
- VIEW-01 search (id, name, signature; ranked list as you type).
- VIEW-02 click -> side panel (kind, signature, file:line, doc, file summary + role, callers/callees/imports/
  imported-by/bases with confidence, all clickable).
- VIEW-03 focus on a node's 1-3 hop neighbourhood.
- VIEW-04 filters by node kind, edge kind and confidence (INFERRED and AMBIGUOUS drawn differently), plus a
  legend with counts.
- VIEW-05 semantic layer when .reaper/semantic.json exists: group colours, summaries, architecture tab whose
  evidence ids focus their nodes, stale entries marked. Without semantic.json the page is the structural view
  and shows no LLM text.
- VIEW-06 big repos: level of detail (file-level view with aggregated edges, expand a file) instead of the
  all-or-nothing files-only cut; the layout stops after it stabilizes.
- VIEW-07 safety: data text reaches the DOM only via textContent, template filled in one pass, a visible
  message when the CDN script fails.
Success truths (must be TRUE):
1. On this repo, typing "run_gr" lists reaper/enrich.py::run_groups; picking it focuses the node, and the panel
   shows its signature, doc, file summary and clickable callers/callees.
2. Hop focus (1-3) and the node-kind, edge-kind and confidence filters combine, and the legend counts match
   what is shown.
3. With semantic.json, nodes are coloured by group and every architecture evidence id focuses its node. With
   semantic.json absent, `reaper export` still works and the page has no LLM text.
4. A synthetic repo above the size budget opens as a file-level view with aggregated edges; a file expands to
   its symbols; the CPU goes idle once the layout settles.
5. A docstring or summary containing "<b>x</b></script>" is shown as plain text.
</domain>

<decisions>
- D-01 Library: stay on vis-network 9.1.9 from unpkg
  (https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js). User said "choose for me"; chosen
  because the Phase 5 tests pin it, it draws dashed edges natively and it covers every VIEW-xx.
- D-02 Semantic layer: `reaper export` reads .reaper/semantic.json when present, with NO CLI change. User
  addition: the LLM layer must be HIDEABLE in the page: one toggle hides all LLM text (summaries, roles,
  group names, architecture tab) and switches group colours back to the structural colouring. LLM text is
  always labelled "LLM-generated"; stale entries are marked "stale". Without semantic.json the page shows no
  LLM text and no toggle.
- D-03 Big repos: level of detail. Above a nodes+edges budget the page opens a file-level view with aggregated
  file->file edges (width = count); double-clicking a file expands it in place to its symbols. The file-level
  data is precomputed in Python. This replaces today's files-only cut, so
  tests/test_outputs.py::test_html_large_graph_shows_files_only may be replaced (log it in SUMMARY); all other
  Phase 5 html tests stay unchanged.
- D-04 Embedded JSON: keep today's node and edge objects (as produced by _vis_node/_vis_edge) and only ADD
  fields/keys, so the Phase 5 html tests (html_data helper) stay untouched. No compact-array payload.
- D-05 No new Python dependencies (stdlib + networkx only; numpy is not in the env).
- D-06 Scripts only from unpkg or jsdelivr, with exact versions.
- D-07 Data or LLM text enters the DOM only via textContent / createElement, never innerHTML (nor
  outerHTML, insertAdjacentHTML, document.write).
- D-08 graph.json and semantic.json formats unchanged.

### Claude's discretion
- UI layout (toolbar, side panel, tabs), colours, the exact level-of-detail budget (roughly 1500 nodes or
  5000 edges as a starting point), hop default, debounce timing.
- Whether HTML_TEMPLATE moves to its own file (e.g. reaper/templates/graph.html). If it does, ship it as
  package data (pyproject.toml) and load it with importlib.resources.
- Deep link (#node=<id>&hops=N) - optional, nice to have.
</decisions>

<canonical_refs>
- /home/keyward/Rajiv_personal/repo-reaper/AGENTS.md (spec, data format, Phase 8 entry, session protocol)
- /home/keyward/Rajiv_personal/repo-reaper/reaper/outputs.py: MAX_HTML_NODES (l.27), VIS_NETWORK_URL (l.28),
  degrees (l.90), HTML_TEMPLATE (l.199), _vis_node (l.266), _vis_edge (l.281), graph_html (l.287),
  export (l.307)
- /home/keyward/Rajiv_personal/repo-reaper/reaper/cli.py: cmd_export (l.52)
- /home/keyward/Rajiv_personal/repo-reaper/reaper/enrich.py: load_semantic (l.80), file_input (l.111),
  cache_key (l.125), communities (l.233), _group_plan (l.285), _fresh (l.399)
- /home/keyward/Rajiv_personal/repo-reaper/tests/test_outputs.py: html_data helper (l.168), html tests
  (l.174-215: loads_vis_network_and_embeds_graph, dashed_when_not_extracted, large_graph_shows_files_only,
  escapes_script_end_in_docs)
</canonical_refs>

<code_context>
- reaper/enrich.py imports reaper.outputs, so outputs must NEVER import enrich (import cycle). Semantic data
  reaches outputs as a plain dict argument built by a helper in enrich and passed in by cli.cmd_export.
- .reaper/ is gitignored; tests copy the fixture to tmp_path first.
- Tests never call a real Ollama; no LLM call is needed for this phase at all.
- Env: conda run -n repo-reaper pytest -q (140 passed at the start of this phase).
</code_context>

<deferred>
- Path tracing between two nodes.
- Group hulls (drawn regions around groups).
- Dark mode.
- An offline (inlined) copy of the vis-network library.
- Precomputed layout (networkx spring_layout needs numpy, not in the env).
- Compact array payload (D-04 chose objects).
- Hard payload ceiling for huge repos (embed files only above N nodes): user chose no ceiling in research
  (2026-11-11); always embed everything.
</deferred>
