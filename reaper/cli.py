"""`reaper` command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from reaper.discover import count_by_language, discover
from reaper import enrich, llm, outputs
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


def _view_semantic(repo: Path, graph: dict) -> dict | None:
    """Semantic layer for graph.html only (D-02); None when semantic.json does not exist
    or cannot be read (then a warning on stderr; export still writes the structural page)."""
    try:
        return enrich.view_semantic(repo, graph)
    except ValueError as err:
        problem = f"is not valid JSON ({err})"
    except AttributeError:  # enrich.load_semantic: valid JSON, but not an object
        problem = "is not a JSON object"
    except OSError as err:  # e.g. PermissionError, IsADirectoryError
        problem = f"cannot be read ({err.strerror or err})"
    print(f"warning: {enrich.semantic_path(repo)} {problem}; graph.html has no semantic layer",
          file=sys.stderr)
    return None


def cmd_export(args: argparse.Namespace) -> int:
    graph = _load_or_complain(args.repo)
    if graph is None:
        return 1
    sem = _view_semantic(args.repo, graph)
    for path in outputs.export(args.repo, graph, sem):
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


def _calls(n: int) -> str:
    return f"{n} call{'s' * (n != 1)}"


def _enrich_files(args: argparse.Namespace, graph: dict, model: str) -> int:
    report = enrich.run_files(args.repo, graph, model=model, limit=args.limit,
                              dry_run=args.dry_run, progress=print)
    for path, reason in report["failed"].items():
        if path not in report["todo"]:  # failed before any call (unreadable file)
            print(f"{path}: FAILED {reason}")
    if args.dry_run:
        print(f"files pass, {model}, dry run: {_calls(len(report['todo']))} "
              f"({report['cached']} cached), ~{report['tokens']} input tokens, "
              f"largest call ~{report['max_tokens']} tokens")
        return 0
    path = enrich.semantic_path(args.repo)
    print(f"files pass, {model}: {len(report['called'])} called, {report['cached']} cached, "
          f"{len(report['failed'])} failed -> {path}")
    return 1 if report["failed"] else 0


def _enrich_groups(args: argparse.Namespace, graph: dict, model: str) -> int:
    report = enrich.run_groups(args.repo, graph, model=model, limit=args.limit,
                               dry_run=args.dry_run, progress=print)
    missing = len(report["missing_summaries"])
    if missing:
        print(f"note: {missing} file{'s have' if missing != 1 else ' has'} no summary; "
              f"run `reaper enrich {args.repo} --pass files` first for better groups",
              file=sys.stderr)
    if args.dry_run:
        print(f"groups pass, {model}, dry run: {_calls(len(report['todo']))} "
              f"({report['cached']} of {report['groups']} groups cached), "
              f"~{report['tokens']} input tokens, largest call ~{report['max_tokens']} tokens")
        return 0
    path = enrich.semantic_path(args.repo)
    print(f"groups pass, {model}: {len(report['called'])} called, {report['cached']} cached, "
          f"{len(report['failed'])} failed -> {path}")
    return 1 if report["failed"] else 0


def _enrich_architecture(args: argparse.Namespace, graph: dict, model: str) -> int:
    report = enrich.run_architecture(args.repo, graph, model=model, dry_run=args.dry_run,
                                     progress=print)
    if args.dry_run:
        print(f"architecture pass, {model}, dry run: {_calls(int(report['todo']))} "
              f"({int(report['cached'])} cached), ~{report['tokens']} input tokens")
        return 0
    dropped = len(report["dropped"])
    print(f"architecture pass, {model}: {'called' if report['called'] else 'cached'}, "
          f"{dropped} evidence id{'s' * (dropped != 1)} dropped -> {report['path']}")
    return 0


ENRICH_PASSES = {"files": _enrich_files, "groups": _enrich_groups,
                 "architecture": _enrich_architecture}


def cmd_enrich(args: argparse.Namespace) -> int:
    graph = _load_or_complain(args.repo)
    if graph is None:
        return 1
    model = args.model or enrich.DEFAULT_MODELS[args.pass_name]
    try:
        return ENRICH_PASSES[args.pass_name](args, graph, model)
    except (enrich.NotReady, llm.LLMError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def _limit(text: str) -> int:
    n = int(text)
    if n < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return n


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

    enr = sub.add_parser("enrich", help="LLM semantic pass via Ollama -> .reaper/semantic.json")
    enr.add_argument("repo", type=Path)
    enr.add_argument("--pass", dest="pass_name", required=True,
                     choices=["files", "groups", "architecture"])
    enr.add_argument("--model", help="Ollama model (default: devstral-small-2:24b for files, "
                                     "qwen3-coder:30b for groups and architecture)")
    enr.add_argument("--limit", type=_limit, metavar="N",
                     help="ask about at most N stale files (or groups), most-connected (largest) "
                          "first; ignored by the architecture pass")
    enr.add_argument("--dry-run", action="store_true",
                     help="print the call count and approx input tokens; call nothing")
    enr.set_defaults(func=cmd_enrich)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.repo.is_dir():
        parser.error(f"not a directory: {args.repo}")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
