"""Rebuild every edge from nodes + raw refs (the global pass; extract stays per-file and pure).

edge = {src, dst, kind, confidence}; kind: contains | imports | inherits | calls
confidence: EXTRACTED (proven by the code), INFERRED (single best guess),
            AMBIGUOUS (one edge per candidate when there are 2..MAX_CANDIDATES).
External nodes ("ext:<top package>") are rebuilt here as well, from imports that leave the repo,
so resolve(resolve(nodes, refs)[0], refs) gives the same result.

Call resolution, first rule that applies wins:
  1. self.x / this.x inside a class: own method EXTRACTED, else nearest base-class method INFERRED;
     super().x / super.x: base-class method INFERRED (else no edge)
  2. the file's import aliases (following re-exports): EXTRACTED; alias leaving the repo: no edge;
     a bare imported repo name that is no class/function there (`const X = memo(..)`): no edge
  3. same-file name (enclosing function scopes, then module level): EXTRACTED;
     then names from `from repo_module import *`: EXTRACTED
  4. builtins (JS/TS files: JS globals such as console, JSON, Map, Error): no edge
  5. last name part: 1 candidate INFERRED, 2..5 AMBIGUOUS, otherwise no edge
     (bare `f()` only matches top-level functions and classes; dotted `x.f()` only methods)
A dotted name that is exactly a repo module also tries the parent module's attribute of that name
(`import {UserCard} from "./components"` -> components/index.ts re-export, not components/UserCard.tsx).
"""

from __future__ import annotations

import builtins
from collections import defaultdict, deque

from reaper.discover import language

EXTRACTED, INFERRED, AMBIGUOUS = "EXTRACTED", "INFERRED", "AMBIGUOUS"
STRENGTH = {EXTRACTED: 3, INFERRED: 2, AMBIGUOUS: 1}
KIND_ORDER = {"contains": 0, "imports": 1, "inherits": 2, "calls": 3}
SYMBOL_KINDS = ("class", "function", "method")
SCOPE_KINDS = ("function", "method")
BUILTINS = frozenset(dir(builtins))
JS_LANGS = ("javascript", "typescript")
JS_GLOBALS = frozenset({
    "console", "JSON", "Math", "Object", "Array", "String", "Number", "Boolean", "Symbol", "BigInt",
    "Promise", "Date", "RegExp", "Error", "TypeError", "RangeError", "SyntaxError", "ReferenceError",
    "Map", "Set", "WeakMap", "WeakSet", "Proxy", "Reflect", "Intl", "parseInt", "parseFloat", "isNaN",
    "isFinite", "encodeURIComponent", "decodeURIComponent", "encodeURI", "decodeURI", "setTimeout",
    "clearTimeout", "setInterval", "clearInterval", "queueMicrotask", "structuredClone", "fetch",
    "require", "globalThis", "window", "document", "process", "Buffer", "URL", "URLSearchParams",
    "TextEncoder", "TextDecoder", "Uint8Array", "ArrayBuffer", "AbortController", "module", "exports",
    # test-runner globals (jest, vitest, mocha)
    "describe", "it", "test", "expect", "beforeEach", "beforeAll", "afterEach", "afterAll", "jest", "vi",
})
SELF_NAMES = ("self", "this")
SUPER_NAMES = ("super()", "super")
MAX_CANDIDATES = 5
MAX_REEXPORT_HOPS = 5


