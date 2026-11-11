"""Phase 5: TREE.txt, SUMMARY.md, graph.html, `reaper export` and `reaper query`.

Expected values are written by hand from the fixture source (tests/fixtures/sample_py/app)
and the hand-checked edge list in test_resolve.py (FIXTURE_EDGES).
"""

import json
import re

from reaper import outputs
from reaper.cli import main
from reaper.graph import build, graph_path

M, R, S, U = "app/models.py", "app/repository.py", "app/service.py", "app/utils.py"

EXPECTED_TREE = """\
app/__init__.py (1 line)

app/models.py (24 lines)
  class Entity  # L4
    def __init__(self, entity_id)  # L7
    def describe(self)  # L10
  class User(Entity)  # L15
    def __init__(self, entity_id, name)  # L18
    def label(self)  # L22

app/repository.py (29 lines)
  class UserRepository  # L8
    def __init__(self)  # L11
    def save(self, user)  # L15
    def dump(self)  # L21
  def validate(user)  # L26

app/service.py (26 lines)
  class UserService  # L9
    def __init__(self, repo=None)  # L12
    def create(self, entity_id, name)  # L15
    def log(self, message)  # L23

app/utils.py (17 lines)
  def normalize(name)  # L5
  def validate(name)  # L10
  def data_dir()  # L15
"""

# Non-contains degree, externals left out; sorted by (-total, id); top 10.
#   create: calls validate, User, normalize, log, label, save
#   repository.py: imports json, models, utils; imported by service
#   service.py: imports os, models, repository, utils
#   utils.py: imports os; imported by repository, service
EXPECTED_TOP = [
    (f"{S}::UserService.create", "method", 0, 6, 6),
    (R, "file", 1, 3, 4),
    (S, "file", 0, 4, 4),
    (U, "file", 2, 1, 3),
    (M, "file", 2, 0, 2),
    (f"{M}::User", "class", 1, 1, 2),          # called by create; inherits Entity
    (f"{M}::User.label", "method", 1, 1, 2),   # called by create; calls describe
    (f"{R}::UserRepository.save", "method", 1, 1, 2),
    (f"{U}::normalize", "function", 2, 0, 2),  # called by create and utils.validate
    (f"{U}::validate", "function", 1, 1, 2),
]


def write(root, files):
    for rel, src in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src)
    return root


# ---------------------------------------------------------------- TREE.txt

def test_tree_exact(sample_repo):
    assert outputs.tree_text(build(sample_repo)) == EXPECTED_TREE


def test_file_outline_is_one_tree_block(sample_repo):
    g = build(sample_repo)
    assert outputs.file_outline(g, U) == EXPECTED_TREE.split("\n\n")[-1].rstrip("\n")


def test_tree_nested_async_and_syntax_error(tmp_path):
    g = build(write(tmp_path, {
        "pkg/a.py": "class A:\n    class Inner:\n        async def run(self) -> int:\n"
                    "            def helper():\n                pass\n",
        "pkg/bad.py": "def broken(:\n",
    }))
    assert outputs.tree_text(g) == (
        "pkg/a.py (5 lines)\n"
        "  class A  # L1\n"
        "    class Inner  # L2\n"
        "      async def run(self) -> int  # L3\n"
        "        def helper()  # L4\n"
        "\n"
        "pkg/bad.py (1 line)\n"
    )


# ---------------------------------------------------------------- SUMMARY.md

def test_summary_stats(sample_repo):
    md = outputs.summary_md(build(sample_repo))
    assert md.startswith("# repo-reaper summary\n")
    # files: 6 discovered (python 5, markdown 1)
    assert "| files | 6 |" in md
    assert "| python | 5 |" in md
    assert "| markdown | 1 |" in md
    # nodes: 5 file, 4 class, 10 method, 4 function, 2 external = 25
    for row in ("| file | 5 |", "| class | 4 |", "| method | 10 |", "| function | 4 |",
                "| external | 2 |", "| nodes | 25 |"):
        assert row in md, row
    # edges: 18 contains, 8 imports, 1 inherits, 12 calls = 39
    for row in ("| contains | 18 |", "| imports | 8 |", "| inherits | 1 |", "| calls | 12 |",
                "| edges | 39 |"):
        assert row in md, row
    # confidence: 4 INFERRED calls (2 base-class, user.label, self.repo.save), rest EXTRACTED
    assert "| EXTRACTED | 35 |" in md
    assert "| INFERRED | 4 |" in md
    assert "| AMBIGUOUS | 0 |" in md


