#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -t 0 || ! -t 1 ]]; then
  echo "Need an interactive TTY (SSH session or local terminal)." >&2
  exit 1
fi
export TERM="${TERM:-xterm-256color}"
if [[ -f .venv/bin/activate ]]; then source .venv/bin/activate; fi
exec python -m snowcrash "$@"
