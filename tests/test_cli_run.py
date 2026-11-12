"""`reaper run`, `--out DIR`, `--version`, and graph.html refreshed by `reaper enrich`.

Expected values are written by hand from tests/fixtures/sample_py: 5 code files (app/__init__,
models, repository, service, utils .py) and one README.md; one Louvain group (see
test_enrich_groups.test_fixture_is_one_group). So `run --llm` asks 5 file calls, 1 group call
and 1 architecture call, in that order. No Ollama is called: llm.chat is replaced by FakeLLM.
"""

import json
import re

import pytest

from reaper import enrich, llm
from reaper.cli import main

CODE_FILES = ["app/__init__.py", "app/models.py", "app/repository.py", "app/service.py",
              "app/utils.py"]
OUTPUTS = {"graph.json", "TREE.txt", "SUMMARY.md", "graph.html"}


class FakeLLM:
    """Stands in for llm.chat; answers each pass by its system prompt; can fail on call N."""

    def __init__(self, fail_at=None):
        self.calls = []  # (pass, model)
        self.fail_at = fail_at

    def __call__(self, model, messages, schema):
        kind = {enrich.FILES_SYSTEM: "files", enrich.GROUPS_SYSTEM: "groups",
                enrich.ARCH_SYSTEM: "architecture"}[messages[0]["content"]]
        self.calls.append((kind, model))
        if self.fail_at == len(self.calls):
            raise llm.LLMError("cannot reach Ollama at x")
        if kind == "files":
            return {"summary": "Does a thing.", "role": "utility"}
        if kind == "groups":
            return {"name": "App", "summary": "The app."}
        return {"overview": "One package.", "decisions": [],
                "patterns": [{"name": "Layers", "explanation": "x",
                              "evidence": ["app/service.py"]}]}

    @property
    def passes(self):
        return [kind for kind, _ in self.calls]


@pytest.fixture
def fake(monkeypatch):
    f = FakeLLM()
    monkeypatch.setattr(llm, "chat", f)
    return f


def html_data(path):
    html = path.read_text(encoding="utf-8")
    m = re.search(r'<script id="graph-data" type="application/json">(.*?)</script>', html, re.S)
    assert m, "embedded graph data not found"
    return json.loads(m.group(1))


# ---------------------------------------------------------------- --version


def test_version(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0
    assert capsys.readouterr().out == "reaper 0.1.0\n"


# ---------------------------------------------------------------- --out


def test_out_puts_every_output_there(sample_repo, tmp_path, capsys):
    out = tmp_path / "elsewhere" / "sample"
    assert main(["map", str(sample_repo), "--out", str(out)]) == 0
    assert main(["export", str(sample_repo), "--out", str(out)]) == 0
    assert {p.name for p in out.iterdir()} == OUTPUTS
    assert not (sample_repo / ".reaper").exists()
    capsys.readouterr()
    assert main(["query", str(sample_repo), "--out", str(out), "deps", "app/service.py"]) == 0
    assert "    app/repository.py\n" in capsys.readouterr().out


def test_out_missing_graph_hint_names_out(sample_repo, tmp_path, capsys):
    out = tmp_path / "o"
    assert main(["export", str(sample_repo), "--out", str(out)]) == 1
    assert f"run `reaper map {sample_repo} --out {out}` first" in capsys.readouterr().err


def test_out_inside_repo_is_never_mapped(sample_repo, capsys):
    out = sample_repo / "reaper-out"
    assert main(["run", str(sample_repo), "--out", str(out)]) == 0
    capsys.readouterr()
    assert main(["update", str(sample_repo), "--out", str(out)]) == 0
    assert capsys.readouterr().out.startswith("0 added, 0 changed, 0 deleted, 6 unchanged\n")
    graph = json.loads((out / "graph.json").read_text())
    assert not [p for p in graph["files"] if p.startswith("reaper-out/")]


def test_out_must_not_be_the_repo(sample_repo):
    with pytest.raises(SystemExit) as e:
        main(["map", str(sample_repo), "--out", str(sample_repo)])
    assert e.value.code == 2


# ---------------------------------------------------------------- run


def test_run_structure_only(sample_repo, fake, capsys):
    assert main(["run", str(sample_repo)]) == 0
    out = sample_repo / ".reaper"
    assert {p.name for p in out.iterdir()} == OUTPUTS
    assert fake.calls == []
    assert html_data(out / "graph.html")["sem"] is None
    assert capsys.readouterr().out.startswith("6 added, 0 changed, 0 deleted, 0 unchanged\n")


def test_run_llm_passes_in_order_then_cached(sample_repo, fake):
    assert main(["run", str(sample_repo), "--llm"]) == 0
    assert fake.passes == ["files"] * 5 + ["groups", "architecture"]
    assert fake.calls[0][1] == "devstral-small-2:24b"
    assert {m for k, m in fake.calls if k != "files"} == {"qwen3-coder:30b"}
    out = sample_repo / ".reaper"
    assert {p.name for p in out.iterdir()} == OUTPUTS | {"semantic.json", "ARCHITECTURE.md"}
    sem = html_data(out / "graph.html")["sem"]
    assert sorted(sem["files"]) == CODE_FILES
    assert [g["name"] for g in sem["groups"].values()] == ["App"]
    assert sem["architecture"]["overview"] == "One package."
    fake.calls.clear()
    assert main(["run", str(sample_repo), "--llm"]) == 0
    assert fake.calls == []


def test_run_llm_one_model_for_every_pass(sample_repo, fake, tmp_path):
    assert main(["run", str(sample_repo), "--llm", "--model", "tiny:1b",
                 "--out", str(tmp_path / "o")]) == 0
    assert len(fake.calls) == 7 and {m for _, m in fake.calls} == {"tiny:1b"}


def test_run_llm_failure_stops_passes_but_exports(sample_repo, monkeypatch, capsys):
    fake = FakeLLM(fail_at=1)
    monkeypatch.setattr(llm, "chat", fake)
    assert main(["run", str(sample_repo), "--llm"]) == 1
    assert fake.passes == ["files"]  # groups and architecture never asked
    assert (sample_repo / ".reaper" / "graph.html").exists()
    err = capsys.readouterr().err
    assert "error: cannot reach Ollama at x" in err
    assert "stopped at the files pass" in err


# ---------------------------------------------------------------- enrich refreshes graph.html


def test_enrich_refreshes_graph_html(sample_repo, fake, capsys):
    assert main(["run", str(sample_repo)]) == 0
    html = sample_repo / ".reaper" / "graph.html"
    assert html_data(html)["sem"] is None
    capsys.readouterr()
    assert main(["enrich", str(sample_repo), "--pass", "files"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == str(html)
    assert sorted(html_data(html)["sem"]["files"]) == CODE_FILES


def test_enrich_dry_run_or_error_writes_no_html(sample_repo, fake):
    assert main(["map", str(sample_repo)]) == 0
    html = sample_repo / ".reaper" / "graph.html"
    assert main(["enrich", str(sample_repo), "--pass", "files", "--dry-run"]) == 0
    assert main(["enrich", str(sample_repo), "--pass", "architecture"]) == 1  # no groups yet
    assert not html.exists() and fake.calls == []
