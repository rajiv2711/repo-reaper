"""Phase 6: `reaper enrich --pass files` with a mocked llm.chat (no real Ollama).

Expected values are written by hand from the fixture source (tests/fixtures/sample_py/app)
and the hand-checked edge list in test_resolve.py (FIXTURE_EDGES).
"""

import hashlib
import json

import pytest

from reaper import enrich, llm
from reaper.cli import main
from reaper.graph import build, save, update

I, M, R, S, U = ("app/__init__.py", "app/models.py", "app/repository.py", "app/service.py",
                 "app/utils.py")
MODEL = "devstral-small-2:24b"

# File rank = sum over the file's nodes of non-contains degree (in + out, edges to externals
# count for the source, as in outputs.degrees); ties by path.
#   service.py    12: file 0+4, UserService.__init__ 1, create 6, log 1
#   models.py     10: file 2, Entity 1 (inherited), Entity.__init__ 1, describe 1,
#                     User 1+1, User.__init__ 1, User.label 1+1
#   repository.py  9: file 1+3, UserRepository 1, __init__ 1, save 1+1, validate 1
#   utils.py       8: file 2+1, normalize 2, validate 1+1, data_dir 1
#   __init__.py    0
RANKED = [S, M, R, U, I]

UTILS_INPUT = '''\
File: app/utils.py

Outline:
app/utils.py (17 lines)
  def normalize(name)  # L5
  def validate(name)  # L10
  def data_dir()  # L15

Source:
"""Small helpers shared across the app."""
import os


def normalize(name):
    """Strip and lowercase a name."""
    return name.strip().lower()


def validate(name):
    """Return True if the name is non-empty after normalizing."""
    return bool(normalize(name))


def data_dir():
    """Return the data directory from the environment."""
    return os.environ.get("APP_DATA", "/tmp/app")
'''


class FakeChat:
    """Stands in for llm.chat; answers per file, can fail for chosen paths."""

    def __init__(self, fail=None, summary="About {path}. It has code.", role="utility"):
        self.calls = []
        self.fail = fail or {}
        self.summary, self.role = summary, role

    def __call__(self, model, messages, schema):
        path = messages[1]["content"].splitlines()[0].removeprefix("File: ")
        self.calls.append({"model": model, "messages": messages, "schema": schema, "path": path})
        if path in self.fail:
            raise self.fail[path]
        return {"summary": self.summary.format(path=path), "role": self.role}

    @property
    def paths(self):
        return [c["path"] for c in self.calls]


@pytest.fixture
def mapped(sample_repo):
    save(sample_repo, build(sample_repo))
    return sample_repo


def run(repo, monkeypatch, fake=None, **kw):
    fake = fake or FakeChat()
    monkeypatch.setattr(llm, "chat", fake)
    graph = json.loads((repo / ".reaper" / "graph.json").read_text())
    return enrich.run_files(repo, graph, **kw), fake


def semantic(repo):
    return json.loads((repo / ".reaper" / "semantic.json").read_text())


def key(model, text):
    return hashlib.sha256(f"{model}\n{enrich.FILES_PROMPT_VERSION}\n{text}".encode()).hexdigest()


def remap(repo):
    graph, _ = update(repo)
    save(repo, graph)


# ---------------------------------------------------------------- inputs

def test_ranked_files(mapped):
    graph = json.loads((mapped / ".reaper" / "graph.json").read_text())
    assert enrich.ranked_files(graph) == RANKED  # README.md has no file node: not a code file


def test_file_input_outline_plus_source(mapped):
    graph = json.loads((mapped / ".reaper" / "graph.json").read_text())
    assert enrich.file_input(graph, mapped, U) == UTILS_INPUT


def test_long_file_truncated_to_first_150_lines(tmp_path):
    (tmp_path / "long.py").write_text("".join(f"x{i} = {i}\n" for i in range(1, 402)))  # 401
    (tmp_path / "edge.py").write_text("".join(f"y{i} = {i}\n" for i in range(1, 301)))  # 300
    graph = build(tmp_path)
    long_in = enrich.file_input(graph, tmp_path, "long.py")
    assert "\nSource (first 150 of 401 lines):\nx1 = 1\n" in long_in
    assert long_in.endswith("x150 = 150\n")
    assert "x151 = 151" not in long_in
    edge_in = enrich.file_input(graph, tmp_path, "edge.py")
    assert "\nSource:\ny1 = 1\n" in edge_in and edge_in.endswith("y300 = 300\n")


