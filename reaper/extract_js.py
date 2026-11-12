"""JavaScript / TypeScript structure extraction via tree-sitter.

extract(path, source, module) is pure: one file in, (nodes, raw refs) out, with no knowledge of
other files. Same contract as extract_py, so resolve treats both languages alike.
Grammar by extension: .ts -> typescript, .tsx -> tsx, else (.js .jsx .mjs .cjs) javascript.

Nodes: the file, plus
  class    class declarations (also abstract, and `const X = class ...`) and TS interfaces;
           signature "User extends Entity implements Named", "interface Named extends Base"
  function function declarations and `const f = () => {}` / `= function () {}`, nested too
  method   class methods and class fields holding a function (`handle = () => {}`)
  Signature "name(params): Ret", prefixed "async " and "*" for generators. doc = first line of the
  /** */ comment directly above; the file doc is a leading /** */ that no declaration claims.
  When a name is defined twice in one scope the first one wins. TS overload and abstract
  signatures, object-literal methods and anonymous functions are not nodes.

Refs (src = id of the innermost enclosing class/function, else the file), in the resolver's dotted form:
  import   target = dotted module [+ "." + imported name], alias = the local name:
             import d from "./m"            -> m.default, d
             import { a as b } from "./m"   -> m.a, b
             import * as ns from "./m"      -> m, ns
             import "./m", import("./m"), require("./m")  -> m, None (binds no name)
             const x = require("m")         -> m, x;  const { a, b: c } = require("m") -> m.a, a / m.b, c
             export { a as b } from "./m"   -> m.a, b;  export * from "./m" -> m, *;  export * as ns -> m, ns
             export default foo, export { a as b }  -> <own module>.foo, default / <own module>.a, b
               (a self-alias: the resolver follows it like a re-export; it adds no edge)
           Relative and "src/..." specifiers become repo module names (module_name rules;
           "./x.js" -> x); specifiers
           leaving the repo and asset files (.css .svg .json ...) give no ref. Packages:
           "react-dom/client" -> react-dom.client, "@scope/pkg/x" -> @scope/pkg.x.
  call     target = dotted callee text of calls, `new X()` and JSX components (<Button />; lowercase
           tags are HTML): "foo", "this.repo.save", "a.b().c"; super(...) -> "super.constructor".
           Callees with no name (obj[k](), f()()) and require()/import() give no call ref.
           Parameter defaults and decorators belong to the enclosing scope.
  inherit  target = extends / implements type text ("Base", "ns.Base"; Base<T> -> "Base");
           an `extends mixin(Base)` call is no base.
Parse errors: tree-sitter marks the code it cannot parse as ERROR subtrees (grammar gaps such as
`styled.div<Props>`...``, or broken code); those are skipped and the rest of the file is extracted.
A file whose top level does not parse at all gives its file node only.
"""

from __future__ import annotations

import posixpath
from contextlib import contextmanager

import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

CODE_EXTS = (".d.ts", ".tsx", ".ts", ".mts", ".cts", ".jsx", ".mjs", ".cjs", ".js")
ASSET_EXTS = frozenset({
    ".css", ".scss", ".sass", ".less", ".json", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".ico", ".html", ".md", ".txt", ".yaml", ".yml", ".wasm", ".woff", ".woff2", ".ttf", ".mp3", ".mp4",
})
FUNCTION_VALUES = frozenset({"arrow_function", "function_expression", "function", "generator_function"})
DECL_WRAPPERS = frozenset({"export_statement", "lexical_declaration", "variable_declaration"})
DOTTED_LEAVES = frozenset({"identifier", "this", "super", "property_identifier",
                           "private_property_identifier", "type_identifier", "nested_identifier"})

_GRAMMARS = {
    "javascript": tree_sitter_javascript.language,
    "typescript": tree_sitter_typescript.language_typescript,
    "tsx": tree_sitter_typescript.language_tsx,
}
_parsers: dict[str, Parser] = {}


