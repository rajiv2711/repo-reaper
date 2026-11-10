import json
from collections import Counter

from reaper.cli import main
from reaper.graph import build, graph_path, load, save


def test_build_fixture(sample_repo):
    g = build(sample_repo)
    assert set(g) == {"meta", "files", "nodes", "refs", "edges"}
    assert set(g["meta"]) == {"version", "generated_at"}
    # every discovered file is tracked (hashes drive incremental updates) ...
    assert list(g["files"]) == ["README.md", "app/__init__.py", "app/models.py",
                                "app/repository.py", "app/service.py", "app/utils.py"]
    # ... but only files with an extractor (Python for now) get nodes
    # Phase 3: resolve adds one external node per out-of-repo import package (ext:json, ext:os)
    assert Counter(n["kind"] for n in g["nodes"]) == {
        "file": 5, "class": 4, "method": 10, "function": 4, "external": 2}
    assert "README.md" not in {n["file"] for n in g["nodes"]}
    assert Counter(r["kind"] for r in g["refs"]) == {"import": 9, "call": 25, "inherit": 1}
    assert Counter(e["kind"] for e in g["edges"]) == {
        "contains": 18, "imports": 8, "inherits": 1, "calls": 12}
    assert len({n["id"] for n in g["nodes"]}) == len(g["nodes"])


def test_save_load_roundtrip(sample_repo):
    g = build(sample_repo)
    path = save(sample_repo, g)
    assert path == graph_path(sample_repo) == sample_repo / ".reaper" / "graph.json"
    assert load(sample_repo) == g
    assert not list(path.parent.glob("*.tmp"))


def test_cli_map(sample_repo, capsys):
    assert main(["map", str(sample_repo)]) == 0
    g = json.loads((sample_repo / ".reaper" / "graph.json").read_text())
    assert len(g["nodes"]) == 25 and len(g["refs"]) == 35 and len(g["edges"]) == 39
    out = capsys.readouterr().out
    assert "graph.json" in out and "25 nodes" in out and "35 refs" in out and "39 edges" in out
    # .reaper/ output is never picked up as input on the next run
    assert main(["map", str(sample_repo)]) == 0
    assert ".reaper/graph.json" not in load(sample_repo)["files"]
