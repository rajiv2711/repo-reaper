# HANDOFF
Phase 6 | status: done

## Done this session
- Tests first, mocked (no Ollama): tests/test_llm.py (13: payload, OLLAMA_HOST forms, retry on 5 bad-reply kinds,
  fake local HTTP server, HTTP 404, closed port); tests/test_enrich.py (20: hand-ranked files, exact input text,
  150/300-line cut, cache, --limit, dry-run, failures, prune, CLI).
- reaper/llm.py: chat(model, messages, schema) -> dict. POST {OLLAMA_HOST|localhost:11434}/api/chat, stream false,
  format=schema, temperature 0, never num_ctx, timeout 600 s. Bad reply (not JSON / missing key / wrong type / not
  in enum; top level only) -> one retry with bad reply + correction appended, then InvalidResponse. Network/HTTP -> LLMError.
- reaper/enrich.py: run_files(root, graph, model, limit, dry_run, progress) -> report. Code files only (file nodes).
  Input = "File: p" + outputs.file_outline + source. input_sha = sha256(f"{model}\n{FILES_PROMPT_VERSION}\n{input}").
  role = enum ROLES (11 incl. "other"); summary cut to 2 sentences. Order: ranked_files (sum of outputs.degrees over
  the file's nodes). --limit N = first N *stale* files, so repeat runs continue. semantic.json saved after every
  answer; deleted files pruned; groups/architecture kept. InvalidResponse skips the file (exit 1); LLMError aborts.
- cli.py: `reaper enrich <repo> --pass files|groups|architecture [--model M] [--limit N] [--dry-run]`; groups and
  architecture say "not implemented yet (Phase 7)", exit 1. Per-pass default models: enrich.DEFAULT_MODELS.
- 9 mutation checks (no cache hit, off-by-one cut, no retry, num_ctx sent, ...) all fail tests. Real run here,
  devstral-small-2:24b --limit 2: 2 called in 25 s, good summaries; dry re-run -> 2 cached.

## Exact next step
Phase 7, tests first with mocked llm.chat: Louvain groups (seed=42) on the file graph; groups pass (member paths +
summaries, cap 12k chars); architecture pass (drop evidence ids not in graph.json); ARCHITECTURE.md. Reuse
enrich.load/save_semantic, cache_key(..., version=...), llm.chat; add run_groups/run_architecture, wire in cmd_enrich.
## Blockers: none
Notes: tests rank high (test_enrich.py was #2 here); proposal only: rank tests last. Ollama here has both models.

## Verify
conda run -n repo-reaper pytest -q                               -> 113 passed
conda run -n repo-reaper reaper enrich . --pass files --dry-run  -> 24 calls, ~35913 tokens (after `reaper map .`)
