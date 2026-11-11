"""Phase 9: Tree mode of graph.html (folders -> files -> classes/functions -> methods, left to right).

Expected rows are written by hand from tests/fixtures/sample_py (not printed from the code).
`test_template_*` never skip; `test_js_*` run the page script in node (see test_html_template.py).
"""

import json

from test_html_template import AMB, SEM, fixture_html, fn_body, html_data, run_js, write

from reaper import outputs
from reaper.graph import build

# (id, depth, row) of tests/fixtures/sample_py with everything shown: one folder, files A-Z
# ("__init__" sorts before "models"), symbols in source order, externals after one blank row.
FIXTURE_TREE = [
    ("dir:app/", 0, 0),
    ("app/__init__.py", 1, 1),
    ("app/models.py", 1, 2),
    ("app/models.py::Entity", 2, 3),
    ("app/models.py::Entity.__init__", 3, 4),
    ("app/models.py::Entity.describe", 3, 5),
    ("app/models.py::User", 2, 6),
    ("app/models.py::User.__init__", 3, 7),
    ("app/models.py::User.label", 3, 8),
    ("app/repository.py", 1, 9),
    ("app/repository.py::UserRepository", 2, 10),
    ("app/repository.py::UserRepository.__init__", 3, 11),
    ("app/repository.py::UserRepository.save", 3, 12),
    ("app/repository.py::UserRepository.dump", 3, 13),
    ("app/repository.py::validate", 2, 14),
    ("app/service.py", 1, 15),
    ("app/service.py::UserService", 2, 16),
    ("app/service.py::UserService.__init__", 3, 17),
    ("app/service.py::UserService.create", 3, 18),
    ("app/service.py::UserService.log", 3, 19),
    ("app/utils.py", 1, 20),
    ("app/utils.py::normalize", 2, 21),
    ("app/utils.py::validate", 2, 22),
    ("app/utils.py::data_dir", 2, 23),
    ("ext:json", 0, 25),
    ("ext:os", 0, 26),
]
FILE_BRANCHES = ["b:app/__init__.py", "b:app/models.py", "b:app/repository.py", "b:app/service.py",
                 "b:app/utils.py"]

# treeLayout(applyView()) as [[id, depth, row], ...] in row order, plus its folders and branches.
LAYOUT = ("(() => { const t = treeLayout(applyView()); "
          "return [Object.entries(t.pos).map(([id, p]) => [id, p.x / COL, p.y / ROW])"
          ".sort((a, b) => a[2] - b[2]), [...t.dirs].sort(), [...t.branches].sort()]; })()")


def rows(tree):
    return [list(r) for r in tree]


def test_js_tree_layout_fixture(sample_repo):
    html = fixture_html(sample_repo)
    assert run_js(html, "[COL, ROW]") == [260, 40]
    assert run_js(html, LAYOUT) == [rows(FIXTURE_TREE), ["dir:app/"], FILE_BRANCHES]
    # x grows with depth and y follows the tree order
    got = run_js(html, '(() => { const p = treeLayout(applyView()).pos; return [p["dir:app/"], '
                       'p["app/models.py"], p["app/models.py::Entity"], p["app/models.py::Entity.__init__"]]; })()')
    assert got == [{"x": 0, "y": 0}, {"x": 260, "y": 80}, {"x": 520, "y": 120}, {"x": 780, "y": 160}]


# Folders before files (even "zz/" before "top.py"), files A-Z ignoring case ("apple" before "Banana"),
# nested folders, root-level files at depth 0, externals last.
NEST = {
    "zz/c.py": "def c():\n    pass\n",
    "pkg/sub/a.py": "def f():\n    pass\n",
    "pkg/apple.py": "import os\n",
    "pkg/Banana.py": "import json\n",
    "top.py": "class T:\n    def m(self):\n        pass\n",
}
NEST_TREE = [
    ("dir:pkg/", 0, 0),
    ("dir:pkg/sub/", 1, 1),
    ("pkg/sub/a.py", 2, 2),
    ("pkg/sub/a.py::f", 3, 3),
    ("pkg/apple.py", 1, 4),
    ("pkg/Banana.py", 1, 5),
    ("dir:zz/", 0, 6),
    ("zz/c.py", 1, 7),
    ("zz/c.py::c", 2, 8),
    ("top.py", 0, 9),
    ("top.py::T", 1, 10),
    ("top.py::T.m", 2, 11),
    ("ext:json", 0, 13),
    ("ext:os", 0, 14),
]


