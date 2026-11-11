---
phase: 8
status: passed
verified: 2026-11-11
score: 18/18 must-have truths verified (T4 CPU idle confirmed by the user in the browser); gaps G1, G2 closed
---

**Human verification (2026-11-11): the user ran the 9-item browser checklist below on the repo, no-sem copy, 400-module
synthetic and AMBIGUOUS/hostile-text pages and replied "all pass" (this includes accepting the log-scale bundle width, D-03).**

# Phase 8: Interactive HTML view - VERIFICATION

Independent goal-backward check of commit 48676c7 against AGENTS.md Phase 8, 08-CONTEXT D-01..D-08 and the 08-PLAN
must_haves. The SUMMARY self-checks were not trusted. The code, the tests and real CLI runs were checked in scratch copies.
The repo's tests never execute `start()`, `refresh()`, `pick()` or the DOM renderers: `boot()` finds no `vis` in node.
So I also ran the real page script in node with a fake DOM and a fake vis (DataSet/DataView/Network). The fake throws like
vis 9.1.9 on unloaded or non-array ids. Scripts are in the session scratchpad `verifier/` folder
(harness.js, sc_main.js, sc_lod.js, probe_*.py).

## Truths
Truths T1-T5 are the AGENTS.md success truths. T6-T18 are the other must_haves truths, in plan order.

