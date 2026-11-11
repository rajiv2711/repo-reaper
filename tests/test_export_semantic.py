"""Phase 8 (08-03): `reaper export` wiring of the semantic layer (D-02, D-08).

`reaper export` reads .reaper/semantic.json when it exists (no CLI change) and passes
enrich.view_semantic(...) to outputs.export; without semantic.json graph.html is byte-identical
to the structural page. Expected values are written by hand from tests/fixtures/sample_py.
"""

import json
import re

from reaper import enrich, outputs
from reaper.cli import main
from reaper.graph import graph_path, load

M = "app/models.py"


def html_data(html):
    m = re.search(r'<script id="graph-data" type="application/json">(.*?)</script>', html, re.S)
    assert m, "embedded graph data not found"
    return json.loads(m.group(1))


def read_html(repo):
    return (graph_path(repo).parent / "graph.html").read_text(encoding="utf-8")


def write_semantic(repo, text):
    path = enrich.semantic_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


SEM = {"files": {M: {"summary": "Makes users <b>x</b></script>", "role": "model",
                     "model": "m", "input_sha": "x"}}}


# ---------------------------------------------------------------- 08-03-1

def test_export_without_semantic_is_byte_identical(sample_repo):
    assert main(["map", str(sample_repo)]) == 0
    assert main(["export", str(sample_repo)]) == 0
    html = read_html(sample_repo)
    graph = load(sample_repo)
    assert html == outputs.graph_html(graph) == outputs.graph_html(graph, None)
    assert html_data(html)["sem"] is None


def test_export_with_semantic_embeds_view(sample_repo):
    assert main(["map", str(sample_repo)]) == 0
    write_semantic(sample_repo, json.dumps(SEM))
    assert main(["export", str(sample_repo)]) == 0
    html = read_html(sample_repo)
    data = html_data(html)
    assert data["sem"]["files"][M] == {"summary": "Makes users <b>x</b></script>",
                                       "role": "model", "model": "m", "stale": True}
    assert "<b>x</b>" not in html
    assert not [n["id"] for n in data["nodes"] if "Makes users" in (n["title"] or "")]


def test_export_corrupt_semantic_warns(sample_repo, capsys):
    assert main(["map", str(sample_repo)]) == 0
    write_semantic(sample_repo, "{not json")
    capsys.readouterr()
    assert main(["export", str(sample_repo)]) == 0
    err = capsys.readouterr().err
    assert "semantic.json" in err and "not valid JSON" in err
    assert html_data(read_html(sample_repo))["sem"] is None


def test_export_non_object_semantic_warns(sample_repo, capsys):
    # [Rule 2] valid JSON that is not an object: warn and fall back, never crash export
    assert main(["map", str(sample_repo)]) == 0
    for text in ("[]", "null"):
        write_semantic(sample_repo, text)
        capsys.readouterr()
        assert main(["export", str(sample_repo)]) == 0
        err = capsys.readouterr().err
        assert "semantic.json" in err and "not a JSON object" in err
        assert html_data(read_html(sample_repo))["sem"] is None


# ---------------------------------------------------------------- 08-03-2 (regression guards)

def test_export_leaves_inputs_untouched(sample_repo):
    assert main(["map", str(sample_repo)]) == 0
    sem_path = write_semantic(sample_repo, json.dumps(SEM))
    graph_bytes, sem_bytes = graph_path(sample_repo).read_bytes(), sem_path.read_bytes()
    assert main(["export", str(sample_repo)]) == 0
    assert graph_path(sample_repo).read_bytes() == graph_bytes
    assert sem_path.read_bytes() == sem_bytes


def test_export_tree_summary_unchanged_by_semantic(sample_repo):
    out = graph_path(sample_repo).parent
    assert main(["map", str(sample_repo)]) == 0
    assert main(["export", str(sample_repo)]) == 0
    before = [(out / name).read_text(encoding="utf-8") for name in ("TREE.txt", "SUMMARY.md")]
    write_semantic(sample_repo, json.dumps(SEM))
    assert main(["export", str(sample_repo)]) == 0
    after = [(out / name).read_text(encoding="utf-8") for name in ("TREE.txt", "SUMMARY.md")]
    assert after == before