def test_js_tree_layout_folders(tmp_path):
    html = outputs.graph_html(build(write(tmp_path, NEST)))
    assert run_js(html, LAYOUT) == [
        rows(NEST_TREE), ["dir:pkg/", "dir:pkg/sub/", "dir:zz/"],
        ["b:dir:pkg/sub/", "b:pkg/Banana.py", "b:pkg/apple.py", "b:pkg/sub/a.py", "b:zz/c.py"]]
    # no "contains" edges enabled: no folder branches either
    got = run_js(html, f'(state.ekinds.delete("contains"), {LAYOUT})')
    assert got[2] == []


def test_js_tree_layout_compacts(sample_repo, monkeypatch):
    html = fixture_html(sample_repo)
    # class filter off: methods hang under their file (nearest visible ancestor) at depth 2
    got = run_js(html, f'(state.kinds.delete("class"), {LAYOUT})')
    assert got[0] == rows([
        ("dir:app/", 0, 0),
        ("app/__init__.py", 1, 1),
        ("app/models.py", 1, 2),
        ("app/models.py::Entity.__init__", 2, 3),
        ("app/models.py::Entity.describe", 2, 4),
        ("app/models.py::User.__init__", 2, 5),
        ("app/models.py::User.label", 2, 6),
        ("app/repository.py", 1, 7),
        ("app/repository.py::UserRepository.__init__", 2, 8),
        ("app/repository.py::UserRepository.save", 2, 9),
        ("app/repository.py::UserRepository.dump", 2, 10),
        ("app/repository.py::validate", 2, 11),
        ("app/service.py", 1, 12),
        ("app/service.py::UserService.__init__", 2, 13),
        ("app/service.py::UserService.create", 2, 14),
        ("app/service.py::UserService.log", 2, 15),
        ("app/utils.py", 1, 16),
        ("app/utils.py::normalize", 2, 17),
        ("app/utils.py::validate", 2, 18),
        ("app/utils.py::data_dir", 2, 19),
        ("ext:json", 0, 21),
        ("ext:os", 0, 22)])
    # file-level view (level of detail): the folder and its files; expanding service.py inserts its symbols
    lod = fixture_html(sample_repo, monkeypatch, 24)
    files = [("dir:app/", 0, 0), ("app/__init__.py", 1, 1), ("app/models.py", 1, 2),
             ("app/repository.py", 1, 3), ("app/service.py", 1, 4), ("app/utils.py", 1, 5)]
    assert run_js(lod, LAYOUT) == [rows(files + [("ext:json", 0, 7), ("ext:os", 0, 8)]), ["dir:app/"],
                                   FILE_BRANCHES]
    got = run_js(lod, f'(state.expanded.add("app/service.py"), {LAYOUT})')
    assert got[0] == rows(files[:5] + [
        ("app/service.py::UserService", 2, 5),
        ("app/service.py::UserService.__init__", 3, 6),
        ("app/service.py::UserService.create", 3, 7),
        ("app/service.py::UserService.log", 3, 8),
        ("app/utils.py", 1, 9),
        ("ext:json", 0, 11),
        ("ext:os", 0, 12)])


def test_template_tree_strings():
    tpl = outputs.HTML_TEMPLATE
    for s in ("function treeLayout(", 'const DIR_PREFIX = "dir:"', "const COL = 260", "const ROW = 40",
              "function treeKey("):
        assert s in tpl, s
    body = fn_body(tpl, "treeLayout")
    # pure: reads V and the static tree indexes only, touches neither the DOM nor vis
    for s in ("document.", "net.", "nodes.update", "nodes.get", "edges.update"):
        assert s not in body, s



