"""Build, load and save <repo>/.reaper/graph.json.

graph = {meta: {version, generated_at}, files, nodes, refs, edges}
`files` lists every discovered file (its sha256 drives incremental updates);
only files whose language has an extractor (Python so far) produce nodes and refs.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from reaper import extract_py
from reaper.discover import discover

VERSION = 1
OUT_DIR = ".reaper"


def graph_path(root: str | os.PathLike) -> Path:
    return Path(root) / OUT_DIR / "graph.json"


def new_graph(files: dict, nodes: list, refs: list, edges: list) -> dict:
    meta = {"version": VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    return {"meta": meta, "files": files, "nodes": nodes, "refs": refs, "edges": edges}


def extract_file(root: Path, rel: str, lang: str) -> tuple[list[dict], list[dict]]:
    """(nodes, refs) for one file; ([], []) when no extractor handles its language."""
    if lang == "python":
        return extract_py.extract(rel, (root / rel).read_bytes(), extract_py.module_name(rel))
    return [], []


def build(root: str | os.PathLike) -> dict:
    """Full structural build: discover every file, extract each one."""
    root = Path(root).resolve()
    files = discover(root)
    nodes, refs = [], []
    for rel, info in files.items():
        n, r = extract_file(root, rel, info["lang"])
        nodes.extend(n)
        refs.extend(r)
    # TODO Phase 3: edges = resolve(nodes, refs)
    return new_graph(files, nodes, refs, edges=[])


def save(root: str | os.PathLike, graph: dict) -> Path:
    """Write graph.json atomically (temp file + rename); return its path."""
    path = graph_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(graph, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def load(root: str | os.PathLike) -> dict:
    return json.loads(graph_path(root).read_text(encoding="utf-8"))
