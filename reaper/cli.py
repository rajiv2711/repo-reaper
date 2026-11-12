"""`reaper` command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from reaper import __version__, enrich, legend, llm, outputs
from reaper.diff import DiffError, diff, format_diff
from reaper.discover import count_by_language, discover
from reaper.graph import build, graph_path, load, save, update


def _where(args: argparse.Namespace) -> str:
    """The repo (and --out) as typed, for "run `reaper ... <where>`" hints."""
    return f"{args.repo}" + (f" --out {args.out}" if args.out else "")


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
    graph = build(args.repo, args.out)
    path = save(args.repo, graph, args.out)
    print(f"{_totals(graph)} -> {path}")
    return 0


def _update(args: argparse.Namespace) -> dict:
    graph, changes = update(args.repo, args.out)
    path = save(args.repo, graph, args.out)
    counts = ", ".join(f"{len(paths)} {kind}" for kind, paths in changes.items())
    print(f"{counts}\n{_totals(graph)} -> {path}")
    return graph


def cmd_update(args: argparse.Namespace) -> int:
    _update(args)
    return 0


def _load_or_complain(args: argparse.Namespace) -> dict | None:
    try:
        return load(args.repo, args.out)
    except FileNotFoundError:
        print(f"no {graph_path(args.repo, args.out)}; run `reaper map {_where(args)}` first",
              file=sys.stderr)
        return None


def _view_semantic(args: argparse.Namespace, graph: dict) -> dict | None:
    """Semantic layer for graph.html only; None when semantic.json does not exist
    or cannot be read (then a warning on stderr; graph.html is still written, structural only)."""
    try:
        return enrich.view_semantic(args.repo, graph, args.out)
    except ValueError as err:
        problem = f"is not valid JSON ({err})"
    except AttributeError:  # enrich.load_semantic: valid JSON, but not an object
        problem = "is not a JSON object"
    except OSError as err:  # e.g. PermissionError, IsADirectoryError
        problem = f"cannot be read ({err.strerror or err})"
    print(f"warning: {enrich.semantic_path(args.repo, args.out)} {problem}; "
          f"graph.html has no semantic layer", file=sys.stderr)
    return None


def _export(args: argparse.Namespace, graph: dict) -> None:
    for path in outputs.export(args.repo, graph, _view_semantic(args, graph), args.out):
        print(path)


def cmd_export(args: argparse.Namespace) -> int:
    graph = _load_or_complain(args)
    if graph is None:
        return 1
    _export(args, graph)
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    graph = _load_or_complain(args)
    if graph is None:
        return 1
    results = outputs.query(graph, args.mode, args.name, depth=args.depth)
    if not results:
        print(f"no node matches {args.name!r}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(results, indent=1, ensure_ascii=False))
    else:
        print(outputs.format_query(args.mode, results, budget=args.budget), end="")
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    """Update the graph, compare the working tree with --base, write the outputs with the Diff
    layer in graph.html and print the changes. Nothing is written when the comparison fails."""
    graph, _ = update(args.repo, args.out)
    try:
        d = diff(args.repo, graph, args.base, args.out)
    except DiffError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    save(args.repo, graph, args.out)
    for path in outputs.export(args.repo, graph, _view_semantic(args, graph), args.out, diff=d):
        print(path)
    print("\n".join([format_diff(d, graph), *legend.diff_key()]))
    return 0


def cmd_rules(args: argparse.Namespace) -> int:
    """Print the agent block (reaper/legend.py); write nothing."""
    print(legend.agent_rules(args.repo, args.out), end="")
    path = graph_path(args.repo, args.out)
    if not path.exists():
        print(f"note: no {path} yet; run `reaper run {_where(args)}` first", file=sys.stderr)
    return 0


def _calls(n: int) -> str:
    return f"{n} call{'s' * (n != 1)}"


def _enrich_files(args: argparse.Namespace, graph: dict, model: str) -> int:
    report = enrich.run_files(args.repo, graph, model=model, limit=args.limit,
                              dry_run=args.dry_run, progress=print, out=args.out)
    for path, reason in report["failed"].items():
        if path not in report["todo"]:  # failed before any call (unreadable file)
            print(f"{path}: FAILED {reason}")
    if args.dry_run:
        print(f"files pass, {model}, dry run: {_calls(len(report['todo']))} "
              f"({report['cached']} cached), ~{report['tokens']} input tokens, "
              f"largest call ~{report['max_tokens']} tokens")
        return 0
    path = enrich.semantic_path(args.repo, args.out)
    print(f"files pass, {model}: {len(report['called'])} called, {report['cached']} cached, "
          f"{len(report['failed'])} failed -> {path}")
    return 1 if report["failed"] else 0


def _enrich_groups(args: argparse.Namespace, graph: dict, model: str) -> int:
    report = enrich.run_groups(args.repo, graph, model=model, limit=args.limit,
                               dry_run=args.dry_run, progress=print, out=args.out)
    missing = len(report["missing_summaries"])
    if missing:
        print(f"note: {missing} file{'s have' if missing != 1 else ' has'} no summary; "
              f"run `reaper enrich {_where(args)} --pass files` first for better groups",
              file=sys.stderr)
    if args.dry_run:
        print(f"groups pass, {model}, dry run: {_calls(len(report['todo']))} "
              f"({report['cached']} of {report['groups']} groups cached), "
              f"~{report['tokens']} input tokens, largest call ~{report['max_tokens']} tokens")
        return 0
    path = enrich.semantic_path(args.repo, args.out)
    print(f"groups pass, {model}: {len(report['called'])} called, {report['cached']} cached, "
          f"{len(report['failed'])} failed -> {path}")
    return 1 if report["failed"] else 0


def _enrich_architecture(args: argparse.Namespace, graph: dict, model: str) -> int:
    report = enrich.run_architecture(args.repo, graph, model=model, dry_run=args.dry_run,
                                     progress=print, out=args.out)
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


def _enrich_pass(args: argparse.Namespace, graph: dict, name: str) -> int | None:
    """Run one pass: its exit status, or None when it stopped early with an error
    (Ollama unreachable, unknown model, architecture before groups)."""
    model = args.model or enrich.DEFAULT_MODELS[name]
    try:
        return ENRICH_PASSES[name](args, graph, model)
    except (enrich.NotReady, llm.LLMError) as e:
        print(f"error: {e}", file=sys.stderr)
        return None


def cmd_enrich(args: argparse.Namespace) -> int:
    graph = _load_or_complain(args)
    if graph is None:
        return 1
    status = _enrich_pass(args, graph, args.pass_name)
    if status is None:
        return 1
    if not args.dry_run:  # keep graph.html in step with semantic.json
        print(outputs.write_html(args.repo, graph, _view_semantic(args, graph), args.out))
    return status


def cmd_run(args: argparse.Namespace) -> int:
    """update, then (with --llm) the files, groups and architecture passes, then export.
    A failing pass stops the LLM passes; the outputs are still written; exit status 1."""
    graph = _update(args)
    status = 0
    if args.llm:
        for name in ENRICH_PASSES:
            result = _enrich_pass(args, graph, name)
            if result != 0:
                status = 1
                print(f"stopped at the {name} pass; run it again to retry "
                      f"(answers already saved are reused)", file=sys.stderr)
                break
    _export(args, graph)
    return status


def _limit(text: str) -> int:
    """argparse type: an integer >= 1."""
    n = int(text)
    if n < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return n


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reaper",
                                     description="Map a code repository into a graph.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # shared by every command that reads or writes the outputs
    repo = argparse.ArgumentParser(add_help=False)
    repo.add_argument("repo", type=Path, help="root of the repository to map")
    repo.add_argument("--out", type=Path, metavar="DIR",
                      help="output directory (default: <repo>/.reaper)")

    scan = sub.add_parser("scan", help="file counts per language")
    scan.add_argument("repo", type=Path)
    scan.set_defaults(func=cmd_scan, out=None)

    run = sub.add_parser("run", parents=[repo],
                         help="update + export in one step; with --llm also the three LLM passes")
    run.add_argument("--llm", action="store_true",
                     help="run the files, groups and architecture passes via Ollama before export")
    run.add_argument("--model", help="one Ollama model for every pass (default: each pass's own)")
    run.add_argument("--limit", type=_limit, metavar="N",
                     help="ask about at most N stale files (and N groups), most-connected first")
    run.set_defaults(func=cmd_run, dry_run=False)

    map_ = sub.add_parser("map", parents=[repo], help="full structural build -> graph.json")
    map_.set_defaults(func=cmd_map)

    upd = sub.add_parser("update", parents=[repo],
                         help="incremental structural update of graph.json (full build if none)")
    upd.set_defaults(func=cmd_update)

    exp = sub.add_parser("export", parents=[repo],
                         help="TREE.txt, SUMMARY.md, graph.html from graph.json")
    exp.set_defaults(func=cmd_export)

    qry = sub.add_parser("query", parents=[repo],
                         help="callers / callees / subclasses of a symbol, deps of a file")
    qry.add_argument("mode", choices=list(outputs.QUERY_MODES))
    qry.add_argument("name", help="node id, qualified name, module name or plain name")
    qry.add_argument("--depth", type=_limit, default=1, metavar="N",
                     help="hops for callers / callees / subclasses (default 1)")
    qry.add_argument("--budget", type=_limit, default=outputs.DEFAULT_BUDGET, metavar="TOKENS",
                     help=f"cap the text output at about this many tokens; the rest is counted "
                          f"per folder (default {outputs.DEFAULT_BUDGET}; --json is never cut)")
    qry.add_argument("--json", action="store_true", help="print results as JSON")
    qry.set_defaults(func=cmd_query)

    rules = sub.add_parser("rules", parents=[repo],
                           help="print a Markdown block for CLAUDE.md / AGENTS.md: how far an "
                                "agent can trust the graph and how to query it (writes nothing)")
    rules.set_defaults(func=cmd_rules)

    dif = sub.add_parser("diff", parents=[repo],
                         help="what changed since a commit (staged, unstaged, untracked): files, "
                              "functions and links; writes the outputs with graph.html's Diff layer")
    dif.add_argument("--base", default="HEAD", metavar="REF",
                     help="commit, branch or tag to compare with (default: HEAD)")
    dif.set_defaults(func=cmd_diff)

    enr = sub.add_parser("enrich", parents=[repo],
                         help="one LLM pass via Ollama -> semantic.json, then refresh graph.html")
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
    if args.out is not None and args.out.resolve() == args.repo.resolve():
        parser.error("--out must not be the repository itself")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
