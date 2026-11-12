"""Call and import rules that keep guesses out of the graph (see reaper/resolve.py docstring).

Every expected edge is written by hand from the small repos below.
"""

from reaper.graph import build

E, I, A = "EXTRACTED", "INFERRED", "AMBIGUOUS"


def mini_repo(tmp_path, files):
    for rel, src in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src)
    return build(tmp_path)


def edges(g, kind):
    return {(e["src"], e["dst"], e["kind"], e["confidence"]) for e in g["edges"] if e["kind"] == kind}


def test_builtin_type_methods_unknown_receivers_and_bare_names(tmp_path):
    g = mini_repo(tmp_path, {
        "lib/store.py": (
            "class Store:\n"
            "    def append(self, x):\n"
            "        pass\n"
            "\n"
            "    def run(self):\n"
            "        pass\n"),
        "lib/far.py": (
            "class Far:\n"
            "    def run(self):\n"
            "        pass\n"
            "\n"
            "    def only_far(self):\n"
            "        pass\n"),
        "app/main.py": (
            "from lib.store import Store\n"
            "\n"
            "def go(s, items):\n"
            "    items.append(1)\n"   # a list method name: no edge, although Store.append is visible
            "    s.run()\n"           # Store.run is visible (imported), Far.run is not: INFERRED
            "    s.only_far()\n"      # Far is never imported here: no edge
            "    helper()\n"),        # not defined here, not imported: a local variable, no edge
    })
    assert edges(g, "calls") == {("app/main.py::go", "lib/store.py::Store.run", "calls", I)}


def test_visible_through_reexport_module_import_and_bases(tmp_path):
    g = mini_repo(tmp_path, {
        "pkg/__init__.py": "from pkg.shapes import Mesh\n",
        "pkg/shapes.py": (
            "class Base:\n"
            "    def area(self):\n"
            "        pass\n"
            "\n"
            "class Mesh(Base):\n"
            "    def gradient(self):\n"
            "        pass\n"),
        "pkg/other.py": (
            "class Other:\n"
            "    def gradient(self):\n"
            "        pass\n"
            "\n"
            "    def area(self):\n"
            "        pass\n"),
        "use_reexport.py": (
            "from pkg import Mesh\n"
            "\n"
            "def f(m):\n"
            "    m.gradient()\n"      # Mesh, re-exported by pkg/__init__.py, is visible; Other is not
            "    m.area()\n"),        # Base.area: Base is a base class of the visible Mesh
        "use_module.py": (
            "import pkg.other as po\n"
            "\n"
            "def g(o):\n"
            "    o.gradient()\n"),    # pkg/other.py imported as a module: its classes are visible
    })
    assert edges(g, "calls") == {
        ("use_reexport.py::f", "pkg/shapes.py::Mesh.gradient", "calls", I),
        ("use_reexport.py::f", "pkg/shapes.py::Base.area", "calls", I),
        ("use_module.py::g", "pkg/other.py::Other.gradient", "calls", I),
    }


def test_self_calls_library_bases_and_subclass_hooks(tmp_path):
    g = mini_repo(tmp_path, {
        "models.py": (
            "import torch.nn as nn\n"
            "\n"
            "class Net(nn.Module):\n"
            "    def forward(self):\n"
            "        self.parameters()\n"   # inherited from torch's nn.Module: no edge to Fake
            "        self.decoder()\n"      # an attribute (self.decoder = ...): no edge
            "\n"
            "class Fake:\n"
            "    def parameters(self):\n"
            "        pass\n"
            "\n"
            "    def decoder(self):\n"
            "        pass\n"
            "\n"
            "class Base:\n"
            "    def run(self):\n"
            "        self.step()\n"         # defined by subclasses A and B (grandchild): AMBIGUOUS each
            "        self.finish()\n"       # defined by one subclass: INFERRED
            "\n"
            "class A(Base):\n"
            "    def step(self):\n"
            "        pass\n"
            "\n"
            "    def finish(self):\n"
            "        pass\n"
            "\n"
            "class B(A):\n"
            "    def step(self):\n"
            "        pass\n"),
    })
    assert edges(g, "calls") == {
        ("models.py::Base.run", "models.py::A.step", "calls", A),
        ("models.py::Base.run", "models.py::B.step", "calls", A),
        ("models.py::Base.run", "models.py::A.finish", "calls", I),
    }


