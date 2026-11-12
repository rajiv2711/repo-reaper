"""What the labels in repo-reaper's outputs mean, written into every output file.

One source for graph.json ("legend"), SUMMARY.md, TREE.txt, graph.html (a comment in <head>),
semantic.json, ARCHITECTURE.md and the key under `reaper query` answers, so an agent or a person
reading any one file learns how far to trust it. Keep it in step with resolve.py's rules.
"""

from __future__ import annotations

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
         "import line or the class line; contains edges have none")
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


def query_key(mode: str) -> list[str]:
    """Two short lines under a query answer."""
    key = ["key: EXTRACTED = proven by the code; INFERRED = one best guess; "
           "AMBIGUOUS = one of 2-5 candidates (more in SUMMARY.md, or graph.json \"legend\")"]
    if mode == "callers":
        key.append("complete: every call written NAME(...) or x.NAME(...) in the parsed files is "
                   "listed, linked to another NAME, or under 'not linked'; not covered: NAME passed "
                   "as a value or renamed, getattr/importlib/config strings")
    return key
