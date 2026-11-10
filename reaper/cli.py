"""`reaper` command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from reaper.discover import count_by_language, discover
from reaper import outputs
from reaper.graph import build, graph_path, load, save, update


def cmd_scan(args: argparse.Namespace) -> int:
    counts = count_by_language(discover(args.repo))
    width = max([len("total"), *map(len, counts)])
    for lang, n in counts.items():
        print(f"{lang:<{width}}  {n}")
    print(f"{'total':<{width}}  {sum(counts.values())}")
    return 0


def _totals(graph: dict) -> str:
    return (f"{len(graph['files'])} files, {len(graph['nodes'])} nodes, "
            f"{len(graph['refs'])} refs, {len(graph['edges'])} edges")


def cmd_map(args: argparse.Namespace) -> int:
    graph = build(args.repo)
    path = save(args.repo, graph)
    print(f"{_totals(graph)} -> {path}")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    graph, changes = update(args.repo)
    path = save(args.repo, graph)
    counts = ", ".join(f"{len(paths)} {kind}" for kind, paths in changes.items())
    print(f"{counts}\n{_totals(graph)} -> {path}")
    return 0


def _load_or_complain(repo: Path) -> dict | None:
    try:
        return load(repo)
    except FileNotFoundError:
        print(f"no {graph_path(repo)}; run `reaper map {repo}` first", file=sys.stderr)
        return None


def cmd_export(args: argparse.Namespace) -> int:
    graph = _load_or_complain(args.repo)
    if graph is None:
        return 1
    for path in outputs.export(args.repo, graph):
        print(path)
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    graph = _load_or_complain(args.repo)
    if graph is None:
        return 1
    results = outputs.query(graph, args.mode, args.name)
    if not results:
        print(f"no node matches {args.name!r}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(results, indent=1, ensure_ascii=False))
    else:
        print(outputs.format_query(args.mode, results), end="")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reaper", description="Map a code repository into a graph.")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="file counts per language")
    scan.add_argument("repo", type=Path)
    scan.set_defaults(func=cmd_scan)

    map_ = sub.add_parser("map", help="full structural build -> .reaper/graph.json")
    map_.add_argument("repo", type=Path)
    map_.set_defaults(func=cmd_map)

    upd = sub.add_parser("update", help="incremental structural update of .reaper/graph.json")
    upd.add_argument("repo", type=Path)
    upd.set_defaults(func=cmd_update)

    exp = sub.add_parser("export", help="TREE.txt, SUMMARY.md, graph.html from .reaper/graph.json")
    exp.add_argument("repo", type=Path)
    exp.set_defaults(func=cmd_export)

    qry = sub.add_parser("query", help="callers / callees of a symbol, deps of a file")
    qry.add_argument("repo", type=Path)
    qry.add_argument("mode", choices=["callers", "callees", "deps"])
    qry.add_argument("name", help="node id, qualified name, module name or plain name")
    qry.add_argument("--json", action="store_true", help="print results as JSON")
    qry.set_defaults(func=cmd_query)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.repo.is_dir():
        parser.error(f"not a directory: {args.repo}")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
