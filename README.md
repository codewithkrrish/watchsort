# watchsort

Watch a folder, sort whatever lands in it. Point it at Downloads and
it files everything into dated, type-based subfolders — `Images/2026-11/`,
`Documents/2026-11/` — and keeps a journal so you can undo it all.

I built this because my Downloads folder is where files go to die.
Every screenshot, PDF, installer and random zip ends up in one pile,
and "I'll sort it later" never happens. watchsort is the later.

## What it does

- **Sorts once** (`sort`) or **keeps watching** (`watch`) — new files
  get filed a few seconds after they land, once they've stopped growing.
- **Dated folders** — files go into `Category/YYYY-MM/` based on when
  they were last modified, so a screenshot from March doesn't land in
  November's folder just because you only just sorted it.
- **Rules you can edit** — a small TOML file maps extensions to
  folders. Add your own categories, no code changes needed.
- **Undo** — every move is written to a journal (`.watchsort/journal.jsonl`
  inside the folder). `watchsort undo` puts files back.
- **Never overwrites** — a name clash becomes `photo (2).png`, and
  undo restores beside the original instead of clobbering it.
- **Skips what's still downloading** — `.crdownload`, `.part`, `.tmp`
  and friends are left alone, and hidden files are never touched.

## Install

Python 3.11 or newer, no other dependencies.

```bash
pip install git+https://github.com/codewithkrrish/watchsort.git
```

Or clone it and run it straight from the folder:

```bash
git clone https://github.com/codewithkrrish/watchsort.git
cd watchsort
python -m watchsort sort ~/Downloads --dry-run
```

## Usage

```bash
# See what would happen, without moving anything
watchsort sort ~/Downloads --dry-run

# Sort what's already there
watchsort sort ~/Downloads

# Keep watching — sorts new files as they settle (Ctrl-C to stop)
watchsort watch ~/Downloads

# Put the last 10 moves back
watchsort undo ~/Downloads

# Undo just the last 3
watchsort undo ~/Downloads --last 3

# Write a starter rules file to edit
watchsort init ~/Downloads
```

Example output:

```
$ watchsort sort ~/Downloads --dry-run
would sort screenshot.png -> Images/2026-11/screenshot.png
would sort invoice.pdf -> Documents/2026-11/invoice.pdf
would sort setup.dmg -> Installers/2026-11/setup.dmg
3 file(s) would move — nothing changed.
```

## Rules file

`watchsort init` writes a starter `rules.toml` into
`<folder>/.watchsort/`. It looks like this:

```toml
[settings]
date_folders = true

[Images]
extensions = [".png", ".jpg", ".jpeg", ".gif", ".webp"]

[Documents]
extensions = [".pdf", ".doc", ".docx", ".txt", ".md"]
```

Category names become folder names. Anything that matches no
category lands in `Other`. Set `date_folders = false` if you'd
rather have flat `Images/` folders with no `YYYY-MM` inside.

## How watch mode works

It polls the folder every 5 seconds (`--interval` to change that).
Polling, not filesystem events — that keeps it dependency-free and
the same on macOS, Linux and Windows. The trade-off is a few seconds
of delay. A file is only sorted once its size is the same across two
polls, so a big download that's still writing doesn't get moved
halfway through.

When you start `watch`, it first sorts whatever is already in the
folder, then keeps watching.

## Project structure

```
watchsort/
  __init__.py    version + package docstring
  cli.py         argument parsing, exit codes, output
  rules.py       TOML rules, defaults, skip logic
  sorter.py      planning moves, collision handling
  journal.py     undo journal (JSON lines, atomic rewrite)
  watcher.py     the polling loop
tests/           pytest — rules, sorter, journal, CLI, watcher
examples/
  rules.toml     a starter rules file
```

## Limitations

- **Polling, not instant.** Files take up to one poll interval
  (default 5s) to get sorted. If you need instant, this isn't the tool.
- **Top level only.** Subfolders are never touched — watchsort only
  sorts loose files, so it can't rearrange something you already
  organised on purpose.
- **By extension, not by content.** A `.pdf` renamed from a `.zip`
  still goes to Documents. It doesn't open files to check what they are.
- **Dates come from modified time.** If a file's mtime is wrong
  (say, extracted from an old archive), it lands in the wrong month.
- **No Windows service / launchd setup yet.** Right now you run
  `watch` yourself, or wire it into your own startup. That's next
  on my list.

## Running the tests

```bash
pip install pytest
python -m pytest
```

## License

MIT — see [LICENSE](LICENSE).

## Author

Krrish — [github.com/codewithkrrish](https://github.com/codewithkrrish)
