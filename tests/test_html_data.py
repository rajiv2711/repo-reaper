"""Phase 8: the JSON embedded in graph.html (level of detail, payload fields, sem slot).

Expected values are written by hand from tests/fixtures/sample_py and the
"Embedded-JSON contract" of phases-archive:docs/phases/08-html-view/08-PLAN.md.
"""

import json
import re

from reaper import outputs
from reaper.graph import build

M, R, S, U = "app/models.py", "app/repository.py", "app/service.py", "app/utils.py"
C = "app/service.py::UserService.create"


def write(root, files):
    for rel, src in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src)
    return root


def html_data(html):
    m = re.search(r'<script id="graph-data" type="application/json">(.*?)</script>', html, re.S)
    assert m, "embedded graph data not found"
    return json.loads(m.group(1))


# One bundle per (file, file) pair; contains and same-file edges left out; sorted by (from, to).
FILE_EDGES = [
    {"id": "f0", "from": R, "to": M, "count": 1,
     "counts": {"imports": {"EXTRACTED": 1}}},
    {"id": "f1", "from": R, "to": U, "count": 2,
     "counts": {"calls": {"EXTRACTED": 1}, "imports": {"EXTRACTED": 1}}},
    {"id": "f2", "from": R, "to": "ext:json", "count": 1,
     "counts": {"imports": {"EXTRACTED": 1}}},
    {"id": "f3", "from": S, "to": M, "count": 3,
     "counts": {"calls": {"EXTRACTED": 1, "INFERRED": 1}, "imports": {"EXTRACTED": 1}}},
    {"id": "f4", "from": S, "to": R, "count": 3,
     "counts": {"calls": {"EXTRACTED": 1, "INFERRED": 1}, "imports": {"EXTRACTED": 1}}},
    {"id": "f5", "from": S, "to": U, "count": 3,
     "counts": {"calls": {"EXTRACTED": 2}, "imports": {"EXTRACTED": 1}}},
    {"id": "f6", "from": S, "to": "ext:os", "count": 1,
     "counts": {"imports": {"EXTRACTED": 1}}},
    {"id": "f7", "from": U, "to": "ext:os", "count": 1,
     "counts": {"imports": {"EXTRACTED": 1}}},
]

LOD_NOTE_24 = ("file-level view: graph has 25 nodes and 39 edges (budget 24 nodes, 5000 edges); "
               "double-click a file to expand it")


# ---------------------------------------------------------------- level of detail (08-01-2)

def test_file_edges_fixture(sample_repo):
    fe = outputs.file_edges(build(sample_repo))
    assert fe == FILE_EDGES
    assert sum(f["count"] for f in fe) == 15


def test_html_lod_file_edges(sample_repo, monkeypatch):
    monkeypatch.setattr(outputs, "MAX_HTML_NODES", 24)  # fixture has 25 nodes
    data = html_data(outputs.graph_html(build(sample_repo)))
    assert data["lod"] is True
    assert len(data["nodes"]) == 25
    assert len(data["edges"]) == 39
    assert data["file_edges"] == FILE_EDGES
    assert data["budget"] == {"nodes": 24, "edges": 5000}
    assert data["note"] == LOD_NOTE_24


def test_html_lod_by_edges(sample_repo, monkeypatch):
    monkeypatch.setattr(outputs, "MAX_HTML_EDGES", 38)  # fixture has 39 edges
    data = html_data(outputs.graph_html(build(sample_repo)))
    assert data["lod"] is True
    assert data["note"].endswith("(budget 1500 nodes, 38 edges); double-click a file to expand it")


def test_html_default_not_lod(sample_repo):
    data = html_data(outputs.graph_html(build(sample_repo)))
    assert data["lod"] is False
    assert data["file_edges"] == []
    assert data["note"] == ""
    assert data["budget"] == {"nodes": 1500, "edges": 5000}


# ---------------------------------------------------------------- payload fields + sem (08-01-3)

NODE_KEYS = {"id", "label", "group", "title", "kind", "name", "file", "line", "signature", "doc",
             "deg"}
EDGE_KEYS = {"from", "to", "kind", "confidence", "dashes", "color", "title", "id"}


def test_html_node_fields(sample_repo):
    nodes = html_data(outputs.graph_html(build(sample_repo)))["nodes"]
    assert all(set(n) == NODE_KEYS for n in nodes)
    by_id = {n["id"]: n for n in nodes}
    c = by_id[C]
    assert (c["kind"], c["name"], c["file"], c["line"], c["signature"], c["doc"], c["deg"]) == (
        "method", "create", S, 15, "create(self, entity_id, name)",
        "Validate, build and save a new user.", 6)
    assert {i: by_id[i]["deg"] for i in (R, S, f"{U}::validate", f"{R}::validate", "ext:os")} == {
        R: 4, S: 4, f"{U}::validate": 2, f"{R}::validate": 1, "ext:os": 0}
    ext = by_id["ext:os"]
    assert (ext["file"], ext["line"], ext["signature"], ext["doc"]) == (None, None, None, None)


def test_html_edge_ids(sample_repo):
    edges = html_data(outputs.graph_html(build(sample_repo)))["edges"]
    assert [e["id"] for e in edges] == [f"e{i}" for i in range(39)]
    assert all(set(e) == EDGE_KEYS for e in edges)


def test_html_top_level(sample_repo):
    g = build(sample_repo)
    data = html_data(outputs.graph_html(g))
    assert set(data) == {"nodes", "edges", "note", "lod", "budget", "meta", "file_edges", "sem",
                         "diff"}
    assert data["meta"] == {"generated_at": g["meta"]["generated_at"], "files": 6, "nodes": 25,
                            "edges": 39}
    assert data["sem"] is None and data["diff"] is None  # diff: only from `reaper diff`
    assert outputs.graph_html(g) == outputs.graph_html(g, None)


SEM = {"files": {M: {"summary": "Makes users <b>x</b></script>\u2028\u2029<!--", "role": "model",
                     "model": "m", "stale": True}},
       "groups": {}, "architecture": None}


def test_html_sem_passthrough_and_escaping(sample_repo):
    html = outputs.graph_html(build(sample_repo), SEM)
    data = html_data(html)
    assert data["sem"] == SEM
    blob = re.search(r'<script id="graph-data" type="application/json">(.*?)</script>',
                     html, re.S).group(1)
    for bad in ("<", "\u2028", "\u2029"):
        assert bad not in blob, repr(bad)
    assert not [n for n in data["nodes"] if "Makes users" in n["title"]]


def test_export_passes_sem(sample_repo):
    g = build(sample_repo)
    out = {p.name: p for p in outputs.export(sample_repo, g, SEM)}
    with_sem = {name: out[name].read_text(encoding="utf-8") for name in out}
    assert html_data(with_sem["graph.html"])["sem"] == SEM
    plain = {p.name: p.read_text(encoding="utf-8") for p in outputs.export(sample_repo, g)}
    assert with_sem["TREE.txt"] == plain["TREE.txt"]
    assert with_sem["SUMMARY.md"] == plain["SUMMARY.md"]
    assert html_data(plain["graph.html"])["sem"] is None
