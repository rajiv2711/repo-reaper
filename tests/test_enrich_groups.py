"""Phase 7: groups (Louvain) + `enrich --pass groups|architecture`, mocked llm.chat.

Expected values are written by hand from the sources below and the fixture edge list in
test_resolve.py (FIXTURE_EDGES).

Fixture file graph (cross-file non-contains edges, undirected, weight = edge count):
R-M 1, R-U 2 (import + data_dir), S-M 3, S-R 3, S-U 3; m = 12, degrees S 9 M 4 R 6 U 5.
Any split has negative modularity (e.g. {S,M}{R,U}: 3/12 - (13/24)^2 + 2/12 - (11/24)^2 < 0),
so Louvain keeps one community; app/__init__.py has no cross-file edge and joins the group
holding most files of its directory "app".

MINI repo: a/ (x, y, z) are densely linked, b/ (p, q) too, one import a/x.py -> b/p.py.
File weights x-y 2, x-z 2, y-z 2, p-q 2, x-p 1 (m = 9): Q({x,y,z},{p,q}) = 6/9 - (13/18)^2
+ 2/9 - (5/18)^2 = 0.29 > 0 = Q(all). b/__init__.py is isolated -> joins the b group;
c/lonely.py (only an external import) and c/other.py are isolated and no group has files in
"c", so they form one group together.
"""

import hashlib
import json
import re

import pytest

from reaper import enrich, llm
from reaper.cli import main
from reaper.graph import build, save, update

I, M, R, S, U = ("app/__init__.py", "app/models.py", "app/repository.py", "app/service.py",
                 "app/utils.py")
MODEL = "qwen3-coder:30b"

MINI = {
    "a/x.py": "from a.y import f\nfrom a.z import g\nfrom b.p import m\n\n\ndef h():\n"
              "    return f() + g()\n",
    "a/y.py": "from a.z import g\n\n\ndef f():\n    return g()\n",
    "a/z.py": "def g():\n    return 1\n",
    "b/__init__.py": "",
    "b/p.py": "from b.q import k\n\n\ndef m():\n    return k()\n",
    "b/q.py": "def k():\n    return 2\n",
    "c/lonely.py": "import os\n\nHOME = os.environ.get('HOME')\n",
    "c/other.py": "Y = 2\n",
}
MINI_GROUPS = [["a/x.py", "a/y.py", "a/z.py"], ["b/__init__.py", "b/p.py", "b/q.py"],
               ["c/lonely.py", "c/other.py"]]
# ranked_files: a/x.py 5 (file 3 + h 2), a/y.py 4, a/z.py 4, b/p.py 3, b/q.py 2, c/lonely.py 1
# (import os), b/__init__.py 0, c/other.py 0
MINI_NAMES = {"a/x.py": ("Alpha", "Alpha summary."), "b/p.py": ("Beta", "Beta summary."),
              "c/lonely.py": ("Gamma", "Gamma summary.")}

FIXTURE_FILES = {S: ("service", "Creates users."), M: ("model", "Defines User and Entity."),
                 R: ("data-access", "Stores users as JSON."), U: ("utility", "Normalizes names.")}
FIXTURE_GROUP_INPUT = """\
Group of 5 files, most-connected first:
- app/service.py [service]: Creates users.
- app/models.py [model]: Defines User and Entity.
- app/repository.py [data-access]: Stores users as JSON.
- app/utils.py [utility]: Normalizes names.
- app/__init__.py: (no summary yet)
"""

MINI_ARCH_INPUT = """\
Groups (3):

g1: Alpha (3 files)
Alpha summary.
Files: a/x.py, a/y.py, a/z.py

g2: Beta (3 files)
Beta summary.
Files: b/p.py, b/q.py, b/__init__.py

g3: Gamma (2 files)
Gamma summary.
Files: c/lonely.py, c/other.py

Cross-group edges (from -> to: count by kind):
- g1 -> g2: 1 (imports 1)

Most-connected nodes (in/out edges over imports, inherits, calls):
- a/x.py: in 0, out 3
- a/x.py::h: in 0, out 2
- a/y.py: in 1, out 1
- a/y.py::f: in 1, out 1
- a/z.py: in 2, out 0
- a/z.py::g: in 2, out 0
- b/p.py: in 1, out 1
- b/p.py::m: in 0, out 1
- b/q.py: in 1, out 0
- b/q.py::k: in 1, out 0
- c/lonely.py: in 0, out 1
"""