def test_imports_from_the_files_own_folder(tmp_path):
    g = mini_repo(tmp_path, {
        "examples/gp/gp_utils.py": "def load():\n    pass\n",
        "examples/gp/train.py": (
            "from gp_utils import load\n"   # line 1
            "import gp_utils\n"             # line 2
            "\n"
            "def main():\n"
            "    load()\n"                  # line 5
            "    gp_utils.load()\n"),       # line 6
        # a script folder: the neighbouring utils.py wins over the repo-root utils.py, as in Python
        "utils.py": "def tool():\n    pass\n",
        "examples/gp/utils.py": "def tool():\n    pass\n",
        "examples/gp/run_tool.py": "import utils\n\ndef main():\n    utils.tool()\n",
        # a neighbouring folder without __init__.py
        "examples/gp/src/helpers.py": "def assist():\n    pass\n",
        "examples/gp/use_src.py": "from src.helpers import assist\n\ndef main():\n    assist()\n",
        # a package folder: Python only finds the neighbour when the folder is on sys.path: INFERRED
        "pkg/__init__.py": "",
        "pkg/neighbour.py": "def ping():\n    pass\n",
        "pkg/tool.py": "from neighbour import ping\n\ndef main():\n    ping()\n",
    })
    assert edges(g, "imports") == {
        ("examples/gp/train.py", "examples/gp/gp_utils.py", "imports", E),
        ("examples/gp/run_tool.py", "examples/gp/utils.py", "imports", E),
        ("examples/gp/use_src.py", "examples/gp/src/helpers.py", "imports", E),
        ("pkg/tool.py", "pkg/neighbour.py", "imports", I),
    }
    assert edges(g, "calls") == {
        ("examples/gp/train.py::main", "examples/gp/gp_utils.py::load", "calls", E),
        ("examples/gp/run_tool.py::main", "examples/gp/utils.py::tool", "calls", E),
        ("examples/gp/use_src.py::main", "examples/gp/src/helpers.py::assist", "calls", E),
        ("pkg/tool.py::main", "pkg/neighbour.py::ping", "calls", I),
    }
    assert not [n for n in g["nodes"] if n["kind"] == "external"]
    # lines: where in the source file each edge comes from; contains edges have none
    lines = {(e["src"], e["dst"]): e.get("lines") for e in g["edges"]}
    assert lines[("examples/gp/train.py", "examples/gp/gp_utils.py")] == [1, 2]
    assert lines[("examples/gp/train.py::main", "examples/gp/gp_utils.py::load")] == [5, 6]
    assert lines[("examples/gp/train.py", "examples/gp/train.py::main")] is None


def test_package_files_keep_absolute_imports_repo_wide(tmp_path):
    g = mini_repo(tmp_path, {
        "utils.py": "def tool():\n    pass\n",
        "pkg/__init__.py": "",
        "pkg/utils.py": "def tool():\n    pass\n",
        "pkg/main.py": "import utils\n\ndef main():\n    utils.tool()\n",
    })
    # inside a package `import utils` is the repo-wide utils.py, not the neighbour (no implicit
    # relative imports in Python 3)
    assert edges(g, "imports") == {("pkg/main.py", "utils.py", "imports", E)}
    assert edges(g, "calls") == {("pkg/main.py::main", "utils.py::tool", "calls", E)}


def test_js_prototype_methods_and_bare_names(tmp_path):
    g = mini_repo(tmp_path, {
        "src/list.js": "export class List {\n  push(x) {}\n  total() {}\n}\n",
        "src/helper.js": "export function helper() {}\n",
        "src/use.js": ('import { List } from "./list";\n'
                       "function f(arr, l) {\n  arr.push(1);\n  l.total();\n  helper();\n}\n"),
    })
    # arr.push: an Array method, no edge; l.total: List is visible; a bare name in JS can be a
    # script global, so it is still matched by name
    assert edges(g, "calls") == {
        ("src/use.js::f", "src/list.js::List.total", "calls", I),
        ("src/use.js::f", "src/helper.js::helper", "calls", I),
    }


# One pair, call sites of different confidence: one edge per confidence, each with its own lines.
SPLIT = {
    "lib/foo.py": (
        "class Foo:\n"
        "    def m(self):\n"
        "        pass\n"),
    "app/main.py": (
        "from lib.foo import Foo\n"      # 1
        "\n"                             # 2
        "def go(x):\n"                   # 3
        "    Foo.m(x)\n"                 # 4: through the imported class: EXTRACTED
        "    x.m()\n"                    # 5: x unknown, Foo the only visible class with m: INFERRED
        "    x.m()\n"                    # 6: INFERRED
        "    Foo.m(x.m())\n"),           # 7: both on one line: the line is EXTRACTED only
    "pkg/__init__.py": "",
    "pkg/neighbour.py": "def ping():\n    pass\n",
    "pkg/tool.py": (
        "from neighbour import ping\n"   # 1: the package folder's neighbour: INFERRED
        "import pkg.neighbour\n"),       # 2: absolute: EXTRACTED
}


def test_a_pair_has_one_edge_per_confidence_each_with_its_own_lines(tmp_path):
    g = mini_repo(tmp_path, SPLIT)
    assert [e for e in g["edges"] if e["kind"] != "contains"] == [
        {"src": "app/main.py", "dst": "lib/foo.py", "kind": "imports", "confidence": E, "lines": [1]},
        {"src": "pkg/tool.py", "dst": "pkg/neighbour.py", "kind": "imports", "confidence": E,
         "lines": [2]},
        {"src": "pkg/tool.py", "dst": "pkg/neighbour.py", "kind": "imports", "confidence": I,
         "lines": [1]},
        {"src": "app/main.py::go", "dst": "lib/foo.py::Foo.m", "kind": "calls", "confidence": E,
         "lines": [4, 7]},
        {"src": "app/main.py::go", "dst": "lib/foo.py::Foo.m", "kind": "calls", "confidence": I,
         "lines": [5, 6]},
    ]
    # contains edges: one per pair, no lines, as before
    assert [e for e in g["edges"] if e["kind"] == "contains"] == [
        {"src": "app/main.py", "dst": "app/main.py::go", "kind": "contains", "confidence": E},
        {"src": "lib/foo.py", "dst": "lib/foo.py::Foo", "kind": "contains", "confidence": E},
        {"src": "lib/foo.py::Foo", "dst": "lib/foo.py::Foo.m", "kind": "contains", "confidence": E},
        {"src": "pkg/neighbour.py", "dst": "pkg/neighbour.py::ping", "kind": "contains",
         "confidence": E},
    ]
