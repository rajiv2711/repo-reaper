"""Phase 10: JavaScript / TypeScript extraction (tree-sitter).

Expected values are written by hand from the fixture source (tests/fixtures/sample_js/src).
"""

from collections import Counter
from pathlib import Path

from reaper.extract_js import extract, module_name

FIX = Path(__file__).parent / "fixtures" / "sample_js"
M, U, R, S = "src/models.ts", "src/utils.js", "src/repository.js", "src/service.ts"
C, X, P = "src/components/UserCard.tsx", "src/components/index.ts", "src/app.jsx"
ALL = (M, U, R, S, C, X, P)


def ex(rel):
    return extract(rel, (FIX / rel).read_bytes(), module_name(rel))


def nodes_of(rel):
    return {n["id"]: n for n in ex(rel)[0]}


def refs_of(rel, kind):
    return [(r["src"], r["target"], r["alias"]) if kind == "import" else (r["src"], r["target"])
            for r in ex(rel)[1] if r["kind"] == kind]


def test_module_names():
    assert module_name(M) == "models"
    assert module_name(X) == "components"
    assert module_name(C) == "components.UserCard"
    assert module_name(P) == "app"
    assert module_name("lib/types.d.ts") == "lib.types"
    assert module_name("index.js") == "index"
    assert module_name("pkg/foo.service.mjs") == "pkg.foo.service"


def test_node_counts():
    counts = Counter(n["kind"] for rel in ALL for n in ex(rel)[0])
    assert counts == {"file": 7, "class": 5, "function": 5, "method": 11}


def test_node_ids_per_file():
    assert set(nodes_of(M)) == {M, f"{M}::Named", f"{M}::Entity", f"{M}::Entity.constructor",
                                f"{M}::Entity.describe", f"{M}::User", f"{M}::User.constructor",
                                f"{M}::User.label"}  # fields (id: number) are not nodes
    assert set(nodes_of(U)) == {U, f"{U}::normalize", f"{U}::validate"}
    assert set(nodes_of(R)) == {R, f"{R}::UserRepository", f"{R}::UserRepository.constructor",
                                f"{R}::UserRepository.save", f"{R}::UserRepository.count",
                                f"{R}::UserRepository.describe"}
    assert set(nodes_of(S)) == {S, f"{S}::UserService", f"{S}::UserService.constructor",
                                f"{S}::UserService.create", f"{S}::UserService.log"}
    assert set(nodes_of(C)) == {C, f"{C}::UserCard", f"{C}::Badge"}
    assert set(nodes_of(X)) == {X}
    assert set(nodes_of(P)) == {P, f"{P}::renderAll"}


def test_node_details():
    def detail(rel, node_id):
        n = nodes_of(rel)[node_id]
        return n["kind"], n["name"], n["line"], n["signature"], n["doc"]

    assert detail(M, M) == ("file", "models", 1, None, "Domain models.")
    assert detail(M, f"{M}::Named") == ("class", "Named", 4, "interface Named", "Anything with a display name.")
    assert detail(M, f"{M}::User") == ("class", "User", 22, "User extends Entity implements Named",
                                       "A user of the system.")
    assert detail(M, f"{M}::Entity.describe") == ("method", "describe", 16, "describe(): string", None)
    assert detail(M, f"{M}::User.constructor") == ("method", "constructor", 25,
                                                   "constructor(id: number, name: string)", None)
    assert detail(U, f"{U}::normalize") == ("function", "normalize", 4, "normalize(name)",
                                            "Trim and lowercase a name.")
    assert detail(U, f"{U}::validate") == ("function", "validate", 9, "validate(name)",
                                           "True when a name is usable.")
    assert detail(R, R) == ("file", "repository", 1, None, "Stores users in memory.")
    assert detail(R, f"{R}::UserRepository.save") == ("method", "save", 13, "save(user)",
                                                      "Save one user; returns the new count.")
    assert detail(S, f"{S}::UserService.create") == ("method", "create", 16, "create(name: string): User",
                                                     "Create and save a user.")
    assert detail(S, f"{S}::UserService.log") == ("method", "log", 26, "log(message: string): void", None)
    assert detail(C, C) == ("file", "components.UserCard", 1, None, "Renders one user.")
    assert detail(C, f"{C}::UserCard") == ("function", "UserCard", 8, "UserCard({ user }: { user: User })",
                                           "Card showing a user's label.")
    assert detail(X, X) == ("file", "components", 1, None, "Public components.")
    assert detail(P, f"{P}::renderAll") == ("function", "renderAll", 8, "renderAll(names)",
                                            "Render one card per name.")


