"""Entry: python -m snowcrash  → terminal UI."""

from __future__ import annotations

import argparse
import os
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Snowcrash rogue-like (terminal)")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed")
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable curses colors (monochrome; also set SNOWCRASH_NO_COLOR=1)",
    )
    args = parser.parse_args(argv)

    if args.no_color:
        os.environ["SNOWCRASH_NO_COLOR"] = "1"

    from .tui.app import run_curses

    return run_curses(seed=args.seed, no_color=args.no_color)


if __name__ == "__main__":
    sys.exit(main())
