"""Phase 2: Python extraction. Expected values were written by hand from the fixture source."""

from collections import Counter

import pytest

from reaper.extract_py import extract, module_name

PY_FILES = [
    "app/__init__.py",
    "app/models.py",
    "app/repository.py",
    "app/service.py",
    "app/utils.py",
]


def run(repo, rel):
    return extract(rel, (repo / rel).read_bytes(), module_name(rel))


def by_id(nodes):
    return {n["id"]: n for n in nodes}


def refs_of(refs, kind):
    return [r for r in refs if r["kind"] == kind]


# --- module names -------------------------------------------------------------

@pytest.mark.parametrize("path, expected", [
    ("app/service.py", "app.service"),
    ("app/__init__.py", "app"),
    ("src/app/service.py", "app.service"),
    ("src/app/__init__.py", "app"),
    ("setup.py", "setup"),
    ("pkg/sub/mod.py", "pkg.sub.mod"),
])
def test_module_name(path, expected):
    assert module_name(path) == expected


# --- nodes --------------------------------------------------------------------

EXPECTED_KINDS = {
    "app/__init__.py": {"file": 1},
    "app/models.py": {"file": 1, "class": 2, "method": 4},
    "app/repository.py": {"file": 1, "class": 1, "method": 3, "function": 1},
    "app/service.py": {"file": 1, "class": 1, "method": 3},
    "app/utils.py": {"file": 1, "function": 3},
}


@pytest.mark.parametrize("rel", PY_FILES)
def test_node_counts_by_kind(sample_repo, rel):
    nodes, _ = run(sample_repo, rel)
    assert Counter(n["kind"] for n in nodes) == EXPECTED_KINDS[rel]


def test_node_ids_models(sample_repo):
    nodes, _ = run(sample_repo, "app/models.py")
    assert [n["id"] for n in nodes] == [
        "app/models.py",
        "app/models.py::Entity",
        "app/models.py::Entity.__init__",
        "app/models.py::Entity.describe",
        "app/models.py::User",
        "app/models.py::User.__init__",
        "app/models.py::User.label",
    ]


def test_file_node(sample_repo):
    nodes, _ = run(sample_repo, "app/__init__.py")
    assert nodes == [{
        "id": "app/__init__.py", "kind": "file", "name": "app", "file": "app/__init__.py",
        "line": 1, "signature": None,
        "doc": "Sample user-management app used as a repo-reaper test fixture.",
    }]


def test_symbol_nodes(sample_repo):
    nodes = by_id(run(sample_repo, "app/models.py")[0])
    assert nodes["app/models.py::User"] == {
        "id": "app/models.py::User", "kind": "class", "name": "User", "file": "app/models.py",
        "line": 15, "signature": "User(Entity)", "doc": "A user with a name.",
    }
    assert nodes["app/models.py::Entity"]["signature"] == "Entity"
    init = nodes["app/models.py::Entity.__init__"]
    assert (init["kind"], init["line"], init["signature"], init["doc"]) == (
        "method", 7, "__init__(self, entity_id)", None)

    nodes = by_id(run(sample_repo, "app/service.py")[0])
    create = nodes["app/service.py::UserService.create"]
    assert (create["name"], create["line"], create["signature"], create["doc"]) == (
        "create", 15, "create(self, entity_id, name)", "Validate, build and save a new user.")
    assert nodes["app/service.py::UserService.__init__"]["signature"] == "__init__(self, repo=None)"

    nodes = by_id(run(sample_repo, "app/repository.py")[0])
    validate = nodes["app/repository.py::validate"]
    assert (validate["kind"], validate["line"], validate["signature"], validate["doc"]) == (
        "function", 26, "validate(user)", "Raise TypeError if the object is not a User.")


# --- refs ---------------------------------------------------------------------

def test_import_refs(sample_repo):
    _, refs = run(sample_repo, "app/service.py")
    got = [(r["src"], r["target"], r["alias"], r["file"], r["line"]) for r in refs_of(refs, "import")]
    assert got == [
        ("app/service.py", "os", "os", "app/service.py", 2),
        ("app/service.py", "app.models.User", "User", "app/service.py", 4),          # from .models
        ("app/service.py", "app.repository.UserRepository", "UserRepository", "app/service.py", 5),
        ("app/service.py", "app.utils.normalize", "normalize", "app/service.py", 6),
        ("app/service.py", "app.utils.validate", "validate", "app/service.py", 6),
    ]

    _, refs = run(sample_repo, "app/repository.py")
    got = [(r["target"], r["alias"], r["line"]) for r in refs_of(refs, "import")]
    assert got == [
        ("json", "json", 2),
        ("app.models.User", "User", 4),
        ("app.utils.data_dir", "data_dir", 5),
    ]


def test_call_refs_service(sample_repo):
    _, refs = run(sample_repo, "app/service.py")
    p = "app/service.py::UserService."
    got = [(r["src"], r["target"], r["line"]) for r in refs_of(refs, "call")]
    assert got == [
        (p + "__init__", "UserRepository", 13),
        (p + "create", "validate", 17),
        (p + "create", "ValueError", 18),
        (p + "create", "User", 19),
        (p + "create", "normalize", 19),
        (p + "create", "self.log", 20),
        (p + "create", "user.label", 20),
        (p + "create", "self.repo.save", 21),
        (p + "log", "os.environ.get", 25),
        (p + "log", "print", 26),
    ]
    assert all(r["alias"] is None and r["file"] == "app/service.py" for r in refs_of(refs, "call"))


