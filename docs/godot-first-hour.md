# Godot client — crash-free first hour

Parent epic **#118**. Player-facing checklist so a courier can jack in on the Godot 4 client against Python `/ws` and survive the first session without known hard crashes.

**Authority unchanged:** Godot is presentation only. Simulation stays on `snowcrash.web`.

## Before you start

1. `./scripts/run_dev.sh` → `ws://127.0.0.1:8766/ws` (or set `SNOWCRASH_WS_URL`)
2. Godot **4.3+** → Import [`godot_client/project.godot`](../godot_client/project.godot) → **F5**
3. Optional: `SNOWCRASH_AUTO_JOIN=1` / `SNOWCRASH_NAME=Demo`

## First-hour play checklist

| Step | Expect | If it fails |
|------|--------|-------------|
| Jack in with a courier name | Status → ONLINE / RTT; 3D street paints | Confirm `:8766/health`; check URL field |
| WASD / QE move + turn | Snapshot updates; no client-side teleport | Server authority — wait for snapshot |
| G pickup · inventory select · U use | Inventory list pulses on pickup; tooltip on hover | Empty street — walk until a drop |
| F fire / ICE dock probe | Log + SFX; ICE lattice if jacked | Focus / LOS may block |
| Death (or soft-hardcore flatline) | **SIGNAL LOST** overlay: cause, last objective, pad options | Onboarding beat uses its own death card — finish/skip beat first |
| Respawn (R or pad button) | Overlay closes; back on street pad | `send_respawn` sends `r` + option id |
| StreetNet chat | Message appears in IRC dock | Docks gated during onboarding beat |
| Disconnect / reconnect same name | Resume by id/name; no duplicate body | See NetClient backoff |
| Low / High quality toggle | Deck Low stays playable; High optional | FpsMeter / #148 |
| Mute + audio sliders | Persist in `user://snowcrash_client.cfg` | #134 |

## Known non-goals / gaps (not crashes)

- Street GPS / minimap still open on #118
- Party / crew / shop / craft / stash surfaces incomplete vs web
- Year-dock heist UX still thin vs web
- macOS export later (#149 Linux/Windows first)
- **No Abandoned Spaceship IP** — original meshes/materials only

## Smoke command (no Godot binary)

```bash
PYTHONPATH=. pytest -q tests/test_godot_death_recap_118.py tests/test_godot_ws_protocol.py tests/test_godot_onboarding_133.py
```

Refs #118
