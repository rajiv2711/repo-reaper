"""Every output explains its own labels, with the same words (reaper/legend.py)."""

import json

from reaper import enrich, legend, outputs
from reaper.cli import main
from reaper.graph import graph_path


def test_every_output_file_carries_the_legend(sample_repo):
    assert main(["run", str(sample_repo)]) == 0
    out = graph_path(sample_repo).parent
    graph = json.loads((out / "graph.json").read_text())
    assert list(graph)[:2] == ["meta", "legend"]           # near the top of the file
    assert set(graph["legend"]["confidence"]) == {"EXTRACTED", "INFERRED", "AMBIGUOUS"}
    assert graph["legend"]["completeness"].startswith("for `callers NAME`, every call site")
    files = {name: (out / name).read_text() for name in ("SUMMARY.md", "TREE.txt", "graph.html")}
    for label, meaning in legend.CONFIDENCE.items():
        assert graph["legend"]["confidence"][label] == meaning
        for name, text in files.items():
            assert meaning in text, (name, label)
    assert legend.COMPLETENESS in files["SUMMARY.md"] and legend.COMPLETENESS in files["TREE.txt"]
    # SUMMARY.md: a section before the stats; TREE.txt: '#' header lines before the first file
    summary = files["SUMMARY.md"]
    assert summary.index("## How to read this graph") < summary.index("## Stats")
    header = files["TREE.txt"].split("\n\n", 1)[0].splitlines()
    assert header[0].startswith("# repo-reaper TREE.txt") and all(line.startswith("#") for line in header)


def test_html_legend_is_a_comment_at_the_top_of_head(sample_repo):
    assert main(["run", str(sample_repo)]) == 0
    html = (graph_path(sample_repo).parent / "graph.html").read_text()
    head = html[html.index("<head>"):html.index("<meta charset")]
    assert head.startswith("<head>\n<!--\nrepo-reaper graph.html:") and head.endswith("-->\n")
    assert head.count("-->") == 1                            # the legend cannot end the comment early
    assert "EXTRACTED: proven by the code" in head


def test_semantic_json_explains_its_fields_and_reads_back_without_it(tmp_path):
    sem = {"files": {"a.py": {"summary": "s", "role": "r", "input_sha": "x", "model": "m"}},
           "groups": {}, "architecture": {}}
    path = enrich.save_semantic(tmp_path, sem)
    on_disk = json.loads(path.read_text())
    assert list(on_disk)[0] == "legend" and on_disk["legend"]["summary"].startswith("LLM-written")
    assert enrich.load_semantic(tmp_path) == sem             # the legend is for readers, not data


def test_query_key_is_printed_once_after_all_answers(sample_repo, capsys):
    assert main(["map", str(sample_repo)]) == 0
    capsys.readouterr()
    assert main(["query", str(sample_repo), "callers", "validate"]) == 0   # two matching nodes
    out = capsys.readouterr().out
    assert out.count("key: EXTRACTED") == 1 and out.count("complete: every call") == 1
    assert main(["query", str(sample_repo), "deps", "app/utils.py"]) == 0
    assert "key:" not in capsys.readouterr().out            # deps has no confidences to explain
    assert outputs.format_query("callees", [{"node": "x", "line": 1, "callees": []}]) == (
        "callees of x  (line 1)\n  (none)\n")                # nothing listed: no key