def test_summary_most_connected(sample_repo):
    md = outputs.summary_md(build(sample_repo))
    section = md.split("## Most-connected nodes\n", 1)[1].split("\n## ", 1)[0]
    rows = re.findall(r"^\| `([^`]+)` \| (\w+) \| (\d+) \| (\d+) \| (\d+) \|$", section, re.M)
    assert [(i, k, int(a), int(b), int(c)) for i, k, a, b, c in rows] == EXPECTED_TOP


def test_summary_externals_and_no_cycles(sample_repo):
    md = outputs.summary_md(build(sample_repo))
    assert "| `os` | 2 | app/service.py, app/utils.py |" in md
    assert "| `json` | 1 | app/repository.py |" in md
    assert md.index("| `os` |") < md.index("| `json` |")  # most-imported first
    cycles = md.split("## Import cycles\n", 1)[1].split("\n## ", 1)[0]
    assert "None." in cycles


def test_summary_import_cycles(tmp_path):
    g = build(write(tmp_path, {
        "a.py": "import b\n",
        "b.py": "import c\n",
        "c.py": "import a\nimport d\n",
        "d.py": "",
        "x.py": "import y\n",
        "y.py": "import x\n",
    }))
    md = outputs.summary_md(g)
    cycles = md.split("## Import cycles\n", 1)[1].split("\n## ", 1)[0]
    assert "None." not in cycles
    assert "a.py -> b.py -> c.py -> a.py" in cycles
    assert "x.py -> y.py -> x.py" in cycles
    assert "d.py" not in cycles


def test_summary_big_cycle_group_is_capped(tmp_path):
    # f0 <-> every other file: one group of 8, shortest cycle f0 -> f1 -> f0
    files = {"f0.py": "".join(f"import f{i}\n" for i in range(1, 8))}
    files.update({f"f{i}.py": "import f0\n" for i in range(1, 8)})
    md = outputs.summary_md(build(write(tmp_path, files)))
    assert ("- f0.py -> f1.py -> f0.py (group of 8 files: "
            "f0.py, f1.py, f2.py, f3.py, f4.py, ... (+3 more))") in md


# ---------------------------------------------------------------- graph.html

def html_data(html):
    m = re.search(r'<script id="graph-data" type="application/json">(.*?)</script>', html, re.S)
    assert m, "embedded graph data not found"
    return json.loads(m.group(1))


def test_html_loads_vis_network_and_embeds_graph(sample_repo):
    html = outputs.graph_html(build(sample_repo))
    assert html.startswith("<!DOCTYPE html>")
    assert '<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js">' in html
    data = html_data(html)
    assert len(data["nodes"]) == 25
    assert len(data["edges"]) == 39
    assert data["note"] == ""
    ids = {n["id"] for n in data["nodes"]}
    assert {M, f"{S}::UserService.create", "ext:os"} <= ids


def test_html_dashed_when_not_extracted(sample_repo):
    edges = html_data(outputs.graph_html(build(sample_repo)))["edges"]
    by_pair = {(e["from"], e["to"], e["kind"]): e for e in edges}
    inferred = by_pair[(f"{S}::UserService.create", f"{R}::UserRepository.save", "calls")]
    extracted = by_pair[(f"{S}::UserService.create", f"{U}::normalize", "calls")]
    assert inferred["dashes"] is True and inferred["confidence"] == "INFERRED"
    assert extracted["dashes"] is False
    assert sum(e["dashes"] for e in edges) == 4  # the 4 INFERRED calls


# Phase 8 D-03 replaced test_html_large_graph_shows_files_only
def test_html_large_graph_opens_file_level(sample_repo, monkeypatch):
    monkeypatch.setattr(outputs, "MAX_HTML_NODES", 24)  # fixture has 25 nodes
    html = outputs.graph_html(build(sample_repo))
    data = html_data(html)
    assert data["lod"] is True
    assert len(data["nodes"]) == 25  # everything is embedded; the page starts at file level
    assert len(data["edges"]) == 39
    assert sorted(n["id"] for n in data["nodes"] if n["group"] in ("file", "external")) == [
        "app/__init__.py", M, R, S, U, "ext:json", "ext:os"]
    assert len(data["file_edges"]) == 8
    assert sum(f["count"] for f in data["file_edges"]) == 15
    assert data["note"] == ("file-level view: graph has 25 nodes and 39 edges (budget 24 nodes, "
                            "5000 edges); double-click a file to expand it")


def test_html_escapes_script_end_in_docs(tmp_path):
    html = outputs.graph_html(build(write(tmp_path, {
        "evil.py": '"""Docs with </script><b>tag</b>."""\n'})))
    assert "</script><b>" not in html
    assert html_data(html)["nodes"][0]["title"].startswith("evil.py")


# ---------------------------------------------------------------- export (CLI)

