"""Phase 11: dark mode of graph.html (OS setting or the Auto / Light / Dark select, kept in localStorage).

Expected values are written by hand from phases-archive:docs/phases/11-dark-mode/11-PLAN.md (not printed from the
code). `test_template_*` never skip; `test_js_*` run the page script in node (see
test_html_template.py), which has no matchMedia and no localStorage, so the page is light there
unless a test stubs them.
"""

import json
import re

from test_html_template import SEM, fixture_html, run_js
from test_html_tree import run_modes

from reaper import outputs
from reaper.graph import build

# CSS tokens: light = the literals of the Phase 8/9 CSS (vis 9.1.9's tooltip defaults for --tip*)
LIGHT_TOKENS = {
    "--bg": "#fff", "--fg": "#222", "--line": "#ddd", "--muted": "#555", "--faint": "#777",
    "--error": "#b00020", "--link": "#1f5a96", "--hover": "#eef3f8", "--badge": "#e8f0e8",
    "--badge-fg": "#333", "--badge-inf": "#fdebd3", "--badge-amb": "#f3e0e0", "--stale": "#f8d7da",
    "--stale-fg": "#b00020", "--llm-bg": "#faf7fb", "--chip": "#f6f6f6", "--chip-line": "#ccc",
    "--branch": "#b0b0b0", "--tip": "#f5f4ed", "--tip-fg": "#000000", "--tip-line": "#808074"}
DARK_TOKENS = {
    "--bg": "#1a1a19", "--fg": "#e8e6e0", "--line": "#3a3a37", "--muted": "#c3c2b7", "--faint": "#898781",
    "--error": "#ff6b7f", "--link": "#7ab4f0", "--hover": "#26323e", "--badge": "#2b3a2b",
    "--badge-fg": "#e8e6e0", "--badge-inf": "#3d2f1c", "--badge-amb": "#3d2626", "--stale": "#3a1d22",
    "--stale-fg": "#ff8a95", "--llm-bg": "#2a2230", "--chip": "#262624", "--chip-line": "#4a4945",
    "--branch": "#5f5e5a", "--tip": "#2c2c2a", "--tip-fg": "#f0efec", "--tip-line": "#6b6a65"}
LIGHT_GROUPS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2",
                "#17becf", "#bcbd22", "#393b79", "#637939", "#8c6d31", "#843c39", "#7b4173"]
# the 4 that fail 3:1 on #1a1a19 swapped for their lighter tab20 siblings (index 5, 9, 12, 13)
DARK_GROUPS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#c49c94", "#e377c2",
               "#17becf", "#bcbd22", "#6b6ecf", "#637939", "#8c6d31", "#d6616b", "#ce6dbd"]
# external #bab0ac -> #79706e in both modes (user decision: method #72b7b2 vs #bab0ac had CVD dE 1.0)
KINDS = {"file": "#4c78a8", "class": "#b279a2", "function": "#54a24b", "method": "#72b7b2",
         "external": "#79706e"}
LIGHT_FONT = {"size": 12, "color": "#343434", "strokeWidth": 0, "strokeColor": "#ffffff"}  # vis defaults
DARK_FONT = {"size": 12, "color": "#f0efec", "strokeWidth": 3, "strokeColor": "#1a1a19"}
LIGHT_DIR = {"shape": "box", "color": {"background": "#eeeeee", "border": "#9e9e9e"},
             "font": {"color": "#222", "strokeWidth": 0}}
DARK_DIR = {"shape": "box", "color": {"background": "#2c2c2a", "border": "#6b6a65"},
            "font": {"color": "#f0efec", "strokeWidth": 0}}
NOGROUP = "app/__init__.py"   # in no SEM group
CONTAINS = "[...new Set(D.edges.filter(e => e.kind === 'contains').map(e => e.color))]"


def env(html, dark_os=None, saved=None):
    """The page with stubbed matchMedia (OS dark or not), localStorage (saved choice) and <html>."""
    pre = ("document.documentElement = {attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, "
           "removeAttribute(k) { delete this.attrs[k]; }};\n")
    if dark_os is not None:
        pre += (f"globalThis.matchMedia = q => ({{matches: {json.dumps(dark_os)} && "
                "q === '(prefers-color-scheme: dark)', addEventListener() {}});\n")
    if saved is not None:
        pre += (f"globalThis.localStorage = {{saved: {{'reaper-theme': {json.dumps(saved)}}}, "
                "getItem(k) { return k in this.saved ? this.saved[k] : null; }, "
                "setItem(k, v) { this.saved[k] = v; }};\n")
    i = html.rindex("<script>") + len("<script>")
    return html[:i] + "\n" + pre + html[i:]


