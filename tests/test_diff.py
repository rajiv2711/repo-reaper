"""`reaper diff`: the working tree compared with a commit (reaper/diff.py).

Scenario on a git copy of tests/fixtures/sample_py. Base commit = the fixture plus app/legacy.py
and a .gitignore (*.log). Then, uncommitted:
  - app/service.py: line 26 inside UserService.log changed; new method UserService.audit
    (lines 28-30) that calls normalize (imported from app.utils)
  - app/utils.py: data_dir (lines 15-17, after two blank lines) deleted, so
    UserRepository.__init__'s call to it loses its link (repository.py itself is unchanged)
  - app/audit_log.py: new, untracked; record (lines 5-8) calls UserService
  - app/legacy.py: deleted (old_name, lines 4-6)
  - README.md: one line appended and staged
  - debug.log: new but ignored, so not a change
Expected values are written by hand from that scenario.
"""

import json
import subprocess

import pytest

from reaper import graph as graph_mod
from reaper.diff import DiffError, diff, format_diff

LEGACY = '"""Old helpers."""\n\n\ndef old_name():\n    """Unused."""\n    return "old"\n'
AUDIT_LOG = ('"""Audit trail."""\nfrom app.service import UserService\n\n\n'
             'def record(name):\n    """Build a service for the audit trail."""\n'
             '    service = UserService()\n    return service\n')
LOG_NEW = ('            print("[app] " + message)\n\n'
           '    def audit(self):\n        """Return the normalized service name."""\n'
           '        return normalize("Audit")\n')


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
                           "-c", "commit.gpgsign=false", *args],
                          cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def changed_repo(sample_repo):
    (sample_repo / "app" / "legacy.py").write_text(LEGACY)
    (sample_repo / ".gitignore").write_text("*.log\n")
    git(sample_repo, "init", "-q")
    git(sample_repo, "symbolic-ref", "HEAD", "refs/heads/main")
    git(sample_repo, "add", "-A")
    git(sample_repo, "commit", "-q", "-m", "base")

    service = sample_repo / "app" / "service.py"
    text = service.read_text()
    assert text.endswith("            print(message)\n")
    service.write_text(text[:-len("            print(message)\n")] + LOG_NEW)
    utils = sample_repo / "app" / "utils.py"
    lines = utils.read_text().splitlines(keepends=True)
    assert lines[14].startswith("def data_dir") and len(lines) == 17
    utils.write_text("".join(lines[:12]))
    (sample_repo / "app" / "audit_log.py").write_text(AUDIT_LOG)
    (sample_repo / "app" / "legacy.py").unlink()
    with open(sample_repo / "README.md", "a") as f:
        f.write("Extra line.\n")
    git(sample_repo, "add", "README.md")
    (sample_repo / "debug.log").write_text("noise\n")
    return sample_repo


def run_diff(repo, base="HEAD"):
    g, _ = graph_mod.update(repo)
    return diff(repo, g, base)


def test_file_statuses_and_line_counts(changed_repo):
    d = run_diff(changed_repo)
    assert d["files"] == {
        "README.md": "modified",
        "app/audit_log.py": "added",
        "app/legacy.py": "deleted",
        "app/service.py": "modified",
        "app/utils.py": "modified",
    }
    assert d["stats"] == {
        "README.md": [1, 0],
        "app/audit_log.py": [8, 0],
        "app/legacy.py": [0, 6],
        "app/service.py": [5, 1],
        "app/utils.py": [0, 5],
    }
    assert (d["base"], d["branch"]) == ("HEAD", "main")
    assert d["commit"] == git(changed_repo, "rev-parse", "HEAD")


def test_node_statuses(changed_repo):
    """A symbol is modified when a changed non-blank line falls inside it and in no deeper
    symbol: UserService.log is, the class UserService is not (line 27 is blank)."""
    assert run_diff(changed_repo)["nodes"] == {
        "README.md": "modified",
        "app/audit_log.py": "added",
        "app/audit_log.py::record": "added",
        "app/legacy.py": "deleted",
        "app/legacy.py::old_name": "deleted",
        "app/service.py": "modified",
        "app/service.py::UserService.audit": "added",
        "app/service.py::UserService.log": "modified",
        "app/utils.py": "modified",
        "app/utils.py::data_dir": "deleted",
    }


