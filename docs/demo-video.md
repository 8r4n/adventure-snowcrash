# Demo video — re-capture recipe

Fresh README demo for current `dev` gameplay (issue #111). Assets:

| File | Role | Target size |
|------|------|-------------|
| `docs/screenshots/demo-2026-09.mp4` | Full feature tour (~90–180s) | ≤ ~4 MB |
| `docs/screenshots/demo-2026-09.gif` | README above-the-fold highlight loop | ≤ ~2–3 MB |
| `docs/screenshots/archive/*.gif` | Retired opening-credits / gameplay loops | historical |

This pass used **puppeteer-core headless frames + ffmpeg** (live Chrome + `x11grab` OOM’d on the shared box). Prefer live desktop capture when memory allows.

## Prerequisites

```bash
cd /path/to/adventure-dev   # worktree on dev
./scripts/run_dev.sh       # :8766, seed 42 by default
# confirm: curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8766/
```

Optional: `ffmpeg`, `google-chrome`, Node + `puppeteer-core` (or computerUse / xdotool on `DISPLAY`).

## Demo beats (full tour checklist)

Aim for a watchable **~90–180s** MP4 covering as many surfaces as fit:

1. **Jack-in / name join** — courier name → Enter streets (`?name=` skips modal)
2. **Opening / intro** — video→ASCII montage; Space/Esc / Skip intro
3. **FPV walk + turn** — WASD move, Q/E turn; Street **GPS** minimap visible
4. **Map** — web is FPV + GPS (no overhead toggle); TUI uses `v` for FPV ↔ overhead
5. **Combat** — `f` fire/melee when hostiles in range
6. **Inventory** — `i`, select, Enter/`u` use
7. **StreetNet / IRC** — chat input + send; dock IRC collapse
8. **Quest journal / compass** — Shift+J or Jrnl dock; objective compass pill
9. **Shop / Craft** — Shop + Craft docks (vendor may be “out of range”)
10. **ICE probes** — ICE dock / `p`; `z`/`x`/`c` stun/reveal/scramble
11. **Cyberspace jack-in** — path to jackpoint `J` (seed 42 ≈ `(13,104)`), then `j` or Jack dock
12. **Globe / teleport UI** — Globe dock; Street → Regions → Globe zoom (credits may block hop)
13. **Primer · Jaunte · Sleeves · Forecast · Ecology** — Shift+P/U/H/F/R (and Empathy Shift+E)
14. **Hello Courier** — HELLO mod dock panel
15. **Catppuccin** — theme select Mocha / Macchiato / Frappé / Latte
16. **Aa large type** — `#btn-large-type` cycles Auto → Large → Compact

Known capture notes: ICE sidebar overlap filed separately; duplicate flash/journal toasts are minor.

## Live capture (preferred)

```bash
# Terminal A
./scripts/run_dev.sh

# Terminal B — Chrome on a real DISPLAY, then record
DISPLAY=:2 google-chrome --window-size=1280,800 \
  --autoplay-policy=no-user-gesture-required \
  'http://127.0.0.1:8766/?name=DemoCourier' &

DISPLAY=:2 ffmpeg -y -video_size 1280x800 -framerate 15 -f x11grab -i :2.0+0,0 -t 150 \
  -c:v libx264 -pix_fmt yuv420p /tmp/demo-raw.mp4

# Drive beats with computerUse / xdotool (skip intro, walk, open docks…)
```

Encode:

```bash
ffmpeg -y -i /tmp/demo-raw.mp4 -c:v libx264 -crf 26 -pix_fmt yuv420p -movflags +faststart -an \
  docs/screenshots/demo-2026-09.mp4

# README GIF (palette, short highlight or full shrink)
ffmpeg -y -i docs/screenshots/demo-2026-09.mp4 \
  -vf "fps=6,scale=480:-1:flags=lanczos,palettegen=stats_mode=diff" /tmp/pal.png
ffmpeg -y -i docs/screenshots/demo-2026-09.mp4 -i /tmp/pal.png \
  -lavfi "fps=6,scale=480:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5" \
  docs/screenshots/demo-2026-09.gif
```

## Puppeteer / frame montage fallback

When live Chrome + x11grab OOMs:

1. Headless Chrome via `puppeteer-core` against `http://127.0.0.1:8766/?name=TourCourier`
2. Script the beat checklist (keyboard + `.dock-btn[data-panel=…]` clicks)
3. Screenshot densely → `ffmpeg -framerate 1.4 -i f%04d.png …`
4. Optional: prepend `snowcrash/static/cutscenes/intro/montage.mp4` (~8–10s)
5. Build a **highlight GIF** from tagged keyframes (join, FPV, GPS, inv, chat, journal, docks, themes) so README stays under ~2–3 MB while MP4 keeps the full tour

Absolute movement helpers toward `J`: `h/j/k/l` → west/south/north/east abs (note: `j` jack_in when `can_jack_in`).

## File size targets

- **MP4:** prefer ≤ 4 MB @ ~960×620, CRF 26–28, no audio, `+faststart`
- **GIF:** prefer ≤ 2–3 MB @ ≤ 480px wide, 4–6 fps, paletteuse + bayer dither
- If GIF bloated, ship a highlight reel and link the MP4 from README

## README embed

Above-the-fold: center the GIF; link MP4 + this doc. Keep archived GIFs under `docs/screenshots/archive/` only.
