#!/usr/bin/env python3
"""Compatibility wrapper for the AI Web Crawler CLI."""
from __future__ import annotations

import sys
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "mcp-server" / "python"
if str(ASSETS_DIR) not in sys.path:
    sys.path.insert(0, str(ASSETS_DIR))

from crawler import main as _main  # type: ignore


def main() -> None:
    """Delegate to the packaged crawler CLI implementation."""
    _main()


if __name__ == "__main__":
    main()
