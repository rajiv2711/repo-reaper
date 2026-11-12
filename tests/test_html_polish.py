"""Phase 13: UI/UX polish of graph.html (toolbar + status, compact LLM groups, details panel + keys,
calmer Tree edges).

Expected values are written by hand from tests/fixtures/sample_py and phases-archive:docs/phases/13-ui-polish/13-PLAN.md
(not printed from the code). `test_template_*` never skip; `test_js_*` run the page script in node
(see test_html_template.py).
"""

import json
import math
import re

import pytest
from test_html_template import AMB, fixture_html, fn_body, html_data, run_js, write
from test_html_theme import LIGHT_TOKENS
from test_html_tree import run_modes

from reaper import outputs
from reaper.graph import build

M, R, S, U = "app/models.py", "app/repository.py", "app/service.py", "app/utils.py"
C = f"{S}::UserService.create"
LOG = f"{S}::UserService.log"

# degree = imports + inherits + calls edges in and out (contains not counted; externals get none, as in
# outputs.degrees / SUMMARY.md), from FIXTURE_EDGES in tests/test_resolve.py: create 6; repository.py
# 3 out + 1 in; service.py 4 out; utils.py 2 in + 1 out; then degree 2 in id order. 11th: Entity (1).
TOP10 = [C, R, S, U, M, f"{M}::User", f"{M}::User.label", f"{R}::UserRepository.save",
         f"{U}::normalize", f"{U}::validate"]

# a key press on the page: target tag, optional modifiers; preventDefault is logged
KEY = ('const seen = []; const key = (k, tag = "BODY", extra = {}) => onKey({key: k, target: {tagName: tag}, '
       'preventDefault() { seen.push("prevent " + k); }, ...extra}); ')


# ---------------------------------------------------------------- details panel + keys

def test_js_top_nodes(sample_repo):
    html = fixture_html(sample_repo)
    assert run_js(html, "topNodes(10)") == TOP10
    assert run_js(html, "topNodes(11)") == TOP10 + [f"{M}::Entity"]
    # degree 0 is left out: app/__init__.py, class UserService, UserRepository.dump, ext:os, ext:json
    assert len(run_js(html, "topNodes(100)")) == 20


def test_js_page_keys(sample_repo):
    html = fixture_html(sample_repo)
    got = run_modes(html, 'graphLaidOut(); ' + KEY +
                    'const s = document.getElementById("search"); s.focus = () => seen.push("focus"); '
                    'key("t"); const a = [mode, els.relayout.hidden, nets[1].opts.interaction.dragNodes]; '
                    'key("g"); const b = [mode, els.relayout.hidden]; '
                    'const f0 = nets[0].calls.length; key("f"); const fits = nets[0].calls.slice(f0); '
                    'key("/"); key("t", "INPUT"); key("t", "SELECT"); key("t", "BODY", {ctrlKey: true}); '
                    'key("t", "BODY", {metaKey: true}); const c = mode; '
                    f'pick({json.dumps(C)}); const d = state.center; key("Escape", "INPUT"); '
                    'return [a, b, fits, seen, c, d, state.center];')
    assert got == [["tree", True, False], ["graph", False], [["fit", "all"]], ["prevent /", "focus"], "graph",
                   C, None]


def test_js_search_keys(sample_repo):
    html = fixture_html(sample_repo)
    got = run_modes(html, 'graphLaidOut(); document.createDocumentFragment = () => stubEl(); '
                    'const s = document.getElementById("search"); s.value = "user"; renderResults("user"); '
                    'const k = key => searchKey({key, preventDefault() {}}); const h0 = hits.hl, n = hits.ids.length; '
                    'k("ArrowDown"); k("ArrowDown"); const a = hits.hl; '
                    'k("ArrowUp"); k("ArrowUp"); k("ArrowUp"); const b = hits.hl; '
                    'k("ArrowDown"); k("ArrowDown"); k("Enter"); const c = state.selected === hits.ids[2]; '
                    'for (let i = 0; i < 50; i++) k("ArrowDown"); const d = hits.hl === hits.ids.length - 1; '
                    's.value = "normalize"; k("Enter"); '
                    'return [n >= 3, h0, a, b, c, d, state.selected, hits.hl];')
    # a box changed without a new list (debounce pending): Enter renders it and picks its first row
    assert got == [True, 0, 2, 0, True, True, f"{U}::normalize", 0]


def test_template_details_and_keys():
    tpl = outputs.HTML_TEMPLATE
    css = tpl[tpl.index("<style>"):tpl.index("</style>")]
    assert re.search(r"\.mono \{[^}]*ui-monospace", css)
    assert '"mono' in fn_body(tpl, "renderDetails")
    for s in ("function renderHome(", "function topNodes(", "function onKey(", "function searchKey(",
              'document.addEventListener("keydown", onKey)', 'search.addEventListener("keydown", searchKey)',
              "Most connected"):
        assert s in tpl, s
    # key hints in the button tooltips
    # (the Graph button's markup is pinned by Phase 9, so its tooltip is set in initModes)
    assert '"mode-graph").title = "Graph view (g)"' in fn_body(tpl, "initModes")
    for s in ('id="fit" title="Fit the view (f)"', 'title="Editor-style tree, left to right (t)"'):
        assert s in tpl, s


