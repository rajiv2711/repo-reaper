# HANDOFF
Phase 1 | status: done

## Done this session
- AGENTS.md (spec + plan) created; Phase 1 ticked.
- pyproject.toml: console script `reaper` -> reaper.cli:main; deps networkx, dev extra pytest. .gitignore per spec.
- Env: conda env `repo-reaper` (Python 3.12, editable install), recreate with `conda env create -f environment.yml`.
- reaper/discover.py: list_files (in git: `git ls-files -co --exclude-standard -z`, else os.walk; SKIP_DIRS in both;
  drops symlinks and index entries missing on disk), language (by extension, "other" if unknown),
  file_info -> {lang, sha256, lines}, discover -> {path: {lang, sha256, lines}} (= graph.json `files`), count_by_language.
- reaper/cli.py: only `reaper scan <repo>` so far; add each subcommand in its own phase.
- Fixture tests/fixtures/sample_py: README.md + app/{__init__,models,utils,repository,service}.py.
  Covers module docstrings, `import os`/`import json`, absolute + relative `from x import y`, Entity -> User,
  self.log() (own method), self.describe() (base-class method), cross-file calls (normalize, validate, data_dir,
  User(), UserRepository()), `validate` defined in both app/utils.py and app/repository.py, builtins (print, isinstance).
- tests/conftest.py `sample_repo` fixture copies sample_py to tmp_path. Tests: tests/test_discovery.py, tests/test_cli.py.

## Exact next step
Phase 2: write tests/test_extract_py.py FIRST, with node counts by kind and specific refs worked out by hand
from the fixture source. Then implement reaper/extract_py.py extract(path, source, module), reaper/graph.py
(load/save .reaper/graph.json) and `reaper map`.
Note: discover() also returns non-Python files (README.md); decide whether they get file nodes.

## Blockers: none

## Note: AGENTS.md Phase 3 lists "(3) same-file name -> EXTRACTED" twice (kept verbatim); treat as one rule.

## Verify
conda run -n repo-reaper pytest -q                              -> 17 passed
conda run -n repo-reaper reaper scan tests/fixtures/sample_py   -> python 5 / markdown 1 / total 6
