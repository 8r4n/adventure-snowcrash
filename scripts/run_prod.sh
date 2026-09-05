#!/usr/bin/env bash
# Production deployment — main branch checkout, port 8765
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export SNOWCRASH_ENV=production
PORT="${PORT:-8765}"
SEED="${SEED:-42}"
if [[ -f .venv/bin/activate ]]; then source .venv/bin/activate; fi
exec python -m snowcrash.web --host 0.0.0.0 --port "$PORT" --seed "$SEED" --env production
