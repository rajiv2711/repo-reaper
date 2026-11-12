"""Phase 3: resolve raw refs into edges.

Expected edges are written by hand from the fixture source (tests/fixtures/sample_py/app).
"""

from collections import Counter

from reaper.graph import build
from reaper.resolve import resolve

E, I, A = "EXTRACTED", "INFERRED", "AMBIGUOUS"
M, R, S, U = "app/models.py", "app/repository.py", "app/service.py", "app/utils.py"

FIXTURE_EDGES = {
    # imports: file -> repo file (longest module prefix), else ext:<top package>
    (R, "ext:json", "imports", E),
    (R, M, "imports", E),                    # from app.models import User
    (R, U, "imports", E),                    # from app.utils import data_dir
    (S, "ext:os", "imports", E),
    (S, M, "imports", E),                    # from .models import User
    (S, R, "imports", E),                    # from .repository import UserRepository
    (S, U, "imports", E),                    # from app.utils import normalize, validate (one edge)
    (U, "ext:os", "imports", E),
    # inherits: User(Entity), Entity defined in the same file
    (f"{M}::User", f"{M}::Entity", "inherits", E),
    # calls
    (f"{M}::User.__init__", f"{M}::Entity.__init__", "calls", I),        # super().__init__ -> base
    (f"{M}::User.label", f"{M}::Entity.describe", "calls", I),           # self.describe, not own -> base
    (f"{R}::UserRepository.__init__", f"{U}::data_dir", "calls", E),     # import alias
    (f"{R}::UserRepository.save", f"{R}::validate", "calls", E),         # same-file name
    (f"{S}::UserService.__init__", f"{R}::UserRepository", "calls", E),  # import alias (class)
    (f"{S}::UserService.create", f"{U}::validate", "calls", E),          # alias beats repository.validate
    (f"{S}::UserService.create", f"{M}::User", "calls", E),              # import alias (class)
    (f"{S}::UserService.create", f"{U}::normalize", "calls", E),         # import alias
    (f"{S}::UserService.create", f"{S}::UserService.log", "calls", E),   # self.log, own method
    (f"{S}::UserService.create", f"{M}::User.label", "calls", I),        # user.label: 1 candidate
    (f"{S}::UserService.create", f"{R}::UserRepository.save", "calls", I),  # self.repo.save: 1 candidate
    (f"{U}::validate", f"{U}::normalize", "calls", E),                   # same-file name
    # no edge: builtins (type, super, isinstance, TypeError, ValueError, print, bool),
    # aliases outside the repo (json.dumps, os.environ.get), no candidate
    # (self.items.items, name.strip, name.strip().lower)
}


def as_tuples(edges, skip_contains=True):
    return [(e["src"], e["dst"], e["kind"], e["confidence"]) for e in edges
            if not (skip_contains and e["kind"] == "contains")]


def mini_repo(tmp_path, files):
    for rel, src in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src)
    return build(tmp_path)


def test_fixture_edges(sample_repo):
    g = build(sample_repo)
    got = as_tuples(g["edges"])
    assert len(got) == len(set(got))  # no duplicates
    assert set(got) == FIXTURE_EDGES


def test_fixture_contains(sample_repo):
    g = build(sample_repo)
    contains = [e for e in g["edges"] if e["kind"] == "contains"]
    assert all(e["confidence"] == E for e in contains)
    # every symbol has exactly one parent: 4 classes + 10 methods + 4 functions
    assert len(contains) == 18
    assert Counter(e["dst"] for e in contains) == {
        n["id"]: 1 for n in g["nodes"] if n["kind"] in ("class", "function", "method")}
    pairs = {(e["src"], e["dst"]) for e in contains}
    assert (M, f"{M}::Entity") in pairs
    assert (f"{M}::Entity", f"{M}::Entity.describe") in pairs
    assert (U, f"{U}::validate") in pairs


def test_external_nodes_and_no_dangling_edges(sample_repo):
    g = build(sample_repo)
    ext = [n for n in g["nodes"] if n["kind"] == "external"]
    assert ext == [
        {"id": "ext:json", "kind": "external", "name": "json", "file": None,
         "line": None, "signature": None, "doc": None},
        {"id": "ext:os", "kind": "external", "name": "os", "file": None,
         "line": None, "signature": None, "doc": None},
    ]
    ids = {n["id"] for n in g["nodes"]}
    assert len(ids) == len(g["nodes"])
    assert all(e["src"] in ids and e["dst"] in ids for e in g["edges"])


