#!/usr/bin/env bash
# Godot 3D demo capture (#166) — fixture stills fallback (software GL safe).
# Prefer live x11grab on a GPU box; this path uses SNOWCRASH_CAPTURE_FIXTURE.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GODOT="${GODOT:-/workspace/tools/godot/godot}"
OUT="${SNOWCRASH_CAPTURE_OUT:-$ROOT/docs/screenshots/_capture_tmp}"
DATE="${CAPTURE_DATE:-$(date -u +%Y-%m-%d)}"
mkdir -p "$OUT" "$ROOT/docs/fixtures"

# Regenerate fixtures from seed 42
python3 "$ROOT/scripts/gen_godot3d_demo_fixture.py"

export DISPLAY="${DISPLAY:-:2}"
export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"
export SNOWCRASH_CAPTURE_FIXTURE="$ROOT/docs/fixtures/demo-godot3d-seed42.json"
export SNOWCRASH_CAPTURE_FIXTURE_ICE="$ROOT/docs/fixtures/demo-godot3d-ice-seed42.json"
export SNOWCRASH_CAPTURE_OUT="$OUT"
export SNOWCRASH_CAPTURE_QUALITY="${SNOWCRASH_CAPTURE_QUALITY:-high}"

echo "Capturing Godot 3D stills → $OUT"
"$GODOT" --path "$ROOT/godot_client" --resolution 1280x800 \
  --rendering-driver "${GODOT_RENDERING_DRIVER:-opengl3}" --display-driver x11 \
  --fixed-fps 10

echo "Encode with ffmpeg (see docs/demo-video.md Godot section)."
echo "Frames in $OUT"