def test_import_refs():
    assert refs_of(M, "import") == [(M, "models.User", "default")]          # export default class User
    assert refs_of(U, "import") == [(U, "utils.normalize", "clean")]        # export { normalize as clean }
    assert refs_of(R, "import") == [(R, "node:path", "path"), (R, "utils.validate", "validate")]
    assert refs_of(S, "import") == [(S, "models.default", "User"),
                                    (S, "repository.UserRepository", "UserRepository"),
                                    (S, "utils", "utils"),                  # "./utils.js" -> utils
                                    (S, "uuid.v4", "uuid")]
    assert refs_of(C, "import") == [(C, "react.default", "React"),
                                    (C, "utils.normalize", "normalize"),
                                    (C, "models.default", "User"),          # ./card.css skipped
                                    (C, "components.UserCard.UserCard", "default")]  # export default function
    assert refs_of(X, "import") == [(X, "components.UserCard.default", "UserCard")]
    assert refs_of(P, "import") == [(P, "components.UserCard", "UserCard"),
                                    (P, "service.UserService", "UserService")]
    lines = {r["target"]: r["line"] for r in ex(S)[1] if r["kind"] == "import"}
    assert lines["uuid.v4"] == 5


def test_call_refs():
    assert refs_of(M, "call") == [(f"{M}::User.constructor", "super.constructor"),
                                  (f"{M}::User.label", "this.describe")]
    assert set(refs_of(U, "call")) == {(f"{U}::normalize", "name.trim().toLowerCase"),
                                       (f"{U}::normalize", "name.trim"),
                                       (f"{U}::validate", "console.warn"),
                                       (f"{U}::validate", "normalize")}
    ctor, save, desc = (f"{R}::UserRepository.{m}" for m in ("constructor", "save", "describe"))
    assert set(refs_of(R, "call")) == {(ctor, "path.join"), (ctor, "Map"), (save, "validate"),
                                       (save, "Error"), (save, "this.items.set"), (save, "this.count"),
                                       (desc, "this.count")}              # require() is not a call ref
    ctor, create, log = (f"{S}::UserService.{m}" for m in ("constructor", "create", "log"))
    assert set(refs_of(S, "call")) == {(ctor, "UserRepository"), (create, "utils.validate"),
                                       (create, "TypeError"), (create, "User"), (create, "uuid"),
                                       (create, "utils.clean"), (create, "this.log"),
                                       (create, "user.label"), (create, "this.repo.save"),
                                       (log, "console.log"), (log, "this.repo.describe")}
    assert set(refs_of(C, "call")) == {(f"{C}::UserCard", "normalize"), (f"{C}::UserCard", "user.label"),
                                       (f"{C}::UserCard", "Badge")}       # <div>, <span>: no ref
    assert refs_of(X, "call") == []
    assert set(refs_of(P, "call")) == {(P, "UserService"), (f"{P}::renderAll", "names.map"),
                                       (f"{P}::renderAll", "UserCard"),
                                       (f"{P}::renderAll", "service.create")}


def test_inherit_refs():
    assert refs_of(M, "inherit") == [(f"{M}::User", "Entity"), (f"{M}::User", "Named")]
    assert refs_of(S, "inherit") == []


MORE = b"""\
import "./side";
import x from "@scope/pkg/sub";
import y from "../../outside";
export * from "./all";
export * as ns from "./ns";
const lazy = import("./lazy");
require("./bare");
/** Gen doc. */
export async function* gen(a) {}
const Mixed = class extends Base {};
abstract class Shape { abstract area(): number; }
class Btn { handle = async (e) => { this.go(e); }; go(e) { obj[k](); f()(); } }
function outer() { function inner() {} const v = function () {}; }
const f = x => x;
export default outer;
"""