def _parser(path: str) -> Parser:
    if path.endswith(".tsx"):
        name = "tsx"
    elif path.endswith((".ts", ".mts", ".cts")):
        name = "typescript"
    else:
        name = "javascript"
    if name not in _parsers:
        _parsers[name] = Parser(Language(_GRAMMARS[name]()))
    return _parsers[name]


def _strip_ext(path: str) -> str:
    for ext in CODE_EXTS:
        if path.endswith(ext):
            return path[: -len(ext)]
    return path


def _dotted_path(stem: str) -> str:
    return stem.replace("/", ".").removesuffix(".index").removeprefix("src.")


def module_name(path: str) -> str:
    """Dotted module name of a repo-relative path: src/components/index.ts -> components."""
    return _dotted_path(_strip_ext(path))


def _text(node: Node) -> str:
    return node.text.decode("utf-8", "replace")


def _flat(node: Node) -> str:
    return " ".join(_text(node).split())


def _string(node: Node | None) -> str | None:
    """Value of a plain string literal (no template strings), else None."""
    if node is None or node.type != "string":
        return None
    return _text(node)[1:-1]


def _name(node: Node) -> str:
    """Identifier text; a string module-export name ("a-b") without its quotes."""
    return _string(node) if node.type == "string" else _text(node)


def _dotted(node: Node | None) -> str | None:
    """'a.b.c' for identifier / member chains; calls and `new` in the chain render as 'f()'."""
    if node is None:
        return None
    t = node.type
    if t in DOTTED_LEAVES:
        return _flat(node)
    if t == "member_expression":
        base = _dotted(node.child_by_field_name("object"))
        prop = node.child_by_field_name("property")
        return f"{base}.{_text(prop)}" if base and prop is not None else None
    if t in ("call_expression", "new_expression"):
        base = _dotted(node.child_by_field_name("function" if t == "call_expression" else "constructor"))
        return f"{base}()" if base else None
    if t in ("non_null_expression", "parenthesized_expression") and node.named_child_count == 1:
        return _dotted(node.named_children[0])  # a!.b, (a).b
    return None


def _type_name(node: Node | None) -> str | None:
    """'Base' / 'ns.Base' for a heritage type; Base<T> -> 'Base'."""
    if node is None:
        return None
    if node.type in ("generic_type", "generic_identifier"):
        return _type_name(node.child_by_field_name("name") or node.named_children[0])
    if node.type in ("type_identifier", "identifier", "nested_type_identifier", "nested_identifier"):
        return _flat(node)
    return _dotted(node)


def _comment_line(comment: Node) -> str | None:
    body = _text(comment).removeprefix("/**").removesuffix("*/")
    for line in body.splitlines():
        line = line.strip().lstrip("*").strip()
        for tag in ("@fileoverview", "@file"):
            if line.startswith(tag + " "):
                line = line[len(tag):].strip()
        if line:
            return line
    return None


def _is_jsdoc(node: Node | None) -> bool:
    return node is not None and node.type == "comment" and _text(node).startswith("/**")


def _fn_signature(name: str, fn: Node) -> str:
    tokens = {c.type for c in fn.children if not c.is_named}
    prefix = ("async " if "async" in tokens else "") + ("*" if "*" in tokens else "")
    params = fn.child_by_field_name("parameters")
    if params is not None:
        p = _flat(params)
    else:
        single = fn.child_by_field_name("parameter")  # x => x
        p = f"({_flat(single)})" if single is not None else "()"
    tp = fn.child_by_field_name("type_parameters")
    ret = fn.child_by_field_name("return_type")
    return f"{prefix}{name}{_flat(tp) if tp else ''}{p}{_flat(ret) if ret else ''}"