def css_block(css, selector):
    m = re.search(re.escape(selector) + r"\s*\{([^{}]*)\}", css)
    assert m, selector
    return dict(re.findall(r"(--[\w-]+):\s*([^;]+);", m.group(1)))


# ---------------------------------------------------------------- template

def test_template_theme_css():
    tpl = outputs.HTML_TEMPLATE
    css = tpl[tpl.index("<style>"):tpl.index("</style>")]
    assert css_block(css, ":root") == LIGHT_TOKENS
    media = css[css.index("@media (prefers-color-scheme: dark)"):]
    assert css_block(media, ':root:not([data-theme="light"])') == DARK_TOKENS
    assert css_block(css, ':root[data-theme="dark"]') == DARK_TOKENS
    assert css.count("color-scheme: dark;") == 2
    # vis injects its own tooltip CSS later; this rule wins by specificity and reads the tokens
    assert "html div.vis-tooltip { background-color: var(--tip); color: var(--tip-fg); " \
           "border-color: var(--tip-line); }" in css
    # every hard-coded colour of the old CSS now reads a token (kind / edge colours are mode-free)
    rest = re.sub(r":root[^{]*\{[^{}]*\}", "", css)
    assert sorted(set(re.findall(r"#[0-9a-fA-F]{3,6}\b", rest))) == sorted(
        {"#fff", "#4c78a8", "#b279a2", "#54a24b", "#72b7b2", "#79706e", "#f58518"})


def test_template_theme_select_and_legend():
    tpl = outputs.HTML_TEMPLATE
    assert ('<select id="theme"><option value="auto">Auto</option><option value="light">Light</option>'
            '<option value="dark">Dark</option></select>') in tpl
    assert 'style="' not in tpl  # legend colours are CSS classes now
    for k in KINDS:
        assert f'class="sw{" box" if k in ("file", "external") else ""} kind-{k}"' in tpl, k
    for k in ("contains", "imports", "inherits", "calls"):
        assert f'class="k e-{k}"' in tpl, k
    assert tpl.count('class="k conf') == 3


def test_js_css_kind_colours_match(sample_repo):
    tpl = outputs.HTML_TEMPLATE
    css = dict(re.findall(r"\.kind-(\w+) \{ background: (#[0-9a-f]{6}); \}", tpl))
    assert css == KINDS
    assert run_js(fixture_html(sample_repo), "KIND_COLOR") == KINDS


# ---------------------------------------------------------------- which theme

def test_js_light_by_default(sample_repo):
    # node: no matchMedia, no localStorage -> light, with the Phase 8/9 values
    got = run_js(env(fixture_html(sample_repo)),
                 f"[DARK, themePref, INK.branch, INK.noGroup, INK.groups, nodeFont(), nodeChosen(), "
                 f"treeGroups().dir, {CONTAINS}, [...new Set(BRANCH_EDGES.map(e => e.color))], "
                 f"document.documentElement.attrs]")
    assert got == [False, "auto", "#b0b0b0", "#c7c7c7", LIGHT_GROUPS, LIGHT_FONT, {"node": True, "label": True}, LIGHT_DIR,
                   ["#b0b0b0"], ["#b0b0b0"], {}]
    assert run_js(fixture_html(sample_repo), "[DARK, themePref]") == [False, "auto"]  # no stubs at all


def test_js_dark_when_os_is_dark(sample_repo):
    html = env(outputs.graph_html(build(sample_repo), SEM), dark_os=True)
    got = run_js(html, f"[DARK, themePref, INK.branch, INK.noGroup, INK.groups, nodeFont(), treeGroups().dir, "
                       f"{CONTAINS}, [...new Set(BRANCH_EDGES.map(e => e.color))], document.documentElement.attrs, "
                       f"nodeColor(byId.get({json.dumps(NOGROUP)}), true), nodeColor(byId.get({json.dumps(NOGROUP)}), false)]")
    assert got == [True, "auto", "#5f5e5a", "#6b6a65", DARK_GROUPS, DARK_FONT, DARK_DIR,
                   ["#5f5e5a"], ["#5f5e5a"], {}, "#6b6a65", "#4c78a8"]
    # selection ring: vis darkens a selected node's border, which vanishes on #1a1a19
    got = run_js(html, "(() => { const c = nodeChosen(), s = {borderColor: 'x', borderWidth: 1}, "
                       "h = {borderColor: 'x', borderWidth: 1}; c.node(s, 'id', true, false); "
                       "c.node(h, 'id', false, true); return [c.label, s, h]; })()")
    assert got == [True, {"borderColor": "#ffffff", "borderWidth": 3}, {"borderColor": "#c3c2b7", "borderWidth": 2}]


