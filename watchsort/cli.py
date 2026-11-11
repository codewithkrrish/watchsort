"""Thin CLI over the watchsort modules.

All the real work lives in rules.py, sorter.py, journal.py and
watcher.py — this file only parses arguments, calls them in order,
and prints human-readable results. Exit codes: 0 ok, 1 a problem the
user can fix, 2 bad flags (argparse's default), 130 stopped with Ctrl-C.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, journal, sorter
from .errors import WatchsortError
from .rules import Rules, load_rules
from .watcher import DEFAULT_INTERVAL_SECONDS, watch

DEFAULT_FOLDER = "~/Downloads"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="watchsort",
        description=(
            "Watch a folder and sort new files into dated, type-based "
            "subfolders. Nothing is ever overwritten, and every move "
            "can be undone."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sort = sub.add_parser("sort", help="sort the files already in a folder, once")
    sort.add_argument("folder", nargs="?", default=DEFAULT_FOLDER)
    sort.add_argument("--rules", type=Path, help="TOML rules file (defaults built in)")
    sort.add_argument("--dry-run", action="store_true", help="show what would move, move nothing")
    sort.add_argument("--quiet", action="store_true", help="only print a summary line")

    watch_cmd = sub.add_parser("watch", help="keep watching a folder and sort new files as they land")
    watch_cmd.add_argument("folder", nargs="?", default=DEFAULT_FOLDER)
    watch_cmd.add_argument("--rules", type=Path, help="TOML rules file (defaults built in)")
    watch_cmd.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_SECONDS,
                           help=f"seconds between checks (default {DEFAULT_INTERVAL_SECONDS})")
    watch_cmd.add_argument("--dry-run", action="store_true", help="announce moves without making them")

    undo = sub.add_parser("undo", help="move the most recent sorted files back where they came from")
    undo.add_argument("folder", nargs="?", default=DEFAULT_FOLDER)
    undo.add_argument("--last", type=int, default=10, help="how many moves to undo (default 10)")

    init = sub.add_parser("init", help="write a starter rules.toml you can edit")
    init.add_argument("folder", nargs="?", default=DEFAULT_FOLDER)
    init.add_argument("--force", action="store_true", help="overwrite an existing rules file")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "sort":
            return cmd_sort(args)
        if args.command == "watch":
            return cmd_watch(args)
        if args.command == "undo":
            return cmd_undo(args)
        if args.command == "init":
            return cmd_init(args)
    except WatchsortError as exc:
        print(f"watchsort: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nstopped watching.", file=sys.stderr)
        return 130
    return 0


def cmd_sort(args: argparse.Namespace) -> int:
    folder = sorter.resolve_folder(args.folder)
    rules = load_rules(args.rules)
    moves = sorter.plan_moves(folder, rules)
    if not moves:
        print("nothing to sort.")
        return 0
    if args.dry_run:
        for move in moves:
            print(f"would sort {move}")
        print(f"{len(moves)} file(s) would move — nothing changed.")
        return 0
    done = sorter.execute_moves(moves)
    journal.record_moves(folder, done)
    if not args.quiet:
        for move in done:
            print(f"sorted {move}")
    print(f"sorted {len(done)} file(s) into {folder}. Undo with: watchsort undo {folder}")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    folder = sorter.resolve_folder(args.folder)
    if args.interval <= 0:
        raise WatchsortError("--interval must be more than 0")
    rules = load_rules(args.rules)
    print(f"watching {folder} (Ctrl-C to stop)...")
    watch(folder, rules, interval=args.interval, dry_run=args.dry_run,
          on_event=lambda msg: print(msg))
    return 0


def cmd_undo(args: argparse.Namespace) -> int:
    folder = sorter.resolve_folder(args.folder)
    result = journal.undo_moves(folder, args.last)
    parts = [f"restored {result.restored} file(s)"]
    if result.renamed:
        parts.append(f"{result.renamed} under a new name (original spot was taken)")
    if result.skipped_missing:
        parts.append(f"{result.skipped_missing} skipped (file was moved or deleted since)")
    print(", ".join(parts) + ".")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    folder = sorter.resolve_folder(args.folder)
    target = folder / ".watchsort" / "rules.toml"
    if target.exists() and not args.force:
        raise WatchsortError(
            f"{target} already exists — edit it directly, or re-run with --force"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    # Write via temp file + rename so a crash can't leave a half file.
    tmp = target.with_suffix(".tmp")
    tmp.write_text(Rules().to_toml(), encoding="utf-8")
    tmp.replace(target)
    print(f"wrote starter rules to {target}")
    print("edit it, then run: watchsort sort --rules " + str(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
