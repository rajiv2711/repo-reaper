"""Phase 8 (08-02): enrich.view_semantic, the `sem` part of graph.html's embedded JSON.

Expected values are written by hand from the fixture (tests/fixtures/sample_py/app) and the
"Embedded-JSON contract" -> sem in docs/phases/08-html-view/08-PLAN.md. No Ollama is called:
semantic.json is written directly with enrich.save_semantic.
"""

from reaper import enrich, outputs
from reaper.enrich import cache_key, file_input
from reaper.graph import build

I, M, R, S, U = ("app/__init__.py", "app/models.py", "app/repository.py", "app/service.py",
                 "app/utils.py")
C = "app/service.py::UserService.create"


def snapshot(repo):
    """Every path under repo with its mtime: view_semantic must never write a file."""
    return sorted((str(p), p.stat().st_mtime_ns) for p in repo.rglob("*"))


def files_section(g, repo):
    return {
        M: {"summary": "Makes users <b>x</b></script>", "role": "model", "model": "m",
            "input_sha": "x"},
        S: {"summary": "Creates users.", "role": "service", "model": "m",
            "input_sha": cache_key("m", file_input(g, repo, S))},
        "app/gone.py": {"summary": "old", "role": "other", "model": "m", "input_sha": "y"},
    }


# ---------------------------------------------------------------- files (08-02-1)

def test_file_input_kids_same_output(sample_repo):
    g = build(sample_repo)
    kids = outputs._children(g)
    for p in (M, S):
        assert file_input(g, sample_repo, p) == file_input(g, sample_repo, p, kids)


def test_view_semantic_absent_is_none(sample_repo):
    g = build(sample_repo)
    before = snapshot(sample_repo)
    assert enrich.view_semantic(sample_repo, g) is None
    assert snapshot(sample_repo) == before


def test_view_semantic_files_staleness(sample_repo):
    g = build(sample_repo)
    enrich.save_semantic(sample_repo, {"files": files_section(g, sample_repo)})
    before = snapshot(sample_repo)
    result = enrich.view_semantic(sample_repo, g)
    assert result["files"] == {
        M: {"summary": "Makes users <b>x</b></script>", "role": "model", "model": "m",
            "stale": True},
        S: {"summary": "Creates users.", "role": "service", "model": "m", "stale": False},
    }
    assert snapshot(sample_repo) == before


def test_view_semantic_missing_source_is_stale(sample_repo):
    g = build(sample_repo)
    sha = cache_key("m", file_input(g, sample_repo, U))
    enrich.save_semantic(sample_repo, {"files": {
        U: {"summary": "Helps.", "role": "utility", "model": "m", "input_sha": sha}}})
    assert enrich.view_semantic(sample_repo, g)["files"][U]["stale"] is False
    (sample_repo / "app" / "utils.py").unlink()
    assert enrich.view_semantic(sample_repo, g)["files"] == {
        U: {"summary": "Helps.", "role": "utility", "model": "m", "stale": True}}


def test_view_semantic_builds_children_once(sample_repo, monkeypatch):
    g = build(sample_repo)
    enrich.save_semantic(sample_repo, {"files": files_section(g, sample_repo)})
    calls = []
    real = outputs._children

    def counting(graph):
        calls.append(1)
        return real(graph)

    monkeypatch.setattr(outputs, "_children", counting)
    result = enrich.view_semantic(sample_repo, g)
    assert sorted(result["files"]) == [M, S]
    assert len(calls) == 1


# ---------------------------------------------------------------- groups (08-02-2)

def save_groups(g, repo):
    """Files section of 08-02-1, then a fresh g1 and a vanished g2; returns g1's members."""
    enrich.save_semantic(repo, {"files": files_section(g, repo)})
    sem0 = enrich.load_semantic(repo)
    gid, members, _, text = enrich._group_plan(g, sem0)[0]
    assert (gid, members) == ("g1", [I, M, R, S, U])
    sem0["groups"] = {
        "g1": {"name": "Users", "summary": "User management.", "members": members,
               "model": "m", "input_sha": cache_key("m", text, enrich.GROUPS_PROMPT_VERSION)},
        "g2": {"name": "Old", "summary": "gone", "members": ["app/gone.py"], "model": "m",
               "input_sha": "y"},
    }
    enrich.save_semantic(repo, sem0)
    return members