| # | Truth (short) | Status | Evidence |
|---|---|---|---|
| T1 | "run_gr" lists run_groups; pick focuses; panel shows sig, doc, file summary, clickable callers/callees | VERIFIED (visual: human) | Harness on a full clone with the repo's semantic.json. Rows: `run_groups`, then `run_groups.store`. Enter picks it: center = run_groups, focus 10, fit of 10 loaded ids. Panel shows the signature, `reaper/enrich.py:300`, the doc, "File summary - LLM-generated" with a `stale` badge, role and summary, then callers (2) and callees (7). Clicking a caller picks it. Tests test_js_rank and test_js_relations pass. |
| T2 | Hop 1-3 + node/edge/confidence filters combine; legend counts = shown | VERIFIED (visual: human) | Harness: the legend DOM counts equal what the DataViews draw, and no drawn edge has an unloaded end. Checked in 9 non-LOD states (load, pick, hops 2/3, calls off, + function off, + INFERRED off, clear, all on) and 10 LOD states. Tests test_js_view_counts and test_js_lod_counts pass. |
| T3 | Group colours; every evidence id focuses; no semantic.json -> export works, no LLM text | VERIFIED (visual: human) | Harness: enrich.py is coloured `#1f77b4` with the layer on and `#4c78a8` with it off. All 7 evidence chips set center = selected = id and fit an id list that contains it. Without semantic.json: `data.sem` is null, the toggle and tab-arch stay hidden, there is no visible `.llm` element, and "LLM-generated" appears 0 times in the DOM. |
| T4 | Above budget: file-level + aggregated edges; file expands; CPU idle | PARTLY: data and logic VERIFIED, CPU idle HUMAN | Synthetic repo (400 modules): lod true, 7201 nodes, 12800 edges, 1200 file_edges summing to the 6000 non-contains edges; the page opens with 401 nodes and 1200 bundles. A double-click expands 17 symbols in a ring within 400 px of the file, and the file does not move; a second double-click collapses. Physics goes off at stabilizationIterationsDone and is never set on again outside Re-layout. |
| T5 | `<b>x</b></script>` in a doc/summary shown as plain text | VERIFIED (visual: human) | probe_escape.py through the CLI: `</script><b>` and `<b>` are absent from the HTML and the strings round-trip. Data text reaches the DOM only through `el()`/textContent (graph.html:417-422). vis 9.1.9 Popup.setText uses `innerText` for string titles (checked in its source). |
| T6 | LLM toggle hides all LLM text, restores kind colours; all LLM text labelled; stale marked; no toggle without sem | VERIFIED | Harness: all 27 LLM strings (summary, role, group names and summaries, overview, patterns, decisions) sit under a `.llm` element, and `body.llm-off .llm` hides them (graph.html:51). The 3 headings say "LLM-generated". Toggling off leaves the arch tab and switches to details. |
| T7 | Legend lists every group: swatch, name, file count, stale, summary | VERIFIED | renderGroupLegend at graph.html:524-547; test_js_groups; harness shows 6 groups. |
| T8 | No sem: export HTML byte-identical to graph_html(load) and graph_html(load, None); sem null | VERIFIED | probe_escape.py; test_export_without_semantic_is_byte_identical. |
| T9 | Phase 5 html tests unchanged except the D-03 replacement | VERIFIED | `git diff HEAD~1 -- tests/`: only test_outputs.py changed, in 1 hunk, which is the replacement. It is logged in 08-01-SUMMARY. |
| T10 | Node and edge objects only gain keys (D-04); everything embedded in both modes | VERIFIED | `_vis_node`/`_vis_edge` are byte-identical to HEAD~1. Key sets are as in the contract. The LOD page embeds all 7201 nodes and 12800 edges. |
| T11 | One-pass fill; no raw `<`, U+2028 or U+2029 in the blob | VERIFIED | outputs.py:209-215 and 289-291; test_html_one_pass_fill. probe: a U+2028 docstring gives an escaped blob. |
| T12 | No innerHTML etc. (D-07); only vis 9.1.9 unpkg and jsDelivr (D-06); message when both fail | VERIFIED | grep: 0 hits for innerHTML, outerHTML, insertAdjacentHTML, document.write, eval(, new Function. Only 2 URLs. The jsDelivr SRI equals the real file's sha384 (downloaded from both CDNs), and jsDelivr sends ACAO `*`. cdnFailed is at graph.html:668. Orchestrator, headless Chrome (`--host-resolver-rules`, `--dump-dom`): unpkg blocked -> jsDelivr draws (status "432 nodes, 1142 edges shown", 1 canvas); both blocked -> `<div id="status" class="error">Could not load vis-network 9.1.9 from unpkg.com or cdn.jsdelivr.net (offline or blocked): the graph cannot be drawn.`, 0 canvas. |
| T13 | Evidence ids exist in graph; dropped listed | VERIFIED | probe: evidence `[C]` and `[app/models.py]`; dropped `['app/ghost.py::nope','old/gone.py']`. On the clone, all 7 ids are nodes. |
| T14 | Physics off at stabilization; only Re-layout turns it on, off after stabilized or 3 s | VERIFIED | graph.html:655-660 and 697-701; test_template_physics_never_back_on. Harness setOptions log: false, true (Re-layout), false (timer). vis 9.1.9 source: setOptions with enabled false sets physicsEnabled false, so _finalizeStabilization's startSimulation is a no-op. |
| T15 | LOD refresh re-applies bundleStyle | VERIFIED | graph.html:641. Harness: the f0 title follows the calls-off and EXTRACTED-off filters. |
| T16 | pick order and fit flag; click = pick(id, false); doubleClick toggles and clears focus | VERIFIED | test_js_pick_fit_flag and test_js_toggle_expand. Harness: a canvas click makes 0 fits. vis doubleClick reads `p.nodes` from the selection, which pick keeps on the file. |
| T17 | Never-skip Python test per VIEW-xx; JS tests skip with a reason, or fail under REAPER_REQUIRE_NODE=1 | VERIFIED | All tests named in the plan's coverage table exist. With node removed from PATH: "SKIPPED [2] ... node >= 18 not found", and with the variable set, "2 failed". |
| T18 | graph.json, semantic.json and CLI unchanged; no new dependency; outputs never imports enrich | VERIFIED | graph/discover/extract_py/resolve/llm have no diff and cli.py has no argparse change. pyproject only gains package-data; environment.yml is untouched. test_outputs_never_imports_enrich passes. probe: semantic.json bytes unchanged after export. |

## Artifacts and key links
All 15 artifacts exist with their `contains` strings, with one exception: the literal `enrich.view_semantic(args.repo, graph)` is
not in cli.py. 08-03 wrapped the call for error handling: cli.py:70 calls `_view_semantic(args.repo, graph)`, which calls
`enrich.view_semantic(repo, graph)` at cli.py:56. The wiring works (test_export_with_semantic_embeds_view and the CLI probes);
only the plan's literal pattern is stale. The other 14 key links match: cli.py:71, outputs.py:303/214/205, enrich.py:605/630
and graph.html:133/365/252/443/704/736/641/762. Handlers are bound in start(): doubleClick, click, hops, filters, search
input and Enter, tabs, clear-focus, Escape, fit, collapse-all, relayout, hashchange and llm-toggle.

## Decisions D-01..D-08
D-01 PASS: vis-network 9.1.9 from unpkg. D-02 PASS: no CLI change; the export reads semantic.json; one toggle; labels and
stale marks; no toggle without sem. D-03 PASS: precomputed file_edges, double-click expand, replaced test logged. Interpretation
to confirm (08-04 log): "width = count" is drawn as `min(8, 1 + log2(count))` (graph.html:239). The width grows with the count
and the exact count is in the tooltip. D-04 PASS. D-05 PASS. D-06 PASS: exact versions and SRI. D-07 PASS. D-08 PASS.
Claimed deviations (08-01..06) checked: none contradicts a D-xx. Nothing from <deferred> was built.

## Phase 5 test integrity
`git show HEAD~1:tests/test_outputs.py` compared with HEAD: the html_data helper and the kept tests
(loads_vis_network_and_embeds_graph, dashed_when_not_extracted, escapes_script_end_in_docs) are unchanged. The only change is the
documented replacement of test_html_large_graph_shows_files_only by test_html_large_graph_opens_file_level. No other expected
value was edited.

## Test run
- `REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q` -> `196 passed in 6.13s` (node v18.19.1)
- `conda run -n repo-reaper pytest -q -rs` -> `196 passed in 6.16s` (0 skipped; 140 at phase start + 56 new)

## Probes run
- `reaper map` and `reaper export` on a copy of reaper/ + pyproject.toml (153 nodes, 367 edges): run_groups has deg 8, line 300, its
  signature and doc; calls in from cli.py::_enrich_groups; 7 callees.
- Full `git clone` + `reaper map`, plus a copy of the repo's semantic.json: export took 1.17 s; sem holds 25 files (4 stale), 6 groups
  (5 stale) and an architecture section (stale, 3 patterns, 3 decisions, 7 evidence ids, all in the graph). The page is 457 KB.
- Fixture copy plus a hostile evil.py docstring and semantic.json: see T5, T8 and T13. A corrupt semantic.json gives a warning on
  stderr, rc 0 and sem null.
- Synthetic repo (08-RESEARCH generator, 400 modules): map + export in 1.2 s; page 3.9 MB; see T4.
- Harness (node + fake vis/DOM) on the clone, the reaper copy and the synthetic pages: see T1-T4, T6, T14-T16. No runtime error in start().
- Edge cases: `reaper export` exits 1 with a traceback for an unreadable semantic.json and for a non-string summary (gaps G1 and G2).

## Gaps
Neither gap affects a must-have truth or a D-xx, so the status stays human_needed. Both are regressions in edge cases: before
Phase 8, `reaper export` never read semantic.json.

**G1. reaper/cli.py:55-61: an unreadable semantic.json crashes export.** `_view_semantic` catches only ValueError and
AttributeError. A PermissionError (or any other OSError) gives rc 1 and a traceback, which contradicts its own docstring at
l.53-54 ("cannot be read ... export still writes the structural page").
```python
# before
    except AttributeError:  # enrich.load_semantic: valid JSON, but not an object
        problem = "is not a JSON object"
# after
    except AttributeError:  # enrich.load_semantic: valid JSON, but not an object
        problem = "is not a JSON object"
    except OSError as err:  # e.g. PermissionError on .reaper/semantic.json
        problem = f"cannot be read ({err.strerror})"
```
**G2. reaper/enrich.py:272-274 (group_input, reached through view_semantic -> _group_plan): a hand-edited non-string summary
crashes export.** `{"files": {"app/service.py": {"summary": 5}}}` raises `TypeError: object of type 'int' has no len()`.
view_semantic otherwise reads malformed entries as missing (08-02). Well-formed files keep the same text and cache keys.
```python
# before
        summary = entry.get("summary")
        if summary:
# after
        summary = entry.get("summary")
        if isinstance(summary, str) and summary:
```
**Gap closure (orchestrator, same day).** Both fixes were applied as shown above (G1 uses `err.strerror or err`). Regression
tests were written first and seen failing (IsADirectoryError and TypeError at enrich.py:274): test_export_unreadable_semantic_warns
(semantic.json is a directory, so an OSError even as root) and test_export_non_string_summary_does_not_crash, both in
tests/test_export_semantic.py. After the fix: `REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q` -> `198 passed in 6.12s`.
Well-formed summaries produce the same group_input text, so cache keys are unchanged.

**Headless pre-check (orchestrator, google-chrome --headless=new --dump-dom, 20 s virtual time).** No console errors and 1
canvas on all 4 pages: repo (status "432 nodes, 1142 edges shown (1142 lines)", toggle visible), no-sem copy (toggle `hidden`,
the only "LLM-generated" strings are the hidden tab-arch button and JS literals), synthetic 400 modules ("401 nodes, 6000 edges
shown (1200 lines) - file-level view ..."), amb repo (9 nodes, 10 edges: 1 INFERRED, 1 AMBIGUOUS). This does not replace the
human checklist below (CPU idle, visuals, clicks).

Notes (contract behaviour, not defects): after "Collapse all" the selected symbol stays drawn alone, because of the selected
exemption (harness: 402 = 401 files + 1). The hop BFS walks through node kinds that are hidden (the contract filters only on
edge kind and confidence), so at hops 2-3 a node can appear whose link to the centre is hidden.

## Human verification needed (08-RESEARCH checklist, adapted)
Setup: `reaper map . && reaper export .` on this repo (semantic.json present). Open `.reaper/graph.html` in a browser with DevTools.
1. **Load and stop.** Expect no console errors. The status shows "Laying out n / 100 ...", then
   "432 nodes, 1142 edges shown (1142 lines)". Once the layout settles, CPU use drops to idle (Task Manager or the DevTools
   Performance tab). Variant: block unpkg.com in DevTools: the status shows "Loading vis-network 9.1.9 from cdn.jsdelivr.net ..."
   and the graph still draws. Block both CDNs: a red "Could not load vis-network 9.1.9 from unpkg.com or cdn.jsdelivr.net ..."
   appears.
2. **Search.** Type `run_gr`: after about 120 ms, `run_groups` is the first row, followed by `run_groups.store`. Press Enter (or
   click the row): the view fits a 10-node focus, the panel opens, and the URL becomes
   `#node=reaper%2Fenrich.py%3A%3Arun_groups&hops=1`.
3. **Panel.** It shows the signature, `reaper/enrich.py:300` and the doc. Below them is a purple block "File summary -
   LLM-generated, model devstral-small-2:24b" with a red `stale` badge, the role and the summary. Then come callers (2), callees
   (7), contains and contained in, each with a confidence badge. Clicking an entry selects that node and fits it.
4. **Focus and filters.** Hops 1/2/3, Clear focus and Esc work. With a focus active, toggle node-kind, edge-kind and confidence
   boxes: the counts and the status line follow every change, and nodes return to their old places. Dashes: INFERRED is
   dashed (8 calls in this repo). AMBIGUOUS is dotted and faded, but this repo has none, so use the 3 files of
   tests/test_resolve.py::test_last_name_matching in a scratch dir.
5. **LLM layer.** Nodes are coloured by group (6 groups). The legend has "Groups - LLM-generated, model ...", and each row shows
   a swatch, name, file count, `stale` and summary. In the Architecture (LLM-generated) tab, each of the 7 chips selects and fits
   its node and switches to Details. Unticking "LLM layer" hides the summaries, roles, group section and Architecture tab and
   restores the kind colours; ticking it again brings them back.
6. **No semantic layer.** On a fresh copy without semantic.json there is no "LLM layer" box, no Architecture tab and no
   LLM text.
7. **Big repo.** Run gen.py with 400 modules, then map and export. The page (3.9 MB) opens with 401 file boxes and 1200 bundles.
   A bundle's width grows with its count; confirm the log scale is acceptable for D-03. Tooltips read "a -> b: n edges (...)".
   Double-clicking a file shows its symbols in a ring and the file does not move; a second double-click collapses it, and
   "Collapse all" collapses everything. The CPU goes idle afterwards, Re-layout stops within 3 s, and typing in search stays
   smooth.
8. **Deep link.** Open `graph.html#node=reaper%2Fenrich.py%3A%3Arun_groups&hops=2`. After the layout, hop 2 is active and
   run_groups is selected and fitted. A reload keeps this, and editing the hash re-applies it.
9. **Hostile text.** Open the page made by probe_escape.py (evil.py docstring plus a hostile semantic.json).
   `<b>x</b></script>` shows as literal text in the panel doc and summary, the node tooltip and the search row. Nothing renders
   bold and the page does not break.
