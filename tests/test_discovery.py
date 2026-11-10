import hashlib
import shutil
import subprocess

import pytest

from reaper.discover import count_by_language, discover, file_info, language, list_files

PY_FILES = [
    "app/__init__.py",
    "app/models.py",
    "app/repository.py",
    "app/service.py",
    "app/utils.py",
]


def test_lists_fixture_files(sample_repo):
    assert list_files(sample_repo) == ["README.md", *PY_FILES]


def test_discover_info(sample_repo):
    files = discover(sample_repo)
    assert list(files) == ["README.md", *PY_FILES]
    for rel, info in files.items():
        data = (sample_repo / rel).read_bytes()
        assert info["sha256"] == hashlib.sha256(data).hexdigest()
        assert info["lines"] == len(data.decode().splitlines())
    assert files["app/utils.py"]["lang"] == "python"
    assert files["app/utils.py"]["lines"] == 17
    assert files["README.md"]["lang"] == "markdown"


def test_count_by_language(sample_repo):
    assert count_by_language(discover(sample_repo)) == {"python": 5, "markdown": 1}


def test_skip_dirs(sample_repo):
    for rel in [
        "node_modules/pkg/index.js",
        ".venv/lib/site.py",
        "venv/lib/site.py",
        "app/__pycache__/models.cpython-311.pyc",
        "dist/out.py",
        "build/out.py",
        ".reaper/graph.json",
        ".git/config",
    ]:
        path = sample_repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x\n")
    assert list_files(sample_repo) == ["README.md", *PY_FILES]


@pytest.mark.parametrize(
    "path, lang",
    [("a/b.py", "python"), ("x.MD", "markdown"), ("web/app.tsx", "typescript"),
     ("Makefile", "other"), ("data.bin", "other")],
)
def test_language(path, lang):
    assert language(path) == lang


@pytest.mark.parametrize("content, lines", [(b"", 0), (b"a", 1), (b"a\n", 1), (b"a\nb", 2), (b"\n\n", 2)])
def test_line_count(tmp_path, content, lines):
    f = tmp_path / "f.txt"
    f.write_bytes(content)
    assert file_info(f)["lines"] == lines


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_git_mode_respects_gitignore(sample_repo):
    def git(*args):
        subprocess.run(["git", *args], cwd=sample_repo, check=True, capture_output=True)

    git("init", "-q")
    (sample_repo / ".gitignore").write_text("ignored.py\n")
    (sample_repo / "ignored.py").write_text("x = 1\n")
    (sample_repo / "gone.py").write_text("x = 1\n")
    git("add", "app/models.py", "gone.py")  # tracked (cached) files
    (sample_repo / "gone.py").unlink()  # still in the index, but not on disk
    assert list_files(sample_repo) == [".gitignore", "README.md", *PY_FILES]