def test_extra_nodes(changed_repo):
    """Nodes the current graph lacks: deleted ones (as they were at the base) and changed files
    that are not parsed (README.md)."""
    extra = {n["id"]: n for n in run_diff(changed_repo)["extra_nodes"]}
    assert sorted(extra) == ["README.md", "app/legacy.py", "app/legacy.py::old_name",
                             "app/utils.py::data_dir"]
    assert extra["README.md"] == {"id": "README.md", "kind": "file", "name": "README.md",
                                  "file": "README.md", "line": 1, "signature": None, "doc": None}
    dd = extra["app/utils.py::data_dir"]
    assert (dd["kind"], dd["line"], dd["end_line"], dd["signature"]) == (
        "function", 15, 17, "data_dir()")


def test_link_changes(changed_repo):
    d = run_diff(changed_repo)
    assert d["edges"]["added"] == [
        ["app/audit_log.py", "app/audit_log.py::record", "contains"],
        ["app/audit_log.py", "app/service.py", "imports"],
        ["app/audit_log.py::record", "app/service.py::UserService", "calls"],
        ["app/service.py::UserService", "app/service.py::UserService.audit", "contains"],
        ["app/service.py::UserService.audit", "app/utils.py::normalize", "calls"],
    ]
    removed = [(e["src"], e["dst"], e["kind"], e["confidence"]) for e in d["edges"]["removed"]]
    assert removed == [
        ("app/legacy.py", "app/legacy.py::old_name", "contains", "EXTRACTED"),
        ("app/repository.py::UserRepository.__init__", "app/utils.py::data_dir", "calls",
         "EXTRACTED"),
        ("app/utils.py", "app/utils.py::data_dir", "contains", "EXTRACTED"),
    ]


def test_base_ref_and_no_changes(changed_repo):
    git(changed_repo, "add", "-A")
    git(changed_repo, "commit", "-q", "-m", "agent work")
    assert run_diff(changed_repo)["files"] == {}
    d = run_diff(changed_repo, "HEAD~1")
    assert (d["base"], d["commit"]) == ("HEAD~1", git(changed_repo, "rev-parse", "HEAD~1"))
    assert d["files"]["app/legacy.py"] == "deleted"
    assert d["nodes"]["app/service.py::UserService.log"] == "modified"


def test_errors(changed_repo, tmp_path):
    g, _ = graph_mod.update(changed_repo)
    with pytest.raises(DiffError, match="unknown base: nope"):
        diff(changed_repo, g, "nope")
    plain = tmp_path / "plain"
    plain.mkdir()
    with pytest.raises(DiffError, match="not a git repository"):
        diff(plain, g, "HEAD")


def test_format(changed_repo):
    g, _ = graph_mod.update(changed_repo)
    d = diff(changed_repo, g)
    short = d["commit"][:7]
    assert format_diff(d, g) == "\n".join([
        f"changes since HEAD ({short}, branch main): 5 files: 1 added, 3 modified, 1 deleted",
        "  M  README.md  +1",
        "  A  app/audit_log.py  +8",
        "       A  record  (line 5)",
        "  D  app/legacy.py  -6",
        "       D  old_name  (line 4)",
        "  M  app/service.py  +5 -1",
        "       M  UserService.log  (line 23)",
        "       A  UserService.audit  (line 28)",
        "  M  app/utils.py  -5",
        "       D  data_dir  (line 15)",
        "links: 3 new, 1 removed (imports +1, calls +2 -1)",
    ])


def test_format_no_changes(changed_repo):
    git(changed_repo, "add", "-A")
    git(changed_repo, "commit", "-q", "-m", "agent work")
    g, _ = graph_mod.update(changed_repo)
    d = diff(changed_repo, g)
    assert format_diff(d, g) == f"no changes since HEAD ({d['commit'][:7]}, branch main)"