# ---------------------------------------------------------------- toolbar + status

def test_js_status_and_note(sample_repo, monkeypatch):
    html = fixture_html(sample_repo)
    got = run_modes(html, 'graphLaidOut(); return [els.status.textContent, els.status.title, '
                          'els["lod-note"].hidden];')
    # 25 nodes, 18 contains + 21 other edges, all drawn
    assert got == ["25 nodes, 39 edges shown (39 lines)", "25 nodes, 39 edges shown (39 lines)", True]
    lod = fixture_html(sample_repo, monkeypatch, 24)
    note = html_data(lod)["note"]
    got = run_modes(lod, 'graphLaidOut(); return [els.status.textContent, els["lod-note"].hidden, '
                         'els["lod-note"].title];')
    assert "file-level" not in got[0] and got[0].endswith(" lines)")
    assert got[1:] == [False, note]


def test_template_toolbar():
    tpl = outputs.HTML_TEMPLATE
    css = tpl[tpl.index("<style>"):tpl.index("</style>")]
    assert tpl.count('id="lod-note"') == 1
    assert re.search(r"#status \{[^}]*white-space: nowrap", css)
    assert re.search(r":focus-visible \{[^}]*var\(--link\)", css)
    # light and dark come from the Phase 11 tokens only (their sets are pinned in test_html_theme.py)
    assert set(re.findall(r"var\((--[\w-]+)\)", css)) <= set(LIGHT_TOKENS)
    assert '"relayout").hidden = m === "tree"' in fn_body(tpl, "setMode")


# ---------------------------------------------------------------- compact LLM groups

def test_template_compact_groups():
    body = fn_body(outputs.HTML_TEMPLATE, "renderGroupLegend")
    for s in ('el("details", "grp")', 'el("summary"', '"llm gsum"', '"badge stale"', "title = "):
        assert s in body, s


# ---------------------------------------------------------------- calmer Tree edges

def test_js_tree_edges_calm(sample_repo, tmp_path, monkeypatch):
    html = fixture_html(sample_repo)
    edge = f'D.edges.find(e => e.from === {json.dumps(C)} && e.to === {json.dumps(LOG)}).id'
    got = run_modes(html, f'graphLaidOut(); setMode("tree"); const id = {edge}; const t = tedges.m.get(id); '
                          'const b = tedges.m.get("b:app/models.py"); const g = edges.m.get(id); '
                          'const v1 = {width: 1, opacity: 0.3}; treeEdgeChosen(v1, id, true, false); '
                          'const v2 = {width: 1, opacity: 0.3}; treeEdgeChosen(v2, id, false, true); '
                          'const v3 = {width: 1, opacity: 1}; treeEdgeChosen(v3, "b:app/models.py", true, false); '
                          'return [t.color, t.width, STRONG.get(id), b.color, b.width, g.color, g.width, '
                          'v1, v2, v3, nets[1].opts.edges.chosen.edge === treeEdgeChosen, '
                          '"chosen" in nets[0].opts.edges];')
    assert got == [{"color": "#f58518", "opacity": 0.3}, 1, {"width": 1, "opacity": 1}, "#b0b0b0", 1,
                   "#f58518", None, {"width": 2, "opacity": 1}, {"width": 1, "opacity": 1},
                   {"width": 2, "opacity": 1}, True, False]
    # Phase 8 dashes stay; AMBIGUOUS keeps its half (0.5 x 0.3)
    amb = outputs.graph_html(build(write(tmp_path / "amb", AMB)))
    got = run_modes(amb, 'graphLaidOut(); setMode("tree"); '
                         'return ["e21", "e22"].map(id => [tedges.m.get(id).color, tedges.m.get(id).dashes, '
                         'tedges.m.get(id).width, STRONG.get(id)]);')
    assert got == [[{"color": "#f58518", "opacity": pytest.approx(0.15)}, [2, 4], 1, {"width": 1, "opacity": 0.5}],
                   [{"color": "#f58518", "opacity": 0.3}, [8, 6], 1, {"width": 1, "opacity": 1}]]
    # file-level bundle f3 service.py -> models.py (calls 2 + imports 1: grey, 1 + log2(3) wide) and a folder
    # bundle (app/ closed: app/ -> ext:os, imports 2: blue, 1 + log2(2) wide), both after refresh()
    lod = fixture_html(sample_repo, monkeypatch, 24)
    got = run_modes(lod, 'graphLaidOut(); setMode("tree"); const f = tedges.m.get("f3"); '
                         'toggleClosed("dir:app/"); refresh(); const d = tedges.m.get("d:dir:app/ -> ext:os"); '
                         'return [f.color, f.width, STRONG.get("f3"), d.color, d.width, STRONG.get(d.id)];')
    assert got == [{"color": "#888", "opacity": 0.3}, 1, {"width": pytest.approx(1 + math.log2(3)), "opacity": 1},
                   {"color": "#4c78a8", "opacity": 0.3}, 1, {"width": 2, "opacity": 1}]