def test_call_refs_models_and_utils(sample_repo):
    _, refs = run(sample_repo, "app/models.py")
    got = [(r["src"], r["target"], r["line"]) for r in refs_of(refs, "call")]
    assert got == [
        ("app/models.py::Entity.describe", "type", 12),
        ("app/models.py::User.__init__", "super().__init__", 19),
        ("app/models.py::User.__init__", "super", 19),
        ("app/models.py::User.label", "self.describe", 24),
    ]

    _, refs = run(sample_repo, "app/utils.py")
    got = [(r["src"], r["target"], r["line"]) for r in refs_of(refs, "call")]
    assert got == [
        ("app/utils.py::normalize", "name.strip().lower", 7),
        ("app/utils.py::normalize", "name.strip", 7),
        ("app/utils.py::validate", "bool", 12),
        ("app/utils.py::validate", "normalize", 12),
        ("app/utils.py::data_dir", "os.environ.get", 17),
    ]

    _, refs = run(sample_repo, "app/repository.py")
    got = [(r["src"], r["target"], r["line"]) for r in refs_of(refs, "call")]
    assert got == [
        ("app/repository.py::UserRepository.__init__", "data_dir", 13),
        ("app/repository.py::UserRepository.save", "validate", 17),
        ("app/repository.py::UserRepository.dump", "json.dumps", 23),
        ("app/repository.py::UserRepository.dump", "self.items.items", 23),
        ("app/repository.py::validate", "isinstance", 28),
        ("app/repository.py::validate", "TypeError", 29),
    ]


def test_inherit_refs(sample_repo):
    _, refs = run(sample_repo, "app/models.py")
    assert refs_of(refs, "inherit") == [{
        "src": "app/models.py::User", "kind": "inherit", "target": "Entity",
        "alias": None, "file": "app/models.py", "line": 15,
    }]


def test_ref_totals(sample_repo):
    totals = Counter()
    for rel in PY_FILES:
        totals.update(r["kind"] for r in run(sample_repo, rel)[1])
    assert totals == {"import": 9, "call": 25, "inherit": 1}


# --- edge cases (inline sources) ----------------------------------------------

def test_syntax_error_gives_file_node_only():
    nodes, refs = extract("pkg/broken.py", "def broken(:\n    pass\n", "pkg.broken")
    assert [(n["id"], n["kind"]) for n in nodes] == [("pkg/broken.py", "file")]
    assert refs == []


def test_null_byte_source_gives_file_node_only():
    nodes, refs = extract("pkg/bad.py", b"x = 1\x00\n", "pkg.bad")
    assert [n["kind"] for n in nodes] == ["file"] and refs == []


def test_relative_imports():
    src = "from . import models\nfrom ..core import base as b\nfrom .x import *\n"
    _, refs = extract("pkg/sub/__init__.py", src, "pkg.sub")
    assert [(r["target"], r["alias"]) for r in refs] == [
        ("pkg.sub.models", "models"), ("pkg.core.base", "b"), ("pkg.sub.x", "*")]

    _, refs = extract("pkg/sub/mod.py", src, "pkg.sub.mod")
    assert [(r["target"], r["alias"]) for r in refs] == [
        ("pkg.sub.models", "models"), ("pkg.core.base", "b"), ("pkg.sub.x", "*")]


def test_import_forms():
    src = "from __future__ import annotations\nimport os.path\nimport numpy as np\nimport a, b.c as d\n"
    _, refs = extract("m.py", src, "m")
    assert [(r["target"], r["alias"], r["line"]) for r in refs] == [
        ("os.path", "os.path", 2), ("numpy", "np", 3), ("a", "a", 4), ("b.c", "d", 4)]


def test_nested_async_and_duplicates():
    src = (
        "import functools\n"
        "class A(base.Base, Generic[T], metaclass=Meta):\n"
        "    class Inner:\n"
        "        def m(self) -> int: return 1\n"
        "    @property\n"
        "    def p(self): return self._p\n"
        "    @p.setter\n"
        "    def p(self, v): self._p = v\n"
        "    async def run(self, *args, k: int = 2, **kw):\n"
        "        def helper(x): return go(x)\n"
        "        return helper(1)\n"
        "@functools.lru_cache(maxsize=None)\n"
        "def top(): handlers[0]()\n"
    )
    nodes, refs = extract("m.py", src, "m")
    got = [(n["id"], n["kind"], n["signature"]) for n in nodes]
    assert got == [
        ("m.py", "file", None),
        ("m.py::A", "class", "A(base.Base, Generic[T], metaclass=Meta)"),
        ("m.py::A.Inner", "class", "Inner"),
        ("m.py::A.Inner.m", "method", "m(self) -> int"),
        ("m.py::A.p", "method", "p(self)"),                       # duplicate p: first one wins
        ("m.py::A.run", "method", "async run(self, *args, k: int=2, **kw)"),
        ("m.py::A.run.helper", "function", "helper(x)"),
        ("m.py::top", "function", "top()"),
    ]
    assert [(r["src"], r["target"]) for r in refs_of(refs, "inherit")] == [
        ("m.py::A", "base.Base"), ("m.py::A", "Generic")]
    calls = [(r["src"], r["target"]) for r in refs_of(refs, "call")]
    assert calls == [
        ("m.py::A.run.helper", "go"),
        ("m.py::A.run", "helper"),
        ("m.py", "functools.lru_cache"),   # decorator call runs in the enclosing scope
    ]                                      # handlers[0]() has no name: no ref
