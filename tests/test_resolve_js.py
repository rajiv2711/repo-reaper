"""Phase 10: resolving JavaScript / TypeScript refs, plus update and TREE.txt on the JS fixture.

Expected edges are written by hand from the fixture source (tests/fixtures/sample_js/src).
"""

from reaper import outputs
from reaper.graph import build, save, update

from test_resolve import as_tuples, mini_repo

E, I, A = "EXTRACTED", "INFERRED", "AMBIGUOUS"
M, U, R, S = "src/models.ts", "src/utils.js", "src/repository.js", "src/service.ts"
C, X, P = "src/components/UserCard.tsx", "src/components/index.ts", "src/app.jsx"

FIXTURE_EDGES = {
    # imports: relative paths -> repo files; packages -> ext:<package>
    (R, "ext:node:path", "imports", E),
    (R, U, "imports", E),                       # require("./utils")
    (S, M, "imports", E),                       # default import
    (S, R, "imports", E),
    (S, U, "imports", E),                       # "./utils.js" names utils.js
    (S, "ext:uuid", "imports", E),
    (C, "ext:react", "imports", E),
    (C, U, "imports", E),                       # "../utils"
    (C, M, "imports", E),                       # import type
    (X, C, "imports", E),                       # export { default as UserCard } from "./UserCard"
    (P, C, "imports", E),                       # { UserCard } from "./components": longest module prefix
    (P, S, "imports", E),
    # inherits: extends + implements, both in the same file
    (f"{M}::User", f"{M}::Entity", "inherits", E),
    (f"{M}::User", f"{M}::Named", "inherits", E),
    # calls
    (f"{M}::User.constructor", f"{M}::Entity.constructor", "calls", I),   # super(id)
    (f"{M}::User.label", f"{M}::Entity.describe", "calls", I),            # this.describe, base method
    (f"{U}::validate", f"{U}::normalize", "calls", E),                    # same file
    (f"{R}::UserRepository.save", f"{U}::validate", "calls", E),          # require destructuring alias
    (f"{R}::UserRepository.save", f"{R}::UserRepository.count", "calls", E),
    (f"{R}::UserRepository.describe", f"{R}::UserRepository.count", "calls", E),
    (f"{S}::UserService.constructor", f"{R}::UserRepository", "calls", E),  # new UserRepository
    (f"{S}::UserService.create", f"{U}::validate", "calls", E),           # utils.validate (namespace)
    (f"{S}::UserService.create", f"{M}::User", "calls", E),               # new User: default -> User
    (f"{S}::UserService.create", f"{U}::normalize", "calls", E),          # utils.clean: renamed export
    (f"{S}::UserService.create", f"{M}::User.label", "calls", I),         # user.label: 1 candidate
    (f"{S}::UserService.create", f"{S}::UserService.log", "calls", E),    # this.log, own method
    (f"{S}::UserService.create", f"{R}::UserRepository.save", "calls", I),  # this.repo.save
    (f"{S}::UserService.log", f"{M}::Entity.describe", "calls", A),       # this.repo.describe: 2 candidates
    (f"{S}::UserService.log", f"{R}::UserRepository.describe", "calls", A),
    (f"{C}::UserCard", f"{U}::normalize", "calls", E),
    (f"{C}::UserCard", f"{M}::User.label", "calls", I),
    (f"{C}::UserCard", f"{C}::Badge", "calls", E),                        # <Badge />, same file
    (P, f"{S}::UserService", "calls", E),                                 # module level new UserService
    (f"{P}::renderAll", f"{C}::UserCard", "calls", E),                    # <UserCard />: index -> default
    (f"{P}::renderAll", f"{S}::UserService.create", "calls", I),          # service.create: 1 candidate
    # no edge: JS globals (console.*, Map, Error, TypeError), aliases outside the repo (uuid, path.join),
    # no candidate (name.trim, ....toLowerCase, this.items.set, names.map), HTML tags (<div>, <span>)
}


def test_fixture_edges(sample_js_repo):
    g = build(sample_js_repo)
    got = as_tuples(g["edges"])
    assert len(got) == len(set(got))
    assert set(got) == FIXTURE_EDGES
    ext = sorted(n["id"] for n in g["nodes"] if n["kind"] == "external")
    assert ext == ["ext:node:path", "ext:react", "ext:uuid"]


def test_update_without_change_is_identical(sample_js_repo):
    g = build(sample_js_repo)
    save(sample_js_repo, g)
    g2, changes = update(sample_js_repo)
    assert changes["added"] == changes["changed"] == changes["deleted"] == []
    assert len(changes["unchanged"]) == 7
    assert (g2["nodes"], g2["refs"], g2["edges"]) == (g["nodes"], g["refs"], g["edges"])


def test_packages_and_globals(tmp_path):
    g = mini_repo(tmp_path, {
        "a.ts": 'import x from "@scope/pkg/sub";\nimport "lodash/fp";\n'
                "class Map {}\nfunction run() { console.log(1); JSON.parse('1'); new Map(); }\n",
        "b.py": "class console:\n    def log(self):\n        pass\n",
    })
    ext = sorted(n["id"] for n in g["nodes"] if n["kind"] == "external")
    assert ext == ["ext:@scope/pkg", "ext:lodash"]
    # console.log is a JS global (no edge to b.py's console.log); a same-file class beats the global Map
    assert as_tuples(g["edges"]) == [("a.ts", "ext:@scope/pkg", "imports", E),
                                     ("a.ts", "ext:lodash", "imports", E),
                                     ("a.ts::run", "a.ts::Map", "calls", E)]


def test_imported_value_and_test_globals_give_no_guess(tmp_path):
    g = mini_repo(tmp_path, {
        "src/Select.tsx": "const Select = forwardRef(() => null);\nexport default Select;\n",
        "src/use.tsx": 'import Select from "./Select";\n'
                       "function view() { return <Select />; }\n"
                       'describe("x", () => { expect(view()).toBe(1); });\n',
        "src/other.ts": "export function Select() {}\nexport function Other() {}\n",
        "src/spec.ts": "export function describe() {}\nexport function expect() {}\n",
    })
    # <Select /> is the imported forwardRef value: no guess at other.ts::Select (rule 5);
    # describe / expect are test-runner globals, not spec.ts's functions
    assert as_tuples(g["edges"]) == [("src/use.tsx", "src/Select.tsx", "imports", E),
                                     ("src/use.tsx", "src/use.tsx::view", "calls", E)]


def test_tree_text_uses_js_keywords(sample_js_repo):
    text = outputs.tree_text(build(sample_js_repo))
    assert "src/models.ts (33 lines)\n" in text
    assert ("  interface Named  # L4\n"
            "  class Entity  # L9\n"
            "    constructor(id: number)  # L12\n"
            "    describe(): string  # L16\n"
            "  class User extends Entity implements Named  # L22\n") in text
    assert "  function normalize(name)  # L4\n" in text
    assert "def " not in text
