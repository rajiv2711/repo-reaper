"""Phase 8: the graph.html page template (reaper/templates/graph.html) and its one-pass fill.

`test_template_*` / `test_html_*` read only Python data or the template/page string; they
never run JavaScript and never skip. `test_js_*` run the page script in node (>= 18) with a
stub DOM via run_js(): they skip with a visible reason when node is missing, and fail instead
when REAPER_REQUIRE_NODE is set.
"""

import importlib.resources
import json
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path

import pytest

from reaper import outputs
from reaper.graph import build

ROOT = Path(__file__).resolve().parent.parent
M, R, S, U = "app/models.py", "app/repository.py", "app/service.py", "app/utils.py"
C = f"{S}::UserService.create"
UNPKG = "https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"
JSDELIVR = "https://cdn.jsdelivr.net/npm/vis-network@9.1.9/standalone/umd/vis-network.min.js"
# tests/test_resolve.py::test_last_name_matching, verbatim: 1 EXTRACTED, 1 AMBIGUOUS pair, 1 INFERRED call
AMB = {
    "amb/a.py": (
        "from amb.b import B\n"
        "\n"
        "class A:\n"
        "    def save(self):\n"
        "        pass\n"
        "\n"
        "    def go(self, other):\n"
        "        self.save()\n"
        "        other.save()\n"
        "        save()\n"
        "        other.ping()\n"
        "        other.shout()\n"
        "\n"
        "    def misc(self, other):\n"
        "        lonely()\n"
        "        other.append(1)\n"),
    "amb/b.py": (
        "class B:\n"
        "    def save(self):\n"
        "        pass\n"
        "\n"
        "    def shout(self):\n"
        "        pass\n"),
    "amb/c.py": "".join(f"class C{i}:\n    def ping(self):\n        pass\n" for i in range(6)),
}
MOD = {"m.py": 'def main():\n    pass\n\nif __name__ == "__main__":\n    main()\n'}


def write(root, files):
    for rel, src in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src)
    return root


def html_data(html):
    m = re.search(r'<script id="graph-data" type="application/json">(.*?)</script>', html, re.S)
    assert m, "embedded graph data not found"
    return json.loads(m.group(1))


NODE_MSG = ("node >= 18 not found: JS behaviour test skipped "
            "(node is a test-time tool, not a Python dependency)")
STUB = """
const stubEl = () => ({textContent: "", hidden: false, style: {}, dataset: {}, className: "",
  classList: {add() {}, remove() {}, toggle() {}, contains() { return false; }},
  addEventListener() {}, appendChild(c) { return c; }, setAttribute() {}});
globalThis.document = {
  getElementById: id => id === "graph-data" ? {textContent: BLOB} : stubEl(),
  createElement: stubEl, head: stubEl(), body: stubEl()};
"""


def _node():
    exe = shutil.which("node")
    if exe:
        try:
            out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30)
            if int(out.stdout.strip().lstrip("v").split(".")[0]) >= 18:
                return exe
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    if os.environ.get("REAPER_REQUIRE_NODE"):
        pytest.fail(NODE_MSG)
    pytest.skip(NODE_MSG)


