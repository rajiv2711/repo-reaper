"""What the labels in repo-reaper's outputs mean, written into every output file.

One source for graph.json ("legend"), SUMMARY.md, TREE.txt, graph.html (a comment in <head>),
semantic.json, ARCHITECTURE.md, the key under `reaper query` answers and the block `reaper rules`
prints for an agent's CLAUDE.md / AGENTS.md, so an agent or a person reading any one file learns
how far to trust it. Keep it in step with resolve.py's rules.
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path

CONFIDENCE = {
    "EXTRACTED": "proven by the code: an import, a definition in scope, self.method in the class, "
                 "or a module in the importing file's own folder (a script folder)",
    "INFERRED": "one best guess: a base-class method reached through self or super(), a hook "
                "that one subclass defines, the only method of that name among the classes the "
                "calling file can see (the object's type is not known), or an import that works "
                "only when its package folder is on sys.path",
    "AMBIGUOUS": "2 to 5 candidates are equally likely: one edge to each",
}
EDGE_KINDS = {
    "contains": "a file or class holds a class, function or method",
    "imports": "a file imports a repo file, or an outside package (ext:<name>)",
    "inherits": "a class inherits from a repo class",
    "calls": "a function, method or module body calls a repo function, method or class",
}
NODE_IDS = ("file: its relative path (app/service.py); symbol: path::Qualified.name "
            "(app/service.py::UserService.create); outside package: ext:<name>")
LINES = ("an edge's lines are the lines in its source file that make it: the call sites, the "
         "import line or the class line; contains edges have none. A pair whose lines differ in "
         "confidence has one edge per confidence, each with only its own lines")
NO_GUESS = ("a call the graph cannot resolve gets no edge, never a guess by name alone; "
            "`reaper query <repo> callers NAME` lists such call sites under 'not linked'")
COMPLETENESS = ("for `callers NAME`, every call site written NAME(...) or x.NAME(...) in the parsed "
                "files is accounted for: an edge to NAME, an edge to another definition with that "
                "name, or a 'not linked' line. Not covered: NAME passed as a value (callbacks=[NAME], "
                "partial(NAME)) or renamed (f = NAME), getattr / importlib / registries / config "
                "strings (Hydra _target_), and files that are not parsed (languages other than "
                "Python, JavaScript and TypeScript, notebooks, files with syntax errors). Names in "
                "comments and docstrings are never calls")
GREP_FOR = "string literals, comments, config files, renames, and the 'not linked' call sites"
SEMANTIC = {
    "summary": "LLM-written, from the file's outline and source (whole up to 300 lines, else the "
               "first 150); not verified against the code",
    "role": "LLM-chosen label for the file's role",
    "input_sha": "hash of what the LLM was shown; an entry whose input changed since is stale",
    "model": "the Ollama model that answered",
    "evidence": "graph.json node ids the LLM cited; ids not in graph.json are dropped",
}


def as_dict() -> dict:
    """The legend as graph.json stores it."""
    return {"confidence": CONFIDENCE, "edge_kinds": EDGE_KINDS, "node_ids": NODE_IDS,
            "lines": LINES, "no_guess": NO_GUESS, "completeness": COMPLETENESS,
            "use_grep_for": GREP_FOR}


def markdown() -> list[str]:
    """The legend as a SUMMARY.md section."""
    return ["## How to read this graph", "",
            *[f"- **{k}**: {v}." for k, v in CONFIDENCE.items()],
            f"- **No guessing**: {NO_GUESS}.",
            f"- **Complete?** {COMPLETENESS}.",
            f"- **Edge kinds**: " + "; ".join(f"`{k}` {v}" for k, v in EDGE_KINDS.items()) + ".",
            f"- **Node ids**: {NODE_IDS}.",
            f"- **lines**: {LINES}.",
            f"- **Use grep for** {GREP_FOR}.", ""]


def plain(prefix: str = "") -> list[str]:
    """The legend as plain text lines (TREE.txt header, graph.html comment)."""
    return [f"{prefix}{k}: {v}." for k, v in CONFIDENCE.items()] + [
        f"{prefix}No guessing: {NO_GUESS}.",
        f"{prefix}Complete? {COMPLETENESS}.",
        f"{prefix}Node ids: {NODE_IDS}.",
        f"{prefix}Use grep for {GREP_FOR}."]


# The trust rule of the token study: with it in their instructions, agents stopped re-checking
# graph answers with grep (-22% input tokens, -36% turns, same accuracy on physicsnemo).
TRUST_RULES = [
    "EXTRACTED results are proven by the code. Use them as they are; do not re-check them with "
    "grep.",
    'A `callers` answer that ends with "not linked: none" is complete for the parsed files: no '
    'other call site uses that name. If it lists "not linked" sites, check only those.',
    'Use grep only for what the graph does not cover: the "not linked" sites, string literals, '
    "comments, config files, a function passed as a value or renamed, and files that are not "
    "parsed (anything but Python, JavaScript, TypeScript).",
    "When a question needs the code's logic, read the source at the lines the graph gives.",
    'With `--depth`, "not linked" covers only the queried name (query a deeper node directly to '
    "see its list).",
]
QUERY_MODES = {
    "callers": 'who calls a function, method or class, with the call-site lines and the '
               '"not linked" sites',
    "callees": "what a function or method calls, with the call-site lines",
    "subclasses": "the classes that inherit from a class",
    "deps": "what a file imports and which files import it, with the import lines",
}
QUERY_NAME = ("NAME: a node id (`app/service.py::UserService.create`), a qualified name "
              "(`UserService.create`), a module name (`app.service`) or a plain name (`create`). "
              "`--depth N` follows N hops; `--budget TOKENS` caps the text (default 2000); "
              "`--json` prints everything.")


def agent_rules(repo: str | os.PathLike, out_dir: str | os.PathLike | None = None) -> str:
    """The Markdown block `reaper rules` prints for an agent's CLAUDE.md / AGENTS.md: what the
    graph is and where, how far to trust it, how to query it. Paths are absolute; `--out` is in
    the commands only when the outputs are not in the default <repo>/.reaper."""
    from reaper.graph import out_dir as outputs_of  # here: graph.py imports this module

    root = Path(repo).resolve()
    where = outputs_of(root, out_dir).resolve()
    opt = f" --out {shlex.quote(str(where))}" if where != outputs_of(root).resolve() else ""
    repo_arg = shlex.quote(str(root))
    return "\n".join([
        "## Code graph (repo-reaper)",
        "",
        f"`{root}` is mapped into a graph of its files, classes, functions and methods and the "
        f"imports, calls and inheritance between them; the outputs are in `{where}` (graph.json, "
        "TREE.txt, SUMMARY.md, graph.html).",
        "",
        "### How far to trust the graph",
        *[f"- {rule}" for rule in TRUST_RULES],
        f"- The graph reflects the code at the last `reaper run`, so run it again after editing "
        f"files: `reaper run {repo_arg}{opt}`.",
        "",
        "### How to query",
        f"`reaper query {repo_arg}{opt} MODE NAME [--depth N] [--budget TOKENS] [--json]`",
        *[f"- `{mode}`: {text}." for mode, text in QUERY_MODES.items()],
        "",
        QUERY_NAME,
    ]) + "\n"


def query_key(mode: str) -> list[str]:
    """Two short lines under a query answer."""
    key = ["key: EXTRACTED = proven by the code; INFERRED = one best guess; "
           "AMBIGUOUS = one of 2-5 candidates (more in SUMMARY.md, or graph.json \"legend\")"]
    if mode == "callers":
        key.append("complete: every call written NAME(...) or x.NAME(...) in the parsed files is "
                   "listed, linked to another NAME, or under 'not linked'; not covered: NAME passed "
                   "as a value or renamed, getattr/importlib/config strings")
    return key