ARCH_REPLY = {
    "overview": "A two-package demo. Package a computes values with helpers from package b.",
    "patterns": [
        {"name": "Layering", "explanation": "a depends on b, never the reverse.",
         "evidence": ["a/x.py", "b/p.py::m", "a/ghost.py::Phantom", "`a/z.py`", "a/x.py"]},
        "not an object",
        {"explanation": "has no name"},
        {"name": "Leaf helpers", "explanation": 7},
    ],
    "decisions": [
        {"decision": "Keep helpers in b", "rationale": "Reuse.", "evidence": ["b/q.py::k",
                                                                              "not-a-node"]},
    ],
}


def first_member(text):
    return re.search(r"^- (\S+?)(?: \[|:)", text, re.M).group(1)


class FakeChat:
    """Stands in for llm.chat. Groups: named by the first listed file (MINI_NAMES, else
    "Group <path>"). Architecture: returns `arch`. Can fail for chosen first files."""

    def __init__(self, arch=None, fail=None, summary="Does {path} things. Second. Third. Fourth."):
        self.calls, self.arch, self.fail, self.summary = [], arch or ARCH_REPLY, fail or {}, summary

    def __call__(self, model, messages, schema):
        text = messages[1]["content"]
        if messages[0]["content"] == enrich.ARCH_SYSTEM:
            self.calls.append({"model": model, "messages": messages, "schema": schema,
                               "key": "architecture"})
            return json.loads(json.dumps(self.arch))
        path = first_member(text)
        self.calls.append({"model": model, "messages": messages, "schema": schema, "key": path})
        if path in self.fail:
            raise self.fail[path]
        name, summary = MINI_NAMES.get(path, (f"  Group\n {path} ", self.summary.format(path=path)))
        return {"name": name, "summary": summary}

    @property
    def keys(self):
        return [c["key"] for c in self.calls]


def write_tree(root, files):
    for rel, src in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src)


@pytest.fixture
def mini(tmp_path):
    repo = tmp_path / "mini"
    write_tree(repo, MINI)
    save(repo, build(repo))
    return repo


@pytest.fixture
def mapped(sample_repo):
    save(sample_repo, build(sample_repo))
    sem = {"files": {p: {"summary": s, "role": r, "input_sha": "x", "model": "m"}
                     for p, (r, s) in FIXTURE_FILES.items()}, "groups": {}, "architecture": {}}
    (sample_repo / ".reaper" / "semantic.json").write_text(json.dumps(sem))
    return sample_repo


def graph_of(repo):
    return json.loads((repo / ".reaper" / "graph.json").read_text())


def semantic(repo):
    return json.loads((repo / ".reaper" / "semantic.json").read_text())


def key(model, version, text):
    return hashlib.sha256(f"{model}\n{version}\n{text}".encode()).hexdigest()


def groups(repo, monkeypatch, fake=None, **kw):
    fake = fake or FakeChat()
    monkeypatch.setattr(llm, "chat", fake)
    return enrich.run_groups(repo, graph_of(repo), **kw), fake


def arch(repo, monkeypatch, fake=None, **kw):
    fake = fake or FakeChat()
    monkeypatch.setattr(llm, "chat", fake)
    return enrich.run_architecture(repo, graph_of(repo), **kw), fake


def remap(repo):
    graph, _ = update(repo)
    save(repo, graph)


# ---------------------------------------------------------------- communities

def test_fixture_is_one_group(mapped):
    assert enrich.communities(graph_of(mapped)) == [[I, M, R, S, U]]


def test_mini_two_clusters_plus_isolated(mini):
    assert enrich.communities(graph_of(mini)) == MINI_GROUPS


def test_isolated_file_alone_in_its_directory(mini):
    write_tree(mini, {"setup.py": "NAME = 'mini'\n"})
    remap(mini)
    assert enrich.communities(graph_of(mini)) == [*MINI_GROUPS, ["setup.py"]]


def test_no_code_files_no_groups(tmp_path):
    (tmp_path / "README.md").write_text("hi\n")
    assert enrich.communities(build(tmp_path)) == []


# ---------------------------------------------------------------- group input

def test_group_input_fixture(mapped):
    files = semantic(mapped)["files"]
    assert enrich.group_input([S, M, R, U, I], files) == FIXTURE_GROUP_INPUT