def test_export_writes_three_files(sample_repo, capsys):
    assert main(["map", str(sample_repo)]) == 0
    assert main(["export", str(sample_repo)]) == 0
    out_dir = graph_path(sample_repo).parent
    assert (out_dir / "TREE.txt").read_text() == EXPECTED_TREE
    assert (out_dir / "SUMMARY.md").read_text().startswith("# repo-reaper summary\n")
    assert "vis-network@9.1.9" in (out_dir / "graph.html").read_text()
    out = capsys.readouterr().out
    for name in ("TREE.txt", "SUMMARY.md", "graph.html"):
        assert name in out


def test_export_without_graph(sample_repo, capsys):
    assert main(["export", str(sample_repo)]) == 1
    assert "reaper map" in capsys.readouterr().err


# ---------------------------------------------------------------- query

def run_query(repo, capsys, *args):
    assert main(["map", str(repo)]) == 0
    capsys.readouterr()
    code = main(["query", str(repo), *args])
    return code, capsys.readouterr()


def test_find_nodes_tiers(sample_repo):
    g = build(sample_repo)
    ids = lambda name: [n["id"] for n in outputs.find_nodes(g, name)]
    assert ids(f"{U}::validate") == [f"{U}::validate"]           # exact id
    assert ids("app.utils.validate") == [f"{U}::validate"]        # module + qualname
    assert ids("UserService.create") == [f"{S}::UserService.create"]  # qualname
    assert ids("app.utils") == [U]                                # module name
    assert ids("os") == ["ext:os"]                                # external name
    assert ids("validate") == [f"{R}::validate", f"{U}::validate"]  # last name part
    assert ids("utils") == [U]                                    # last module part of a file
    assert ids("nope") == []


def test_query_callers_text(sample_repo, capsys):
    code, out = run_query(sample_repo, capsys, "callers", "validate")
    assert code == 0
    assert out.out == (
        f"callers of {R}::validate\n"
        f"  EXTRACTED  {R}::UserRepository.save  (line 15)\n"
        f"callers of {U}::validate\n"
        f"  EXTRACTED  {S}::UserService.create  (line 15)\n"
    )


def test_query_callees_json(sample_repo, capsys):
    code, out = run_query(sample_repo, capsys, "callees", "UserService.create", "--json")
    assert code == 0
    [res] = json.loads(out.out)
    assert res["node"] == f"{S}::UserService.create"
    assert [(c["id"], c["confidence"]) for c in res["callees"]] == [
        (f"{M}::User", "EXTRACTED"),
        (f"{M}::User.label", "INFERRED"),
        (f"{R}::UserRepository.save", "INFERRED"),
        (f"{S}::UserService.log", "EXTRACTED"),
        (f"{U}::normalize", "EXTRACTED"),
        (f"{U}::validate", "EXTRACTED"),
    ]
    assert res["callees"][0]["file"] == M and res["callees"][0]["line"] == 15


def test_query_callers_none(sample_repo, capsys):
    code, out = run_query(sample_repo, capsys, "callers", "UserService.create")
    assert code == 0
    assert out.out == f"callers of {S}::UserService.create\n  (none)\n"


def test_query_deps_file_json(sample_repo, capsys):
    code, out = run_query(sample_repo, capsys, "deps", "app.service", "--json")
    assert code == 0
    [res] = json.loads(out.out)
    assert res["node"] == S
    assert [d["id"] for d in res["imports"]] == [M, R, U, "ext:os"]
    assert res["imported_by"] == []


def test_query_deps_external_and_symbol(sample_repo, capsys):
    code, out = run_query(sample_repo, capsys, "deps", "os", "--json")
    [res] = json.loads(out.out)
    assert res["node"] == "ext:os"
    assert res["imports"] == []
    assert [d["id"] for d in res["imported_by"]] == [S, U]
    # a symbol name means the deps of the file that defines it
    code, out = run_query(sample_repo, capsys, "deps", "data_dir", "--json")
    [res] = json.loads(out.out)
    assert res["node"] == U
    assert [d["id"] for d in res["imports"]] == ["ext:os"]
    assert [d["id"] for d in res["imported_by"]] == [R, S]


def test_query_deps_text(sample_repo, capsys):
    code, out = run_query(sample_repo, capsys, "deps", "app/utils.py")
    assert out.out == (
        f"deps of {U}\n"
        "  imports:\n"
        "    ext:os\n"
        "  imported by:\n"
        f"    {R}\n"
        f"    {S}\n"
    )


def test_query_no_match(sample_repo, capsys):
    code, out = run_query(sample_repo, capsys, "callers", "nope")
    assert code == 1
    assert "no node matches 'nope'" in out.err


def test_query_without_graph(sample_repo, capsys):
    assert main(["query", str(sample_repo), "callers", "validate"]) == 1
    assert "reaper map" in capsys.readouterr().err
