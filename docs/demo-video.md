# Demo video — re-capture recipe

## Godot 3D hero (#166) — current README

| File | Role | Size (2026-09-13) |
|------|------|-------------------|
| `docs/screenshots/demo-godot3d-2026-09-13.mp4` | Godot 3D street + ICE stills reel (~12s) + trailer bed | ~1.1 MB |
| `docs/screenshots/demo-godot3d-2026-09-13.gif` | README above-the-fold Godot 3D loop | ~1.3 MB |
| `docs/screenshots/demo-godot3d-2026-09-13-street.png` | Street still (kit + jackpoint glow) | still |
| `docs/screenshots/demo-godot3d-2026-09-13-ice.png` | ICE lattice still | still |
| `docs/fixtures/demo-godot3d-seed42.json` | Sparse absolute-map fixture (seed 42 @ jackpoint) | capture input |
| `docs/fixtures/demo-godot3d-ice-seed42.json` | ICE cyberspace fixture | capture input |
| `docs/screenshots/demo-2026-09-13.*` | Secondary web ASCII desktop tour | archived-as-secondary |

### Why stills fallback (this agent box)

Live Godot ↔ `/ws` on **llvmpipe** starves WebSocket polling during High-preset AOI rebuild (reconnect storm / never paints). Capture therefore:

1. `python3 scripts/gen_godot3d_demo_fixture.py` — seed-42 world, force near **J**, sparse absolute `map` rows (Street3D indexes by world x/y)
2. Godot `SNOWCRASH_CAPTURE_FIXTURE=…` loads JSON offline, applies `Street3D.apply_snapshot`, orbits yaw, saves SubViewport PNGs (`scripts/capture_godot3d_demo.sh`)
3. `ffmpeg` stitches PNG → MP4 (+ `docs/audio/trailer-bed-30s.wav`) → palette GIF

