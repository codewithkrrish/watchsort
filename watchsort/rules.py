"""Sorting rules: which extension goes in which folder.

Rules live in a small TOML file so you can edit them by hand — no need
to touch the code to teach watchsort a new file type. If no rules file
is given (or it doesn't exist yet), the built-in defaults are used.

Example rules file::

    [settings]
    date_folders = true

    [Images]
    extensions = [".png", ".jpg", ".jpeg", ".gif", ".webp"]

    [Documents]
    extensions = [".pdf", ".docx", ".txt", ".md"]

A category is just a TOML table whose key is the folder name and whose
``extensions`` list holds the extensions (with the leading dot) that
belong there. Anything that matches no category lands in ``Other``.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from .errors import RulesError

DEFAULT_CATEGORY = "Other"

# Extensions that mean "this file is still downloading". Sorting one of
# these would move a half-written file and confuse the browser, so they
# are always skipped.
IN_PROGRESS_SUFFIXES = frozenset(
    {".crdownload", ".part", ".tmp", ".download", ".!ut", ".opdownload"}
)

DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "Images": [
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg",
        ".heic", ".tif", ".tiff", ".raw",
    ],
    "Documents": [
        ".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt", ".epub",
    ],
    "Spreadsheets": [".csv", ".xls", ".xlsx", ".ods", ".numbers"],
    "Presentations": [".ppt", ".pptx", ".key", ".odp"],
    "Videos": [".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"],
    "Audio": [".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"],
    "Archives": [".zip", ".tar", ".gz", ".7z", ".rar", ".bz2", ".xz"],
    "Code": [
        ".py", ".js", ".ts", ".html", ".css", ".json", ".java",
        ".c", ".cpp", ".go", ".rs", ".sh",
    ],
    "Installers": [".dmg", ".exe", ".msi", ".pkg", ".deb", ".appimage"],
}

DEFAULT_DATE_FOLDERS = True


class Rules:
    """The effective sorting rules: categories plus settings."""

    def __init__(
        self,
        categories: dict[str, list[str]] | None = None,
        date_folders: bool = DEFAULT_DATE_FOLDERS,
    ) -> None:
        self.categories = categories if categories is not None else {
            name: list(exts) for name, exts in DEFAULT_CATEGORIES.items()
        }
        self.date_folders = date_folders
        # Extension (lowercased, with dot) -> category, built once so
        # lookups stay cheap even with a big custom rules file.
        self._by_extension: dict[str, str] = {}
        for category, extensions in self.categories.items():
            for ext in extensions:
                self._by_extension[ext.lower()] = category

    def category_for(self, filename: str) -> str:
        """Return the folder a file belongs in, or ``Other``."""
        return self._by_extension.get(Path(filename).suffix.lower(), DEFAULT_CATEGORY)

    def to_toml(self) -> str:
        """Render the rules back out as TOML (used by ``watchsort init``)."""
        lines = [
            "# watchsort rules — edit freely, then point watchsort at this file",
            "# with --rules. Categories are folder names; extensions need the dot.",
            "",
            "[settings]",
            f"date_folders = {'true' if self.date_folders else 'false'}",
            "",
        ]
        for category, extensions in self.categories.items():
            quoted = ", ".join(f'"{ext}"' for ext in extensions)
            lines.append(f"[{category}]")
            lines.append(f"extensions = [{quoted}]")
            lines.append("")
        return "\n".join(lines)


def load_rules(path: Path | None) -> Rules:
    """Load rules from *path*, or return the defaults if *path* is None.

    Raises RulesError with a plain message if the file is unreadable,
    not valid TOML, or shaped wrong — the CLI turns that into stderr
    text, not a traceback.
    """
    if path is None:
        return Rules()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise RulesError(f"can't read rules file {path}: {exc.strerror}") from exc
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise RulesError(f"{path} is not valid TOML: {exc}") from exc
    return _rules_from_data(data, path)


def _rules_from_data(data: dict, path: Path) -> Rules:
    if not isinstance(data, dict):
        raise RulesError(f"{path}: top level must be TOML tables, not {type(data).__name__}")

    settings = data.get("settings", {})
    if not isinstance(settings, dict):
        raise RulesError(f"{path}: [settings] must be a table")
    date_folders = settings.get("date_folders", DEFAULT_DATE_FOLDERS)
    if not isinstance(date_folders, bool):
        raise RulesError(f"{path}: settings.date_folders must be true or false")

    categories: dict[str, list[str]] = {}
    for key, value in data.items():
        if key == "settings":
            continue
        if not isinstance(value, dict) or not isinstance(value.get("extensions"), list):
            raise RulesError(
                f"{path}: [{key}] must be a table with an 'extensions' list"
            )
        extensions = value["extensions"]
        if not all(isinstance(ext, str) and ext.startswith(".") for ext in extensions):
            raise RulesError(
                f"{path}: [{key}].extensions must be strings starting with '.'"
            )
        categories[key] = list(extensions)

    if not categories:
        raise RulesError(f"{path}: no categories defined — add at least one table")
    return Rules(categories=categories, date_folders=date_folders)


def is_skippable(filename: str) -> bool:
    """True for files watchsort should never touch.

    Hidden files (dotfiles) and in-progress downloads are left alone.
    """
    name = Path(filename).name
    if name.startswith("."):
        return True
    return Path(filename).suffix.lower() in IN_PROGRESS_SUFFIXES