# ---------------------------------------------------------------- the pass

def test_first_run_asks_every_file_most_connected_first(mapped, monkeypatch):
    report, fake = run(mapped, monkeypatch)
    assert fake.paths == RANKED
    assert report["called"] == RANKED and report["cached"] == 0 and report["failed"] == {}
    graph = json.loads((mapped / ".reaper" / "graph.json").read_text())
    for call in fake.calls:
        assert call["model"] == MODEL
        assert call["schema"] == enrich.FILES_SCHEMA
        assert [m["role"] for m in call["messages"]] == ["system", "user"]
        assert call["messages"][0]["content"] == enrich.FILES_SYSTEM
        assert call["messages"][1]["content"] == enrich.file_input(graph, mapped, call["path"])
    sem = semantic(mapped)
    assert set(sem) == {"files", "groups", "architecture"}
    assert sorted(sem["files"]) == sorted(RANKED)
    assert sem["files"][U] == {"summary": "About app/utils.py. It has code.", "role": "utility",
                               "input_sha": key(MODEL, UTILS_INPUT), "model": MODEL}


def test_second_run_makes_zero_calls(mapped, monkeypatch):
    run(mapped, monkeypatch)
    before = semantic(mapped)
    report, fake = run(mapped, monkeypatch)
    assert fake.calls == []
    assert report["called"] == [] and report["cached"] == 5
    assert semantic(mapped) == before


def test_only_changed_file_is_asked_again(mapped, monkeypatch):
    run(mapped, monkeypatch)
    with open(mapped / U, "a") as f:
        f.write("\n\ndef shout(name):\n    return name.upper()\n")
    remap(mapped)
    report, fake = run(mapped, monkeypatch)
    assert fake.paths == [U]
    assert report["cached"] == 4
    assert "def shout(name)  # L20" in fake.calls[0]["messages"][1]["content"]


def test_other_model_asks_again(mapped, monkeypatch):
    run(mapped, monkeypatch)
    report, fake = run(mapped, monkeypatch, model="qwen3-coder:30b")
    assert fake.paths == RANKED
    assert {e["model"] for e in semantic(mapped)["files"].values()} == {"qwen3-coder:30b"}


def test_limit_takes_most_connected_uncached_files(mapped, monkeypatch):
    _, fake = run(mapped, monkeypatch, limit=2)
    assert fake.paths == [S, M]
    _, fake = run(mapped, monkeypatch, limit=2)
    assert fake.paths == [R, U]
    _, fake = run(mapped, monkeypatch)
    assert fake.paths == [I]
    _, fake = run(mapped, monkeypatch, limit=2)
    assert fake.paths == []


def test_dry_run_counts_without_calling(mapped, monkeypatch):
    graph = json.loads((mapped / ".reaper" / "graph.json").read_text())
    chars = {p: len(enrich.FILES_SYSTEM) + len(enrich.file_input(graph, mapped, p)) for p in RANKED}
    report, fake = run(mapped, monkeypatch, dry_run=True)
    assert fake.calls == [] and not (mapped / ".reaper" / "semantic.json").exists()
    assert report["todo"] == RANKED and report["called"] == []
    assert report["tokens"] == sum(chars.values()) // 4
    assert report["max_tokens"] == max(chars.values()) // 4
    report, _ = run(mapped, monkeypatch, dry_run=True, limit=1)
    assert report["todo"] == [S] and report["tokens"] == chars[S] // 4
    run(mapped, monkeypatch)
    report, fake = run(mapped, monkeypatch, dry_run=True)
    assert report["todo"] == [] and report["tokens"] == 0 and report["cached"] == 5


def test_invalid_reply_skips_file_and_retries_next_run(mapped, monkeypatch):
    fake = FakeChat(fail={R: llm.InvalidResponse("bad JSON twice")})
    report, _ = run(mapped, monkeypatch, fake)
    assert fake.paths == RANKED                       # keeps going after the failure
    assert list(report["failed"]) == [R] and "bad JSON" in report["failed"][R]
    assert R not in semantic(mapped)["files"] and len(semantic(mapped)["files"]) == 4
    _, fake = run(mapped, monkeypatch)
    assert fake.paths == [R]