# ---------------------------------------------------------------- Tree look as data copies; Graph data untouched (task 2)

BRANCH = {"enabled": True, "type": "cubicBezier", "forceDirection": "horizontal"}
CURVE = {"enabled": True, "type": "curvedCW", "roundness": 0.25}
NO_ARROW = {"to": {"enabled": False}}
PHASE8_EDGE_KEYS = "color,confidence,dashes,from,id,kind,title,to"


def test_js_tree_edge_styles(sample_repo, tmp_path, monkeypatch):
    html = fixture_html(sample_repo)
    got = run_js(html, "treeEdgeItems().map(e => [e.id, e.kind, e.smooth, "
                       "e.kind === 'contains' ? [e.color, e.width, e.arrows] : null])")
    raw = [g for g in got if not g[0].startswith("b:")]
    assert [g[0] for g in raw] == [e["id"] for e in html_data(html)["edges"]]
    assert {g[1] for g in raw} == {"contains", "imports", "inherits", "calls"}
    for _, kind, smooth, look in raw:
        # contains = the tree's branches (thin grey, no arrow); every other kind bends over the tree
        assert (smooth, look) == ((BRANCH, ["#b0b0b0", 1, NO_ARROW]) if kind == "contains" else (CURVE, None))
    # page-only branches folder -> file, same look as contains
    assert sorted(g for g in got if g[0].startswith("b:")) == [
        [b, "contains", BRANCH, ["#b0b0b0", 1, NO_ARROW]] for b in FILE_BRANCHES]
    assert sorted(run_js(html, "BRANCH_EDGES.map(e => [e.id, e.from, e.to])")) == [
        [b, "dir:app/", b[2:]] for b in FILE_BRANCHES]
    # Phase 8 dashes and AMBIGUOUS transparency carry over to the Tree copies
    amb = outputs.graph_html(build(write(tmp_path / "amb", AMB)))
    assert run_js(amb, 'treeEdgeItems().filter(e => e.confidence && e.confidence !== "EXTRACTED")'
                       '.map(e => [e.id, e.dashes, e.color])') == [
        ["e21", [2, 4], {"color": "#f58518", "opacity": 0.5}], ["e22", [8, 6], "#f58518"]]
    # file-level bundles bend like relations and keep their Phase 8 style
    lod = fixture_html(sample_repo, monkeypatch, 24)
    got = run_js(lod, 'treeEdgeItems().filter(e => e.id === "f3").map(e => [e.from, e.to, e.smooth, e.title])')
    assert got == [["app/service.py", "app/models.py", CURVE,
                    "app/service.py -> app/models.py: 3 edges "
                    "(calls 2: EXTRACTED 1, INFERRED 1; imports 1: EXTRACTED 1)"]]


def test_js_tree_labels(tmp_path, sample_repo):
    html = outputs.graph_html(build(write(tmp_path / "nest", NEST)))
    got = run_js(html, "treeNodeItems().map(n => [n.id, n.label, n.group])")
    by_id = {i: [label, group] for i, label, group in got}
    # folder = its name, file = basename (its folder is drawn above it), symbols keep the Phase 8 label
    assert by_id["dir:pkg/"] == ["pkg", "dir"]
    assert by_id["dir:pkg/sub/"] == ["sub", "dir"]
    assert by_id["dir:zz/"] == ["zz", "dir"]
    assert by_id["pkg/sub/a.py"] == ["a.py", "file"]
    assert by_id["top.py"] == ["top.py", "file"]
    assert by_id["top.py::T.m"] == ["T.m", "method"]
    assert by_id["ext:os"] == ["os", "external"]
    assert len(got) == len(by_id) == 3 + 11  # 3 folders + every graph node
    assert run_js(html, "[...DIRS.values()].map(d => d.title).sort()") == ["pkg/", "pkg/sub/", "zz/"]
    # no colour on the items: vis would let the group style override a colour given at add time
    sem = outputs.graph_html(build(sample_repo), SEM)
    assert run_js(sem, 'treeNodeItems().filter(n => "color" in n).length') == 0