def test_group_input_capped_at_12k_chars():
    members = [f"m{i:02}.py" for i in range(20)]
    files = {p: {"summary": "x" * 900, "role": "other"} for p in members}
    text = enrich.group_input(members, files)
    assert len(text) <= 12000
    # header 41 chars + 12 lines of 919 = 11069; a 13th line would pass the cap minus the
    # 40 chars kept for the closing line
    assert [ln.split()[1] for ln in text.splitlines() if ln.startswith("- ")] == members[:12]
    assert text.endswith("\n(8 more files not shown)\n")
    small = enrich.group_input(members[:3], files)
    assert "not shown" not in small and small.count("\n- ") == 3


def test_group_input_long_summary_cut():
    text = enrich.group_input(["big.py"], {"big.py": {"summary": "y" * 20000, "role": "other"}})
    assert len(text) < 1100 and "big.py" in text and "not shown" not in text


# ---------------------------------------------------------------- groups pass

def test_groups_first_run(mapped, monkeypatch):
    files_before = semantic(mapped)["files"]
    report, fake = groups(mapped, monkeypatch)
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["model"] == MODEL and call["schema"] == enrich.GROUPS_SCHEMA
    assert call["messages"] == [{"role": "system", "content": enrich.GROUPS_SYSTEM},
                                {"role": "user", "content": FIXTURE_GROUP_INPUT}]
    assert report["called"] == ["g1"] and report["cached"] == 0 and report["failed"] == {}
    assert report["missing_summaries"] == [I]
    sem = semantic(mapped)
    assert sem["files"] == files_before
    assert sem["groups"] == {"g1": {
        "name": f"Group {S}",                                   # whitespace collapsed
        "summary": f"Does {S} things. Second. Third.",           # at most 3 sentences
        "members": [I, M, R, S, U],
        "input_sha": key(MODEL, enrich.GROUPS_PROMPT_VERSION, FIXTURE_GROUP_INPUT),
        "model": MODEL}}


def test_groups_second_run_zero_calls(mini, monkeypatch):
    groups(mini, monkeypatch)
    before = semantic(mini)
    report, fake = groups(mini, monkeypatch)
    assert fake.calls == [] and report["cached"] == 3 and report["called"] == []
    assert semantic(mini) == before


def test_groups_order_ids_and_members(mini, monkeypatch):
    _, fake = groups(mini, monkeypatch)
    assert fake.keys == ["a/x.py", "b/p.py", "c/lonely.py"]
    assert fake.calls[2]["messages"][1]["content"] == (
        "Group of 2 files, most-connected first:\n"
        "- c/lonely.py: (no summary yet)\n- c/other.py: (no summary yet)\n")
    sem = semantic(mini)["groups"]
    assert {g: (e["name"], e["members"]) for g, e in sem.items()} == {
        "g1": ("Alpha", MINI_GROUPS[0]), "g2": ("Beta", MINI_GROUPS[1]),
        "g3": ("Gamma", MINI_GROUPS[2])}


def test_changed_file_summary_asks_its_group_again(mini, monkeypatch):
    groups(mini, monkeypatch)
    sem = semantic(mini)
    sem["files"]["b/q.py"] = {"summary": "Returns two.", "role": "utility", "input_sha": "x",
                              "model": "m"}
    (mini / ".reaper" / "semantic.json").write_text(json.dumps(sem))
    report, fake = groups(mini, monkeypatch)
    assert fake.keys == ["b/p.py"] and report["cached"] == 2
    assert "- b/q.py [utility]: Returns two.\n" in fake.calls[0]["messages"][1]["content"]


def test_cache_survives_group_id_shift(mini, monkeypatch):
    groups(mini, monkeypatch)
    write_tree(mini, {"d/d1.py": "from d.d2 import u\nfrom d.d3 import v\nfrom d.d4 import w\n\n\n"
                                 "def t():\n    return u() + v() + w()\n",
                      "d/d2.py": "from d.d3 import v\n\n\ndef u():\n    return v()\n",
                      "d/d3.py": "from d.d4 import w\n\n\ndef v():\n    return w()\n",
                      "d/d4.py": "def w():\n    return 0\n"})
    remap(mini)
    report, fake = groups(mini, monkeypatch)
    assert fake.keys == ["d/d1.py"] and report["cached"] == 3
    sem = semantic(mini)["groups"]
    assert sem["g1"]["members"] == ["d/d1.py", "d/d2.py", "d/d3.py", "d/d4.py"]
    assert [sem[g]["name"] for g in ("g2", "g3", "g4")] == ["Alpha", "Beta", "Gamma"]


