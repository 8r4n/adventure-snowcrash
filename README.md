# Snowcrash

A short, playable cyberpunk **rogue-like** in Python: turn-based streets of fractured LA. Web client uses continuous **1st-person video→ASCII FPV** plus a GTA-style **enhanced ASCII minimap**; TUI stays overhead ASCII. Fog of war, inventory, melee + hack/ranged, courier quest for **Payload-Zero**.

Original theme inspired by the *vibe* of Cataclysm: DDA mechanics and Neal Stephenson’s Metaverse — **no copied text or assets**.

You are **Rin Vale**, freelance Metaverse courier/hacker. Recover or neutralize a linguistic payload from a street jackpoint, then punch it through an uplink node.

## Requirements

- Python 3.11+ (3.12/3.13 fine)
- Linux/macOS recommended for the curses TUI
- Web deps listed in `requirements.txt` (FastAPI + Uvicorn)

## Install

```bash
cd adventure
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run — terminal (curses)

```bash
python -m snowcrash
python -m snowcrash --seed 42
```

## Run — web

```bash
python -m snowcrash.web
# optional:
python -m snowcrash.web --host 0.0.0.0 --port 8765 --seed 42
```

Then open **http://127.0.0.1:8765/** (or your host’s IP on port **8765**).

On first load (and **Replay intro** / restart after death-win) the web UI plays a fullscreen **opening cinematic**: high-fidelity **colored ASCII video** (canvas sample of a procedural MP4) with timed story beats for Rin Vale / Payload-Zero. **Space / Esc / Skip intro** dismisses it, then the playable HUD starts (`/api/new` is deferred until the intro ends so gameplay SFX do not overlap).

The main viewport is a live **1st-person ASCII raycast** (branded video→ASCII Metaverse layer). A corner **Street GPS** radar shows an **enhanced-resolution ASCII** crop of the same glyph map (not PNG tiles) — colorized, 2×2 upscaled cells, facing marker.
Short procedural SFX play for move/combat/loot — **Mute** / **m** (localStorage; default volume ~0.4).
Jackpoint / uplink / payload / NPC / terminal / door still trigger denser **jack-in ASCII cutscenes** (Space/Esc skip). TUI has no FPV/cutscenes yet.
Quest rooms: **J** jackpoint, **U** Metaverse uplink.

To regenerate sprites after editing `scripts/gen_tiles.py`:

```bash
source .venv/bin/activate
pip install pillow   # generator only; not a runtime dep
python scripts/gen_tiles.py
```

To regenerate SFX WAVs (stdlib only — no extra deps):

```bash
python scripts/gen_sfx.py
python scripts/gen_cutscenes.py   # stdlib ASCII cutscene packs
python scripts/gen_intro_video.py # Pillow + ffmpeg → colored-ASCII intro MP4
```

## Controls

| Key | Action |
|-----|--------|
| `W`/`S` (web) | Forward / back (relative to facing) |
| `A`/`D` (web) | Strafe left / right |
| `Q`/`E` or ←/→ (web) | Turn left / right |
| `WASD` / arrows / `hjkl` (TUI) | Absolute move |
| `g` | Get / pick up |
| `i` | Inventory |
| `e` | Equip / unequip (in inventory) |
| `u` | Use item (inventory selection, or click item on web) |
| `d` | Drop (inventory) |
| `f` | Ranged pulse (if pistol equipped) or **hack** attack |
| `.` / Space | Wait |
| `?` | Help |
| `r` | Restart (after death/win) |
| `q` | Quit (TUI) |
| `m` (web) | Mute / unmute SFX |
| Space / Esc (web) | Skip opening intro or 1st-person cutscene |

Bump into NPCs to talk. Walk onto items and press `g`. Bring **Payload-Zero** next to the Metaverse uplink custodian to win.

## Perspective / FPV + minimap

**Opening cinematic:** `snowcrash/static/ascii-video.js` (`VideoAsciiCanvas`) samples each frame of `static/cutscenes/intro/montage.mp4` onto a canvas and draws a dense charset with **per-glyph RGB from the source** (~120–200 columns, rAF loop). Source media is original procedural footage (neon grids, skyline, datastream, tunnel) — no copyrighted clips. Rebuild with `python scripts/gen_intro_video.py` (Pillow + ffmpeg).

**Web default after intro:** continuous **1st-person video→ASCII FPV** (live raycaster synced to the tile world + facing). Corner **Street GPS** = enhanced ASCII minimap (glyph language, upscaled/colorized — not the PNG tile set).

Movement is **relative to facing** (GTA-like): `W/S` forward/back, `A/D` strafe, `Q/E` (or arrows) turn.

Jack-in intensives still queue prebaked ASCII cutscene packs in `snowcrash/static/cutscenes/`:

| Trigger | Cutscene id |
|---------|-------------|
| Near jackpoint (`J`) first time | `jackpoint` |
| Pick up Payload-Zero | `payload` |
| Talk to an NPC | `talk` |
| Use a datachip | `terminal` |
| Walk through a door (once) | `door` |
| Win at Metaverse uplink | `uplink` |

Rebuild packs with `python scripts/gen_cutscenes.py` (no OpenCV at runtime).

## Map landmarks

- **Safehouse** (NW) — briefing with Relay Tran
- **Neon Club** (NE) — tips + pulse pistol loot
- **Jackpoint** (SW, `J`) — Payload-Zero + hostile security
- **Uplink** (SE, `U`) — deliver / neutralize to win

Enemies: `i` infected avatars, `t` street thugs, `d` security drones.
Web tiles live in `snowcrash/static/tiles/` (see `tiles.json` for glyph → sprite + legend labels).

## Package layout

```
adventure/
  LICENSE
  README.md
  requirements.txt
  snowcrash/
    __main__.py          # TUI entry
    engine.py            # shared game logic
    mapgen.py, entities.py, items.py, constants.py
    tui/app.py           # curses frontend
    web/                 # FastAPI frontend
      __main__.py
      app.py
    templates/index.html
    static/{style.css,game.js,ascii-video.js,tiles/,sfx/,cutscenes/,cutscenes/intro/}
  scripts/gen_tiles.py   # Pillow one-shot sprite bake
  scripts/gen_sfx.py     # stdlib procedural WAV bake
  scripts/gen_cutscenes.py  # stdlib 1st-person ASCII packs
  scripts/gen_intro_video.py  # Pillow+ffmpeg opening montage MP4
```

## License

MIT — see `LICENSE`.
