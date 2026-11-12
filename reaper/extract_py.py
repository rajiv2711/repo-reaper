"""Python structure extraction via `ast`.

extract(path, source, module) is pure: one file in, (nodes, raw refs) out, with no
knowledge of other files. Edges are built later by resolve.

Nodes: the file, plus every class / function / method (nested ones too), with id
"<path>::<Outer.inner>", line, signature and first docstring line. When a name is
defined twice in one scope (e.g. a property and its setter) the first one wins.

Refs (src = id of the innermost enclosing class/function, else the file):
  import   target = absolute dotted name (relative imports made absolute),
           alias  = the dotted text that refers to target in this file:
             import a.b        -> target a.b, alias a.b
             import a.b as c   -> target a.b, alias c
             from a import b   -> target a.b, alias b      (b may be a module or a symbol)
             from a import *   -> target a,   alias *
           `from __future__` imports are skipped (not dependencies).
  call     target = dotted callee text: "foo", "self.repo.save", "super().__init__",
           "name.strip().lower". Callees with no name (handlers[0](), f()()) give no ref.
           Decorators, default values and annotations belong to the enclosing scope.
  inherit  target = dotted base class text ("Entity", "base.Base"; Generic[T] -> "Generic").
           Keyword arguments such as metaclass= are not bases.
A file that does not parse gives its file node only.
"""

from __future__ import annotations

import ast
import warnings
from contextlib import contextmanager


def module_name(path: str) -> str:
    """Dotted module name of a repo-relative path: app/service.py -> app.service."""
    name = path.removesuffix(".pyi").removesuffix(".py").replace("/", ".")
    name = name.removesuffix(".__init__")
    return name.removeprefix("src.")


def _first_line(doc: str | None) -> str | None:
    lines = (doc or "").strip().splitlines()
    return lines[0].strip() if lines else None


def _dotted(expr: ast.expr) -> str | None:
    """'a.b.c' for Name/Attribute chains; calls in the chain render as 'f()'; else None."""
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        base = _dotted(expr.value)
        return f"{base}.{expr.attr}" if base else None
    if isinstance(expr, ast.Call):
        base = _dotted(expr.func)
        return f"{base}()" if base else None
    return None


def _function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
    sig = f"{prefix}{node.name}({ast.unparse(node.args)})"
    if node.returns is not None:
        sig += f" -> {ast.unparse(node.returns)}"
    return sig


def _class_signature(node: ast.ClassDef) -> str:
    parts = [ast.unparse(e) for e in (*node.bases, *node.keywords)]
    return f"{node.name}({', '.join(parts)})" if parts else node.name


class _Extractor(ast.NodeVisitor):
    def __init__(self, path: str, module: str):
        self.path = path
        is_package = path.rsplit("/", 1)[-1] in ("__init__.py", "__init__.pyi")
        self.package = module if is_package else module.rpartition(".")[0]
        self.nodes: list[dict] = []
        self.refs: list[dict] = []
        self.ids: set[str] = set()
        self.scope: list[tuple[str, str]] = [(path, "file")]  # (node id, kind), innermost last
        self.qual: list[str] = []

    # -- helpers ---------------------------------------------------------------

    def _ref(self, kind: str, target: str, alias: str | None, line: int) -> None:
        self.refs.append({"src": self.scope[-1][0], "kind": kind, "target": target,
                          "alias": alias, "file": self.path, "line": line})

    def _define(self, node, kind: str, signature: str) -> str:
        node_id = f"{self.path}::{'.'.join([*self.qual, node.name])}"
        if node_id not in self.ids:
            self.ids.add(node_id)
            self.nodes.append({
                "id": node_id, "kind": kind, "name": node.name, "file": self.path,
                "line": node.lineno, "end_line": node.end_lineno, "signature": signature,
                "doc": _first_line(ast.get_docstring(node)),
            })
        return node_id

    @contextmanager
    def _inside(self, node_id: str, kind: str, name: str):
        self.scope.append((node_id, kind))
        self.qual.append(name)
        try:
            yield
        finally:
            self.scope.pop()
            self.qual.pop()

    def _absolute(self, module: str | None, level: int) -> str:
        if level == 0:
            return module or ""
        parts = self.package.split(".") if self.package else []
        keep = len(parts) - (level - 1)
        base = parts[:keep] if keep >= 0 else []  # beyond the top package: best effort
        return ".".join([*base, module] if module else base)

    # -- visitors --------------------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        for a in node.names:
            self._ref("import", a.name, a.asname or a.name, node.lineno)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level == 0 and node.module == "__future__":
            return
        base = self._absolute(node.module, node.level)
        for a in node.names:
            if a.name == "*":
                self._ref("import", base, "*", node.lineno)
            else:
                target = f"{base}.{a.name}" if base else a.name
                self._ref("import", target, a.asname or a.name, node.lineno)

    def visit_Call(self, node: ast.Call) -> None:
        target = _dotted(node.func)
        if target and not target.endswith(")"):  # f()() calls a result, not a name
            self._ref("call", target, None, node.lineno)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        for expr in (*node.decorator_list, *node.bases, *node.keywords):
            self.visit(expr)  # evaluated in the enclosing scope
        node_id = self._define(node, "class", _class_signature(node))
        for base in node.bases:
            target = _dotted(base.value if isinstance(base, ast.Subscript) else base)
            if target and not target.endswith(")"):
                self.refs.append({"src": node_id, "kind": "inherit", "target": target,
                                  "alias": None, "file": self.path, "line": node.lineno})
        with self._inside(node_id, "class", node.name):
            for stmt in node.body:
                self.visit(stmt)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for expr in node.decorator_list:
            self.visit(expr)
        self.visit(node.args)  # defaults and annotations run at definition time
        if node.returns is not None:
            self.visit(node.returns)
        kind = "method" if self.scope[-1][1] == "class" else "function"
        node_id = self._define(node, kind, _function_signature(node))
        with self._inside(node_id, kind, node.name):
            for stmt in node.body:
                self.visit(stmt)

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function


def extract(path: str, source: str | bytes, module: str) -> tuple[list[dict], list[dict]]:
    """(nodes, refs) for one Python file. path is repo-relative POSIX; module from module_name()."""
    file_node = {"id": path, "kind": "file", "name": module or path, "file": path,
                 "line": 1, "signature": None, "doc": None}
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # e.g. SyntaxWarning for invalid escapes
            tree = ast.parse(source, filename=path)
        ex = _Extractor(path, module)
        ex.visit(tree)
    except (SyntaxError, ValueError, RecursionError):
        return [file_node], []
    file_node["doc"] = _first_line(ast.get_docstring(tree))
    return [file_node, *ex.nodes], ex.refs