**Renderer note:** OpenGL Compatibility on software GL (SSAO/SSIL/volumetric/TAA need Forward+/Vulkan — use a GPU box for live High GI). Materials (#156), kit (#158), landmarks (#150), camera juice (#161) still read in frames. **No Abandoned Spaceship IP.**

### Live Godot capture (preferred on GPU + DISPLAY)

```bash
ADVENTURE_QA=1 ./scripts/run_dev.sh   # Terminal A — ws://127.0.0.1:8766/ws

# Terminal B
cd godot_client
SNOWCRASH_AUTO_JOIN=1 SNOWCRASH_NAME=Demo3D \
  /workspace/tools/godot/godot --path . --resolution 1280x800
# or: SNOWCRASH_WS_URL=ws://127.0.0.1:8766/ws ./build/linux/Snowcrash.x86_64

# Terminal C — after Jack in, Quality High (F8)
ffmpeg -y -video_size 1280x800 -framerate 30 -f x11grab -i ${DISPLAY}.0+0,0 -t 75 \
  -c:v libx264 -pix_fmt yuv420p /tmp/godot3d-raw.mp4
```

Beat sheet (~45–90s): neon street corridor → walk/turn (camera feel) → **J** landmark → jack in → ICE lattice → jack out → optional Globe dock → end on High street.

### Fixture stills encode

```bash
./scripts/capture_godot3d_demo.sh
# then encode frames in $SNOWCRASH_CAPTURE_OUT (see script) with the ffmpeg recipe under Web section below (fps/scale/palette).
```

`Refs #163` · `Refs #141` — do not close those epics from #166.

---

## Web ASCII tour (secondary)

Fresh README demo for current `dev` gameplay (**#126** live desktop; supersedes #111 montage). Assets:

| File | Role | Size (2026-09-13) |
|------|------|-------------------|
| `docs/screenshots/demo-2026-09-13.mp4` | Live feature tour (~68s) + trailer bed (#134) | ~3.4 MB |
| `docs/screenshots/demo-2026-09-13.gif` | README above-the-fold highlight loop | ~1.5 MB |
| `docs/screenshots/archive/demo-2026-09-montage.*` | Retired #111 puppeteer frame montage | historical |
| `docs/screenshots/archive/*.gif` | Older opening-credits / gameplay loops | historical |

## Capture method (2026-09-13)

**True live desktop recording** on `DISPLAY=:2`:

1. `ADVENTURE_QA=1 ./scripts/run_dev.sh` (:8766, seed 42)
2. Chrome (`1280×800`, `--remote-debugging-port=9222`) → `/?name=DemoCourier`
3. `ffmpeg` **x11grab** @ 12 fps of `:2.0+0,0`
4. Drive beats via **puppeteer-core CDP** attached to that live Chrome + **#112** QA HTTP (`/qa/action`, `/qa/snapshot`) for deterministic walk/turn/fire
5. Mux looping `docs/audio/trailer-bed-30s.wav` (#134) into the MP4 (AAC)

Memory held (~7 GiB available); no OOM this pass. Cyberspace jackpoint walk on seed 42 streets remains long/walled — Jack dock + year panels are shown; full `jack_in` at `J (13,104)` may need a longer follow-up pass.

## Prerequisites

```bash
cd /path/to/adventure-dev   # worktree on dev
ADVENTURE_QA=1 ./scripts/run_dev.sh       # :8766, seed 42 by default
# confirm: curl -s http://127.0.0.1:8766/qa/status
```

Optional: `ffmpeg`, `google-chrome`, Node + `puppeteer-core`, `xdotool`, Xvfb/`DISPLAY`.

## Demo beats (full tour checklist)

Aim for a watchable **~60–180s** MP4 covering as many surfaces as fit:

1. **Jack-in / name join** — courier name → Enter streets (`?name=` skips modal)
2. **Opening / intro** — video→ASCII montage; Space/Esc / Skip intro
3. **FPV walk + turn** — WASD / QA `forward`+`turn_*`; Street **GPS** minimap visible
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

Known capture notes: ICE sidebar overlap filed separately; duplicate flash/journal toasts fixed in #124.

## Live capture (preferred)

```bash
# Terminal A
ADVENTURE_QA=1 ./scripts/run_dev.sh

# Terminal B — Chrome on a real DISPLAY (+ optional CDP)
DISPLAY=:2 google-chrome --window-size=1280,800   --remote-debugging-port=9222   --autoplay-policy=no-user-gesture-required   'http://127.0.0.1:8766/?name=DemoCourier' &

DISPLAY=:2 ffmpeg -y -video_size 1280x800 -framerate 12 -f x11grab -i :2.0+0,0 -t 130   -c:v libx264 -pix_fmt yuv420p /tmp/demo-raw.mp4

# Drive beats: CDP puppeteer against :9222 and/or QA HTTP + xdotool
```

Encode (with trailer bed):

```bash
ffmpeg -y -ss 1.5 -t 68 -i /tmp/demo-raw.mp4   -stream_loop -1 -i docs/audio/trailer-bed-30s.wav   -filter_complex "[0:v]fps=10,scale=900:-2:flags=lanczos,setsar=1[v]"   -map '[v]' -map 1:a   -c:v libx264 -crf 28 -pix_fmt yuv420p -movflags +faststart   -c:a aac -b:a 64k -ac 1 -t 68   docs/screenshots/demo-2026-09-13.mp4

# README GIF (highlight concat + palette)
ffmpeg -y -i docs/screenshots/demo-2026-09-13.mp4   -vf "fps=4,scale=420:-1:flags=lanczos,palettegen=stats_mode=diff" /tmp/pal.png
ffmpeg -y -i docs/screenshots/demo-2026-09-13.mp4 -i /tmp/pal.png   -lavfi "fps=4,scale=420:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5"   docs/screenshots/demo-2026-09-13.gif
```

## Puppeteer / frame montage fallback

When live Chrome + x11grab OOMs (as on #111):

1. Headless Chrome via `puppeteer-core` against `http://127.0.0.1:8766/?name=TourCourier`
2. Script the beat checklist (keyboard + `.dock-btn[data-panel=…]` clicks)
3. Screenshot densely → `ffmpeg -framerate 1.4 -i f%04d.png …`
4. Optional: prepend `snowcrash/static/cutscenes/intro/montage.mp4` (~8–10s)
5. Build a **highlight GIF** from tagged keyframes so README stays under ~2–3 MB

Prefer `#112` QA (`ADVENTURE_QA=1`, `scripts/qa_smoke.py` / `/qa/*`) to drive deterministic movement even during live capture.

Absolute movement helpers toward `J`: QA `e_abs`/`w_abs`/`s_abs`/`n_abs` (or keys `h/j/k/l` — note `j` is `jack_in` when `can_jack_in`).

## File size targets

- **MP4:** prefer ≤ 4 MB @ ~900×560, CRF 26–28, AAC trailer bed OK, `+faststart`
- **GIF:** prefer ≤ 2–3 MB @ ≤ 420px wide, 4–5 fps, paletteuse + bayer dither
- If GIF bloated, ship a highlight reel and link the MP4 from README

## README embed

Above-the-fold: center the GIF; link MP4 + this doc. Keep archived assets under `docs/screenshots/archive/` only.
