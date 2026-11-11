"""Error types for watchsort.

One base class, a few specific ones, so the CLI can print a plain
English message and exit 1 instead of dumping a traceback on the user.
"""


class WatchsortError(Exception):
    """Something went wrong that the user can act on."""


class FolderError(WatchsortError):
    """The folder to sort is missing, not a folder, or not readable."""


class RulesError(WatchsortError):
    """The rules file exists but can't be read or doesn't make sense."""


class JournalError(WatchsortError):
    """The undo journal is missing or unreadable."""
