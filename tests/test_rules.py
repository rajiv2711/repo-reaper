"""`reaper rules`: the Markdown block an agent's CLAUDE.md / AGENTS.md gets, so it trusts the graph.

The trust rule is the one the token study used (-22% input tokens, -36% turns, same accuracy).
Expected text is written by hand.
"""

from reaper.cli import main

TRUST = [
    "### How far to trust the graph",
    "- EXTRACTED results are proven by the code. Use them as they are; do not re-check them with "
    "grep.",
    '- A `callers` answer that ends with "not linked: none" is complete for the parsed files: no '
    'other call site uses that name. If it lists "not linked" sites, check only those.',
    '- Use grep only for what the graph does not cover: the "not linked" sites, string literals, '
    "comments, config files, a function passed as a value or renamed, and files that are not "
    "parsed (anything but Python, JavaScript, TypeScript).",
    "- When a question needs the code's logic, read the source at the lines the graph gives.",
    '- With `--depth`, "not linked" covers only the queried name (query a deeper node directly to '
    "see its list).",
]
MODES = [
    '- `callers`: who calls a function, method or class, with the call-site lines and the '
    '"not linked" sites.',
    "- `callees`: what a function or method calls, with the call-site lines.",
    "- `subclasses`: the classes that inherit from a class.",
    "- `deps`: what a file imports and which files import it, with the import lines.",
    "",
    "NAME: a node id (`app/service.py::UserService.create`), a qualified name "
    "(`UserService.create`), a module name (`app.service`) or a plain name (`create`). "
    "`--depth N` follows N hops; `--budget TOKENS` caps the text (default 2000); `--json` prints "
    "everything.",
]


def block(repo, out, out_opt):
    return "\n".join([
        "## Code graph (repo-reaper)",
        "",
        f"`{repo}` is mapped into a graph of its files, classes, functions and methods and the "
        f"imports, calls and inheritance between them; the outputs are in `{out}` (graph.json, "
        "TREE.txt, SUMMARY.md, graph.html).",
        "",
        *TRUST,
        f"- The graph reflects the code at the last `reaper run`, so run it again after editing "
        f"files: `reaper run {repo}{out_opt}`.",
        "",
        "### How to query",
        f"`reaper query {repo}{out_opt} MODE NAME [--depth N] [--budget TOKENS] [--json]`",
        *MODES,
    ]) + "\n"


def test_rules_with_the_default_out_dir(sample_repo, capsys):
    assert main(["run", str(sample_repo)]) == 0
    capsys.readouterr()
    assert main(["rules", str(sample_repo)]) == 0
    out, err = capsys.readouterr()
    repo = sample_repo.resolve()
    assert out == block(repo, repo / ".reaper", "")      # no --out: it is the default
    assert err == ""
    assert len(out.splitlines()) <= 25


def test_rules_with_out_and_no_graph_yet(sample_repo, tmp_path, capsys):
    dest = tmp_path / "elsewhere"
    assert main(["rules", str(sample_repo), "--out", str(dest)]) == 0   # still exit 0
    out, err = capsys.readouterr()
    repo, abs_dest = sample_repo.resolve(), dest.resolve()
    assert out == block(repo, abs_dest, f" --out {abs_dest}")
    assert err == (f"note: no {dest / 'graph.json'} yet; "
                   f"run `reaper run {sample_repo} --out {dest}` first\n")
    assert not dest.exists() and not (sample_repo / ".reaper").exists()   # writes nothing


def test_rules_paths_are_absolute(sample_repo, capsys, monkeypatch):
    monkeypatch.chdir(sample_repo.parent)
    assert main(["rules", sample_repo.name, "--out", "out"]) == 0
    out = capsys.readouterr().out
    assert f"`reaper query {sample_repo.resolve()} --out {sample_repo.parent.resolve() / 'out'} " \
           "MODE NAME" in out
