import shutil
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "sample_py"


@pytest.fixture
def sample_repo(tmp_path):
    """A fresh copy of tests/fixtures/sample_py; tests never touch the original."""
    dst = tmp_path / "sample_py"
    shutil.copytree(FIXTURE, dst, ignore=shutil.ignore_patterns("__pycache__", ".reaper"))
    return dst


FIXTURE_JS = Path(__file__).parent / "fixtures" / "sample_js"


@pytest.fixture
def sample_js_repo(tmp_path):
    """A fresh copy of tests/fixtures/sample_js (JavaScript + TypeScript)."""
    dst = tmp_path / "sample_js"
    shutil.copytree(FIXTURE_JS, dst, ignore=shutil.ignore_patterns(".reaper"))
    return dst
