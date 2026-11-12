"""Build, load and save graph.json (in <repo>/.reaper/, or the --out dir).

graph = {meta: {version, generated_at}, files, nodes, refs, edges}
`files` lists every discovered file (its sha256 drives incremental updates);
only files whose language has an extractor (Python, JavaScript, TypeScript) produce nodes and refs.

build() extracts every file; update() reuses the nodes and refs of files whose sha256
is unchanged since the saved graph.json and re-extracts the rest. Both then rebuild all
edges with resolve(), so an update gives the same graph as a full build.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from reaper import extract_js, extract_py
from reaper.discover import discover
from reaper.resolve import resolve

VERSION = 1
OUT_DIR = ".reaper"


def out_dir(root: str | os.PathLike, out: str | os.PathLike | None = None) -> Path:
    """Where the outputs go: `out` when given, else <root>/.reaper."""
    return Path(out) if out is not None else Path(root) / OUT_DIR


def graph_path(root: str | os.PathLike, out: str | os.PathLike | None = None) -> Path:
    return out_dir(root, out) / "graph.json"


def new_graph(files: dict, nodes: list, refs: list, edges: list) -> dict:
    meta = {"version": VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    return {"meta": meta, "files": files, "nodes": nodes, "refs": refs, "edges": edges}


def extract_file(root: Path, rel: str, lang: str) -> tuple[list[dict], list[dict]]:
    """(nodes, refs) for one file; ([], []) when no extractor handles its language."""
    if lang == "python":
        return extract_py.extract(rel, (root / rel).read_bytes(), extract_py.module_name(rel))
    if lang in ("javascript", "typescript"):
        return extract_js.extract(rel, (root / rel).read_bytes(), extract_js.module_name(rel))
    return [], []


def build(root: str | os.PathLike, out: str | os.PathLike | None = None) -> dict:
    """Full structural build: discover every file, extract each one, resolve edges."""
    return _assemble(root, None, out)[0]


def update(root: str | os.PathLike, out: str | os.PathLike | None = None) -> tuple[dict, dict]:
    """Incremental build against the saved graph.json: (graph, changes).

    changes = {added, changed, deleted, unchanged}, each a sorted list of paths. Unchanged
    files keep their nodes and refs; added/changed files are re-extracted; deleted files drop
    out; then resolve() rebuilds every edge. No graph.json, or one with another format
    version, means a full build (every file "added"). The caller saves the graph.
    """
    try:
        previous = load(root, out)
    except FileNotFoundError:
        previous = None
    if previous is not None and previous.get("meta", {}).get("version") != VERSION:
        previous = None
    return _assemble(root, previous, out)


def _inside(root: Path, out: str | os.PathLike | None) -> tuple[str, ...]:
    """The output dir relative to root when it lies inside the repo, so it is never mapped."""
    if out is None:
        return ()
    try:
        rel = Path(out).resolve().relative_to(root).as_posix()
    except ValueError:
        return ()
    return (rel,) if rel != "." else ()


def _assemble(root: str | os.PathLike, previous: dict | None,
              out: str | os.PathLike | None = None) -> tuple[dict, dict]:
    root = Path(root).resolve()
    files = discover(root, _inside(root, out))
    old_files = previous["files"] if previous else {}
    old_nodes, old_refs = defaultdict(list), defaultdict(list)
    for n in previous["nodes"] if previous else []:
        old_nodes[n["file"]].append(n)  # external nodes (file None) are never reused: resolve rebuilds them
    for r in previous["refs"] if previous else []:
        old_refs[r["file"]].append(r)

    changes = {"added": [], "changed": [], "deleted": sorted(set(old_files) - set(files)),
               "unchanged": []}
    nodes, refs = [], []
    for rel, info in files.items():  # discover order (sorted), same as a full build
        old = old_files.get(rel)
        if old is not None and old["sha256"] == info["sha256"]:
            changes["unchanged"].append(rel)
            n, r = old_nodes[rel], old_refs[rel]
        else:
            changes["added" if old is None else "changed"].append(rel)
            n, r = extract_file(root, rel, info["lang"])
        nodes.extend(n)
        refs.extend(r)
    nodes, edges = resolve(nodes, refs)
    return new_graph(files, nodes, refs, edges), changes


def save(root: str | os.PathLike, graph: dict, out: str | os.PathLike | None = None) -> Path:
    """Write graph.json atomically (temp file + rename); return its path."""
    path = graph_path(root, out)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(graph, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def load(root: str | os.PathLike, out: str | os.PathLike | None = None) -> dict:
    return json.loads(graph_path(root, out).read_text(encoding="utf-8"))