def run_js(html, expr):
    """Run the page's inline script in node with a stub DOM; return JSON.stringify(expr)."""
    exe = _node()
    blob = re.search(r'<script id="graph-data" type="application/json">(.*?)</script>',
                     html, re.S).group(1)
    script = re.findall(r"<script>(.*?)</script>", html, re.S)[-1]
    js = (STUB.replace("BLOB", json.dumps(blob)) + script
          + f"\nprocess.stdout.write(JSON.stringify({expr}));\n")
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "page.js"
        path.write_text(js, encoding="utf-8")
        out = subprocess.run([exe, str(path)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def fixture_html(repo, monkeypatch=None, max_nodes=None):
    if max_nodes is not None:
        monkeypatch.setattr(outputs, "MAX_HTML_NODES", max_nodes)
    return outputs.graph_html(build(repo))


# ---------------------------------------------------------------- template file (08-01-1)

def test_template_is_package_data():
    with open(ROOT / "pyproject.toml", "rb") as f:
        cfg = tomllib.load(f)
    assert "templates/*.html" in cfg["tool"]["setuptools"]["package-data"]["reaper"]
    res = importlib.resources.files("reaper").joinpath("templates/graph.html")
    assert res.read_bytes().startswith(b"<!DOCTYPE html>")  # no BOM
    assert res.read_text(encoding="utf-8") == outputs.HTML_TEMPLATE


def test_html_one_pass_fill(tmp_path, monkeypatch):
    # A slot name inside the URL or inside the data must never be filled a second time.
    monkeypatch.setattr(outputs, "VIS_NETWORK_URL", "https://x/__DATA__.js")
    html = outputs.graph_html(build(write(tmp_path, {
        "evil.py": '"""__VIS__ __DATA__ __X__"""\n'})))
    assert '<script src="https://x/__DATA__.js"></script>' in html
    assert html_data(html)["nodes"][0]["title"] == "evil.py\n__VIS__ __DATA__ __X__"


def test_template_slots():
    assert set(re.findall(r"__([A-Z]+)__", outputs.HTML_TEMPLATE)) == {"VIS", "DATA"}


def test_template_never_uses_innerhtml():
    tpl = outputs.HTML_TEMPLATE
    for bad in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(",
                "multi:", 'id="vis"'):
        assert bad not in tpl, bad
    assert tpl.count('<script id="graph-data"') == 1


def test_outputs_never_imports_enrich():
    src = (ROOT / "reaper" / "outputs.py").read_text(encoding="utf-8")
    imports = [line for line in src.splitlines()
               if re.match(r"\s*(import|from)\s", line)]
    assert imports, "no import lines found"
    assert not [line for line in imports if "enrich" in line]


# ---------------------------------------------------------------- skeleton, boot, edge styles (08-04-1)

def test_js_parses(sample_repo):
    html = fixture_html(sample_repo)
    assert run_js(html, "D.nodes.length") == 25
    assert run_js(html, "EDGE_COLORS") == outputs.EDGE_COLORS


def test_template_dom_hooks():
    tpl = outputs.HTML_TEMPLATE
    for hook in ("llm-toggle", "clear-focus", "fit", "collapse-all", "relayout", "status", "search",
                 "results", "legend", "net", "panel", "tab-details", "tab-arch", "details", "arch"):
        assert tpl.count(f'id="{hook}"') == 1, hook
    attrs = ([f'data-hops="{n}"' for n in (1, 2, 3)]
             + [f'data-node-kind="{k}"' for k in ("file", "class", "function", "method", "external")]
             + [f'data-edge-kind="{k}"' for k in ("contains", "imports", "inherits", "calls")]
             + [f'data-conf="{c}"' for c in ("EXTRACTED", "INFERRED", "AMBIGUOUS")])
    for attr in attrs:
        assert tpl.count(attr) == 1, attr
    for exact in ('<label id="llm-toggle" hidden>', '<button id="tab-arch" class="llm" hidden>',
                  '<div id="arch" class="llm" hidden>', "[hidden] { display: none !important; }"):
        assert exact in tpl, exact


def test_template_cdn_fallback(sample_repo):
    tpl = outputs.HTML_TEMPLATE
    for s in ('typeof vis === "undefined"', "Loading vis-network 9.1.9",
              "Could not load vis-network 9.1.9 from unpkg.com or cdn.jsdelivr.net", "onerror",
              JSDELIVR, "sha384-yxKDWWf0wwdUj/gPeuL11czrnKFQROnLgY8ll7En9NYoXibgg3C6NK/UDHNtUgWJ",
              '<script src="__VIS__"></script>'):
        assert s in tpl, s
    html = fixture_html(sample_repo)
    assert html.count("<script src=") == 1
    assert set(re.findall(r'https://[^\s"\'<>]+', html)) == {UNPKG, JSDELIVR}


def test_template_edge_styles():
    tpl = outputs.HTML_TEMPLATE
    for s in ("INFERRED: [8, 6]", "AMBIGUOUS: [2, 4]", "opacity: 0.5", "smooth: false"):
        assert s in tpl, s


def test_html_ambiguous_is_dashed(tmp_path):
    data = html_data(outputs.graph_html(build(write(tmp_path, AMB))))
    assert [(e["id"], e["confidence"], e["dashes"]) for e in data["edges"]
            if e["confidence"] != "EXTRACTED"] == [("e21", "AMBIGUOUS", True),
                                                   ("e22", "INFERRED", True)]


def test_js_edge_styles_at_load(tmp_path):
    html = outputs.graph_html(build(write(tmp_path, AMB)))
    got = run_js(html, 'D.edges.filter(e => e.confidence !== "EXTRACTED")'
                       '.map(e => [e.id, e.dashes, e.color])')
    assert got == [["e21", [2, 4], {"color": "#f58518", "opacity": 0.5}],
                   ["e22", [8, 6], "#f58518"]]


# ---------------------------------------------------------------- view, filters, legend, hop focus (08-04-2)

VIEW = ("(() => { const V = applyView(); "
        "return [[V.nodes.size, V.raw.size, V.agg.size], legendCounts(V)]; })()")


def counts(node, edge, conf, lines):
    return {"node": dict(zip(("file", "class", "function", "method", "external"), node)),
            "edge": dict(zip(("contains", "imports", "inherits", "calls"), edge)),
            "conf": dict(zip(("EXTRACTED", "INFERRED", "AMBIGUOUS"), conf)), "lines": lines}


def test_js_bfs_hops(sample_repo):
    html = fixture_html(sample_repo)
    one = sorted([f"{M}::User", f"{M}::User.label", f"{R}::UserRepository.save", C,
                  f"{S}::UserService.log", f"{U}::normalize", f"{U}::validate"])
    two = sorted(one + [f"{M}::Entity", f"{M}::Entity.describe", f"{R}::validate"])
    assert run_js(html, f"[...bfs({json.dumps(C)}, 1)].sort()") == one
    assert run_js(html, f"[...bfs({json.dumps(C)}, 2)].sort()") == two
    assert len(two) == 10
    assert run_js(html, f"[...bfs({json.dumps(C)}, 3)].sort()") == two


def test_js_bfs_respects_filters(sample_repo):
    html = fixture_html(sample_repo)
    assert run_js(html, f'(state.ekinds.delete("calls"), [...bfs({json.dumps(C)}, 1)])') == [C]


def test_js_view_counts(sample_repo):
    html = fixture_html(sample_repo)
    c = json.dumps(C)
    assert run_js(html, VIEW) == [[25, 39, 0], counts((5, 4, 4, 10, 2), (18, 8, 1, 12), (35, 4, 0), 39)]
    [sizes, legend] = run_js(html, f'(state.conf.delete("INFERRED"), {VIEW})')
    assert sizes == [25, 35, 0]
    assert legend["edge"]["calls"] == 8 and legend["conf"]["INFERRED"] == 0
    focus = f"state.center = {c}, state.focus = bfs({c}, 1)"
    assert run_js(html, f"({focus}, {VIEW})") == [
        [7, 8, 0], counts((0, 1, 2, 4, 0), (1, 0, 0, 7), (6, 2, 0), 8)]
    [sizes, legend] = run_js(html, f'({focus}, state.kinds.delete("function"), {VIEW})')
    assert sizes == [5, 5, 0]
    assert legend["conf"] == {"EXTRACTED": 3, "INFERRED": 2, "AMBIGUOUS": 0}
    assert run_js(html, f'(state.kinds.delete("method"), state.selected = {c}, '
                        f"applyView().nodes.has({c}))") is True


def test_js_lod_focus(sample_repo, tmp_path, monkeypatch):
    html = fixture_html(sample_repo, monkeypatch, 24)
    after = "[[V.nodes.size, V.raw.size, V.agg.size], [...state.expanded].sort()]"
    assert run_js(html, f"(() => {{ focusOn({json.dumps(C)}); const V = applyView(); "
                        f"return {after}; }})()") == [[7, 8, 0], [M, R, S, U]]
    assert run_js(html, f"(() => {{ focusOn({json.dumps(M)}); const V = applyView(); "
                        f"return {after}; }})()") == [[3, 0, 3], []]
    mod = fixture_html(write(tmp_path / "mod", MOD), monkeypatch, 1)
    assert run_js(mod, f'(() => {{ focusOn("m.py"); const V = applyView(); '
                       f"return {after}; }})()") == [[1, 0, 0], []]


def test_template_focus_strings():
    tpl = outputs.HTML_TEMPLATE
    for s in ("function bfs(", "function refocus(", "function focusOn(", "legendCounts(V)",
              'addEventListener("change"'):
        assert s in tpl, s


# ---------------------------------------------------------------- LOD, expand/collapse, layout stop (08-04-3)

def fn_body(tpl, name):
    """Text from "function <name>(" to the next top-level function (or the end)."""
    start = tpl.index(f"function {name}(")
    end = tpl.find("\nfunction ", start)
    return tpl[start:] if end == -1 else tpl[start:end]


def test_js_lod_counts(sample_repo, monkeypatch):
    html = fixture_html(sample_repo, monkeypatch, 24)
    assert run_js(html, VIEW) == [[7, 0, 8], counts((5, 0, 0, 0, 2), (0, 8, 0, 7), (13, 2, 0), 8)]
    expand = f"state.expanded = new Set([{json.dumps(S)}, {json.dumps(M)}])"
    assert run_js(html, f"({expand}, {VIEW})") == [
        [17, 17, 7], counts((5, 3, 0, 7, 2), (10, 8, 1, 10), (25, 4, 0), 24)]
    [sizes, legend] = run_js(html, f'({expand}, state.ekinds.delete("calls"), {VIEW})')
    assert sizes == [17, 12, 7]
    assert legend["conf"] == {"EXTRACTED": 19, "INFERRED": 0, "AMBIGUOUS": 0}
    style = run_js(html, "bundleStyle(D.file_edges[3])")
    assert (style["dashes"], style["color"]) == (False, "#888")
    assert style["width"] == pytest.approx(2.585, abs=1e-3)
    assert style["title"] == ("app/service.py -> app/models.py: 3 edges "
                              "(calls 2: EXTRACTED 1, INFERRED 1; imports 1: EXTRACTED 1)")
    style = run_js(html, '(state.conf.delete("EXTRACTED"), bundleStyle(D.file_edges[3]))')
    assert (style["dashes"], style["color"]) == ([8, 6], "#f58518")
    assert style["title"] == "app/service.py -> app/models.py: 1 edge (calls 1: INFERRED 1)"


def test_js_toggle_expand(sample_repo, tmp_path, monkeypatch):
    s = json.dumps(S)
    sizes = "[V.nodes.size, V.raw.size, V.agg.size]"
    html = fixture_html(sample_repo, monkeypatch, 24)
    # click, click, doubleClick on a file: the clicks expand nothing, the doubleClick expands it
    clicks = (f"focusOn({s}); focusOn({s}); const e0 = [...state.expanded]; "
              f"const r = toggleExpand({s}); const V = applyView();")
    got = run_js(html, f"(() => {{ {clicks} return [e0, r, [...state.expanded], state.focus, "
                       f"state.center, {sizes}, "
                       f"[...V.nodes].filter(x => x.startsWith({s} + '::')).sort()]; }})()")
    assert got == [[], "expanded", [S], None, None, [11, 5, 8],
                   [f"{S}::UserService", f"{S}::UserService.__init__", C, f"{S}::UserService.log"]]
    # then a second doubleClick collapses it
    got = run_js(html, f"(() => {{ {clicks} const r2 = toggleExpand({s}); const W = applyView(); "
                       f"return [r2, [...state.expanded], [W.nodes.size, W.raw.size, W.agg.size]]; }})()")
    assert got == ["collapsed", [], [7, 0, 8]]
    # a symbol is never toggled
    got = run_js(html, f"(() => {{ focusOn({json.dumps(C)}); const r = toggleExpand({json.dumps(C)}); "
                       "return [r, state.center, [...state.expanded].sort()]; })()")
    assert got == [None, C, [M, R, S, U]]
    mod = fixture_html(write(tmp_path / "mod", MOD), monkeypatch, 1)
    got = run_js(mod, '(() => { focusOn("m.py"); toggleExpand("m.py"); const V = applyView(); '
                      f"return [{sizes}, [...state.expanded], state.focus]; }})()")
    assert got == [[2, 2, 0], ["m.py"], None]
    monkeypatch.setattr(outputs, "MAX_HTML_NODES", 1500)
    assert run_js(outputs.graph_html(build(sample_repo)), f"toggleExpand({s})") is None


def test_template_lod_strings():
    tpl = outputs.HTML_TEMPLATE
    for s in ("stabilizationIterationsDone", "physics: {enabled: false}", 'net.on("doubleClick"',
              "function toggleExpand(", "function bundleStyle(", "D.file_edges", "improvedLayout",
              "hideEdgesOnDrag", "Math.log2", "getPositions("):
        assert s in tpl, s
    assert "storePositions" not in tpl
    body = fn_body(tpl, "refresh")
    assert "edges.update(D.file_edges.map(" in body and "bundleStyle(f)" in body


def test_template_physics_never_back_on():
    tpl = outputs.HTML_TEMPLATE
    bodies = re.findall(r"setOptions\(\{physics: \{([^{}]*)\}\}\)", tpl)
    # Phase 11 (user-approved): applyTheme() also restyles
    # with one setOptions that never touches physics
    theme = "network.setOptions({...look, groups})"
    assert len(bodies) == tpl.count("setOptions(") - tpl.count(theme)
    assert tpl.count(theme) == 1
    assert "physics" not in fn_body(tpl, "applyTheme")
    assert len(bodies) >= 2
    assert sorted(bodies) == ["enabled: false"] * (len(bodies) - 1) + ["enabled: true"]
    assert "RELAYOUT_MS = 3000" in tpl
    rl = fn_body(tpl, "relayout")
    for s in ("setOptions({physics: {enabled: true}})", 'net.once("stabilized", ', "setTimeout(",
              "RELAYOUT_MS"):
        assert s in rl, s
    assert "setOptions({physics: {enabled: true}})" not in tpl.replace(rl, "")


# ---------------------------------------------------------------- search, pick, tabs (08-05-1)

def test_js_rank(sample_repo):
    html = fixture_html(sample_repo)
    assert run_js(html, 'rank("valid")') == [f"{U}::validate", f"{R}::validate"]
    assert run_js(html, 'rank("create")') == [C]
    assert run_js(html, 'rank("NORM")') == [f"{U}::normalize"]
    assert run_js(html, 'rank("ext:o")') == ["ext:os"]
    assert run_js(html, 'rank("  ")') == []


def test_js_fit_ids(sample_repo):
    html = fixture_html(sample_repo)
    c = json.dumps(C)
    got = run_js(html, f'(() => {{ state.kinds.delete("function"); focusOn({c}); const V = applyView(); '
                       "return [Array.isArray(fitIds(V)), fitIds(V).sort()]; })()")
    assert got == [True, [f"{M}::User", f"{M}::User.label", f"{R}::UserRepository.save", C,
                          f"{S}::UserService.log"]]
    got = run_js(html, f'(() => {{ state.kinds.delete("function"); focusOn({c}); '
                       "state.center = state.focus = null; return fitIds(applyView()); })()")
    assert got == [C]


def test_js_pick_fit_flag(sample_repo):
    html = fixture_html(sample_repo)
    c = json.dumps(C)
    got = run_js(html, "(() => { const calls = []; globalThis.history = {replaceState() {}}; "
                       "renderDetails = () => {}; showTab = () => {}; refresh = () => applyView(); "
                       'net = {selectNodes: ids => calls.push(["select", ids]), '
                       'fit: o => calls.push(["fit", o.nodes.length])}; '
                       f"pick({c}, false); const a = calls.splice(0); pick({c}); return [a, calls]; }})()")
    assert got == [[["select", [C]]], [["select", [C]], ["fit", 7]]]


def test_template_search_strings():
    tpl = outputs.HTML_TEMPLATE
    for s in ('id="search"', 'id="results"', "MAX_RESULTS = 30", "DEBOUNCE_MS = 120",
              "createDocumentFragment", 'net.on("click"', "function pick(id, fit = true)",
              "pick(p.nodes[0], false)", "function showTab(", "function fitIds(", 'showTab("details")',
              'showTab("arch")'):
        assert s in tpl, s
    assert "pick(p.nodes[0])" not in tpl
    assert tpl.count("net.fit({nodes: ") == tpl.count("net.fit({nodes: fitIds(V)})") >= 1
    body = fn_body(tpl, "pick")
    assert body.index("renderDetails(id)") < body.index("refresh()") < body.index("net.fit(")
    assert "if (fit) net.fit({nodes: fitIds(V)})" in body
    assert "state.expanded" not in body


# ---------------------------------------------------------------- details panel (08-05-2)

def test_js_relations(sample_repo):
    html = fixture_html(sample_repo)
    assert run_js(html, f"relations({json.dumps(C)})") == {
        "callers": [],
        "callees": [[f"{M}::User", "EXTRACTED"], [f"{M}::User.label", "INFERRED"],
                    [f"{R}::UserRepository.save", "INFERRED"], [f"{S}::UserService.log", "EXTRACTED"],
                    [f"{U}::normalize", "EXTRACTED"], [f"{U}::validate", "EXTRACTED"]],
        "imports": [], "imported by": [], "bases": [], "subclasses": [], "contains": [],
        "contained in": [["app/service.py::UserService", "EXTRACTED"]]}
    assert run_js(html, f'relations("{U}::validate")["callers"]') == [[C, "EXTRACTED"]]
    assert run_js(html, f'relations("{R}")["imports"]') == [
        [M, "EXTRACTED"], [U, "EXTRACTED"], ["ext:json", "EXTRACTED"]]
    assert run_js(html, f'relations("{R}")["imported by"]') == [[S, "EXTRACTED"]]
    assert run_js(html, 'relations("app/models.py::User")["bases"]') == [
        ["app/models.py::Entity", "EXTRACTED"]]


def test_template_panel_strings():
    tpl = outputs.HTML_TEMPLATE
    for s in ("function renderDetails(", "function relations(", "replaceChildren(", '"badge"',
              "File summary - LLM-generated, model "):
        assert s in tpl, s


# ---------------------------------------------------------------- LLM layer, toggle, groups, architecture (08-05-3)

SEM = {"files": {},
       "groups": {"g2": {"name": "B", "summary": "Helpers.", "members": [U], "model": "m", "stale": False},
                  "g10": {"name": "C", "summary": "Data model.", "members": [M], "model": "m",
                          "stale": True},
                  "g1": {"name": "A", "summary": "Service and storage.", "members": [S, R], "model": "m",
                         "stale": False}},
       "architecture": None}


def test_js_groups(sample_repo):
    graph = build(sample_repo)
    html = outputs.graph_html(graph, SEM)
    ids = [C, U, M, "app/__init__.py", "ext:os"]
    assert run_js(html, "[" + ", ".join(f"groupIndex(byId.get({json.dumps(i)}))" for i in ids) + "]") == [
        0, 1, 2, -1, -1]
    assert run_js(html, "groupRows().map(r => [r.gid, r.name, r.files, r.stale, r.summary])") == [
        ["g1", "A", 2, False, "Service and storage."], ["g2", "B", 1, False, "Helpers."],
        ["g10", "C", 1, True, "Data model."]]
    assert run_js(html, "groupHeading()") == "Groups - LLM-generated, model m"
    plain = outputs.graph_html(graph)
    assert run_js(plain, f"[groupIndex(byId.get({json.dumps(C)})), groupRows()]") == [-1, []]


def test_template_llm_strings():
    tpl = outputs.HTML_TEMPLATE
    for s in ("body.llm-off .llm", 'classList.toggle("llm-off"', "function setLLM(", "function groupRows(",
              "Architecture (LLM-generated)", "Groups - LLM-generated", '"stale"', '"#llm-toggle input"',
              'addEventListener("change", ev => setLLM(ev.target.checked))'):
        assert s in tpl, s


# ---------------------------------------------------------------- deep link #node=<id>&hops=N (08-06-1)

C_HASH = "#node=app%2Fservice.py%3A%3AUserService.create&hops=2"


def test_js_hash(sample_repo):
    html = fixture_html(sample_repo)
    assert run_js(html, f"hashFor({json.dumps(C)}, 2)") == C_HASH
    assert run_js(html, f"parseHash({json.dumps(C_HASH)})") == {"node": C, "hops": 2}
    assert run_js(html, 'parseHash("#node=ext%3Aos&hops=9")') == {"node": "ext:os", "hops": 3}
    assert run_js(html, 'parseHash("#node=ext%3Aos")') == {"node": "ext:os", "hops": 1}
    assert run_js(html, 'parseHash("#node=nope&hops=2")') is None
    assert run_js(html, 'parseHash("")') is None
    # Bad hops values fall back to 1; a hand-typed raw id works; junk never throws.
    assert run_js(html, 'parseHash("#node=ext%3Aos&hops=0")') == {"node": "ext:os", "hops": 1}
    assert run_js(html, 'parseHash("#node=ext%3Aos&hops=abc")') == {"node": "ext:os", "hops": 1}
    assert run_js(html, 'parseHash("#node=app/service.py::UserService.create&hops=3")') == {
        "node": C, "hops": 3}
    assert run_js(html, 'parseHash("#node=%E0%A4%A&hops=2")') is None
    assert run_js(html, 'parseHash("#hops=2")') is None
    assert run_js(html, 'parseHash("#node=")') is None
    assert run_js(html, "D.nodes.every(n => { const p = parseHash(hashFor(n.id, 3)); "
                        "return p !== null && p.node === n.id && p.hops === 3; })") is True


def test_js_hash_written_and_applied(sample_repo):
    html = fixture_html(sample_repo)
    stubs = ("const urls = []; globalThis.history = {replaceState: (s, t, u) => urls.push([s, t, u])}; "
             'globalThis.location = {href: "file:///r/graph.html?x=1#node=x", hash: ""}; '
             "renderDetails = () => {}; showTab = () => {}; refresh = () => applyView(); "
             "net = {selectNodes() {}, fit() {}}; ")
    # pick writes #node=<id>&hops=<state.hops>; Clear removes the hash (rest of the URL kept).
    got = run_js(html, f"(() => {{ {stubs}state.hops = 2; pick({json.dumps(C)}); clearFocus(); "
                       "return [urls, state.center, state.selected]; })()")
    assert got == [[[None, "", C_HASH], [None, "", "file:///r/graph.html?x=1"]], None, C]
    # applyHash: clamped hops (button marked), then pick(id) with fit; unknown id: nothing at all.
    buttons = ("const marks = []; document.querySelectorAll = () => [1, 2, 3].map(n => ({dataset: "
               "{hops: String(n)}, classList: {toggle: (c, on) => marks.push([n, c, on])}})); "
               "const picks = []; pick = (...a) => picks.push(a); ")
    got = run_js(html, f"(() => {{ {stubs}{buttons}location.hash = \"#node=ext%3Aos&hops=9\"; applyHash(); "
                       "return [state.hops, picks, marks]; })()")
    assert got == [3, [["ext:os"]], [[1, "active", False], [2, "active", False], [3, "active", True]]]
    got = run_js(html, f"(() => {{ {stubs}{buttons}location.hash = \"#node=nope&hops=3\"; applyHash(); "
                       "return [state.hops, picks, marks, urls]; })()")
    assert got == [1, [], [], []]


def test_template_hash_strings():
    tpl = outputs.HTML_TEMPLATE
    for s in ('addEventListener("hashchange"', "history.replaceState", "function parseHash(",
              "function hashFor(", "new URLSearchParams(", "encodeURIComponent("):
        assert s in tpl, s
    assert "setHash(id)" in fn_body(tpl, "pick")
    assert "setHash(null)" in fn_body(tpl, "clearFocus")
    body = fn_body(tpl, "start")
    assert 'window.addEventListener("hashchange", applyHash)' in body
    # The hash is applied once, after the first stabilization (layout settled, then pick + fit).
    assert (body.index('net.once("stabilizationIterationsDone"') < body.index("applyHash();")
            < body.index('net.on("doubleClick"'))
    assert "setHash(state.center)" in body
