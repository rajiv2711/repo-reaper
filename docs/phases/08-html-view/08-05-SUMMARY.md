# 08-05 SUMMARY: template search, panel, LLM layer

Plan 08-05 (wave 3, depends on 08-04). Requirements: VIEW-01, VIEW-02, VIEW-05, D-02, D-07. Status: done.

## Built
- 08-05-1 Search + pick + tabs (reaper/templates/graph.html):
  - `rank(q)`: name, id and signature are lower-cased once (`searchKeys`). Tiers: 1 name == q, 2 starts with, 3 contains, 4 id contains, 5 signature contains. Ties go to the higher deg, then the lower id. Capped at `MAX_RESULTS = 30`.
  - `#search` is debounced (`DEBOUNCE_MS = 120`). Result rows are li > button (label, kind, id), built with createElement + textContent in a DocumentFragment. A row click or Enter (first row) calls `pick(id)`.
  - `fitIds(V)` (only loaded ids, always an Array).
  - `function pick(id, fit = true)` in the contract order: renderDetails, showTab("details"), focusOn, `const V = refresh()`, selectNodes([id]), then `if (fit) net.fit({nodes: fitIds(V)})`.
  - `showTab(name)` uses the hidden attribute, marks the active tab button and remembers it in `activeTab`. #tab-details and #tab-arch are wired.
  - Canvas click: `net.on("click", p => { if (p.nodes.length) pick(p.nodes[0], false); })`.
- 08-05-2 Details panel:
  - `relations(id)` covers all D.edges: callers/callees, imports/imported by, bases/subclasses, contains/contained in. Each section is a list of [otherId, confidence], sorted by id.
  - `renderDetails(id)` uses `replaceChildren` and shows label, kind + id, signature, file:line and doc.
  - When `D.sem.files[fileOf(id)]` exists, it adds a `.llm` block titled "File summary - LLM-generated, model X", with a "stale" badge, the role and the summary.
  - It then shows the non-empty relation sections. Each row is a button (the other id, click -> pick(other)) plus a span.badge (confidence).
- 08-05-3 LLM layer:
  - `groupRows()` returns groups in numeric gid order (g1, g2, g10). `groupIndex(n)` uses a top-level `groupOf` index built from groupRows. `groupHeading()` returns "Groups - LLM-generated, model ...".
  - Group palette: GROUP_COLORS cycled. A file in no group is "#c7c7c7"; externals keep KIND_COLOR.
  - `setLLM(on)`: toggles `body.llm-off` (CSS `body.llm-off .llm {display:none}`), does one `nodes.update` with explicit colours (group palette or KIND_COLOR), and switches to Details if Architecture is open.
  - Legend section (class llm), only when there are groups: groupHeading(), then per group a swatch, the name, the file count, a "stale" badge and the summary (its own `.llm` element), plus a grey "no group" row.
  - Architecture tab (`renderArch`):
    - Heading "Architecture - LLM-generated, model X", with a stale badge.
    - Overview, then patterns and decisions; their evidence chips are buttons that call pick(id).
    - The line "N evidence ids not found in graph.json were dropped".
  - start() does the LLM wiring only when D.sem is set: unhide #llm-toggle, setLLM(true), and `addEventListener("change", ev => setLLM(ev.target.checked))` on `#llm-toggle input`.

Files changed: reaper/templates/graph.html, tests/test_html_template.py (8 new tests).
Tests added: test_js_rank, test_js_fit_ids, test_js_pick_fit_flag, test_template_search_strings, test_js_relations, test_template_panel_strings, test_js_groups, test_template_llm_strings. Each was written first from the values the plan pins, and failed before its implementation. None are regression guards.

## D-xx honoured
- D-02: all LLM text sits in `.llm` elements labelled "LLM-generated", and stale entries carry a "stale" badge. One checkbox hides them all, including the Architecture tab, and restores kind colours. With sem null there is no toggle, no legend groups and no Architecture tab.
- D-07: everything goes through createElement + textContent. There is no innerHTML, outerHTML, insertAdjacentHTML or document.write.
- D-01/D-06: the static `<script src="__VIS__"></script>` is byte-identical.
- D-04/D-08: the payload, graph.json, semantic.json and the CLI are untouched. D-05: no new dependency. The JS is ES2020 and runs on node 18.19.

## Deviations
- Logged as the plan requires: a canvas click calls `pick(id, false)`, which does not fit, unlike 08-RESEARCH P4 (fit on every pick).
  - Reason: vis 9.1.9 `fit()` is instant. A fit after the first tap of a double-click moves the file out from under the pointer, so `doubleClick` gets no node and the LOD expand breaks (truth 4, D-03).
  - Search rows, Enter, panel links and evidence chips still fit.
- [Rule 2] `pick()` returns early for an id that is not in `byId`. vis throws on unknown ids, and evidence or hash ids come from data.
- [Rule 1] My first badge CSS used `.badge[data-conf="INFERRED"]`, which broke the existing count==1 check in test_template_dom_hooks. I switched to the unquoted selector `.badge[data-conf=INFERRED]`. The existing test is unchanged.
- Discretion items (no rule): group colours are applied only when sem has at least one group, otherwise the kind colours stay. A grey "no group" legend row. A "no match" result row. Singular wording "1 evidence id ... was dropped".
- No transcription errors against the plan's pinned values. No Rule 4 stop. No blockers.

## Verification
- `conda run -n repo-reaper pytest -q` -> 193 passed in 4.12s
- `REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q` -> 193 passed in 5.17s
- Headless Chrome smoke test on a scratchpad copy of this repo (429 nodes, 1134 edges), with a hand-built sem containing "<b>x</b></script>":
  - Typing "run_gr" lists reaper/enrich.py::run_groups first. Enter selects it, focuses 10 nodes, and the panel shows the signature, file:line, doc, the labelled file summary and 11 relation buttons.
  - The text appears literally (0 `<b>` elements).
  - The toggle off leaves 0 visible `.llm` elements and returns the kind colour; on brings them back.
  - Evidence chips pick their node.
  - The plain page has no toggle and no Architecture tab.
  - LOD (MAX_HTML_NODES=50): picking a symbol expands the focused files, and select and fit do not throw.
  - The repo's .reaper/ was not touched.

Self-Check: PASSED
