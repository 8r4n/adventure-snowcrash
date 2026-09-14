#!/usr/bin/env bash
# Headless rebuild of Blender-authored kit meshes (#179).
# Requires Blender 4.3+ with numpy on that interpreter (glTF exporter).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BLENDER="${BLENDER:-blender}"
OUT="${OUT:-$ROOT/godot_client/models}"
BLEND_OUT="${BLEND_OUT:-$ROOT/tools/blender/src}"
SCRIPT="$ROOT/tools/blender/export_kit.py"

if ! command -v "$BLENDER" >/dev/null 2>&1; then
  echo "error: blender not on PATH (set BLENDER=...)" >&2
  exit 1
fi

if [[ ! -f "$SCRIPT" ]]; then
  echo "error: missing $SCRIPT" >&2
  exit 1
fi

mkdir -p "$OUT" "$BLEND_OUT"

echo "exporting kit → $OUT  (blender=$BLENDER)"
"$BLENDER" --background --python "$SCRIPT" -- --out "$OUT" --blend-out "$BLEND_OUT" "$@"
echo "done"
