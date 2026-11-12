"""List a repository's files with language, sha256 and line count.

Inside a git work tree the file list comes from
`git ls-files -co --exclude-standard` (tracked + untracked, minus ignored);
otherwise from os.walk. SKIP_DIRS are dropped in both modes.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from collections import Counter
from pathlib import Path

SKIP_DIRS = frozenset(
    {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".reaper"}
)

LANGUAGES = {
    ".py": "python", ".pyi": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".go": "go", ".rs": "rust", ".java": "java", ".kt": "kotlin", ".scala": "scala",
    ".rb": "ruby", ".php": "php", ".swift": "swift", ".cs": "csharp",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp",
    ".sh": "shell", ".bash": "shell", ".sql": "sql",
    ".html": "html", ".css": "css",
    ".md": "markdown", ".rst": "rst", ".txt": "text",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
}
OTHER = "other"


def language(path: str) -> str:
    """Language name for a path, by file extension ("other" if unknown)."""
    return LANGUAGES.get(os.path.splitext(path)[1].lower(), OTHER)


def file_info(path: str | os.PathLike) -> dict:
    """{lang, sha256, lines} for one file. Reads in chunks, so size doesn't matter."""
    digest = hashlib.sha256()
    lines = 0
    last = b""
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            digest.update(chunk)
            lines += chunk.count(b"\n")
            last = chunk[-1:]
    if last and last != b"\n":
        lines += 1  # final line without a trailing newline
    return {"lang": language(os.fspath(path)), "sha256": digest.hexdigest(), "lines": lines}


def _skipped(rel: str) -> bool:
    return any(part in SKIP_DIRS for part in rel.split("/")[:-1])


def _git_files(root: Path) -> list[str] | None:
    """Paths from git relative to root, or None if root is not in a git work tree."""
    try:
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=root, capture_output=True, text=True,
        )
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return None
        out = subprocess.run(
            ["git", "ls-files", "-co", "--exclude-standard", "-z"],
            cwd=root, capture_output=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None  # git missing or failing: fall back to os.walk
    return [p for p in out.stdout.decode("utf-8", "surrogateescape").split("\0") if p]


def _walk_files(root: Path) -> list[str]:
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel_dir = Path(dirpath).relative_to(root)
        found.extend((rel_dir / name).as_posix() for name in filenames)
    return found


def list_files(root: str | os.PathLike, exclude: tuple[str, ...] = ()) -> list[str]:
    """Sorted, de-duplicated relative POSIX paths of regular files under root.

    `exclude`: relative POSIX dirs to leave out (e.g. an output dir inside the repo)."""
    root = Path(root).resolve()
    candidates = _git_files(root)
    if candidates is None:
        candidates = _walk_files(root)
    result = set()
    prefixes = tuple(d.rstrip("/") + "/" for d in exclude)
    for rel in candidates:
        if _skipped(rel) or rel.startswith(prefixes):
            continue
        full = root / rel
        # git -c also lists files deleted from disk; symlinks could point outside root.
        if full.is_symlink() or not full.is_file():
            continue
        result.add(rel)
    return sorted(result)


def discover(root: str | os.PathLike, exclude: tuple[str, ...] = ()) -> dict[str, dict]:
    """{relative path: {lang, sha256, lines}} for every file in the repo, sorted by path."""
    root = Path(root).resolve()
    files = {}
    for rel in list_files(root, exclude):
        try:
            files[rel] = file_info(root / rel)
        except OSError:
            continue  # unreadable (permissions, vanished mid-scan): leave it out
    return files


def count_by_language(files: dict[str, dict]) -> dict[str, int]:
    """{lang: file count}, most common first, ties by name."""
    counts = Counter(info["lang"] for info in files.values())
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