def test_js_graph_data_untouched(sample_repo):
    # Graph mode keeps the Phase 8 node and edge objects: no tree labels or curves leak into D
    html = fixture_html(sample_repo)
    expr = ("[[...new Set(D.edges.map(e => Object.keys(e).sort().join()))], "
            "D.nodes.filter(n => n.kind === 'file').map(n => n.label)]")
    files = ["app/__init__.py", "app/models.py", "app/repository.py", "app/service.py", "app/utils.py"]
    assert run_js(html, expr) == [[PHASE8_EDGE_KEYS], files]
    assert run_js(html, f"(treeEdgeItems(), treeNodeItems(), {expr})") == [[PHASE8_EDGE_KEYS], files]


def test_template_tree_styles():
    tpl = outputs.HTML_TEMPLATE
    for s in ('type: "cubicBezier", forceDirection: "horizontal"', 'type: "curvedCW", roundness: 0.25',
              "function treeLabel(", "function treeNodeItems(", "function treeEdgeItems(",
              "function bundleEdge(", "const BRANCH_EDGES", 'dir: {shape: "box"'):
        assert s in tpl, s
    # Graph mode still feeds vis the Phase 8 objects with the global `smooth: false`
    body = fn_body(tpl, "start")
    for s in ("new vis.DataSet(D.nodes)", "smooth: false"):
        assert s in body, s
    for s in ("treeNodeItems", "treeEdgeItems", "cubicBezier", "curvedCW"):
        assert s not in body, s


def test_html_tree_data_unchanged(sample_repo):
    # folders and curves exist only in the page: the embedded data has no folder ids and no vis styling keys
    data = html_data(fixture_html(sample_repo))
    assert not [n for n in data["nodes"] if n["id"].startswith("dir:")]
    assert {k for e in data["edges"] for k in e} == set(PHASE8_EDGE_KEYS.split(","))


# ---------------------------------------------------------------- Graph | Tree modes (task 3)

