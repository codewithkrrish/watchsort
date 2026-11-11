"""Entry point so ``python -m watchsort`` works."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
