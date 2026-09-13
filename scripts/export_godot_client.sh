#!/usr/bin/env bash
# Headless Godot desktop export for adventure-snowcrash (#149).
# Artifacts land under build/linux and build/windows (gitignored).
# Docs: docs/godot-desktop-export.md
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT="${ROOT}/godot_client"
PRESETS="${PROJECT}/export_presets.cfg"
OUT_LINUX="${ROOT}/build/linux"
OUT_WINDOWS="${ROOT}/build/windows"

usage() {
  cat <<'USAGE'
Usage: ./scripts/export_godot_client.sh [linux|windows|all]

  linux    Export Linux/X11 x86_64 → build/linux/Snowcrash.x86_64 (+ .pck)
  windows  Export Windows Desktop  → build/windows/Snowcrash.exe (+ .pck)
  all      Both (default)

Environment:
  GODOT          Path to Godot 4.x binary (overrides PATH lookup)
  GODOT_BIN      Alias for GODOT

Requires matching export templates installed for the Godot version
(Editor → Manage Export Templates, or headless template zip).
USAGE
}

die() { echo "error: $*" >&2; exit 1; }

resolve_godot() {
  if [[ -n "${GODOT:-}" ]]; then
    echo "${GODOT}"
    return
  fi
  if [[ -n "${GODOT_BIN:-}" ]]; then
    echo "${GODOT_BIN}"
    return
  fi
  local candidate
  for candidate in godot4 godot Godot; do
    if command -v "${candidate}" >/dev/null 2>&1; then
      command -v "${candidate}"
      return
    fi
  done
  # Common local install paths (optional)
  for candidate in \
    "${HOME}/.local/share/godot/godot" \
    "${HOME}/Applications/Godot" \
    /opt/godot/Godot \
    /usr/local/bin/godot4 \
    /usr/local/bin/godot; do
    if [[ -x "${candidate}" ]]; then
      echo "${candidate}"
      return
    fi
  done
  return 1
}

TARGET="${1:-all}"
case "${TARGET}" in
  -h|--help|help) usage; exit 0 ;;
  linux|windows|all) ;;
  *) usage >&2; die "unknown target '${TARGET}'" ;;
esac

[[ -f "${PROJECT}/project.godot" ]] || die "missing ${PROJECT}/project.godot"
if [[ ! -f "${PRESETS}" ]]; then
  if [[ -f "${PRESETS}.example" ]]; then
    die "missing ${PRESETS} — copy from export_presets.cfg.example first"
  fi
  die "missing ${PRESETS}"
fi

if ! GODOT_PATH="$(resolve_godot)"; then
  cat >&2 <<'MISSING'
error: Godot 4 binary not found on PATH (tried godot4, godot, Godot).

Install Godot 4.3+ from https://godotengine.org/download
then either:
  export GODOT=/path/to/Godot_v4.x.x
  ./scripts/export_godot_client.sh
or put `godot4` / `godot` on your PATH.

Also install matching **export templates** (Editor → Manage Export Templates
→ Download and Install). Without templates, headless --export-release fails.

See docs/godot-desktop-export.md
MISSING
  exit 127
fi

# Sanity: must be Godot 4.x
VER_LINE="$("${GODOT_PATH}" --version 2>/dev/null || true)"
if [[ -z "${VER_LINE}" ]]; then
  die "could not run '${GODOT_PATH} --version'"
fi
if [[ ! "${VER_LINE}" =~ ^4\. ]]; then
  die "need Godot 4.x (got: ${VER_LINE})"
fi

echo "Using Godot: ${GODOT_PATH} (${VER_LINE})"
echo "Project:     ${PROJECT}"

export_one() {
  local preset="$1"
  local out_dir="$2"
  local out_file="$3"
  mkdir -p "${out_dir}"
  echo "→ Exporting '${preset}' → ${out_file}"
  # --path must be the project folder; export path is relative to project (../build/...)
  if ! "${GODOT_PATH}" --headless --path "${PROJECT}" --export-release "${preset}" "${out_file}"; then
    cat >&2 <<'FAIL'
error: Godot export failed.

Common causes:
  • Export templates not installed for this Godot version
  • Preset name mismatch in godot_client/export_presets.cfg
  • First-time import needed: open project once in the editor, then retry

See docs/godot-desktop-export.md
FAIL
    exit 1
  fi
  if [[ ! -e "${out_file}" ]]; then
    die "export reported success but missing artifact: ${out_file}"
  fi
  echo "  ok: ${out_file}"
  # Companion .pck when embed_pck=false
  local pck="${out_file%.*}.pck"
  if [[ -f "${pck}" ]]; then
    echo "  ok: ${pck}"
  fi
}

# export_path in presets is relative to godot_client/ → ../build/...
LINUX_ARTIFACT="${OUT_LINUX}/Snowcrash.x86_64"
WINDOWS_ARTIFACT="${OUT_WINDOWS}/Snowcrash.exe"

case "${TARGET}" in
  linux)
    export_one "Linux/X11 (Steam Deck / desktop)" "${OUT_LINUX}" "${LINUX_ARTIFACT}"
    ;;
  windows)
    export_one "Windows Desktop" "${OUT_WINDOWS}" "${WINDOWS_ARTIFACT}"
    ;;
  all)
    export_one "Linux/X11 (Steam Deck / desktop)" "${OUT_LINUX}" "${LINUX_ARTIFACT}"
    export_one "Windows Desktop" "${OUT_WINDOWS}" "${WINDOWS_ARTIFACT}"
    ;;
esac

echo
echo "Artifacts:"
[[ "${TARGET}" == "linux" || "${TARGET}" == "all" ]] && ls -la "${OUT_LINUX}" || true
[[ "${TARGET}" == "windows" || "${TARGET}" == "all" ]] && ls -la "${OUT_WINDOWS}" || true
echo
echo "WS URL for exported builds: set SNOWCRASH_WS_URL (see docs/godot-desktop-export.md)"