# A minimal vis (DataSet / DataView / Network recording its calls) and browser globals, so the real
# start() (Graph mode, Phase 8) and the mode switch run in node. nets[0] = Graph, nets[1] = Tree.
FAKE_VIS = """
globalThis.window = {addEventListener() {}};
globalThis.location = {hash: HASH, href: "file:///r/graph.html"};
globalThis.history = {replaceState() {}};
const els = {};
const mkEl = id => {
  const e = stubEl(), cls = new Set(), ls = {};
  Object.assign(e, {id, clientWidth: 1000, clientHeight: 800, disabled: false, cls, replaceChildren() {},
    addEventListener: (ev, fn) => { (ls[ev] = ls[ev] || []).push(fn); },
    click: () => (ls.click || []).forEach(f => f({}))});
  e.classList = {add: c => cls.add(c), remove: c => cls.delete(c), contains: c => cls.has(c),
    toggle: (c, on) => ((on === undefined ? !cls.has(c) : on) ? cls.add(c) : cls.delete(c))};
  return e;
};
const getEl = document.getElementById;
document.getElementById = id => id === "graph-data" ? getEl(id) : (els[id] = els[id] || mkEl(id));
document.querySelectorAll = () => [];
document.querySelector = q => mkEl(q);
document.addEventListener = () => {};
renderDetails = () => {};
class DataSet {
  constructor(items) { this.m = new Map(items.map(i => [i.id, {...i}])); }
  update(list) {
    list = [].concat(list);
    const real = list.filter(i => !String(i.id).startsWith("dir:"));  // folders have no LLM colour
    if (this === tnodes && real.length) log.push(("x" in real[0] ? "pos" : "") + (real.every(i => "color" in i) ? "+colour" : ""));
    if (this === nodes && real.length) glog.push(("x" in real[0] ? "pos" : "") + (real.every(i => "color" in i) ? "+colour" : ""));
    for (const i of list) this.m.set(i.id, {...(this.m.get(i.id) || {}), ...i});
  }
  get(ids) { return ids.map(id => this.m.get(id)); }
}
class DataView {
  constructor(ds, o) { this.ds = ds; this.filter = o.filter; }
  refresh() {}
  getIds() { return [...this.ds.m.values()].filter(this.filter).map(i => i.id); }
}
const nets = [], log = [], glog = [];
class Network {
  constructor(el, data, opts) {
    Object.assign(this, {el, view: data.nodes, opts, calls: [], handlers: {}});
    nets.push(this);
    log.push("network " + el.id);
  }
  on(ev, fn) { (this.handlers[ev] = this.handlers[ev] || []).push(fn); }
  once(ev, fn) { this.on(ev, fn); }
  emit(ev, p) { (this.handlers[ev] || []).forEach(f => f(p || {})); }
  setOptions(o) { this.calls.push(["setOptions", o]); }
  getPositions() {
    const out = {};
    for (const id of this.view.getIds()) out[id] = {x: this.view.ds.m.get(id).x, y: this.view.ds.m.get(id).y};
    return out;
  }
  fit(o) { this.calls.push(["fit", o ? o.nodes.length : "all"]); }
  moveTo(o) { this.calls.push(["moveTo", o]); }
  selectNodes(ids) { this.calls.push(["select", ids]); }
  unselectAll() { this.calls.push(["unselect"]); }
}
globalThis.vis = {DataSet, DataView, Network};
// rows of a DataSet as shown by its view: [id, x / COL, y / ROW], top-down
const rowsOf = (ds, view) => view.getIds().map(id => [id, ds.m.get(id).x / COL, ds.m.get(id).y / ROW])
  .sort((a, b) => a[2] - b[2]);
const want = () => Object.entries(treeLayout(applyView()).pos).map(([id, p]) => [id, p.x / COL, p.y / ROW])
  .sort((a, b) => a[2] - b[2]);
// Graph mode as left by a finished force layout: positions set, first layout done
const graphLaidOut = () => {
  start();
  nodes.update(D.nodes.map((n, i) => ({id: n.id, x: 7 * i, y: -3 * i})));
  nets[0].emit("stabilizationIterationsDone");
};
const graphSnap = () => JSON.stringify([...nodes.m.values()].map(n => [n.id, n.x, n.y, n.label, n.color]));
"""


def run_modes(html, body, hash_=""):
    return run_js(html, "(() => { " + FAKE_VIS.replace("HASH", json.dumps(hash_)) + body + " })()")


def test_js_mode_switch(sample_repo):
    html = fixture_html(sample_repo)
    # Graph is the default and is the Phase 8 network; Tree waits for the graph's first layout
    got = run_modes(html, 'start(); setMode("tree"); return [mode, nets.length, nets[0].opts.physics.solver, '
                          'els["mode-tree"].disabled, net === nets[0]];')
    assert got == ["graph", 1, "forceAtlas2Based", True, True]
    # Tree: its own network (physics off) at the tree positions; the Graph network is left alone
    # (only its physics switched off), Graph positions and labels unchanged
    got = run_modes(html, 'graphLaidOut(); const s = graphSnap(); const g0 = nets[0].calls.length; '
                          'els["mode-tree"].click(); const t = nets[1]; '
                          'return [mode, net === t, t.opts.physics, t.opts.layout, els.net.cls.has("off"), '
                          'els.tree.cls.has("off"), rowsOf(tnodes, tnodeView), t.calls, nets[0].calls.slice(g0), '
                          'graphSnap() === s];')
    (m, is_tree, physics, layout, net_off, tree_off, pos, tcalls, gcalls, same) = got
    assert (m, is_tree, physics, layout, net_off, tree_off) == (
        "tree", True, {"enabled": False}, {"improvedLayout": False}, True, False)
    assert pos == rows(FIXTURE_TREE)
    assert tcalls == [["unselect"], ["moveTo", {"position": {"x": 370, "y": 360}, "scale": 1}]]
    assert gcalls == [["setOptions", {"physics": {"enabled": False}}]]
    assert same
    # a filter change in Tree compacts the tree and does not touch the Graph data or network;
    # back in Graph the Phase 8 refresh applies it with the Graph positions kept
    got = run_modes(html, 'graphLaidOut(); const s = graphSnap(); setMode("tree"); const g0 = nets[0].calls.length; '
                          'state.kinds.delete("class"); refresh(); const t = rowsOf(tnodes, tnodeView); '
                          'const a = [t.length, t[3], JSON.stringify(t) === JSON.stringify(want()), graphSnap() === s, '
                          'nets[0].calls.length - g0]; '
                          'setMode("graph"); return [a, mode, net === nets[0], els.net.cls.has("off"), '
                          'els.tree.cls.has("off"), nodeView.getIds().length, graphSnap() === s, nets[1].calls.slice(-1)];')
    [a, m, is_graph, net_off, tree_off, n_graph, same, tlast] = got
    assert a == [22, ["app/models.py::Entity.__init__", 2, 3], True, True, 0]
    assert (m, is_graph, net_off, tree_off, n_graph, same) == ("graph", True, False, True, 21, True)


