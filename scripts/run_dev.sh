#!/usr/bin/env bash
# Dev deployment — use adventure-dev worktree (dev branch), port 8766
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export SNOWCRASH_ENV=dev
PORT="${PORT:-8766}"
SEED="${SEED:-42}"
if [[ -f .venv/bin/activate ]]; then source .venv/bin/activate; fi
exec python -m snowcrash.web --host 0.0.0.0 --port "$PORT" --seed "$SEED" --env dev
