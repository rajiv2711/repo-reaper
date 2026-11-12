"""Phase 12: Tree overview of graph.html (collapsible folders with folder bundles).

Expected rows, bundles and counts are written by hand from tests/fixtures/sample_py and the small
repos below (not printed from the code). `test_js_*` run the page script in node.
"""

import json

from test_html_template import fixture_html, run_js, write
from test_html_tree import FIXTURE_TREE, LAYOUT, NEST, rows, run_modes

from reaper import outputs
from reaper.graph import build

CLOSE_APP = 'state.closed.add("dir:app/"), '
# treeView(applyView()) as [nodes, raw edges as [from, to, kind], file bundles, closed, folder bundles]
TREE_VIEW = ("(() => { const T = treeView(applyView()); return [[...T.nodes].sort(), "
             "[...T.raw].map(id => [edgeById.get(id).from, edgeById.get(id).to, edgeById.get(id).kind]).sort(), "
             "[...T.agg].sort(), [...T.closed].sort(), "
             "[...T.folds.values()].map(f => [f.id, f.from, f.to, f.counts]).sort()]; })()")
APP_JSON = "d:dir:app/ -> ext:json"
APP_OS = "d:dir:app/ -> ext:os"
APP_FOLDS = [[APP_JSON, "dir:app/", "ext:json", {"imports": {"EXTRACTED": 1}}],
             [APP_OS, "dir:app/", "ext:os", {"imports": {"EXTRACTED": 2}}]]
APP_CLOSED_ROWS = [["dir:app/", 0, 0], ["ext:json", 0, 2], ["ext:os", 0, 3]]


def test_js_closed_folder_fixture(sample_repo):
    html = fixture_html(sample_repo)
    assert run_js(html, "[state.closed.size, TREE_ROWS]") == [0, 60]
    # app/ closed: one leaf row for the folder, externals after a blank row, no branches
    assert run_js(html, f"({CLOSE_APP}{LAYOUT})") == [APP_CLOSED_ROWS, ["dir:app/"], []]
    # every edge inside app/ is hidden; the imports of os (service.py, utils.py) and json
    # (repository.py) become two folder bundles
    assert run_js(html, f"({CLOSE_APP}{TREE_VIEW})") == [["ext:json", "ext:os"], [], [], ["dir:app/"], APP_FOLDS]
    # nothing closed: the drawn sets are applyView()'s, no folder bundles
    got = run_js(html, "(() => { const V = applyView(), T = treeView(V); return [[...T.nodes].join() === "
                       "[...V.nodes].join(), [...T.raw].join() === [...V.raw].join(), T.agg.size, T.folds.size, "
                       "T.closed.size, T.nodes.size, T.raw.size]; })()")
    assert got == [True, True, 0, 0, 0, 25, 21 + 18]  # 21 relations + 18 contains


def test_js_folder_bundle_look_and_legend(sample_repo):
    html = fixture_html(sample_repo)
    # a folder bundle looks like a file-level bundle; its tooltip names the folder by its path
    got = run_js(html, f'({CLOSE_APP}(() => {{ const s = bundleStyle(treeView(applyView()).folds.get("{APP_OS}")); '
                       'return [s.width, s.dashes, s.color === EDGE_COLORS.imports, s.title]; })())')
    assert got == [2, False, True, "app/ -> ext:os: 2 edges (imports 2: EXTRACTED 2)"]
    # legend counts what Tree draws: 2 externals, the 3 bundled imports, 2 lines
    got = run_js(html, f"({CLOSE_APP}legendCounts(treeView(applyView())))")
    assert got["node"]["external"] == 2 and sum(got["node"].values()) == 2
    assert got["edge"]["imports"] == 3 and sum(got["edge"].values()) == 3
    assert got["conf"] == {"EXTRACTED": 3, "INFERRED": 0, "AMBIGUOUS": 0}
    assert got["lines"] == 2


# lib/ calls into itself and is called from app/main.py
CROSS = {
    "lib/core.py": "def helper():\n    pass\n",
    "lib/extra.py": "from lib.core import helper\n\n\ndef run():\n    helper()\n",
    "app/main.py": "from lib.core import helper\n\n\ndef main():\n    helper()\n",
}


