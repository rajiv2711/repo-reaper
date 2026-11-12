"""`reaper query`: --depth, subclasses, call-site lines, the "not linked" footer and --budget.

Expected output is written by hand from the small repo below (line numbers in the comments).
"""

import json
import re

import pytest

from reaper.cli import main

CORE = (
    "class Base:\n"            # 1
    "    def run(self):\n"     # 2
    "        pass\n"           # 3
    "\n"                       # 4
    "class Mid(Base):\n"       # 5
    "    pass\n"               # 6
    "\n"                       # 7
    "class Leaf(Mid):\n"       # 8
    "    pass\n"               # 9
    "\n"                       # 10
    "def helper():\n"          # 11
    "    pass\n"               # 12
    "\n"                       # 13
    "def entry():\n"           # 14
    "    helper()\n"           # 15
)
USE = (
    "import numpy as np\n"                     # 1
    "from lib.core import entry, helper\n"     # 2
    "\n"                                       # 3
    "def a():\n"                               # 4
    "    entry()\n"                            # 5
    "    helper()\n"                           # 6
    "\n"                                       # 7
    "def b():\n"                               # 8
    "    a()\n"                                # 9
    "    entry()\n"                            # 10
    "\n"                                       # 11
    "def c(thing):\n"                          # 12
    "    b()\n"                                # 13
    "    thing.entry()\n"                      # 14: unknown receiver: not linked
    "    np.entry()\n"                         # 15: through numpy: not ours, left out
)


@pytest.fixture
def repo(tmp_path):
    for rel, src in {"lib/core.py": CORE, "lib/use.py": USE}.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(src)
    assert main(["map", str(tmp_path)]) == 0
    return tmp_path


def run(repo, capsys, *args):
    capsys.readouterr()
    code = main(["query", str(repo), *args])
    return code, capsys.readouterr().out


def test_callers_depth_2_with_call_sites_and_footer(repo, capsys):
    code, out = run(repo, capsys, "callers", "entry", "--depth", "2")
    assert code == 0
    assert out == (
        "callers of lib/core.py::entry  (line 14)\n"
        "  2 callers: 2 EXTRACTED; hop 2: 1 caller: 1 EXTRACTED\n"
        "  EXTRACTED  lib/use.py::a  (calls at line 5)\n"
        "    EXTRACTED  lib/use.py::b  (calls at line 9)  (see above)\n"   # b is a hop-1 caller too
        "  EXTRACTED  lib/use.py::b  (calls at line 10)\n"
        "    EXTRACTED  lib/use.py::c  (calls at line 13)\n"
        "  not linked: 1 call site named entry that the graph could not resolve (check only these):\n"
        "    lib/use.py:14  thing.entry()  in lib/use.py::c\n"
    )


def test_callers_json_nests_and_marks_repeats(repo, capsys):
    code, out = run(repo, capsys, "callers", "entry", "--depth", "2", "--json")
    [res] = json.loads(out)
    assert (res["node"], res["line"]) == ("lib/core.py::entry", 14)
    a, b = res["callers"]
    assert (a["id"], a["lines"], b["id"], b["lines"]) == ("lib/use.py::a", [5], "lib/use.py::b", [10])
    assert a["callers"] == [{"id": "lib/use.py::b", "kind": "function", "file": "lib/use.py", "line": 8,
                             "confidence": "EXTRACTED", "lines": [9], "repeat": True}]
    assert [(k["id"], k["lines"]) for k in b["callers"]] == [("lib/use.py::c", [13])]
    assert res["unlinked"] == [{"src": "lib/use.py::c", "file": "lib/use.py", "line": 14,
                                "target": "thing.entry"}]


def test_callees_and_subclasses(repo, capsys):
    code, out = run(repo, capsys, "callees", "a")
    assert out == (
        "callees of lib/use.py::a  (line 4)\n"
        "  2 callees: 2 EXTRACTED\n"
        "  EXTRACTED  lib/core.py::entry  (called at line 5)\n"
        "  EXTRACTED  lib/core.py::helper  (called at line 6)\n"
    )
    code, out = run(repo, capsys, "subclasses", "Base", "--depth", "2")
    assert out == (
        "subclasses of lib/core.py::Base  (line 1)\n"
        "  1 subclass: 1 EXTRACTED; hop 2: 1 subclass: 1 EXTRACTED\n"
        "  EXTRACTED  lib/core.py::Mid  (line 5)\n"
        "    EXTRACTED  lib/core.py::Leaf  (line 8)\n"
    )


def test_budget_cuts_lines_and_says_what_shows_all(tmp_path, capsys):
    files = {"lib/core.py": CORE}
    for folder, n in (("x", 30), ("y", 20)):
        for i in range(n):
            files[f"{folder}/m{i:02d}.py"] = "from lib.core import helper\n\ndef f():\n    helper()\n"
    for rel, src in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(src)
    assert main(["map", str(tmp_path)]) == 0
    code, out = run(tmp_path, capsys, "callers", "helper", "--budget", "100")
    lines = out.splitlines()
    assert lines[:2] == ["callers of lib/core.py::helper  (line 11)", "  51 callers: 51 EXTRACTED"]
    shown = lines[2:-3]
    assert all(line.startswith("  EXTRACTED  ") for line in shown)
    assert len("\n".join(lines[:2 + len(shown)])) <= 100 * 4   # header + listed callers fit
    m = re.fullmatch(r"  \.\.\. (\d+) more callers \((.*)\)", lines[-3])
    assert m, lines[-3]
    assert int(m[1]) == 51 - len(shown)
    per_folder = dict(part.split(" ") for part in m[2].split(", "))
    assert sum(map(int, per_folder.values())) == int(m[1]) and set(per_folder) <= {"lib/", "x/", "y/"}
    n = re.fullmatch(r"  \((\d+) of 51 lines not shown; --budget (\d+) shows all\)", lines[-2])
    assert n and int(n[1]) == int(m[1]), lines[-2]
    assert lines[-1] == "  not linked: none"
    # the suggested budget shows every caller, and no notice
    code, out = run(tmp_path, capsys, "callers", "helper", "--budget", n[2])
    assert "not shown" not in out and out.count("EXTRACTED  ") == 51


def test_footer_says_when_the_name_is_a_builtin_method(tmp_path, capsys):
    files = {"lib/bag.py": "class Bag:\n    def append(self, x):\n        pass\n",
             "lib/use.py": "def f(items):\n    items.append(1)\n"}
    for rel, src in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(src)
    assert main(["map", str(tmp_path)]) == 0
    code, out = run(tmp_path, capsys, "callers", "Bag.append")
    assert out == (
        "callers of lib/bag.py::Bag.append  (line 2)\n"
        "  (none)\n"
        "  not linked: 1 call site named append that the graph could not resolve (check only these; "
        "append is also a built-in list/dict/str (or JS Array, String...) method, so most of these "
        "are probably that):\n"
        "    lib/use.py:2  items.append()  in lib/use.py::f\n"
    )
