"""Compatibility entrypoint; the implementation lives with the Reporter UI."""

from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.reporter.ui.app import render_app


if __name__ == "__main__":
    render_app()
