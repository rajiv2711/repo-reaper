# 08-06 deep link - SUMMARY

Plan 08-06 (wave 4, VIEW-03, 08-CONTEXT discretion, Q4). Task 08-06-1 done.

## Built
- `#node=<encodeURIComponent(id)>&hops=N` deep link in reaper/templates/graph.html.
- Pure (DOM-free, node-testable): `parseHash(h)` -> `{node, hops}` | null. It uses URLSearchParams on the hash
  without its "#". Hops are clamped to 1-3; a missing or non-numeric value gives 1. An unknown or empty id gives
  null. Malformed percent escapes never throw. `hashFor(id, hops)` -> `"#node=" + encodeURIComponent(id) + "&hops=" + hops`.
- DOM helpers (top-level functions, called only from start() and handlers):
  - `setHash(id)`: `history.replaceState(null, "", hashFor(id, state.hops))`; `null` removes the hash and keeps
    the rest of the URL (`location.href.split("#")[0]`).
  - `setHops(n)`: sets state.hops and marks the matching `data-hops` button.
  - `applyHash()`: parseHash(location.hash), then setHops + `pick(node)` (with fit); no hash or an unknown id does nothing.
- Wiring: `pick()` ends with `setHash(id)`; `clearFocus()` (Clear button and Escape) calls `setHash(null)`; the hop
  buttons use `setHops`, then refocus, refresh, and `setHash(state.center)` when there is a centre; start() calls
  `applyHash()` inside the first `stabilizationIterationsDone` handler and registers
  `window.addEventListener("hashchange", applyHash)`.
- D-07: the hash only selects an id through `byId` (a Map). Hash text never reaches the DOM.

## Files
- reaper/templates/graph.html (deep-link functions + wiring; the static `<script src="__VIS__"></script>` tag is unchanged).
- tests/test_html_template.py (+3 tests): `test_js_hash` (pinned values + bad hops 0/abc -> 1, raw hand-typed id,
  malformed `%E0%A4%A` -> null, `#hops=2` / `#node=` -> null, round trip of every fixture id),
  `test_js_hash_written_and_applied` (pick writes `C_HASH` at hops 2; Clear writes the URL without the hash;
  applyHash with hops=9 -> hops 3, button 3 marked, `pick("ext:os")` with fit; an unknown id -> no pick, no mark, no URL write),
  `test_template_hash_strings` (never skips: pinned strings + setHash in pick/clearFocus, applyHash after the first
  stabilization, hashchange listener in start()).

## D-xx honoured
D-01 (vis 9.1.9, tag untouched), D-05 (no dependency), D-06 (no new URL; test_template_cdn_fallback still sees only
unpkg + jsDelivr), D-07 (no innerHTML/outerHTML/insertAdjacentHTML/document.write; the hash goes through a Map
lookup only), D-08 / CLI unchanged. The template JS stays ES2020 (URLSearchParams, Number.parseInt/isNaN).

## Deviations
- [Rule 2] `setHash` wraps replaceState in try/catch. A srcdoc/data/blob frame cannot rewrite its URL (it throws),
  and an optional deep link must never break pick or Clear.
- [Rule 2] Clear rebuilds the URL with `location.href.split("#")[0]` instead of `pathname + search`. The latter does
  not resolve for opaque-path URLs (about:srcdoc). I changed my own new test to match before the template
  implemented it; no existing expected value was edited.
- [Rule 2] parseHash strips a leading "#" with `replace(/^#/, "")` instead of `slice(1)`, so input without "#" still
  works. Decoding uses URLSearchParams (lenient, never throws), not decodeURIComponent, which throws URIError on
  malformed escapes.
- Hop handler refactor: the new shared `setHops(n)` marks the button by its `data-hops` value, so applyHash can
  reuse it.
- Choice (plan is silent): only Clear/Escape removes the hash. doubleClick expand/collapse and Collapse all keep it
  (the selection stays). A hop change writes the hash only when a centre exists.
- Not run here: manual browser check 8 (reload of graph.html#node=...&hops=2), which belongs to the verify step.
  A scratch node smoke test of start() with a fake vis
  (/tmp/claude-1000/-home-keyward-Rajiv-personal-repo-reaper/1bfe7f79-8443-4ceb-a7cb-813202d8937a/scratchpad/x0806/smoke.py)
  showed: no pick before stabilization; then hops 2 marked, pick C + fit(10), hash written; hop 3 rewrites the
  hash; hashchange to ext:os re-applies; a bogus id is ignored; Clear writes file:///x/graph.html.

## Tests
- Tests first: 3 failed before the implementation, then `REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q tests/test_html_template.py` -> 31 passed.
- `conda run -n repo-reaper pytest -q` -> 196 passed in 6.30s
- `REAPER_REQUIRE_NODE=1 conda run -n repo-reaper pytest -q` -> 196 passed in 5.88s

Self-Check: PASSED
