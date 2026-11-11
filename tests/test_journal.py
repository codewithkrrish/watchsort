"""Tests for the undo journal."""

from pathlib import Path

import pytest

from watchsort import journal
from watchsort.errors import JournalError
from watchsort.sorter import Move


def _make_moved_file(tmp_path: Path, name: str = "photo.png") -> Move:
    dest_dir = tmp_path / "Images" / "2026-11"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name
    dest.write_text("data", encoding="utf-8")
    return Move(source=tmp_path / name, destination=dest)


def test_record_and_read_roundtrip(tmp_path: Path):
    move = _make_moved_file(tmp_path)
    journal.record_moves(tmp_path, [move])
    entries = journal.read_entries(tmp_path)
    assert len(entries) == 1
    assert entries[0].source == move.source
    assert entries[0].destination == move.destination


def test_read_empty_journal(tmp_path: Path):
    assert journal.read_entries(tmp_path) == []


def test_undo_restores_file(tmp_path: Path):
    move = _make_moved_file(tmp_path)
    journal.record_moves(tmp_path, [move])
    result = journal.undo_moves(tmp_path, 1)
    assert result.restored == 1
    assert (tmp_path / "photo.png").exists()
    assert not move.destination.exists()
    assert journal.read_entries(tmp_path) == []


def test_undo_only_last_n(tmp_path: Path):
    first = _make_moved_file(tmp_path, "one.png")
    second = _make_moved_file(tmp_path, "two.png")
    journal.record_moves(tmp_path, [first, second])
    result = journal.undo_moves(tmp_path, 1)
    assert result.restored == 1
    assert (tmp_path / "two.png").exists()
    assert not (tmp_path / "one.png").exists()
    assert len(journal.read_entries(tmp_path)) == 1


def test_undo_skips_file_deleted_since(tmp_path: Path):
    move = _make_moved_file(tmp_path)
    journal.record_moves(tmp_path, [move])
    move.destination.unlink()  # user deleted it meanwhile
    result = journal.undo_moves(tmp_path, 1)
    assert result.restored == 0
    assert result.skipped_missing == 1


def test_undo_never_overwrites_original_spot(tmp_path: Path):
    move = _make_moved_file(tmp_path)
    journal.record_moves(tmp_path, [move])
    # A new file with the same name appeared where the old one was.
    (tmp_path / "photo.png").write_text("new file", encoding="utf-8")
    result = journal.undo_moves(tmp_path, 1)
    assert result.restored == 1
    assert result.renamed == 1
    assert (tmp_path / "photo.png").read_text() == "new file"
    assert (tmp_path / "photo (2).png").read_text() == "data"


def test_undo_with_no_journal_is_an_error(tmp_path: Path):
    with pytest.raises(JournalError, match="nothing to undo"):
        journal.undo_moves(tmp_path, 5)


def test_undo_prunes_empty_folders(tmp_path: Path):
    move = _make_moved_file(tmp_path)
    journal.record_moves(tmp_path, [move])
    journal.undo_moves(tmp_path, 1)
    assert not (tmp_path / "Images").exists()


def test_corrupt_journal_is_an_error(tmp_path: Path):
    path = journal.journal_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("this is not json\n", encoding="utf-8")
    with pytest.raises(JournalError, match="corrupt"):
        journal.read_entries(tmp_path)


def test_undo_count_larger_than_journal_undoes_all(tmp_path: Path):
    move = _make_moved_file(tmp_path)
    journal.record_moves(tmp_path, [move])
    result = journal.undo_moves(tmp_path, 99)
    assert result.restored == 1