def test_groups_gone_are_dropped(mini, monkeypatch):
    groups(mini, monkeypatch)
    for rel in ("c/lonely.py", "c/other.py"):
        (mini / rel).unlink()
    remap(mini)
    _, fake = groups(mini, monkeypatch)
    assert fake.calls == []
    assert sorted(semantic(mini)["groups"]) == ["g1", "g2"]


def test_groups_limit(mini, monkeypatch):
    _, fake = groups(mini, monkeypatch, limit=1)
    assert fake.keys == ["a/x.py"] and sorted(semantic(mini)["groups"]) == ["g1"]
    _, fake = groups(mini, monkeypatch, limit=5)
    assert fake.keys == ["b/p.py", "c/lonely.py"]


def test_groups_dry_run(mini, monkeypatch):
    graph = graph_of(mini)
    inputs = [enrich.group_input(sorted(m, key=enrich.ranked_files(graph).index), {})
              for m in MINI_GROUPS]
    chars = [len(enrich.GROUPS_SYSTEM) + len(t) for t in inputs]
    report, fake = groups(mini, monkeypatch, dry_run=True)
    assert fake.calls == [] and not (mini / ".reaper" / "semantic.json").exists()
    assert report["todo"] == ["g1", "g2", "g3"]
    assert report["tokens"] == sum(chars) // 4 and report["max_tokens"] == max(chars) // 4


def test_groups_invalid_reply_skips_group(mini, monkeypatch):
    fake = FakeChat(fail={"b/p.py": llm.InvalidResponse("bad JSON twice")})
    report, _ = groups(mini, monkeypatch, fake)
    assert fake.keys == ["a/x.py", "b/p.py", "c/lonely.py"]
    assert list(report["failed"]) == ["g2"]
    assert sorted(semantic(mini)["groups"]) == ["g1", "g3"]
    _, fake = groups(mini, monkeypatch)
    assert fake.keys == ["b/p.py"]


def test_groups_unreachable_ollama_keeps_finished(mini, monkeypatch):
    fake = FakeChat(fail={"b/p.py": llm.LLMError("cannot reach Ollama")})
    with pytest.raises(llm.LLMError):
        groups(mini, monkeypatch, fake)
    assert sorted(semantic(mini)["groups"]) == ["g1"]


# ---------------------------------------------------------------- architecture pass

def test_arch_input(mini, monkeypatch):
    groups(mini, monkeypatch)
    assert enrich.arch_input(graph_of(mini), semantic(mini)) == MINI_ARCH_INPUT


def test_arch_needs_groups(mini, monkeypatch):
    with pytest.raises(enrich.NotReady, match="--pass groups"):
        arch(mini, monkeypatch)
    groups(mini, monkeypatch, limit=2)
    with pytest.raises(enrich.NotReady, match="1 of 3 groups"):
        arch(mini, monkeypatch, dry_run=True)


def test_arch_needs_fresh_groups(mini, monkeypatch):
    groups(mini, monkeypatch)
    sem = semantic(mini)
    sem["files"]["a/z.py"] = {"summary": "Returns one.", "role": "utility", "input_sha": "x",
                              "model": "m"}
    (mini / ".reaper" / "semantic.json").write_text(json.dumps(sem))
    with pytest.raises(enrich.NotReady, match="g1"):
        arch(mini, monkeypatch)
    groups(mini, monkeypatch)
    write_tree(mini, {"c/third.py": "Z = 3\n"})        # grouping changes: c group grows
    remap(mini)
    with pytest.raises(enrich.NotReady):
        arch(mini, monkeypatch)


