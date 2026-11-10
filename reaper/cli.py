"""`reaper` command-line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from reaper.discover import count_by_language, discover
from reaper.graph import build, save


def cmd_scan(args: argparse.Namespace) -> int:
    counts = count_by_language(discover(args.repo))
    width = max([len("total"), *map(len, counts)])
    for lang, n in counts.items():
        print(f"{lang:<{width}}  {n}")
    print(f"{'total':<{width}}  {sum(counts.values())}")
    return 0


def cmd_map(args: argparse.Namespace) -> int:
    graph = build(args.repo)
    path = save(args.repo, graph)
    print(f"{len(graph['files'])} files, {len(graph['nodes'])} nodes, "
          f"{len(graph['refs'])} refs, {len(graph['edges'])} edges -> {path}")
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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.repo.is_dir():
        parser.error(f"not a directory: {args.repo}")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