class _Extractor:
    def __init__(self, path: str, module: str):
        self.path = path
        self.module = module
        self.nodes: list[dict] = []
        self.refs: list[dict] = []
        self.ids: set[str] = set()
        self.scope: list[tuple[str, str]] = [(path, "file")]  # (node id, kind), innermost last
        self.qual: list[str] = []
        self.claimed: set[int] = set()  # start bytes of comments used as symbol docs

    # -- helpers ---------------------------------------------------------------

    def _ref(self, kind: str, target: str, alias: str | None, node: Node, src: str | None = None) -> None:
        self.refs.append({"src": src or self.scope[-1][0], "kind": kind, "target": target,
                          "alias": alias, "file": self.path, "line": node.start_point[0] + 1})

    def _doc(self, node: Node) -> str | None:
        anchor = node
        while anchor.parent is not None and anchor.parent.type in DECL_WRAPPERS:
            anchor = anchor.parent
        prev = anchor.prev_named_sibling
        if _is_jsdoc(prev) and prev.end_point[0] >= anchor.start_point[0] - 1:
            self.claimed.add(prev.start_byte)
            return _comment_line(prev)
        return None

    def _define(self, name: str, kind: str, node: Node, signature: str) -> str:
        node_id = f"{self.path}::{'.'.join([*self.qual, name])}"
        if node_id not in self.ids:
            self.ids.add(node_id)
            self.nodes.append({
                "id": node_id, "kind": kind, "name": name, "file": self.path,
                "line": node.start_point[0] + 1, "end_line": node.end_point[0] + 1,
                "signature": signature, "doc": self._doc(node),
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

    def _module(self, source: Node | None) -> str | None:
        """Dotted module for an import specifier string; None when it gives no ref."""
        spec = _string(source)
        if not spec or spec.startswith("/"):
            return None
        if spec.startswith(".") or spec.startswith("src/"):  # "src/x": a repo path (baseUrl ".")
            joined = posixpath.normpath(posixpath.join(posixpath.dirname(self.path), spec)
                                        if spec.startswith(".") else spec)
            if joined == ".." or joined.startswith("../"):
                return None  # leaves the repo
            if joined == ".":
                joined = "index"
            if posixpath.splitext(joined)[1].lower() in ASSET_EXTS:
                return None
            return _dotted_path(_strip_ext(joined))
        parts = [p for p in spec.split("/") if p]
        n = 2 if spec.startswith("@") and len(parts) > 1 else 1
        head, rest = "/".join(parts[:n]), parts[n:]
        if rest and posixpath.splitext(rest[-1])[1].lower() in ASSET_EXTS:
            return head  # a package's stylesheet: still a dependency on the package
        if rest:
            rest[-1] = _strip_ext(rest[-1])
        return ".".join([head, *[p for p in rest if p]])

    # -- walk ------------------------------------------------------------------

    def visit_children(self, node: Node) -> None:
        for child in node.named_children:
            self.visit(child)

    def visit(self, node: Node) -> None:
        t = node.type
        if t == "ERROR":
            return  # unparsed code: no structure claimed from it
        if t in ("function_declaration", "generator_function_declaration"):
            name = node.child_by_field_name("name")
            if name is not None:
                return self._function(node, _text(name), node)
        elif t in ("class_declaration", "abstract_class_declaration"):
            name = node.child_by_field_name("name")
            if name is not None:
                return self._class(node, _text(name), node)
        elif t == "interface_declaration":
            return self._interface(node)
        elif t == "variable_declarator":
            name, value = node.child_by_field_name("name"), node.child_by_field_name("value")
            if name is not None and name.type == "identifier" and value is not None:
                if value.type in FUNCTION_VALUES:
                    return self._function(value, _text(name), node)
                if value.type == "class":
                    return self._class(value, _text(name), node)
        elif t == "method_definition" and self.scope[-1][1] == "class":  # not anonymous classes / objects
            name = node.child_by_field_name("name")
            if name is not None and name.type != "computed_property_name":
                return self._function(node, _text(name), node)
        elif t in ("field_definition", "public_field_definition") and self.scope[-1][1] == "class":
            name = node.child_by_field_name("property") or node.child_by_field_name("name")
            value = node.child_by_field_name("value")
            if (name is not None and name.type in ("property_identifier", "private_property_identifier")
                    and value is not None and value.type in FUNCTION_VALUES):
                return self._function(value, _text(name), node)
        elif t == "import_statement":
            return self._import(node)
        elif t == "export_statement":
            return self._export(node)
        elif t == "call_expression":
            return self._call(node)
        elif t == "new_expression":
            target = _dotted(node.child_by_field_name("constructor"))
            if target and not target.endswith(")"):
                self._ref("call", target, None, node)
        elif t in ("jsx_opening_element", "jsx_self_closing_element"):
            target = _dotted(node.child_by_field_name("name"))
            if target and target[0].isupper():
                self._ref("call", target, None, node)
        self.visit_children(node)

    def _function(self, fn: Node, name: str, decl: Node) -> None:
        """fn: the function node (params + body); decl: the node that names it (doc, line)."""
        body = fn.child_by_field_name("body")
        for child in fn.named_children:  # parameter defaults and decorators: enclosing scope
            if child != body:
                self.visit(child)
        for child in decl.named_children if decl != fn else ():
            if child != fn and child.type == "decorator":
                self.visit(child)
        kind = "method" if self.scope[-1][1] == "class" else "function"
        node_id = self._define(name, kind, decl, _fn_signature(name, fn))
        if body is not None:
            with self._inside(node_id, kind, name):
                self.visit(body)

    def _class(self, cls: Node, name: str, decl: Node) -> None:
        heritage = next((c for c in cls.named_children if c.type == "class_heritage"), None)
        for child in cls.named_children:  # decorators and `extends mixin(Base)` run outside the class
            if child.type in ("decorator", "class_heritage"):
                self.visit(child)
        tp = cls.child_by_field_name("type_parameters")
        sig = f"{name}{_flat(tp) if tp else ''}" + (f" {_flat(heritage)}" if heritage else "")
        node_id = self._define(name, "class", decl, sig)
        for base in self._bases(heritage):
            self._ref("inherit", base, None, cls, src=node_id)
        body = cls.child_by_field_name("body")
        if body is not None:
            with self._inside(node_id, "class", name):
                self.visit(body)

    @staticmethod
    def _bases(heritage: Node | None) -> list[str]:
        if heritage is None:
            return []
        types = []
        for clause in heritage.named_children:
            if clause.type == "extends_clause":
                types += clause.children_by_field_name("value")
            elif clause.type == "implements_clause":
                types += clause.named_children
            else:
                types.append(clause)  # javascript: class_heritage holds the expression itself
        names = [_type_name(t) for t in types]
        return [n for n in names if n and not n.endswith(")")]

    def _interface(self, node: Node) -> None:
        name = node.child_by_field_name("name")
        if name is None:
            return
        tp = node.child_by_field_name("type_parameters")
        ext = next((c for c in node.named_children if c.type == "extends_type_clause"), None)
        sig = f"interface {_text(name)}{_flat(tp) if tp else ''}" + (f" {_flat(ext)}" if ext else "")
        node_id = self._define(_text(name), "class", node, sig)
        for t in ext.children_by_field_name("type") if ext else ():
            base = _type_name(t)
            if base:
                self._ref("inherit", base, None, node, src=node_id)

    def _import(self, node: Node) -> None:
        module = self._module(node.child_by_field_name("source"))
        if module is None:
            return
        clause = next((c for c in node.named_children if c.type == "import_clause"), None)
        if clause is None:
            self._ref("import", module, None, node)
            return
        for c in clause.named_children:
            if c.type == "identifier":
                self._ref("import", f"{module}.default", _text(c), node)
            elif c.type == "namespace_import" and c.named_child_count:
                self._ref("import", module, _text(c.named_children[0]), node)
            elif c.type == "named_imports":
                for spec in c.named_children:
                    name = spec.child_by_field_name("name")
                    if spec.type == "import_specifier" and name is not None:
                        alias = spec.child_by_field_name("alias") or name
                        self._ref("import", f"{module}.{_name(name)}", _name(alias), node)

    def _export(self, node: Node) -> None:
        source = node.child_by_field_name("source")
        decl = node.child_by_field_name("declaration")
        value = node.child_by_field_name("value")
        clause = next((c for c in node.named_children if c.type == "export_clause"), None)
        if source is not None:  # re-export from another module
            module = self._module(source)
            if module is None:
                return
            ns = next((c for c in node.named_children if c.type == "namespace_export"), None)
            if clause is not None:
                for name, alias in self._specifiers(clause):
                    self._ref("import", f"{module}.{name}", alias, node)
            elif ns is not None and ns.named_child_count:
                self._ref("import", module, _name(ns.named_children[0]), node)
            else:
                self._ref("import", module, "*", node)
            return
        is_default = any(c.type == "default" for c in node.children if not c.is_named)
        if decl is not None:
            self.visit(decl)
            name = decl.child_by_field_name("name")
            if is_default and name is not None:
                self._ref("import", f"{self.module}.{_text(name)}", "default", node)
        elif value is not None:
            if value.type == "identifier":
                self._ref("import", f"{self.module}.{_text(value)}", "default", node)
            else:
                self.visit(value)
        elif clause is not None:
            for name, alias in self._specifiers(clause):
                if alias != name:
                    self._ref("import", f"{self.module}.{name}", alias, node)

    @staticmethod
    def _specifiers(clause: Node) -> list[tuple[str, str]]:
        out = []
        for spec in clause.named_children:
            name = spec.child_by_field_name("name")
            if spec.type == "export_specifier" and name is not None:
                alias = spec.child_by_field_name("alias") or name
                out.append((_name(name), _name(alias)))
        return out

    def _call(self, node: Node) -> None:
        fn = node.child_by_field_name("function")
        args = node.child_by_field_name("arguments")
        first = args.named_children[0] if args is not None and args.named_child_count else None
        if fn is not None and (fn.type == "import" or (fn.type == "identifier" and _text(fn) == "require")):
            module = self._module(first)
            if module is not None:
                self._require(node, module)
        elif fn is not None and fn.type == "super":
            self._ref("call", "super.constructor", None, node)
        else:
            target = _dotted(fn)
            if target and not target.endswith(")"):  # f()() calls a result, not a name
                self._ref("call", target, None, node)
        self.visit_children(node)

    def _require(self, call: Node, module: str) -> None:
        """require("m") / import("m"): `const x = require(..)` binds x, a destructuring binds its names."""
        parent = call.parent
        is_require = call.child_by_field_name("function").type != "import"
        if (not is_require or parent is None or parent.type != "variable_declarator"
                or parent.child_by_field_name("value") != call):
            self._ref("import", module, None, call)
            return
        pattern = parent.child_by_field_name("name")
        if pattern.type == "identifier":
            self._ref("import", module, _text(pattern), call)
        elif pattern.type == "object_pattern":
            for p in pattern.named_children:
                if p.type == "shorthand_property_identifier_pattern":
                    self._ref("import", f"{module}.{_text(p)}", _text(p), call)
                elif p.type == "pair_pattern":
                    key, val = p.child_by_field_name("key"), p.child_by_field_name("value")
                    if key is not None and val is not None and val.type == "identifier":
                        self._ref("import", f"{module}.{_name(key)}", _text(val), call)
        else:
            self._ref("import", module, None, call)


def extract(path: str, source: str | bytes, module: str) -> tuple[list[dict], list[dict]]:
    """(nodes, refs) for one JS/TS file. path is repo-relative POSIX; module from module_name()."""
    file_node = {"id": path, "kind": "file", "name": module or path, "file": path,
                 "line": 1, "signature": None, "doc": None}
    data = source.encode("utf-8") if isinstance(source, str) else source
    tree = _parser(path).parse(data)
    root = tree.root_node
    ex = _Extractor(path, module)
    try:
        ex.visit_children(root)
    except RecursionError:
        return [file_node], []
    first = next((c for c in root.named_children if c.type != "hash_bang_line"), None)
    if _is_jsdoc(first) and first.start_byte not in ex.claimed:
        file_node["doc"] = _comment_line(first)
    return [file_node, *ex.nodes], ex.refs
