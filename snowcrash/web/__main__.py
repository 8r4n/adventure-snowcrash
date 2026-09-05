"""Entry: python -m snowcrash.web"""

from __future__ import annotations

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="Snowcrash rogue-like (web)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--env",
        choices=("production", "dev"),
        default=os.environ.get("SNOWCRASH_ENV", "production"),
        help="Deployment label (production|dev). Also reads SNOWCRASH_ENV.",
    )
    args = parser.parse_args()

    import uvicorn

    from .app import create_app

    os.environ["SNOWCRASH_ENV"] = args.env
    app = create_app(default_seed=args.seed, deploy_env=args.env)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