def test_more_forms():
    nodes, refs = extract("lib/mod.ts", MORE, "lib.mod")
    sigs = {n["id"].partition("::")[2]: (n["kind"], n["signature"]) for n in nodes if n["kind"] != "file"}
    assert sigs == {
        "gen": ("function", "async *gen(a)"),
        "Mixed": ("class", "Mixed extends Base"),
        "Shape": ("class", "Shape"),                 # abstract method signature: no node
        "Btn": ("class", "Btn"),
        "Btn.handle": ("method", "async handle(e)"),
        "Btn.go": ("method", "go(e)"),
        "outer": ("function", "outer()"),
        "outer.inner": ("function", "inner()"),
        "outer.v": ("function", "v()"),
        "f": ("function", "f(x)"),
    }
    assert [n["doc"] for n in nodes if n["name"] == "gen"] == ["Gen doc."]
    imports = [(r["target"], r["alias"]) for r in refs if r["kind"] == "import"]
    assert imports == [("lib.side", None), ("@scope/pkg.sub.default", "x"),  # ../../outside leaves the repo
                       ("lib.all", "*"), ("lib.ns", "ns"), ("lib.lazy", None), ("lib.bare", None),
                       ("lib.mod.outer", "default")]
    assert [(r["src"], r["target"]) for r in refs if r["kind"] == "inherit"] == [("lib/mod.ts::Mixed", "Base")]
    calls = [(r["src"], r["target"]) for r in refs if r["kind"] == "call"]
    assert calls == [("lib/mod.ts::Btn.handle", "this.go"),
                     ("lib/mod.ts::Btn.go", "f")]   # obj[k](): no ref; f()(): only the inner f()


def test_parse_error_gives_file_node_only():
    nodes, refs = extract("bad.js", b"function (\n", "bad")
    assert nodes == [{"id": "bad.js", "kind": "file", "name": "bad", "file": "bad.js", "line": 1,
                      "signature": None, "doc": None}]
    assert refs == []


def test_unparsed_code_is_skipped_rest_extracted():
    src = b"function a() {}\n}\nfunction b() { a(); }\n"   # stray "}" -> one ERROR node
    nodes, refs = extract("u.ts", src, "u")
    assert [n["id"] for n in nodes] == ["u.ts", "u.ts::a", "u.ts::b"]
    assert [(r["src"], r["target"]) for r in refs] == [("u.ts::b", "a")]


def test_anonymous_class_methods_are_not_functions():
    src = b"module.exports = class { save() { log(); } };\nconst o = { m() {} };\n"
    nodes, refs = extract("r.js", src, "r")
    assert [n["id"] for n in nodes] == ["r.js"]
    assert [(r["src"], r["target"]) for r in refs] == [("r.js", "log")]


def test_src_specifier_is_a_repo_path():
    _, refs = extract("src/a/b.ts", b'import x from "src/models";\nimport "src/styles.css";\n', "a.b")
    assert [(r["target"], r["alias"]) for r in refs] == [("models.default", "x")]  # asset skipped


def test_end_lines():
    """Class/function/method nodes carry end_line; file nodes do not (counted by hand)."""
    def span(rel, node_id):
        n = nodes_of(rel)[node_id]
        return n["line"], n["end_line"]

    assert span(M, f"{M}::Named") == (4, 6)
    assert span(M, f"{M}::Entity") == (9, 19)
    assert span(M, f"{M}::Entity.describe") == (16, 18)
    assert span(M, f"{M}::User") == (22, 33)
    assert span(M, f"{M}::User.constructor") == (25, 28)
    assert span(U, f"{U}::normalize") == (4, 6)
    assert span(U, f"{U}::validate") == (9, 15)
    assert span(C, f"{C}::UserCard") == (8, 15)
    assert "end_line" not in nodes_of(M)[M]