def test_resolve_is_idempotent_and_order_independent(sample_repo):
    g = build(sample_repo)
    nodes, edges = resolve(g["nodes"], g["refs"])  # nodes already contain ext nodes
    assert nodes == g["nodes"] and edges == g["edges"]
    # files in another order (incremental updates append re-extracted files at the end)
    by_file = lambda items: sorted(items, key=lambda x: x["file"] or "", reverse=True)
    nodes2, edges2 = resolve(by_file(g["nodes"]), by_file(g["refs"]))
    assert sorted(n["id"] for n in nodes2) == sorted(n["id"] for n in nodes)
    assert edges2 == edges


def test_aliases_reexports_star_imports_and_scopes(tmp_path):
    g = mini_repo(tmp_path, {
        "pkg/__init__.py": "from .core import Engine\n",
        "pkg/ext.py": "",
        "pkg/core.py": (
            "class Base:\n"
            "    def start(self):\n"
            "        return 1\n"
            "\n"
            "class Engine(Base):\n"
            "    def run(self):\n"
            "        return self.start()\n"),
        "pkg/extra.py": "def helper():\n    return 2\n",
        "pkg/plugins.py": (
            "import requests\n"
            "import pkg.extension\n"       # not a file: falls back to pkg/__init__.py, not pkg/ext.py
            "from pkg import core\n"
            "from pkg import Engine\n"
            "from pkg.extra import *\n"
            "\n"
            "class Turbo(core.Engine):\n"
            "    def get(self):\n"
            "        pass\n"
            "\n"
            "    def boost(self):\n"
            "        self.start()\n"        # grandparent method
            "        self.missing()\n"      # not on class or bases, no candidate: no edge
            "        requests.get()\n"      # alias outside the repo: no edge despite Turbo.get
            "        helper()\n"            # star import
            "        Engine()\n"            # re-exported by pkg/__init__.py
            "\n"
            "def get():\n"
            "    def inner():\n"
            "        return 1\n"
            "    return inner()\n"),        # nested function scope
    })
    C, P = "pkg/core.py", "pkg/plugins.py"
    assert set(as_tuples(g["edges"])) == {
        ("pkg/__init__.py", C, "imports", E),
        (P, "ext:requests", "imports", E),
        (P, "pkg/__init__.py", "imports", E),   # pkg.extension and pkg.Engine
        (P, C, "imports", E),
        (P, "pkg/extra.py", "imports", E),
        (f"{C}::Engine", f"{C}::Base", "inherits", E),
        (f"{P}::Turbo", f"{C}::Engine", "inherits", E),
        (f"{C}::Engine.run", f"{C}::Base.start", "calls", I),
        (f"{P}::Turbo.boost", f"{C}::Base.start", "calls", I),
        (f"{P}::Turbo.boost", "pkg/extra.py::helper", "calls", E),
        (f"{P}::Turbo.boost", f"{C}::Engine", "calls", E),
        (f"{P}::get", f"{P}::get.inner", "calls", E),
    }
    assert "ext:requests" in {n["id"] for n in g["nodes"]}


def test_last_name_matching(tmp_path):
    g = mini_repo(tmp_path, {
        "amb/a.py": (
            "from amb.b import B\n"
            "\n"
            "class A:\n"
            "    def save(self):\n"
            "        pass\n"
            "\n"
            "    def go(self, other):\n"
            "        self.save()\n"         # own method: EXTRACTED
            "        other.save()\n"        # A.save + B.save, both visible here: AMBIGUOUS each
            "        save()\n"              # (A.save upgraded to EXTRACTED); bare name never means a method
            "        other.ping()\n"        # C0..C5.ping, but c.py is not imported here: no edge
            "        other.shout()\n"       # B.shout, the only visible shout: INFERRED
            "\n"
            "    def misc(self, other):\n"
            "        lonely()\n"            # Python: not defined here, not imported -> a local variable
            "        other.append(1)\n"),   # a list method on a receiver of unknown type: no edge
        "amb/b.py": (
            "class B:\n"
            "    def save(self):\n"
            "        pass\n"
            "\n"
            "    def shout(self):\n"
            "        pass\n"),
        "amb/c.py": "".join(f"class C{i}:\n    def ping(self):\n        pass\n" for i in range(6)),
    })
    calls = {t for t in as_tuples(g["edges"]) if t[2] == "calls"}
    assert calls == {
        ("amb/a.py::A.go", "amb/a.py::A.save", "calls", E),
        ("amb/a.py::A.go", "amb/b.py::B.save", "calls", A),
        ("amb/a.py::A.go", "amb/b.py::B.shout", "calls", I),
    }
