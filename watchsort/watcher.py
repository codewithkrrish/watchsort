"""Watch mode: poll the folder and sort new files as they settle.

Deliberately polling, not inotify/FSEvents: it keeps the tool
dependency-free and identical on macOS, Linux and Windows. The cost
is a few seconds of delay and a tiny bit of CPU every poll — a fair
trade for a tool whose whole point is zero setup.

A file is only sorted once its size hasn't changed between two polls,
so a big download that's still writing doesn't get moved halfway
through. (In-progress extensions like ``.crdownload`` are skipped
outright by the rules module.)
"""

from __future__ import annotations

import time
from pathlib import Path

from . import journal, sorter
from .rules import Rules, is_skippable

DEFAULT_INTERVAL_SECONDS = 5


def watch(
    folder: Path,
    rules: Rules,
    interval: float = DEFAULT_INTERVAL_SECONDS,
    dry_run: bool = False,
    on_event=None,
    stop_after: int | None = None,
) -> None:
    """Poll *folder* forever, sorting new files as they settle.

    *on_event* is an optional callback receiving a short string for
    every interesting thing (used by the CLI for output). *stop_after*
    limits the loop to that many polls — only used by tests, so they
    don't have to run forever. Raises KeyboardInterrupt on Ctrl-C;
    the CLI turns that into a clean exit.
    """
    # Sort what's already there first, so watch doesn't leave a mess
    # behind while it waits for new files.
    _sort_once(folder, rules, dry_run=dry_run, on_event=on_event)

    seen: dict[Path, int] = {}  # path -> size at last poll
    reported_dry: set[Path] = set()  # dry-run files already announced
    polls = 0
    while True:
        time.sleep(interval)
        polls += 1
        for entry in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
            if not entry.is_file() or entry.is_symlink() or is_skippable(entry.name):
                continue
            size = entry.stat().st_size
            if seen.get(entry) != size:
                # Either brand new, or still growing — wait for it.
                seen[entry] = size
                continue
            seen.pop(entry, None)
            if dry_run:
                if entry not in reported_dry:
                    dest = sorter.destination_for(entry, folder, rules)
                    _emit(on_event, f"would sort {entry.name} -> {dest}")
                    reported_dry.add(entry)
                continue
            moves = sorter.plan_moves(folder, rules)
            if moves:
                done = sorter.execute_moves(moves)
                journal.record_moves(folder, done)
                for move in done:
                    _emit(on_event, f"sorted {move}")
            break  # re-scan from the top after any batch of moves
        if stop_after is not None and polls >= stop_after:
            return


def _sort_once(
    folder: Path,
    rules: Rules,
    dry_run: bool,
    on_event=None,
) -> None:
    moves = sorter.plan_moves(folder, rules)
    if not moves:
        _emit(on_event, "nothing to sort")
        return
    if dry_run:
        for move in moves:
            _emit(on_event, f"would sort {move}")
        return
    done = sorter.execute_moves(moves)
    journal.record_moves(folder, done)
    for move in done:
        _emit(on_event, f"sorted {move}")


def _emit(on_event, message: str) -> None:
    if on_event is not None:
        on_event(message)