def test_js_saved_choice_beats_os(sample_repo):
    html = fixture_html(sample_repo)
    q = "[DARK, themePref, INK.label, document.documentElement.attrs]"
    assert run_js(env(html, dark_os=True, saved="light"), q) == [False, "light", "#343434", {"data-theme": "light"}]
    assert run_js(env(html, dark_os=False, saved="dark"), q) == [True, "dark", "#f0efec", {"data-theme": "dark"}]
    assert run_js(env(html, dark_os=True, saved="auto"), q) == [True, "auto", "#f0efec", {}]
    assert run_js(env(html, dark_os=True, saved="bogus"), q) == [True, "auto", "#f0efec", {}]


# ---------------------------------------------------------------- switching (both networks)

SWITCH = """
graphLaidOut(); setMode("tree");
const posG = graphSnapPos(), posT = treeSnapPos();
const look = n => { const o = n.calls.filter(c => c[0] === "setOptions" && c[1].groups).pop()[1];
  return [o.nodes.font, typeof o.nodes.chosen.node, o.groups.dir || null]; };
const snap = () => [look(nets[0]), look(nets[1]),
  [...new Set(D.edges.filter(e => e.kind === "contains").map(e => edges.m.get(e.id).color))],
  [...new Set([...tedges.m.values()].filter(e => e.kind === "contains").map(e => e.color))],
  nodes.m.get(NOGROUP).color, tnodes.m.get(NOGROUP).color, groupSwatches.map(([s]) => s.style.background),
  {...document.documentElement.attrs}, localStorage.saved["reaper-theme"],
  graphSnapPos() === posG && treeSnapPos() === posT];
setTheme("dark"); const dark = snap();
setTheme("light"); const light = snap();
return [dark, light];
"""
POS = ("const graphSnapPos = () => JSON.stringify([...nodes.m.values()].map(n => [n.id, n.x, n.y])); "
       "const treeSnapPos = () => JSON.stringify([...tnodes.m.values()].map(n => [n.id, n.x, n.y])); ")


def test_js_theme_switch_restyles_both_networks(sample_repo):
    html = env(outputs.graph_html(build(sample_repo), SEM), dark_os=False, saved="auto")
    dark, light = run_modes(html, f"const NOGROUP = {json.dumps(NOGROUP)}; " + POS + SWITCH)
    # group legend rows: g1, g2, g10 (indexes 0-2 keep their colour), then "no group"
    assert dark == [[DARK_FONT, "function", None], [DARK_FONT, "function", DARK_DIR], ["#5f5e5a"], ["#5f5e5a"],
                    "#6b6a65", "#6b6a65", ["#1f77b4", "#ff7f0e", "#2ca02c", "#6b6a65"],
                    {"data-theme": "dark"}, "dark", True]
    assert light == [[LIGHT_FONT, "boolean", None], [LIGHT_FONT, "boolean", LIGHT_DIR], ["#b0b0b0"], ["#b0b0b0"],
                     "#c7c7c7", "#c7c7c7", ["#1f77b4", "#ff7f0e", "#2ca02c", "#c7c7c7"],
                     {"data-theme": "light"}, "light", True]


def test_js_theme_untouched_at_start(sample_repo):
    # start() and the first Tree build make no extra setOptions or DataSet writes for the theme
    html = env(outputs.graph_html(build(sample_repo), SEM), dark_os=True)
    got = run_modes(html, 'graphLaidOut(); setMode("tree"); '
                          'return [nets.map(n => n.calls.filter(c => c[0] === "setOptions").map(c => Object.keys(c[1]))), '
                          'nets.map(n => n.opts.nodes.font), [...new Set(log)]];')
    assert got == [[[["physics"], ["physics"]], []], [DARK_FONT, DARK_FONT], ["network net", "pos+colour", "network tree"]]