def test_unreachable_ollama_aborts_but_keeps_finished_files(mapped, monkeypatch):
    fake = FakeChat(fail={R: llm.LLMError("cannot reach Ollama")})
    with pytest.raises(llm.LLMError):
        run(mapped, monkeypatch, fake)
    assert fake.paths == [S, M, R]                    # stops at the first transport error
    assert sorted(semantic(mapped)["files"]) == [M, S]


def test_summary_cut_to_two_sentences(mapped, monkeypatch):
    run(mapped, monkeypatch, FakeChat(summary="Loads users. Saves them. Also logs.  "))
    assert semantic(mapped)["files"][U]["summary"] == "Loads users. Saves them."


def test_deleted_file_dropped(mapped, monkeypatch):
    run(mapped, monkeypatch)
    (mapped / U).unlink()
    remap(mapped)
    report, fake = run(mapped, monkeypatch)
    assert fake.calls == []                           # other files' inputs did not change
    assert report["pruned"] == [U]
    assert sorted(semantic(mapped)["files"]) == sorted([I, M, R, S])


def test_semantic_json_other_sections_kept(mapped, monkeypatch):
    (mapped / ".reaper" / "semantic.json").write_text(json.dumps(
        {"files": {}, "groups": {"g0": {"name": "core"}}, "architecture": {"overview": "x"}}))
    run(mapped, monkeypatch)
    sem = semantic(mapped)
    assert sem["groups"] == {"g0": {"name": "core"}} and sem["architecture"] == {"overview": "x"}


def test_schema_roles():
    assert enrich.FILES_SCHEMA["required"] == ["summary", "role"]
    assert enrich.FILES_SCHEMA["properties"]["role"]["enum"] == list(enrich.ROLES)
    assert "other" in enrich.ROLES


# ---------------------------------------------------------------- CLI

def test_cli_needs_graph(sample_repo, capsys):
    assert main(["enrich", str(sample_repo), "--pass", "files", "--dry-run"]) == 1
    assert "reaper map" in capsys.readouterr().err


def test_cli_dry_run(mapped, monkeypatch, capsys):
    fake = FakeChat()
    monkeypatch.setattr(llm, "chat", fake)
    assert main(["enrich", str(mapped), "--pass", "files", "--dry-run", "--limit", "3"]) == 0
    out = capsys.readouterr().out
    assert "3 calls" in out and MODEL in out and "tokens" in out
    assert fake.calls == []


def test_cli_files_pass(mapped, monkeypatch, capsys):
    fake = FakeChat()
    monkeypatch.setattr(llm, "chat", fake)
    assert main(["enrich", str(mapped), "--pass", "files", "--model", "tiny:1b"]) == 0
    out = capsys.readouterr().out
    assert "5 called, 0 cached, 0 failed" in out and "semantic.json" in out
    assert {c["model"] for c in fake.calls} == {"tiny:1b"}
    assert main(["enrich", str(mapped), "--pass", "files", "--model", "tiny:1b"]) == 0
    assert "0 called, 5 cached, 0 failed" in capsys.readouterr().out


def test_cli_failures_exit_nonzero(mapped, monkeypatch, capsys):
    monkeypatch.setattr(llm, "chat", FakeChat(fail={R: llm.InvalidResponse("bad")}))
    assert main(["enrich", str(mapped), "--pass", "files"]) == 1
    assert "4 called, 0 cached, 1 failed" in capsys.readouterr().out
    monkeypatch.setattr(llm, "chat", FakeChat(fail={S: llm.LLMError("cannot reach Ollama at x")}))
    (mapped / ".reaper" / "semantic.json").unlink()
    assert main(["enrich", str(mapped), "--pass", "files"]) == 1
    assert "cannot reach Ollama" in capsys.readouterr().err


def test_cli_architecture_needs_groups_pass(mapped, capsys):
    # Phase 6 placeholder ("not implemented") replaced: Phase 7 implements groups/architecture
    assert main(["enrich", str(mapped), "--pass", "architecture", "--dry-run"]) == 1
    assert "--pass groups" in capsys.readouterr().err
