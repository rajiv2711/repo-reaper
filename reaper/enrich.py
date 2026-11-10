"""Semantic passes over graph.json with a local LLM; results go to <repo>/.reaper/semantic.json.

semantic.json = {files: {path: {summary, role, input_sha, model}}, groups: {...}, architecture: {...}}

Files pass: one call per code file (files with a file node). Input = the file's TREE outline plus
its source (whole when <= 300 lines, else the first 150). input_sha = sha256(model, prompt
version, input), so a file is asked again only when its input, the model or the prompt changes.
Work goes most-connected file first and semantic.json is saved after every answer, so an
interrupted run (or --limit) keeps what it finished and the next run picks up the rest.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Callable

from reaper import llm, outputs
from reaper.graph import graph_path

DEFAULT_MODELS = {"files": "devstral-small-2:24b", "groups": "qwen3-coder:30b",
                  "architecture": "qwen3-coder:30b"}
SECTIONS = ("files", "groups", "architecture")

MAX_WHOLE_LINES = 300  # longer files are cut to their first HEAD_LINES lines
HEAD_LINES = 150

# Bump FILES_PROMPT_VERSION whenever FILES_SYSTEM, ROLES or the input layout change: it is part
# of every cache key, so the bump makes the next run ask about every file again.
FILES_PROMPT_VERSION = "files-1"
ROLES = ("entrypoint", "api", "service", "model", "data-access", "utility", "config", "test",
         "script", "package", "other")
FILES_SYSTEM = """\
You describe one source file of a software repository for a code map.
You get the file's path, an outline of its classes and functions with line numbers, and its \
source (possibly cut off).
Reply with a JSON object:
- "summary": at most 2 sentences on what the file does and its key classes or functions. \
Start with a verb, e.g. "Parses ...". Be concrete.
- "role": the file's main role, one of: entrypoint (CLI, main, app startup), api (routes, \
handlers, public interface), service (business logic, orchestration), model (data structures, \
domain types, schemas), data-access (storage, databases, file formats, network clients), \
utility (generic helpers), config (settings, constants), test (tests, fixtures), script \
(build, deploy, one-off tooling), package (package init, re-exports), other.
Describe only what the given text shows; do not guess about other files."""
FILES_SCHEMA = {"type": "object",
                "properties": {"summary": {"type": "string"},
                               "role": {"type": "string", "enum": list(ROLES)}},
                "required": ["summary", "role"]}


# ---------------------------------------------------------------- semantic.json

def semantic_path(root: str | os.PathLike) -> Path:
    return graph_path(root).parent / "semantic.json"


def load_semantic(root: str | os.PathLike) -> dict:
    path = semantic_path(root)
    sem = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for section in SECTIONS:
        sem.setdefault(section, {})
    return sem


def save_semantic(root: str | os.PathLike, sem: dict) -> Path:
    """Write semantic.json atomically (temp file + rename); return its path."""
    path = semantic_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(sem, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


# ---------------------------------------------------------------- files pass

def ranked_files(graph: dict) -> list[str]:
    """Code files (file nodes), most-connected first: sum of the non-contains degree
    (outputs.degrees) of every node in the file; ties by path."""
    file_of = {n["id"]: n["file"] for n in graph["nodes"]}
    score = Counter()
    for node_id, (d_in, d_out) in outputs.degrees(graph).items():
        score[file_of[node_id]] += d_in + d_out
    files = [n["id"] for n in graph["nodes"] if n["kind"] == "file"]
    return sorted(files, key=lambda f: (-score[f], f))


def file_input(graph: dict, root: str | os.PathLike, path: str) -> str:
    """The user message for one file: path, TREE outline, source (cut when long)."""
    text = (Path(root) / path).read_bytes().decode("utf-8", errors="replace")
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    if len(lines) > MAX_WHOLE_LINES:
        head = f"Source (first {HEAD_LINES} of {len(lines)} lines):"
        text = "\n".join(lines[:HEAD_LINES]) + "\n"
    else:
        head = "Source:"
    return f"File: {path}\n\nOutline:\n{outputs.file_outline(graph, path)}\n\n{head}\n{text}"


def cache_key(model: str, text: str, version: str = FILES_PROMPT_VERSION) -> str:
    return hashlib.sha256(f"{model}\n{version}\n{text}".encode("utf-8")).hexdigest()


def two_sentences(text: str) -> str:
    """At most the first two sentences, whitespace collapsed."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", " ".join(text.split()))
    return " ".join(parts[:2])


def run_files(root: str | os.PathLike, graph: dict, model: str = DEFAULT_MODELS["files"],
              limit: int | None = None, dry_run: bool = False,
              progress: Callable[[str], None] | None = None) -> dict:
    """Summarize every code file whose cached answer is stale; return a report.

    report = {model, todo (paths to ask, after --limit), called, cached (count), failed
    {path: reason}, pruned (entries of files gone from the graph), tokens and max_tokens
    (approx input tokens of the todo calls, chars / 4)}. dry_run computes the report and
    writes nothing. An invalid reply skips that file; llm.LLMError otherwise (Ollama down,
    unknown model) stops the run, keeping the answers saved so far.
    """
    say = progress or (lambda _msg: None)
    sem = load_semantic(root)
    cache = sem["files"]
    ranked = ranked_files(graph)
    todo, cached, failed = [], 0, {}
    for path in ranked:
        try:
            text = file_input(graph, root, path)
        except OSError as e:
            failed[path] = f"cannot read: {e}"
            continue
        key = cache_key(model, text)
        if cache.get(path, {}).get("input_sha") == key:
            cached += 1
        else:
            todo.append((path, text, key))
    if limit is not None:
        todo = todo[:limit]
    chars = [len(FILES_SYSTEM) + len(text) for _, text, _ in todo]
    report = {"model": model, "todo": [p for p, _, _ in todo], "called": [], "cached": cached,
              "failed": failed, "pruned": sorted(set(cache) - set(ranked)),
              "tokens": sum(chars) // 4, "max_tokens": max(chars, default=0) // 4}
    if dry_run:
        return report

    for path in report["pruned"]:
        del cache[path]
    if report["pruned"]:
        save_semantic(root, sem)
    for i, (path, text, key) in enumerate(todo, 1):
        messages = [{"role": "system", "content": FILES_SYSTEM}, {"role": "user", "content": text}]
        try:
            reply = llm.chat(model, messages, FILES_SCHEMA)
        except llm.InvalidResponse as e:
            failed[path] = str(e)
            say(f"[{i}/{len(todo)}] {path}: FAILED {e}")
            continue
        cache[path] = {"summary": two_sentences(reply["summary"]), "role": reply["role"],
                       "input_sha": key, "model": model}
        save_semantic(root, sem)
        report["called"].append(path)
        say(f"[{i}/{len(todo)}] {path}: {reply['role']}")
    return report