def test_js_mode_pick_and_fit(sample_repo):
    html = fixture_html(sample_repo)
    c = "app/service.py::UserService.create"
    # pick and Fit act on the shown network only
    got = run_modes(html, f'graphLaidOut(); setMode("tree"); const g0 = nets[0].calls.length, t0 = nets[1].calls.length; '
                          f'pick({json.dumps(c)}); els.fit.click(); '
                          f'return [nets[0].calls.length - g0, nets[1].calls.slice(t0), state.selected];')
    g_new, tcalls, selected = got
    assert g_new == 0 and selected == c
    assert tcalls[0] == ["select", [c]] and tcalls[1][0] == "fit" and tcalls[2] == ["fit", "all"]
    # back in Graph: the selection made in Tree is selected and its focus fitted (like pick)
    got = run_modes(html, f'graphLaidOut(); setMode("tree"); pick({json.dumps(c)}); const g0 = nets[0].calls.length; '
                          'setMode("graph"); return nets[0].calls.slice(g0).map(x => x[0]);')
    assert got == ["select", "fit"]
    # first Tree open with a selection made in Graph: fit its focus instead of the top of the tree
    got = run_modes(html, f'graphLaidOut(); pick({json.dumps(c)}); setMode("tree"); return nets[1].calls.map(x => x[0]);')
    assert got == ["select", "fit"]


def test_js_tree_relayout_and_expand(sample_repo, monkeypatch):
    html = fixture_html(sample_repo)
    # Re-layout in Tree puts a dragged node back, never turns physics on (Graph's Re-layout unchanged)
    got = run_modes(html, 'graphLaidOut(); setMode("tree"); tnodes.update({id: "app/models.py", x: 999, y: 999}); '
                          'els.relayout.click(); const t = tnodes.m.get("app/models.py"); '
                          'const tset = nets[1].calls.filter(c => c[0] === "setOptions"); '
                          'setMode("graph"); const g0 = nets[0].calls.length; els.relayout.click(); '
                          'return [t.x, t.y, tset, nets[0].calls.slice(g0)];')
    assert got == [260, 80, [], [["setOptions", {"physics": {"enabled": True}}]]]
    # file-level view: double-click in Tree expands a file under its row; back in Graph its symbols get
    # the Phase 8 ring around the file's Graph position
    lod = fixture_html(sample_repo, monkeypatch, 24)
    got = run_modes(lod, 'graphLaidOut(); setMode("tree"); nets[1].emit("doubleClick", {nodes: ["app/service.py"]}); '
                         'const t = rowsOf(tnodes, tnodeView); const ok = JSON.stringify(t) === JSON.stringify(want()); '
                         'setMode("graph"); const f = nodes.m.get("app/service.py"); '
                         'const r = symbolsOf.get("app/service.py").map(id => Math.round(Math.hypot(nodes.m.get(id).x - f.x, '
                         'nodes.m.get(id).y - f.y))); return [t.length, t[5], ok, r];')
    assert got == [12, ["app/service.py::UserService", 2, 5], True, [84, 84, 84, 84]]