# ---------------------------------------------------------------- page data and CLI

def test_page_data(changed_repo):
    """graph.html gets a `diff` block: statuses by node id and by page edge id ("e<i>" = the
    graph's edge i; "x<j>" = removed edge j, drawn only with Diff on), plus the nodes and edges
    the current graph lacks, marked diffOnly (and ghost when deleted). The graph's own nodes and
    edges in the page data are not touched."""
    from test_html_template import html_data
    from reaper import outputs

    g, _ = graph_mod.update(changed_repo)
    d = diff(changed_repo, g)
    assert html_data(outputs.graph_html(g))["diff"] is None
    data = html_data(outputs.graph_html(g, None, d))
    assert len(data["edges"]) == len(g["edges"]) and len(data["nodes"]) == len(g["nodes"])
    page = data["diff"]
    assert (page["base"], page["commit"], page["branch"]) == ("HEAD", d["commit"], "main")
    assert page["files"] == d["files"] and page["stats"] == d["stats"] and page["nodes"] == d["nodes"]
    ends = {e["id"]: (e["from"], e["to"], e["kind"]) for e in data["edges"]}
    added = sorted(ends[i] for i, s in page["edges"].items() if s == "added")
    assert added == [
        ("app/audit_log.py", "app/audit_log.py::record", "contains"),
        ("app/audit_log.py", "app/service.py", "imports"),
        ("app/audit_log.py::record", "app/service.py::UserService", "calls"),
        ("app/service.py::UserService", "app/service.py::UserService.audit", "contains"),
        ("app/service.py::UserService.audit", "app/utils.py::normalize", "calls"),
    ]
    assert {i: s for i, s in page["edges"].items() if s == "removed"} == {
        "x0": "removed", "x1": "removed", "x2": "removed"}
    assert [(e["id"], e["from"], e["to"], e["kind"], e["confidence"], e["diffOnly"])
            for e in page["extra_edges"]] == [
        ("x0", "app/legacy.py", "app/legacy.py::old_name", "contains", "EXTRACTED", True),
        ("x1", "app/repository.py::UserRepository.__init__", "app/utils.py::data_dir", "calls",
         "EXTRACTED", True),
        ("x2", "app/utils.py", "app/utils.py::data_dir", "contains", "EXTRACTED", True),
    ]
    assert [(n["id"], n["label"], n["kind"], n["diffOnly"], n["ghost"])
            for n in page["extra_nodes"]] == [
        ("README.md", "README.md", "file", True, False),
        ("app/legacy.py", "app/legacy.py", "file", True, True),
        ("app/legacy.py::old_name", "old_name", "function", True, True),
        ("app/utils.py::data_dir", "data_dir", "function", True, True),
    ]


def test_cli_diff(changed_repo, capsys):
    from reaper.cli import main
    from test_html_template import html_data

    assert main(["diff", str(changed_repo)]) == 0
    out = capsys.readouterr().out
    assert "changes since HEAD (" in out and "  A  app/audit_log.py  +8\n" in out
    assert "links: 3 new, 1 removed (imports +1, calls +2 -1)\n" in out
    assert "key: A added, M modified, D deleted" in out
    html = (changed_repo / ".reaper" / "graph.html").read_text()
    assert html_data(html)["diff"]["files"]["app/legacy.py"] == "deleted"
    assert graph_mod.load(changed_repo)["meta"]["version"] == graph_mod.VERSION
    # a plain run writes the page without the diff again
    assert main(["run", str(changed_repo)]) == 0
    assert html_data((changed_repo / ".reaper" / "graph.html").read_text())["diff"] is None