def test_arch_first_run_drops_unknown_evidence(mini, monkeypatch):
    groups(mini, monkeypatch)
    report, fake = arch(mini, monkeypatch)
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["model"] == MODEL and call["schema"] == enrich.ARCH_SCHEMA
    assert call["messages"] == [{"role": "system", "content": enrich.ARCH_SYSTEM},
                                {"role": "user", "content": MINI_ARCH_INPUT}]
    assert report["called"] is True
    a = semantic(mini)["architecture"]
    assert a == {
        "overview": ARCH_REPLY["overview"],
        "patterns": [{"name": "Layering", "explanation": "a depends on b, never the reverse.",
                      "evidence": ["a/x.py", "b/p.py::m", "a/z.py"]},
                     {"name": "Leaf helpers", "explanation": "", "evidence": []}],
        "decisions": [{"decision": "Keep helpers in b", "rationale": "Reuse.",
                       "evidence": ["b/q.py::k"]}],
        "dropped_evidence": ["a/ghost.py::Phantom", "not-a-node"],
        "input_sha": key(MODEL, enrich.ARCH_PROMPT_VERSION, MINI_ARCH_INPUT),
        "model": MODEL}
    assert len(semantic(mini)["groups"]) == 3            # groups kept
    md = (mini / ".reaper" / "ARCHITECTURE.md").read_text()
    assert report["path"] == mini / ".reaper" / "ARCHITECTURE.md"
    assert "LLM-generated" in md.splitlines()[2] and MODEL in md
    for text in (ARCH_REPLY["overview"], "## Patterns", "### Layering", "`b/p.py::m`",
                 "## Design decisions", "### Keep helpers in b", "Reuse.", "`b/q.py::k`",
                 "Alpha", "Gamma summary.", "g1 -> g2", "2 evidence ids"):
        assert text in md
    assert "ghost" not in md and "not-a-node" not in md


def test_arch_second_run_zero_calls_rewrites_md(mini, monkeypatch):
    groups(mini, monkeypatch)
    arch(mini, monkeypatch)
    before = semantic(mini)
    md_path = mini / ".reaper" / "ARCHITECTURE.md"
    md = md_path.read_text()
    md_path.unlink()
    report, fake = arch(mini, monkeypatch)
    assert fake.calls == [] and report["called"] is False
    assert semantic(mini) == before and md_path.read_text() == md


def test_arch_new_group_answer_asks_again(mini, monkeypatch):
    groups(mini, monkeypatch)
    arch(mini, monkeypatch)
    sem = semantic(mini)
    sem["groups"]["g2"]["name"] = "Helpers"              # as if groups were asked again
    (mini / ".reaper" / "semantic.json").write_text(json.dumps(sem))
    _, fake = arch(mini, monkeypatch)
    assert fake.keys == ["architecture"]
    assert "g2: Helpers (3 files)" in fake.calls[0]["messages"][1]["content"]


def test_arch_dry_run(mini, monkeypatch):
    groups(mini, monkeypatch)
    report, fake = arch(mini, monkeypatch, dry_run=True)
    assert fake.calls == [] and report["called"] is False and report["todo"] is True
    assert report["tokens"] == (len(enrich.ARCH_SYSTEM) + len(MINI_ARCH_INPUT)) // 4
    assert semantic(mini)["architecture"] == {}
    assert not (mini / ".reaper" / "ARCHITECTURE.md").exists()


def test_arch_input_caps():
    assert enrich.ARCH_TOP_NODES >= 10 and enrich.GROUP_MAX_CHARS == 12000


# ---------------------------------------------------------------- CLI

def test_cli_groups_and_architecture(mini, monkeypatch, capsys):
    fake = FakeChat()
    monkeypatch.setattr(llm, "chat", fake)
    assert main(["enrich", str(mini), "--pass", "architecture"]) == 1
    assert "--pass groups" in capsys.readouterr().err
    assert main(["enrich", str(mini), "--pass", "groups", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "3 calls" in out and MODEL in out and fake.calls == []
    assert main(["enrich", str(mini), "--pass", "groups"]) == 0
    captured = capsys.readouterr()
    assert "3 called, 0 cached, 0 failed" in captured.out
    assert "8 files have no summary" in captured.err and "--pass files" in captured.err
    assert main(["enrich", str(mini), "--pass", "groups"]) == 0
    assert "0 called, 3 cached, 0 failed" in capsys.readouterr().out
    assert main(["enrich", str(mini), "--pass", "architecture", "--dry-run"]) == 0
    assert "1 call" in capsys.readouterr().out
    assert main(["enrich", str(mini), "--pass", "architecture", "--model", "tiny:1b"]) == 0
    out = capsys.readouterr().out
    assert "ARCHITECTURE.md" in out and "2 evidence ids dropped" in out
    assert fake.calls[-1]["model"] == "tiny:1b"
    assert main(["enrich", str(mini), "--pass", "architecture", "--model", "tiny:1b"]) == 0
    assert "cached" in capsys.readouterr().out


def test_cli_groups_failure_exit_nonzero(mini, monkeypatch, capsys):
    monkeypatch.setattr(llm, "chat", FakeChat(fail={"b/p.py": llm.InvalidResponse("bad")}))
    assert main(["enrich", str(mini), "--pass", "groups"]) == 1
    assert "2 called, 0 cached, 1 failed" in capsys.readouterr().out
