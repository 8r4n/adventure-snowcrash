"""Entry: python -m snowcrash.web"""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Snowcrash rogue-like (web)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    import uvicorn

    from .app import create_app

    app = create_app(default_seed=args.seed)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
