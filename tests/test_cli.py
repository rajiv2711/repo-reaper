import pytest

from reaper.cli import main


def test_scan_prints_counts(sample_repo, capsys):
    assert main(["scan", str(sample_repo)]) == 0
    lines = [line.split() for line in capsys.readouterr().out.splitlines()]
    assert lines == [["python", "5"], ["markdown", "1"], ["total", "6"]]


def test_scan_missing_dir(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["scan", str(tmp_path / "nope")])
    assert exc.value.code == 2
    assert "not a directory" in capsys.readouterr().err