def resolve(nodes: list[dict], refs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (nodes, edges): `nodes` without stale external nodes plus fresh ones; all edges."""
    nodes = [n for n in nodes if n["kind"] != "external"]
    r = _Resolver(nodes, refs)
    r.contains()
    r.imports()
    r.inherits()
    r.calls()
    ext = [{"id": f"ext:{name}", "kind": "external", "name": name, "file": None,
            "line": None, "signature": None, "doc": None} for name in sorted(r.external)]
    edges = [{"src": s, "dst": d, "kind": k, "confidence": c}
             for (s, d, k), c in sorted(r.edges.items(),
                                        key=lambda kv: (KIND_ORDER[kv[0][2]], kv[0][0], kv[0][1]))]
    return nodes + ext, edges


def _split(node_id: str) -> tuple[str, list[str]]:
    """'a.py::C.m' -> ('a.py', ['C', 'm']); 'a.py' -> ('a.py', [])."""
    file_id, _, qual = node_id.partition("::")
    return file_id, qual.split(".") if qual else []


class _Resolver:
    def __init__(self, nodes: list[dict], refs: list[dict]):
        self.by_id = {n["id"]: n for n in nodes}
        self.nodes = nodes
        self.refs = refs
        self.edges: dict[tuple[str, str, str], str] = {}
        self.external: set[str] = set()
        self.bases: dict[str, list[str]] = defaultdict(list)

        # module name -> file id (duplicate module names: smallest path wins, order-independent)
        self.modules: dict[str, str] = {}
        for n in sorted((n for n in nodes if n["kind"] == "file"), key=lambda n: n["id"]):
            self.modules.setdefault(n["name"], n["id"])

        # last name -> symbol ids, for rule 5
        self.by_name: dict[str, list[str]] = defaultdict(list)
        for n in sorted((n for n in nodes if n["kind"] in SYMBOL_KINDS), key=lambda n: n["id"]):
            self.by_name[n["name"]].append(n["id"])

        # per-file import aliases (later line wins, like Python rebinding) and star imports
        self.aliases: dict[str, dict[str, str]] = defaultdict(dict)
        self.stars: dict[str, list[str]] = defaultdict(list)
        imports = sorted((r for r in refs if r["kind"] == "import"),
                         key=lambda r: (r["file"], r["line"]))
        for ref in imports:
            alias, target = ref["alias"], ref["target"]
            if alias is None:  # side-effect import (JS `import "./m"`): binds no name
                continue
            if alias == "*":
                if target not in self.stars[ref["file"]]:
                    self.stars[ref["file"]].append(target)
                continue
            self.aliases[ref["file"]][alias] = target
            if "." in alias:  # `import a.b` also binds `a`
                top = alias.split(".")[0]
                self.aliases[ref["file"]].setdefault(top, top)

    # -- lookups ---------------------------------------------------------------

    def _add(self, src: str, dst: str, kind: str, confidence: str) -> None:
        key = (src, dst, kind)
        old = self.edges.get(key)
        if old is None or STRENGTH[confidence] > STRENGTH[old]:
            self.edges[key] = confidence

    def _kind(self, node_id: str) -> str | None:
        n = self.by_id.get(node_id)
        return n["kind"] if n else None

    def module_of(self, dotted: str) -> tuple[str, str] | None:
        """Longest repo module that prefixes `dotted` (whole components): (file id, rest)."""
        parts = dotted.split(".")
        for i in range(len(parts), 0, -1):
            file_id = self.modules.get(".".join(parts[:i]))
            if file_id:
                return file_id, ".".join(parts[i:])
        return None

    def expand(self, file_id: str, text: str) -> str | None:
        """Rewrite `text` through the file's longest matching import alias, or None.

        A called alias keeps its call: 'Path().resolve' -> 'pathlib.Path().resolve'.
        """
        aliases = self.aliases.get(file_id, {})
        parts = text.split(".")
        for i in range(len(parts), 0, -1):
            last = parts[i - 1]
            name = last.removesuffix("()")
            target = aliases.get(".".join([*parts[:i - 1], name]))
            if target is not None:
                return ".".join([target + last[len(name):], *parts[i:]])
        return None

    def symbol(self, dotted: str, hops: int = MAX_REEXPORT_HOPS) -> str | None:
        """Repo symbol id for an absolute dotted name, following re-exports and star imports."""
        hit = self.module_of(dotted)
        if hit and not hit[1] and "." in dotted:  # exactly a module: maybe its parent's attribute
            parent, _, last = dotted.rpartition(".")
            up = self.module_of(parent)
            hit = (up[0], f"{up[1]}.{last}" if up[1] else last) if up else None
        if not hit or not hit[1]:
            return None
        file_id, rest = hit
        sym = f"{file_id}::{rest}"
        if self._kind(sym) in SYMBOL_KINDS:
            return sym
        if hops == 0:
            return None
        nxt = [self.expand(file_id, rest)] + [f"{star}.{rest}" for star in self.stars.get(file_id, [])]
        for candidate in nxt:
            if candidate and candidate != dotted:
                found = self.symbol(candidate, hops - 1)
                if found:
                    return found
        return None

    def local(self, src: str, text: str) -> str | None:
        """Same-file definition visible from `src`: enclosing function scopes, then module level."""
        file_id, parts = _split(src)
        for i in range(len(parts), 0, -1):
            scope = f"{file_id}::{'.'.join(parts[:i])}"
            if self._kind(scope) in SCOPE_KINDS and self._kind(f"{scope}.{text}") in SYMBOL_KINDS:
                return f"{scope}.{text}"
        sym = f"{file_id}::{text}"
        return sym if self._kind(sym) in SYMBOL_KINDS else None

    def star(self, file_id: str, text: str) -> str | None:
        for module in self.stars.get(file_id, []):
            found = self.symbol(f"{module}.{text}")
            if found:
                return found
        return None

    def enclosing_class(self, src: str) -> str | None:
        file_id, parts = _split(src)
        for i in range(len(parts), 0, -1):
            cls = f"{file_id}::{'.'.join(parts[:i])}"
            if self._kind(cls) == "class":
                return cls
        return None

    def base_method(self, cls: str, name: str) -> str | None:
        """Nearest method `name` in the base classes of `cls` (breadth-first, cycle-safe)."""
        queue, seen = deque(self.bases.get(cls, [])), {cls}
        while queue:
            base = queue.popleft()
            if base in seen:
                continue
            seen.add(base)
            if self._kind(f"{base}.{name}") in SYMBOL_KINDS:
                return f"{base}.{name}"
            queue.extend(self.bases.get(base, []))
        return None

    # -- edge passes -----------------------------------------------------------

    def contains(self) -> None:
        for n in self.nodes:
            if n["kind"] not in SYMBOL_KINDS:
                continue
            file_id, parts = _split(n["id"])
            parent = f"{file_id}::{'.'.join(parts[:-1])}" if len(parts) > 1 else file_id
            self._add(parent if parent in self.by_id else file_id, n["id"], "contains", EXTRACTED)

    def imports(self) -> None:
        for ref in self.refs:
            if ref["kind"] != "import" or not ref["target"]:
                continue
            hit = self.module_of(ref["target"])
            if hit:
                if hit[0] != ref["file"]:
                    self._add(ref["file"], hit[0], "imports", EXTRACTED)
            else:
                top = ref["target"].split(".")[0]
                self.external.add(top)
                self._add(ref["file"], f"ext:{top}", "imports", EXTRACTED)

    def inherits(self) -> None:
        for ref in self.refs:  # within a file, refs keep source order: bases stay in MRO order
            if ref["kind"] != "inherit":
                continue
            text, src = ref["target"], ref["src"]
            expanded = self.expand(ref["file"], text)
            if expanded is not None:
                dst = self.symbol(expanded)  # None when the base lives outside the repo
            else:
                dst = self.local(src, text) or self.star(ref["file"], text)
            if dst and dst != src and self._kind(dst) == "class":
                self._add(src, dst, "inherits", EXTRACTED)
                if dst not in self.bases[src]:
                    self.bases[src].append(dst)

    def calls(self) -> None:
        for ref in self.refs:
            if ref["kind"] == "call":
                for dst, confidence in self._call(ref):
                    self._add(ref["src"], dst, "calls", confidence)

    def _call(self, ref: dict) -> list[tuple[str, str]]:
        src, text, file_id = ref["src"], ref["target"], ref["file"]
        parts = text.split(".")

        # 1. self.x / this.x / super().x / super.x
        if len(parts) == 2 and parts[0] in SELF_NAMES + SUPER_NAMES:
            cls = self.enclosing_class(src)
            if cls:
                own = f"{cls}.{parts[1]}"
                if parts[0] in SELF_NAMES and self._kind(own) in SYMBOL_KINDS:
                    return [(own, EXTRACTED)]
                base = self.base_method(cls, parts[1])
                if base:
                    return [(base, INFERRED)]
            if parts[0] in SUPER_NAMES:
                return []  # base outside the repo (or object): don't guess

        # 2. import aliases
        expanded = self.expand(file_id, text)
        if expanded is not None:
            if self.module_of(expanded) is None:
                return []  # alias points outside the repo
            dst = self.symbol(expanded)
            if dst:
                return [(dst, EXTRACTED)]
            if len(parts) == 1:
                return []  # we know where the name comes from and it is no node: don't guess

        # 3. same file, then star imports
        dst = self.local(src, text) or self.star(file_id, text)
        if dst:
            return [(dst, EXTRACTED)]

        # 4. builtins
        known = JS_GLOBALS if language(file_id) in JS_LANGS else BUILTINS
        if parts[0].removesuffix("()") in known:
            return []

        # 5. last name part: bare `f()` -> top-level functions/classes; `x.f()` -> methods
        if len(parts) == 1:
            cands = [c for c in self.by_name.get(text, [])
                     if self._kind(c) in ("class", "function") and len(_split(c)[1]) == 1]
        else:
            cands = [c for c in self.by_name.get(parts[-1], []) if self._kind(c) == "method"]
        if len(cands) == 1:
            return [(cands[0], INFERRED)]
        if 2 <= len(cands) <= MAX_CANDIDATES:
            return [(c, AMBIGUOUS) for c in cands]
        return []
