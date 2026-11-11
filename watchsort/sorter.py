"""Decide where files go, and move them there.

Kept separate from the CLI on purpose: the sorting logic is the part
worth testing, and it shouldn't know anything about argparse.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .errors import FolderError
from .rules import Rules, is_skippable

# "photo (2).png" — the number goes before the extension, the way
# Finder and Explorer do it, so it still opens with a double-click.
COLLISION_TEMPLATE = " ({n})"


@dataclass(frozen=True)
class Move:
    """One planned file move: from here, to there."""

    source: Path
    destination: Path

    def __str__(self) -> str:
        return f"{self.source.name} -> {self.destination}"


def resolve_folder(folder: str | Path) -> Path:
    """Turn user input into an existing, readable directory."""
    path = Path(folder).expanduser()
    if not path.exists():
        raise FolderError(f"no such folder: {path}")
    if not path.is_dir():
        raise FolderError(f"not a folder: {path}")
    if not os.access(path, os.R_OK | os.W_OK):
        raise FolderError(f"can't read/write folder: {path}")
    return path.resolve()


def destination_for(file: Path, folder: Path, rules: Rules) -> Path:
    """Where *file* belongs inside *folder* under *rules*.

    Dated subfolders come from the file's last-modified time, so a
    screenshot from last month doesn't land in this month's folder
    just because you only just sorted it.
    """
    category = rules.category_for(file.name)
    target_dir = folder / category
    if rules.date_folders:
        month = datetime.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m")
        target_dir = target_dir / month
    return target_dir / file.name


def plan_moves(folder: Path, rules: Rules) -> list[Move]:
    """List the moves for every sortable top-level file in *folder*.

    Only the top level is sorted — recursing into subfolders would
    rearrange things the user already organised, which is not our call.
    Files already inside a category folder are left alone.
    """
    moves: list[Move] = []
    # Track destinations claimed by earlier moves in this run so two
    # files with the same name don't get planned onto each other.
    claimed: set[Path] = set()
    for entry in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_file() or entry.is_symlink():
            continue
        if is_skippable(entry.name):
            continue
        dest = destination_for(entry, folder, rules)
        dest = _free_name(dest, claimed)
        claimed.add(dest)
        moves.append(Move(source=entry, destination=dest))
    return moves


def _free_name(dest: Path, claimed: set[Path]) -> Path:
    """If *dest* is taken, find the next free ``name (2).ext`` variant."""
    if not dest.exists() and dest not in claimed:
        return dest
    stem, suffix = dest.stem, dest.suffix
    n = 2
    while True:
        candidate = dest.with_name(f"{stem}{COLLISION_TEMPLATE.format(n=n)}{suffix}")
        if not candidate.exists() and candidate not in claimed:
            return candidate
        n += 1


def execute_moves(moves: list[Move]) -> list[Move]:
    """Carry out *moves*, creating target folders as needed.

    Returns the moves that actually happened, so the caller can journal
    exactly those. A move that fails mid-run stops the run with the
    error — the journal only ever records completed moves, which is
    what makes undo trustworthy.
    """
    done: list[Move] = []
    for move in moves:
        move.destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Same-filesystem rename: atomic, no half-moved file.
            os.replace(move.source, move.destination)
        except OSError:
            # Different filesystem (rare inside one folder tree, but
            # possible with symlinked subfolders): copy then delete.
            shutil.move(str(move.source), str(move.destination))
        done.append(move)
    return done
