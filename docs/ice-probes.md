# ICE probes (Focus quickhacks)

Issue **#46** (parent campaign **#42**). StreetNet system hacks: spend **Focus** to stun cameras/decks, reveal fog + tag nodes, or scramble aggro. Implemented on the **MMORPG / web (dev)** path (`GameWorld` + year features), not the single-player curses TUI yet.

Source of truth: `snowcrash/constants.py` (`ICE_PROBES`), `snowcrash/systems/year_features.py` (`_ice_probe_action`, `_seed_ice_cameras`), web UI in `snowcrash/static/game.js` + dock panel in `templates/index.html`.

## Probe catalog

| Id | Name | Focus | Cooldown | Radius | Duration | Effect |
|----|------|------:|---------:|-------:|---------:|--------|
| `stun` | Stun Spike | 4 | 12s | 8 | 6s | Freeze the **nearest** camera, drone, or thug deck in range |
| `reveal` | ICE Scan | 3 | 8s | 12 | 10s | Pulse StreetNet fog; tag nearby cameras / drones / thug decks (works even with no live targets) |
| `scramble` | Aggro Scramble | 5 | 15s | 10 | 8s | Hostiles in range wander (ignore chase); cameras get a half-duration soft stun |

Default nearby-list radius in the ICE snapshot: **10** (`ICE_PROBE_RADIUS_DEFAULT`).

## Targets

- **Street cameras** (`c`) — seeded near vendors, jackpoint, uplink, spawn pads (`_seed_ice_cameras`). Track `stunned_until` / `revealed_until`.
- **Drones** (`d`) and **thug decks** (`t`) — living enemies on the same plane; stun sets `stunned_until`, scramble sets `scrambled_until`.
- AI (`enemy_tick`): stunned actors skip the tick; scrambled actors **wander only** (no chase). Couriers in cyberspace are not aggro targets.

Stun/scramble require at least one target in the probe’s radius (reveal does not).

## How to fire

### Web (recommended)

| Key | Action |
|-----|--------|
| `z` | `ice_probe stun` |
| `x` | `ice_probe reveal` |
| `c` | `ice_probe scramble` |
| `p` | Open the **ICE** year dock (catalog + nearby list + Probe buttons) |

Dock button **ICE** is the same panel. Buttons send `ice_probe` with the probe id.

### Actions / aliases (WebSocket / handlers)

- `ice_probe <type>` with `stun` | `reveal` | `scramble` (also `list` / `help` / `?` for catalog)
- Shortcuts: `ice_stun`, `probe_reveal`, `ice_scramble`, etc. (`ice_*` / `probe_*` prefixes)
- Chat-style aliases: `probe`, `ice` with the same arg

Insufficient Focus, unknown type, empty stun/scramble range, or active cooldown → log only; Focus is not spent on a failed cast (except reveal, which always spends when Focus/cooldown allow).

## Focus & cooldowns

- Cost deducted from `actor.focus` on success.
- Per-probe cooldown stored on `agent.ice_cooldowns[id]` as a ready-at unix time.
- Snapshot `ice.probes[]` exposes `focus_cost`, `cooldown`, `ready_in`, `ready`, plus `ice.nearby`, `ice.focus` / `max_focus`.
- Regen Focus via wait / Focus Tabs / kills (same Focus economy as fire/hack/fly).

## Relation to cyberspace (#47)

Inside a jacked **ICE-gate** node, `stun` and `reveal` melt nearby `I` cells (`_cyber_clear_ice_near`: radius 1 for stun, 2 for reveal). `scramble` does nothing useful in-node (no street hostiles). See [cyberspace.md](cyberspace.md).

## TUI note

Curses TUI (`python -m snowcrash`) uses `engine.handle_action` and does **not** wire ICE probes yet. Help text documents the verbs for the shared control language; play probes on **dev web** (`./scripts/run_dev.sh`, port 8766).
