"""Phase 9: Tree mode of graph.html (folders -> files -> classes/functions -> methods, left to right).

Expected rows are written by hand from tests/fixtures/sample_py (not printed from the code).
`test_template_*` never skip; `test_js_*` run the page script in node (see test_html_template.py).
"""

import json

from test_html_template import fixture_html, fn_body, html_data, run_js, write

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