def test_js_tree_llm_colours(sample_repo):
    html = outputs.graph_html(build(sample_repo), SEM)
    c = json.dumps("app/service.py::UserService.create")
    # vis re-applies the group style to a node updated without a colour, so with semantic.json every
    # Tree position update carries the LLM colour; setLLM recolours both modes and Tree keeps it
    got = run_modes(html, f'graphLaidOut(); setMode("tree"); const on = tnodes.m.get({c}).color; '
                          f'setLLM(false); refresh(); const off = tnodes.m.get({c}).color; '
                          f'setLLM(true); state.kinds.delete("class"); refresh(); '
                          f'return [[...new Set(log.filter(x => x !== "network net"))], on, off, tnodes.m.get({c}).color];')
    assert got == [["pos+colour", "network tree", "+colour"], "#1f77b4", "#72b7b2", "#1f77b4"]
    # without semantic.json Tree never sets a colour (the group styles colour by kind)
    plain = fixture_html(sample_repo)
    got = run_modes(plain, 'graphLaidOut(); setMode("tree"); refresh(); return [...new Set(log)];')
    assert got == ["network net", "pos", "network tree"]


def test_js_graph_keeps_llm_colours(sample_repo, monkeypatch):
    # Phase 8 bug fixed with the user's OK: Graph's refresh() wrote positions back without a colour,
    # so vis re-applied the group style and the LLM colours turned into kind colours on the first
    # click. With semantic.json every Graph position write-back (ring included) now carries the colour.
    html = outputs.graph_html(build(sample_repo), SEM)
    got = run_modes(html, 'graphLaidOut(); glog.length = 0; refresh(); state.kinds.delete("class"); refresh(); '
                          'return [...new Set(glog)];')
    assert got == ["pos+colour"]
    monkeypatch.setattr(outputs, "MAX_HTML_NODES", 24)
    lod = outputs.graph_html(build(sample_repo), SEM)
    got = run_modes(lod, 'graphLaidOut(); glog.length = 0; toggleExpand("app/service.py"); refresh(); '
                         'return [[...new Set(glog)], nodes.m.get("app/service.py::UserService.create").color];')
    assert got == [["pos+colour"], "#1f77b4"]
    # without semantic.json Graph never sets a colour (unchanged Phase 8 behaviour)
    plain = fixture_html(sample_repo)
    assert run_modes(plain, 'graphLaidOut(); glog.length = 0; refresh(); return [...new Set(glog)];') == ["pos"]


def test_template_modes():
    tpl = outputs.HTML_TEMPLATE
    for s in ('<button id="mode-graph" class="active">Graph</button>', '<button id="mode-tree" disabled',
              '<div id="tree" class="off"></div>', ".off { visibility: hidden; }", "function setMode(",
              "function startTree(", "function refreshTree(", "function topView("):
        assert s in tpl, s
    assert tpl.count('id="mode-graph"') == tpl.count('id="mode-tree"') == tpl.count('id="tree"') == 1
    # Graph mode is the Phase 8 network: same options in start(); the mode work is outside it
    body = fn_body(tpl, "start")
    for s in ("layout: {improvedLayout: shownNodes <= 150}", 'physics: {solver: "forceAtlas2Based"',
              "new vis.DataSet(D.nodes)", "initModes();"):
        assert s in body, s
    for s in ("treeLayout", "tnodes", "setMode"):
        assert s not in body, s
    assert fn_body(tpl, "refresh").startswith('function refresh() {\n  if (mode === "tree") return refreshTree();')
    assert 'if (mode === "tree")' in fn_body(tpl, "relayout")
