# Snowcrash

A short, playable cyberpunk **rogue-like** in Python: turn-based streets of fractured LA (ASCII TUI + 32×32 web tiles), fog of war, inventory, melee + hack/ranged combat, and a courier quest for **Payload-Zero**.

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

The web UI renders a neon 32×32 tile map (not bare ASCII) with a legend under the grid.
Press **A** or use the **ASCII view** button to switch back to the classic glyph map.
Short procedural SFX play for move/combat/loot — **Mute** button or **m** (remembered in localStorage; default volume ~0.4).
Quest rooms show **J** (jackpoint) and **U** (Metaverse uplink) as distinct tiles.

To regenerate sprites after editing `scripts/gen_tiles.py`:

```bash
source .venv/bin/activate
pip install pillow   # generator only; not a runtime dep
python scripts/gen_tiles.py
```

To regenerate SFX WAVs (stdlib only — no extra deps):

```bash
python scripts/gen_sfx.py
```

## Controls

| Key | Action |
|-----|--------|
| `WASD` / arrows / `hjkl` | Move |
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
| `A` (web) | Toggle tiles / ASCII |
| `m` (web) | Mute / unmute SFX |

Bump into NPCs to talk. Walk onto items and press `g`. Bring **Payload-Zero** next to the Metaverse uplink custodian to win.

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
    static/{style.css,game.js,tiles/,sfx/}
  scripts/gen_tiles.py   # Pillow one-shot sprite bake
  scripts/gen_sfx.py     # stdlib procedural WAV bake
```

## License

MIT — see `LICENSE`.
