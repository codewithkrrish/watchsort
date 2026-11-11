"""Tests for the CLI: flags, exit codes, and end-to-end behaviour."""

from pathlib import Path

import pytest

from watchsort.cli import main
from watchsort.rules import Rules


def _touch(path: Path, content: str = "x") -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_sort_moves_files_and_reports(tmp_path: Path, capsys):
    _touch(tmp_path / "a.png")
    _touch(tmp_path / "b.pdf")
    assert main(["sort", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "sorted 2 file(s)" in out
    assert not (tmp_path / "a.png").exists()


def test_sort_dry_run_moves_nothing(tmp_path: Path, capsys):
    _touch(tmp_path / "a.png")
    assert main(["sort", str(tmp_path), "--dry-run"]) == 0
    assert (tmp_path / "a.png").exists()
    assert "would sort" in capsys.readouterr().out


def test_sort_empty_folder(tmp_path: Path, capsys):
    assert main(["sort", str(tmp_path)]) == 0
    assert "nothing to sort" in capsys.readouterr().out


def test_sort_missing_folder_is_exit_1(capsys):
    assert main(["sort", "/definitely/not/a/folder"]) == 1
    assert "watchsort: no such folder" in capsys.readouterr().err


def test_bad_flag_is_exit_2(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["sort", "--nope"])
    assert exc.value.code == 2


def test_undo_via_cli(tmp_path: Path, capsys):
    _touch(tmp_path / "a.png")
    assert main(["sort", str(tmp_path), "--quiet"]) == 0
    assert main(["undo", str(tmp_path)]) == 0
    assert (tmp_path / "a.png").exists()
    assert "restored 1 file(s)" in capsys.readouterr().out


def test_undo_with_no_journal_is_exit_1(tmp_path: Path, capsys):
    assert main(["undo", str(tmp_path)]) == 1
    assert "nothing to undo" in capsys.readouterr().err


def test_init_writes_rules_and_refuses_second_time(tmp_path: Path, capsys):
    assert main(["init", str(tmp_path)]) == 0
    rules_file = tmp_path / ".watchsort" / "rules.toml"
    assert rules_file.exists()
    # Loads back to the same defaults.
    from watchsort.rules import load_rules
    assert load_rules(rules_file).category_for("x.png") == Rules().category_for("x.png")

    assert main(["init", str(tmp_path)]) == 1
    assert "already exists" in capsys.readouterr().err

    assert main(["init", str(tmp_path), "--force"]) == 0


def test_sort_with_custom_rules(tmp_path: Path):
    rules_file = tmp_path / "rules.toml"
    rules_file.write_text('[Screenshots]\nextensions = [".png"]\n', encoding="utf-8")
    _touch(tmp_path / "shot.png")
    assert main(["sort", str(tmp_path), "--rules", str(rules_file)]) == 0
    assert list((tmp_path / "Screenshots").rglob("shot.png"))


def test_watch_sorts_new_file_and_stops(tmp_path: Path):
    # stop_after keeps the test from running forever.
    from watchsort.watcher import watch

    _touch(tmp_path / "first.png")
    messages: list[str] = []
    watch(tmp_path, Rules(), interval=0.01, on_event=messages.append, stop_after=2)
    assert not (tmp_path / "first.png").exists()

    # A file dropped in mid-watch gets sorted once it settles.
    _touch(tmp_path / "second.png")
    watch(tmp_path, Rules(), interval=0.01, on_event=messages.append, stop_after=3)
    assert not (tmp_path / "second.png").exists()
    assert any("sorted" in m for m in messages)


def test_watch_dry_run_moves_nothing(tmp_path: Path):
    from watchsort.watcher import watch

    _touch(tmp_path / "a.png")
    messages: list[str] = []
    watch(tmp_path, Rules(), interval=0.01, dry_run=True,
          on_event=messages.append, stop_after=2)
    assert (tmp_path / "a.png").exists()
    assert any("would sort" in m for m in messages)


def test_watch_bad_interval_is_exit_1(tmp_path: Path, capsys):
    assert main(["watch", str(tmp_path), "--interval", "0"]) == 1
    assert "--interval must be more than 0" in capsys.readouterr().err