def test_cli_diff_base_and_errors(changed_repo, tmp_path, capsys):
    from reaper.cli import main

    assert main(["diff", str(changed_repo), "--base", "nope"]) == 1
    assert capsys.readouterr().err.strip() == "error: unknown base: nope"
    assert not (changed_repo / ".reaper").exists()  # nothing written on an error
    git(changed_repo, "add", "-A")
    git(changed_repo, "commit", "-q", "-m", "agent work")
    out_dir = tmp_path / "out"
    assert main(["diff", str(changed_repo), "--base", "HEAD~1", "--out", str(out_dir)]) == 0
    assert "changes since HEAD~1 (" in capsys.readouterr().out
    assert (out_dir / "graph.html").exists()
    plain = tmp_path / "plain"
    plain.mkdir()
    assert main(["diff", str(plain)]) == 1
    assert capsys.readouterr().err.startswith("error: not a git repository")


# ---------------------------------------------------------------- graph.html Diff layer (node)

def diff_html(repo):
    from reaper import outputs

    g, _ = graph_mod.update(repo)
    return outputs.graph_html(g, None, diff(repo, g))


def page(html, expr):
    from test_html_template import run_js

    return run_js(html, expr)


def modes(html, body):
    from test_html_tree import run_modes

    return run_modes(html, body)


def test_js_diff_only_items_follow_the_toggle(changed_repo):
    html = diff_html(changed_repo)
    got = page(html, '(() => { const on = applyView(); diffOn = false; const off = applyView(); '
                     'const ids = ["app/legacy.py", "app/legacy.py::old_name", "app/utils.py::data_dir", '
                     '"README.md"]; return [ids.map(i => on.nodes.has(i)), ids.map(i => off.nodes.has(i)), '
                     '["x0", "x1", "x2"].map(i => on.raw.has(i)), ["x0", "x1", "x2"].map(i => off.raw.has(i)), '
                     'rank("data_dir").length, (diffOn = true, rank("data_dir"))]; })()')
    assert got == [[True] * 4, [False] * 4, [True] * 3, [False] * 3, 0, ["app/utils.py::data_dir"]]


def test_js_diff_node_colours(changed_repo):
    html = diff_html(changed_repo)
    ids = ["app/service.py::UserService.log", "app/models.py::User", "app/audit_log.py",
           "app/utils.py::data_dir"]
    got = page(html, f'(() => {{ const ids = {json.dumps(ids)}; const on = ids.map(llmColour); '
                     'diffOn = false; return [on, ids.slice(0, 3).map(llmColour)]; })()')
    assert got == [
        [{"color": "#b26b00"}, {"color": "#8a8a8a"}, {"color": "#2f8a3a"},
         {"color": {"background": "#c0392b", "border": "#c0392b"}, "opacity": 0.55,
          "shapeProperties": {"borderDashes": [4, 3]}}],
        [{"color": "#72b7b2"}, {"color": "#b279a2"}, {"color": "#4c78a8"}],
    ]
    # a page without a diff sends no colour, as before
    from reaper import outputs
    plain = outputs.graph_html(graph_mod.update(changed_repo)[0])
    assert page(plain, 'llmColour("app/models.py::User")') == {}


def test_js_diff_tree_opens_on_the_changes(changed_repo):
    html = diff_html(changed_repo)
    got = page(html, '(() => { state.closed = diffClosed(); const p = treeLayout(applyView()).pos; '
                     'return [[...state.closed].sort(), Object.entries(p).map(([id, q]) => [id, q.x / COL, q.y / ROW])'
                     '.sort((a, b) => a[2] - b[2])]; })()')
    closed, rows = got
    assert closed == ["app/models.py", "app/repository.py"]
    assert rows == [
        ["dir:app/", 0, 0],
        ["app/__init__.py", 1, 1],
        ["app/audit_log.py", 1, 2],
        ["app/audit_log.py::record", 2, 3],
        ["app/legacy.py", 1, 4],
        ["app/legacy.py::old_name", 2, 5],
        ["app/models.py", 1, 6],
        ["app/repository.py", 1, 7],
        ["app/service.py", 1, 8],
        ["app/service.py::UserService", 2, 9],
        ["app/service.py::UserService.__init__", 3, 10],
        ["app/service.py::UserService.create", 3, 11],
        ["app/service.py::UserService.log", 3, 12],
        ["app/service.py::UserService.audit", 3, 13],
        ["app/utils.py", 1, 14],
        ["app/utils.py::normalize", 2, 15],
        ["app/utils.py::validate", 2, 16],
        ["app/utils.py::data_dir", 2, 17],
        ["README.md", 0, 18],
        ["ext:json", 0, 20],
        ["ext:os", 0, 21],
    ]


