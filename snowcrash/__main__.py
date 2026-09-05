"""Entry: python -m snowcrash  → terminal UI."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Snowcrash rogue-like (terminal)")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed")
    args = parser.parse_args(argv)

    from .tui.app import run_curses

    return run_curses(seed=args.seed)


if __name__ == "__main__":
    sys.exit(main())
