"""Phase 4: incremental update.

Expected changes, counts and edges are written by hand from the fixture source
(tests/fixtures/sample_py/app) and the edits in `mutate` below.
"""

import json
from collections import Counter

from reaper import graph as graph_mod
from reaper.cli import main
from reaper.graph import build, graph_path, load, save, update

E, I = "EXTRACTED", "INFERRED"
INIT, M, R, S, U = "app/__init__.py", "app/models.py", "app/repository.py", "app/service.py", "app/utils.py"
ST = "app/store.py"
ALL = ["README.md", INIT, M, R, S, U]

# app/utils.py v2: `import os` and data_dir() removed, slugify() added
UTILS_V2 = '''"""Small helpers shared across the app."""


def normalize(name):
    """Strip and lowercase a name."""
    return name.strip().lower()


def validate(name):
    """Return True if the name is non-empty after normalizing."""
    return bool(normalize(name))


def slugify(name):
    """Return a URL-safe version of a name."""
    clean = normalize(name)
    return clean.replace(" ", "-")
'''

STORE = '''"""Dict-backed storage that replaces the old repository."""
from app.models import Entity
from app.utils import slugify


class MemoryStore:
    """Keeps entities in a dict keyed by slug."""

    def __init__(self):
        self.items = {}

    def save(self, entity):
        """Store an entity under its slugified description."""
        self.items[slugify(entity.describe())] = entity
        return entity
'''

# every non-contains edge after `mutate`
MUTATED_EDGES = {
    (S, "ext:os", "imports", E),
    (S, M, "imports", E),
    (S, INIT, "imports", E),   # .repository is gone: longest existing module prefix is the package `app`
    (S, U, "imports", E),
    (ST, M, "imports", E),
    (ST, U, "imports", E),
    (f"{M}::User", f"{M}::Entity", "inherits", E),
    (f"{M}::User.__init__", f"{M}::Entity.__init__", "calls", I),
    (f"{M}::User.label", f"{M}::Entity.describe", "calls", I),
    (f"{S}::UserService.create", f"{U}::validate", "calls", E),
    (f"{S}::UserService.create", f"{M}::User", "calls", E),
    (f"{S}::UserService.create", f"{U}::normalize", "calls", E),
    (f"{S}::UserService.create", f"{S}::UserService.log", "calls", E),
    (f"{S}::UserService.create", f"{M}::User.label", "calls", I),
    # unchanged service.py, new target: self.repo.save now has one candidate, in the added file
    (f"{S}::UserService.create", f"{ST}::MemoryStore.save", "calls", I),
    (f"{U}::validate", f"{U}::normalize", "calls", E),
    (f"{U}::slugify", f"{U}::normalize", "calls", E),
    (f"{ST}::MemoryStore.save", f"{U}::slugify", "calls", E),
    (f"{ST}::MemoryStore.save", f"{M}::Entity.describe", "calls", I),   # entity.describe: 1 candidate
    # gone: everything from repository.py, (S, R) imports, (U, ext:os) imports,
    # UserService.__init__ -> UserRepository (alias now resolves to nothing), ext:json
}


def mutate(repo):
    """Edit app/utils.py, delete app/repository.py, add app/store.py."""
    (repo / U).write_text(UTILS_V2)
    (repo / R).unlink()
    (repo / ST).write_text(STORE)


def as_tuples(edges):
    return [(e["src"], e["dst"], e["kind"], e["confidence"]) for e in edges if e["kind"] != "contains"]


def strip_time(g):
    """The graph without meta.generated_at (the only field allowed to differ between runs)."""
    return {**g, "meta": {k: v for k, v in g["meta"].items() if k != "generated_at"}}


def spy_extract(monkeypatch):
    """Record the paths graph.extract_file is called with."""
    seen = []
    real = graph_mod.extract_file

    def spy(root, rel, lang):
        seen.append(rel)
        return real(root, rel, lang)

    monkeypatch.setattr(graph_mod, "extract_file", spy)
    return seen


def test_no_graph_json_means_full_build(sample_repo):
    g, changes = update(sample_repo)
    assert changes == {"added": ALL, "changed": [], "deleted": [], "unchanged": []}
    assert strip_time(g) == strip_time(build(sample_repo))


def test_no_change_gives_identical_graph(sample_repo, monkeypatch):
    before = build(sample_repo)
    save(sample_repo, before)
    seen = spy_extract(monkeypatch)
    after, changes = update(sample_repo)
    assert changes == {"added": [], "changed": [], "deleted": [], "unchanged": ALL}
    assert seen == []  # nothing re-extracted
    assert strip_time(after) == strip_time(before)
    save(sample_repo, after)  # and it survives the JSON round trip
    assert strip_time(load(sample_repo)) == strip_time(before)


def test_edit_delete_add_changes(sample_repo, monkeypatch):
    save(sample_repo, build(sample_repo))
    mutate(sample_repo)
    seen = spy_extract(monkeypatch)
    _, changes = update(sample_repo)
    assert changes == {"added": [ST], "changed": [U], "deleted": [R],
                       "unchanged": ["README.md", INIT, M, S]}
    assert seen == [ST, U]  # only added + changed files are re-extracted


def test_edit_delete_add_graph(sample_repo):
    save(sample_repo, build(sample_repo))
    mutate(sample_repo)
    g, _ = update(sample_repo)
    assert list(g["files"]) == ["README.md", INIT, M, S, ST, U]
    assert R not in {n["file"] for n in g["nodes"]} | {r["file"] for r in g["refs"]}
    assert Counter(n["kind"] for n in g["nodes"]) == {
        "file": 5, "class": 4, "method": 9, "function": 3, "external": 1}
    assert [n["id"] for n in g["nodes"] if n["kind"] == "external"] == ["ext:os"]
    assert Counter(r["kind"] for r in g["refs"]) == {"import": 7, "call": 22, "inherit": 1}
    assert Counter(e["kind"] for e in g["edges"]) == {
        "contains": 16, "imports": 6, "inherits": 1, "calls": 12}
    got = as_tuples(g["edges"])
    assert len(got) == len(set(got))
    assert set(got) == MUTATED_EDGES
    ids = {n["id"] for n in g["nodes"]}
    assert all(e["src"] in ids and e["dst"] in ids for e in g["edges"])  # nothing dangling


def test_update_matches_full_build(sample_repo):
    save(sample_repo, build(sample_repo))
    mutate(sample_repo)
    g, _ = update(sample_repo)
    assert strip_time(g) == strip_time(build(sample_repo))


def test_other_format_version_means_full_build(sample_repo, monkeypatch):
    g = build(sample_repo)
    g["meta"]["version"] = 0
    save(sample_repo, g)
    seen = spy_extract(monkeypatch)
    _, changes = update(sample_repo)
    assert changes["added"] == ALL and changes["unchanged"] == []
    assert seen == ALL


def test_cli_update(sample_repo, capsys):
    assert main(["map", str(sample_repo)]) == 0
    mutate(sample_repo)
    capsys.readouterr()
    assert main(["update", str(sample_repo)]) == 0
    out = capsys.readouterr().out
    for part in ("1 added", "1 changed", "1 deleted", "4 unchanged",
                 "22 nodes", "30 refs", "35 edges", "graph.json"):
        assert part in out
    g = json.loads(graph_path(sample_repo).read_text())
    assert ST in g["files"] and R not in g["files"]
    assert main(["update", str(sample_repo)]) == 0
    out = capsys.readouterr().out
    assert "0 added, 0 changed, 0 deleted, 6 unchanged" in out