def test_view_semantic_groups_staleness(sample_repo):
    g = build(sample_repo)
    save_groups(g, sample_repo)
    before = snapshot(sample_repo)
    groups = enrich.view_semantic(sample_repo, g)["groups"]
    assert groups["g1"] == {"name": "Users", "summary": "User management.",
                            "members": [I, M, R, S, U], "model": "m", "stale": False}
    assert groups["g2"] == {"name": "Old", "summary": "gone", "members": [], "model": "m",
                            "stale": True}
    assert snapshot(sample_repo) == before
    # the group input holds the file summaries, so a changed summary makes g1 stale
    sem = enrich.load_semantic(sample_repo)
    sem["files"][M]["summary"] = "Defines users."
    enrich.save_semantic(sample_repo, sem)
    assert enrich.view_semantic(sample_repo, g)["groups"]["g1"]["stale"] is True


# ---------------------------------------------------------------- architecture (08-02-3)

def test_view_semantic_architecture(sample_repo):
    g = build(sample_repo)
    save_groups(g, sample_repo)
    sem = enrich.load_semantic(sample_repo)
    text = enrich.arch_input(g, sem)
    sem["architecture"] = {
        "overview": "Layered app.",
        "patterns": [{"name": "Layers", "explanation": "service -> repository",
                      "evidence": [C, "app/ghost.py::nope"]}],
        "decisions": [{"decision": "In-memory store", "rationale": "simple",
                       "evidence": ["app/repository.py::UserRepository"]}],
        "dropped_evidence": ["old::id"], "model": "m",
        "input_sha": cache_key("m", text, enrich.ARCH_PROMPT_VERSION)}
    enrich.save_semantic(sample_repo, sem)
    before = snapshot(sample_repo)
    assert enrich.view_semantic(sample_repo, g)["architecture"] == {
        "overview": "Layered app.",
        "patterns": [{"name": "Layers", "explanation": "service -> repository",
                      "evidence": [C]}],
        "decisions": [{"decision": "In-memory store", "rationale": "simple",
                       "evidence": ["app/repository.py::UserRepository"]}],
        "model": "m", "stale": False, "dropped": ["app/ghost.py::nope", "old::id"]}
    assert snapshot(sample_repo) == before
    sem["architecture"]["input_sha"] = "z"
    enrich.save_semantic(sample_repo, sem)
    assert enrich.view_semantic(sample_repo, g)["architecture"]["stale"] is True


def test_view_semantic_partial_entries(sample_repo):
    g = build(sample_repo)
    enrich.save_semantic(sample_repo, {"groups": {"g0": {"name": "core"}},
                                       "architecture": {"overview": "x"}})
    assert enrich.view_semantic(sample_repo, g) == {
        "files": {},
        "groups": {"g0": {"name": "core", "summary": None, "members": [], "model": None,
                          "stale": True}},
        "architecture": {"overview": "x", "patterns": [], "decisions": [], "model": None,
                         "stale": True, "dropped": []}}


def test_view_semantic_empty_architecture_is_null(sample_repo):
    g = build(sample_repo)
    enrich.save_semantic(sample_repo, {"files": {}})
    assert enrich.view_semantic(sample_repo, g) == {"files": {}, "groups": {},
                                                    "architecture": None}


def test_view_semantic_malformed_entries(sample_repo):
    """Hand-edited semantic.json: wrong types read as missing keys, never crash."""
    g = build(sample_repo)
    enrich.save_semantic(sample_repo, {
        "files": {M: "oops"}, "groups": {"g1": ["x"]},
        "architecture": {"overview": 3, "patterns": "no", "dropped_evidence": [1, "a"]}})
    assert enrich.view_semantic(sample_repo, g) == {
        "files": {M: {"summary": None, "role": None, "model": None, "stale": True}},
        "groups": {"g1": {"name": None, "summary": None, "members": [], "model": None,
                          "stale": True}},
        "architecture": {"overview": "", "patterns": [], "decisions": [], "model": None,
                         "stale": True, "dropped": ["a"]}}