def test_js_closed_folder_cross_edges(tmp_path):
    html = outputs.graph_html(build(write(tmp_path, CROSS)))
    close = 'state.closed.add("dir:lib/"), '
    assert run_js(html, f"({close}{LAYOUT})") == [
        [["dir:app/", 0, 0], ["app/main.py", 1, 1], ["app/main.py::main", 2, 2], ["dir:lib/", 0, 3]],
        ["dir:app/", "dir:lib/"], ["b:app/main.py"]]
    # app/main.py keeps its contains edge; its import and call into lib/ end at the closed folder;
    # lib/'s own import and call are hidden
    assert run_js(html, f"({close}{TREE_VIEW})") == [
        ["app/main.py", "app/main.py::main"],
        [["app/main.py", "app/main.py::main", "contains"]],
        [], ["dir:lib/"],
        [["d:app/main.py -> dir:lib/", "app/main.py", "dir:lib/", {"imports": {"EXTRACTED": 1}}],
         ["d:app/main.py::main -> dir:lib/", "app/main.py::main", "dir:lib/", {"calls": {"EXTRACTED": 1}}]]]


def test_js_closed_nested_folder_and_auto_close(tmp_path):
    html = outputs.graph_html(build(write(tmp_path, NEST)))
    # pkg/sub/ closed: a leaf at depth 1, the rows below it move up by two, its file branch goes
    assert run_js(html, f'(state.closed.add("dir:pkg/sub/"), {LAYOUT})') == [
        rows([("dir:pkg/", 0, 0), ("dir:pkg/sub/", 1, 1), ("pkg/apple.py", 1, 2), ("pkg/Banana.py", 1, 3),
              ("dir:zz/", 0, 4), ("zz/c.py", 1, 5), ("zz/c.py::c", 2, 6), ("top.py", 0, 7), ("top.py::T", 1, 8),
              ("top.py::T.m", 2, 9), ("ext:json", 0, 11), ("ext:os", 0, 12)]),
        ["dir:pkg/", "dir:pkg/sub/", "dir:zz/"],
        ["b:dir:pkg/sub/", "b:pkg/Banana.py", "b:pkg/apple.py", "b:zz/c.py"]]
    # an outer closed folder hides the inner one: pkg/ stands for pkg/sub/a.py
    assert run_js(html, '(state.closed.add("dir:pkg/"), state.closed.add("dir:pkg/sub/"), '
                        '[standIn("pkg/sub/a.py::f"), standIn("pkg/apple.py"), standIn("zz/c.py"), standIn("dir:pkg/sub/")])') \
        == ["dir:pkg/", "dir:pkg/", "zz/c.py", "dir:pkg/"]
    # auto close: closable = folders and files with symbols (apple.py and Banana.py have none), tree
    # depth: pkg/ zz/ top.py 0, pkg/sub/ zz/c.py 1, pkg/sub/a.py 2. Rows without externals: 12 all
    # open, 11 with depth 2 closed, 9 with depth >= 1 closed, 3 with all closed. state.closed is kept.
    depth1 = ["dir:pkg/sub/", "pkg/sub/a.py", "zz/c.py"]
    every = ["dir:pkg/", "dir:pkg/sub/", "dir:zz/", "pkg/sub/a.py", "top.py", "zz/c.py"]
    auto = "[12, 11, 10, 9, 8, 2].map(b => [...autoClosed(applyView(), b)].sort()).concat([state.closed.size])"
    assert run_js(html, auto) == [[], ["pkg/sub/a.py"], depth1, depth1, every, every, 0]


def test_js_tree_folder_toggle(sample_repo):
    html = fixture_html(sample_repo)
    c = "app/service.py::UserService.create"
    # Tree opens fully expanded on the fixture; double-click app/ closes it, again opens it
    got = run_modes(html, 'graphLaidOut(); const s = graphSnap(); setMode("tree"); const t = nets[1]; '
                          'const a = [state.closed.size, rowsOf(tnodes, tnodeView)]; '
                          't.emit("doubleClick", {nodes: ["dir:app/"]}); '
                          'const b = [rowsOf(tnodes, tnodeView), tnodes.m.get("dir:app/").label, '
                          'tnodes.m.get("dir:app/").title, tedgeView.getIds().sort(), legendCounts(tshown).lines, '
                          'els.status.textContent]; '
                          't.emit("doubleClick", {nodes: ["dir:app/"]}); '
                          'const d = [rowsOf(tnodes, tnodeView), tnodes.m.get("dir:app/").label, '
                          'tnodes.m.get("dir:app/").title]; '
                          't.emit("doubleClick", {nodes: ["dir:app/"]}); setMode("graph"); '
                          'return [a, b, d, nodeView.getIds().length, graphSnap() === s, state.closed.size];')
    a, b, d, n_graph, same, n_closed = got
    assert a == [0, rows(FIXTURE_TREE)]
    assert b == [APP_CLOSED_ROWS, "app/ (5)", "app/ - 5 files, double-click to open", [APP_JSON, APP_OS], 2,
                 "2 nodes, 3 edges shown (2 lines), 1 closed (double-click to open)"]
    assert d == [rows(FIXTURE_TREE), "app", "app/"]
    # Graph mode ignores closed folders: every node, positions and labels as left
    assert (n_graph, same, n_closed) == (25, True, 1)
    # pick reveals a node inside a closed folder and selects it
    got = run_modes(html, f'graphLaidOut(); setMode("tree"); state.closed.add("dir:app/"); refresh(); '
                          f'pick({json.dumps(c)}); return [state.closed.size, tnodeView.getIds().includes({json.dumps(c)}), '
                          f'nets[1].calls.filter(x => x[0] === "select").pop()];')
    assert got == [0, True, ["select", [c]]]
    # a focus inside a closed folder is fitted as that folder (the externals are not in the focus)
    got = run_modes(html, f'graphLaidOut(); setMode("tree"); pick({json.dumps(c)}); '
                          'nets[1].emit("doubleClick", {nodes: ["dir:app/"]}); '
                          'return [fitIds(tshown), state.focus.size, state.selected];')
    assert got == [["dir:app/"], 7, c]


