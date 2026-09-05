# Staging notes (year backend)

## Environments
- **dev**: `scripts/run_dev.sh` — `deploy_env=dev`, hot reload via uvicorn if configured.
- **prod**: `scripts/run_prod.sh`.
- **SSH / TUI**: Prefer `scripts/play_ssh.sh` (see README). Engine + curses complete the Payload-Zero loop offline (#38).

## Auth nick stub (#25)
- `POST /api/auth/nick` with `{"nick":"YourName"}` returns `{token, nick, stub:true}`.
- No OAuth secrets required. Tokens live in memory only on the process.
- Action `auth_nick <name>` binds a stub nick on the agent.

## Data-driven districts (#37)
- Edit `snowcrash/systems/data/districts.json` (also `recipes.json`, `season.json`).
- Reload: restart the server **or** `POST /api/reload_defs`.
- Fractional x0/y0/x1/y1 are normalized against map width/height. `undercity` binds to UNDER plane.

## Interest management / AOI (#18)
- Action WebSocket broadcasts use `interested_player_ids` (self + Manhattan AOI 28 + party/crew).
- Tick broadcasts remain full-fanout so AI movement stays visible.
- Entity lists in snapshots stay FOV-culled (existing).
- See `snowcrash/systems/aoi.py`.

## Analytics (#32)
- Events: join / payload / uplink / death / report.
- `GET /api/analytics` JSON; `GET /api/analytics?format=csv` CSV export.
- Replay crumbs: `GET /api/replay?limit=200`.

## Migration stub (#39)
- See `docs/migrations/2026_year_backend_stub.md`.
- In-memory season / crew / housing — no DB yet. Restart clears progress.

## Web-only gaps (TUI vs web) (#38)
TUI (`snowcrash/tui` + `engine.py`) completes Payload-Zero (jackpoint → uplink).
**Web/MMORPG-only** (not fully mirrored in curses):
- StreetNet IRC channels, party/crew chat
- Live vendors / craft bench actions over WS
- Districts, weather ticker, bosses, contracts board
- Opt-in PvP arenas, raids, spectate/replay APIs
- Season cosmetics, analytics endpoints, auth nick stub


## CI (#39)
- Workflow template: `docs/ci-github-actions.yml`.
- Copy to `.github/workflows/ci.yml` when the pushing credential has the `workflow` scope (OAuth apps often lack it).
- Locally: `PYTHONPATH=. pytest -q`
