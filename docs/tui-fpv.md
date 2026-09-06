# TUI ASCII FPV (curses / SSH)

Issue **#78** (parent campaign **#42**). Bring a **first-person ASCII view** into the curses terminal client so SSH / `./scripts/play_ssh.sh` / `python -m snowcrash` feel closer to the web Metaverse jack-in — not only the overhead map.

Web FPV (`docs/fpv.md`) paints a neon raycast canvas then samples it to glyphs. The TUI path skips the canvas and **raycasts straight to ASCII columns** from the local map + facing (stdlib / curses only).

## Player fantasy

Over SSH in an ~80×24 terminal: look through the courier’s eyes — walls scale with distance, doors/water block rays, nearby hostiles/NPCs/landmarks appear as billboards, crosshair + compass on the status strip. Press **`v`** to flip back to a classic overhead map (camera-centered on you).

## Controls (TUI)

| Key | Action |
|-----|--------|
| `v` | Toggle **FPV ↔ overhead map** (no turn cost) |
| `w` / `a` / `s` / `d` | Forward / strafe left / back / strafe right |
| `←` / `→` or `,` / `e` | Turn left / right |
| `↑` / `↓` | Forward / back |
| `q` | Quit (TUI; web uses `q` for turn left) |
| `?` | Help (lists FPV toggle) |

Default view is **FPV**. Override with env:

```bash
export SNOWCRASH_TUI_VIEW=map   # or fpv
python -m snowcrash --seed 42
# monochrome:
python -m snowcrash --no-color
```

## Status line

Always visible under the view pane:

- HP / Focus
- Compass (`^ N`, `> E`, …)
- `[FPV]` or `[MAP]` tag
- Payload + short objective hint
- `[v view]` reminder

## SSH / TERM notes

- Launcher: `./scripts/play_ssh.sh` (sets `TERM=xterm-256color` when unset).
- Minimum size **40×12** (existing guard + resize prompt).
- `--no-color` / `SNOWCRASH_NO_COLOR=1` keeps glyphs readable without color pairs.
- Redraw is one full frame per input (turn-based) — fine for remote TTYs.

## Smoke test

```bash
PYTHONPATH=. pytest -q tests/test_tui_fpv.py
```

The test drives the raycaster without a real curses TTY: facing/strafe change the frame; `--no-color` path stays ASCII-only.

## Files

| Path | Role |
|------|------|
| `snowcrash/tui/fpv.py` | Column raycast → ASCII rows + optional color-pair ids |
| `snowcrash/tui/app.py` | View toggle, relative keys, centered overhead, status |
| `tests/test_tui_fpv.py` | Renderer + key-map smoke |