def test_js_tree_auto_close_on_first_open(tmp_path, sample_repo):
    # NEST has 12 rows without externals: with a budget of 10 the first Tree build closes depth >= 1
    html = outputs.graph_html(build(write(tmp_path / "nest", NEST))).replace(
        "const TREE_ROWS = 60;", "const TREE_ROWS = 10;")
    got = run_modes(html, 'graphLaidOut(); setMode("tree"); return [[...state.closed].sort(), '
                          'tnodes.m.get("dir:pkg/sub/").label, tnodes.m.get("zz/c.py").label, '
                          'tnodes.m.get("zz/c.py").title, rowsOf(tnodes, tnodeView).length];')
    assert got == [["dir:pkg/sub/", "pkg/sub/a.py", "zz/c.py"], "sub/ (1)", "c.py (1)",
                   "zz/c.py - 1 symbol, double-click to open", 11]
    # a selection made in Graph is revealed when Tree is first built (auto close uses the whole tree,
    # not the focus, so pkg/sub/ and a.py are closed first and then opened for a.py::f)
    got = run_modes(html, 'graphLaidOut(); pick("pkg/sub/a.py::f"); setMode("tree"); '
                          'return [[...state.closed], tnodeView.getIds().includes("pkg/sub/a.py::f")];')
    assert got == [["zz/c.py"], True]


def test_js_closed_file_fixture(sample_repo, monkeypatch):
    html = fixture_html(sample_repo)
    close = 'state.closed.add("app/service.py"), '
    # service.py closed: its 4 symbols leave their rows; the rows below move up by four
    got = run_js(html, f"({close}{LAYOUT})")
    assert got[0] == [r for r in rows(FIXTURE_TREE) if not r[0].startswith("app/service.py::")][:16] + rows([
        ("app/utils.py", 1, 16), ("app/utils.py::normalize", 2, 17), ("app/utils.py::validate", 2, 18),
        ("app/utils.py::data_dir", 2, 19), ("ext:json", 0, 21), ("ext:os", 0, 22)])
    # its file-level imports stay; the calls out of its symbols end at the file; create -> log is hidden
    got = run_js(html, f"({close}{TREE_VIEW})")
    assert got[3] == ["app/service.py"]
    assert ["app/service.py", "app/models.py", "imports"] in got[1]
    assert not [r for r in got[1] if r[0].startswith("app/service.py::") or r[1].startswith("app/service.py::")]
    assert got[4] == [
        ["d:app/service.py -> app/models.py::User", "app/service.py", "app/models.py::User", {"calls": {"EXTRACTED": 1}}],
        ["d:app/service.py -> app/models.py::User.label", "app/service.py", "app/models.py::User.label",
         {"calls": {"INFERRED": 1}}],
        ["d:app/service.py -> app/repository.py::UserRepository", "app/service.py",
         "app/repository.py::UserRepository", {"calls": {"EXTRACTED": 1}}],
        ["d:app/service.py -> app/repository.py::UserRepository.save", "app/service.py",
         "app/repository.py::UserRepository.save", {"calls": {"INFERRED": 1}}],
        ["d:app/service.py -> app/utils.py::normalize", "app/service.py", "app/utils.py::normalize",
         {"calls": {"EXTRACTED": 1}}],
        ["d:app/service.py -> app/utils.py::validate", "app/service.py", "app/utils.py::validate",
         {"calls": {"EXTRACTED": 1}}]]
    # closable: folders and files with symbols; in the file-level view files expand instead
    assert run_js(html, '["dir:app/", "app/service.py", "app/__init__.py", "ext:os", "app/service.py::UserService"]'
                        '.map(closable)') == [True, True, False, False, False]
    lod = fixture_html(sample_repo, monkeypatch, 24)
    assert run_js(lod, '["dir:app/", "app/service.py"].map(closable)') == [True, False]