def test_js_diff_edges_and_relations(changed_repo):
    html = diff_html(changed_repo)
    new_call = ('Object.keys(D.diff.edges).find(i => D.diff.edges[i] === "added" && '
                'edgeById.get(i).to === "app/utils.py::normalize")')
    got = modes(html, f'graphLaidOut(); const id = {new_call}; const look = i => {{ const e = edges.m.get(i); '
                      'return [e.color, e.width, e.dashes]; }; const on = [look(id), look("x1")]; '
                      'const rel = relations("app/utils.py::normalize").callers; '
                      'const dd = relations("app/utils.py::data_dir"); '
                      'setDiff(false); return [on, look(id), rel, dd.callers, dd["contained in"]];')
    on, off, callers, dd_callers, dd_in = got
    assert on == [[{"color": "#2f8a3a", "opacity": 1}, 2, False],
                  [{"color": "#c0392b", "opacity": 0.8}, 2, [4, 4]]]
    assert off == ["#f58518", 1, False]
    assert callers == [["app/service.py::UserService.audit", "EXTRACTED", "added"],
                       ["app/service.py::UserService.create", "EXTRACTED"],
                       ["app/utils.py::validate", "EXTRACTED"]]
    assert dd_callers == [["app/repository.py::UserRepository.__init__", "EXTRACTED", "removed"]]
    assert dd_in == [["app/utils.py", "EXTRACTED", "removed"]]


def test_js_diff_bundle_shows_a_new_link(changed_repo):
    """app/service.py closed: its calls to normalize fold into one bundle, green because one of
    them (UserService.audit's) is new."""
    html = diff_html(changed_repo)
    got = page(html, '(() => { state.closed = new Set(["app/service.py"]); const T = treeView(applyView()); '
                     'const f = T.folds.get("d:app/service.py -> app/utils.py::normalize"); '
                     'const on = bundleStyle(f).color, drawn = foldLook(f); diffOn = false; '
                     'return [f.diff, on, bundleStyle(f).color, [drawn.color, drawn.width], foldLook(f).color]; })()')
    # drawn at full strength while Diff is on (a plain bundle is calmed to 30% opacity)
    assert got == [{"added": 1}, "#2f8a3a", "#f58518", ["#2f8a3a", 2], {"color": "#f58518", "opacity": 0.3}]


def test_js_diff_change_rows(changed_repo):
    html = diff_html(changed_repo)
    assert page(html, "changeRows()") == [
        ["README.md", "M", "+1"],
        ["app/audit_log.py", "A", "+8"],
        ["app/legacy.py", "D", "-6"],
        ["app/service.py", "M", "+5 -1"],
        ["app/utils.py", "M", "-5"],
    ]


def test_js_tree_is_the_default_view(changed_repo):
    """boot(): the Graph network lays itself out hidden, then Tree opens (with or without a diff)."""
    from reaper import outputs

    for html in (diff_html(changed_repo), outputs.graph_html(graph_mod.update(changed_repo)[0])):
        got = modes(html, 'boot(); const before = [mode, els.net.cls.has("off"), nets.length]; '
                          'nodes.update(D.nodes.map((n, i) => ({id: n.id, x: i, y: i}))); '
                          'nets[0].emit("stabilizationIterationsDone"); '
                          'return [before, mode, net === nets[1], els.net.cls.has("off"), els.tree.cls.has("off")];')
        assert got == [["graph", True, 1], "tree", True, True, False]
