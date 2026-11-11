"""The undo journal: a plain JSON-lines log of every move.

One line per move, newest last::

    {"moved_at": "2026-11-11T09:30:00", "src": "...", "dest": "..."}

``watchsort undo`` walks the newest entries first and moves files back.
The journal lives in a ``.watchsort`` folder inside the watched folder,
so it travels with the folder and never needs a global database. (It's
a dotfolder, so the sorter skips it when scanning.)

Writes are append-only; undo rewrites the file via temp file + rename
so a crash can't leave a half-written journal behind.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .errors import JournalError
from .sorter import Move

STATE_DIRNAME = ".watchsort"
JOURNAL_FILENAME = "journal.jsonl"


@dataclass(frozen=True)
class JournalEntry:
    """One recorded move."""

    moved_at: str
    source: Path
    destination: Path

    def to_line(self) -> str:
        return json.dumps(
            {
                "moved_at": self.moved_at,
                "src": str(self.source),
                "dest": str(self.destination),
            }
        )

    @classmethod
    def from_line(cls, line: str) -> "JournalEntry":
        data = json.loads(line)
        return cls(
            moved_at=data["moved_at"],
            source=Path(data["src"]),
            destination=Path(data["dest"]),
        )


def journal_path(folder: Path) -> Path:
    """Where the journal for *folder* lives."""
    return folder / STATE_DIRNAME / JOURNAL_FILENAME


def record_moves(folder: Path, moves: list[Move]) -> None:
    """Append *moves* to the folder's journal (creates it if needed)."""
    if not moves:
        return
    path = journal_path(folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now().isoformat(timespec="seconds")
    lines = "".join(
        JournalEntry(moved_at=now, source=m.source, destination=m.destination).to_line()
        + "\n"
        for m in moves
    )
    # Plain append: each line is written in one go, and a crash mid-run
    # can only lose the tail, never corrupt earlier entries.
    with path.open("a", encoding="utf-8") as handle:
        handle.write(lines)


def read_entries(folder: Path) -> list[JournalEntry]:
    """All journal entries for *folder*, oldest first."""
    path = journal_path(folder)
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise JournalError(f"can't read journal {path}: {exc.strerror}") from exc
    entries: list[JournalEntry] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            entries.append(JournalEntry.from_line(line))
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise JournalError(f"journal {path} is corrupt: {exc}") from exc
    return entries


@dataclass
class UndoResult:
    """What ``undo_moves`` did, in plain counts for the CLI to report."""

    restored: int = 0
    skipped_missing: int = 0  # destination file gone (user moved/deleted it)
    renamed: int = 0  # restored under a new name because the spot was taken


def undo_moves(folder: Path, count: int) -> UndoResult:
    """Undo the newest *count* moves for *folder*.

    Moves files back to where they came from. If the original spot is
    now occupied, the file is restored next to it as ``name (2).ext``
    instead of overwriting — undo should never destroy anything either.
    Entries that were undone are removed from the journal; entries for
    files that no longer exist at their destination are also dropped,
    since there's nothing left to undo for them.
    """
    if count <= 0:
        raise JournalError("--last must be at least 1")
    entries = read_entries(folder)
    if not entries:
        raise JournalError(f"nothing to undo — no journal in {folder}")
    if count > len(entries):
        count = len(entries)

    to_undo = entries[-count:]
    remaining = entries[:-count]
    result = UndoResult()

    for entry in reversed(to_undo):
        if not entry.destination.exists():
            result.skipped_missing += 1
            continue
        target = entry.source
        if target.exists():
            # Original spot taken: restore beside it, don't overwrite.
            target = _free_name(target)
            result.renamed += 1
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(entry.destination, target)
        except OSError:
            shutil.move(str(entry.destination), str(target))
        result.restored += 1
        _prune_empty_parents(entry.destination.parent, folder)

    _rewrite_journal(folder, remaining)
    return result


def _free_name(path: Path) -> Path:
    stem, suffix = path.stem, path.suffix
    n = 2
    while True:
        candidate = path.with_name(f"{stem} ({n}){suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def _prune_empty_parents(start: Path, stop_at: Path) -> None:
    """Remove empty category/month folders left behind after an undo."""
    current = start
    while current != stop_at and current.is_relative_to(stop_at):
        try:
            current.rmdir()  # only succeeds when empty
        except OSError:
            break
        current = current.parent


def _rewrite_journal(folder: Path, entries: list[JournalEntry]) -> None:
    path = journal_path(folder)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(entry.to_line() + "\n")
    os.replace(tmp, path)
