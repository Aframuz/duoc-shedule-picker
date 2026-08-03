"""PyInstaller entry point.

The frozen build runs its entry script as a top-level module, so
``schedule_picker/__main__.py`` cannot be used directly — its relative imports
have no parent package. This wrapper imports absolutely instead.
"""

from schedule_picker.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
