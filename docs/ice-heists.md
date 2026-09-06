# Deep ICE heist runs + hostile AI presence

Issue **#56** (parent campaign **#42**). Related: [ICE probes](ice-probes.md) (#46), [cyberspace](cyberspace.md) (#47).

Neuromancer-inspired fantasy of layered ICE and mythic hostile intelligence — **original Metaverse naming and prose only** (Black Lattice Vault, Null Choir).

Source of truth: `snowcrash/systems/ice_heists.py` (`IceHeistMixin`), mixed into `YearFeaturesMixin` / `GameWorld`. Mode `heist` is handled in `mmorpg.handle_action` / snapshot map swap (same pattern as cyberspace).

## Goal

Multi-step jack-in heists: penetrate **3 ICE layers**, risk flatline (Focus/HP), optional AI antagonist. Failure costs **stun / debt / heat** without soft-locking the street loop.

## Template

| Id | Name | Layers |
|----|------|-------:|
| `black_lattice_vault` | **Black Lattice Vault** | 3 |

| Layer | Name | Notes |
|------:|------|-------|
| 1 | Perimeter Scrub | Light ICE; melt with probes, take `%` core, exit `X` |
| 2 | Honeycomb Lattice | Denser ICE; bumps tax Focus **and** HP |
| 3 | Core Sanctum | **Null Choir** AI boss stub pulses Focus/HP; seize core and escape |

Glyphs match cyberspace: `#` wall · `.` floor · `I` ICE · `%` core · `X` exit · `@` you.

## How to start a heist

1. Play on **dev web** (`./scripts/run_dev.sh`, port **8766**).
2. Reach the street **jackpoint (`J`)** (stand on or adjacent; Manhattan ≤ 1).
3. Send action / chat:
   - `heist_start` (aliases: `deep_heist`, `ice_heist`, `start_heist`, `vault_heist`)
   - or `jack_in heist` / `jack_in vault` / `jack_in deep`
4. Status anytime: `heist` / `heist_status`.

Street body is parked with a long invuln shield (same idea as #47). Esc / `heist_abort` / `jack_out` leaves the vault.

## ICE synergy (#46)

Inside a heist layer, **`stun`** and **`reveal`** melt nearby `I` cells (stun radius 1, reveal radius 2) using the same Focus costs and cooldowns as street probes. `scramble` does nothing useful in-vault.

Web keys `z` / `x` still fire probes while `mode == heist`.

## Failure costs (no soft-lock)

On abort / Focus flatline / AI pulse forced jack-out:

| Cost | Effect | Recovery |
|------|--------|----------|
| **Stun** | ~8s neural stun — cannot re-enter heist | Wait it out |
| **Debt** | +8 `bandwidth_debt` | `pay_bandwidth` / earn credits |
| **Heat** | +12 corp heat | Safehouse shed / time / contest patrol |
| **Cooldown** | ~20s before another `heist_start` | Wait |

HP is clamped to ≥1 on heist abort so the courier is **not** soft-locked dead on the street. Play continues: walk, trade, shed heat, jack maze nodes, retry the vault later.

## Hostile AI presence

### StreetNet omen

`_tick_ice_heist` periodically pushes `kind=ice_heist_omen` world events and system log lines naming **Null Choir** — myth/corporate force, not a street spawn.

### Cyberspace boss stub (layer 3)

Session field `ai` with stub HP. Every few actions the Choir **pulses** (−Focus/−HP). Probes and core pickup chip stub HP. This is an attention stub, not a full combat AI — grab the core and exit.

## Rewards

Per layer clear: vault dump datachip + credits + small Focus top-up.

Finale (all 3 layers):

- **Black Lattice Shard** (`heist_shard`)
- +40 credits, Focus bump, season XP
- Quest flags `ice_heist_cleared` / `ice_heists_cleared++`
- Journal note + side quest `ice_heist` marked done

## Snapshot field `ice_heist`

Inactive: `can_start`, stun/cooldown timers, omen blurb, win/fail counts.

Active: layer map rows, `ice_remaining`, `loot_taken`, `ai` stub card, `failure_costs.soft_lock: false`, street pad.

While `mode == heist`, MMORPG snapshot **swaps** the ASCII map to the vault layer (GPS/FPV consumers).

## Actions

| Action | Effect |
|--------|--------|
| `heist_start` / `deep_heist` / `ice_heist` | Start vault at J |
| `jack_in heist` | Same via jack_in arg |
| `heist` / `heist_status` | Log status / omen |
| `heist_abort` / Esc / `jack_out` | Leave (costs if incomplete) |
| `ice_probe stun\|reveal` | Melt vault ICE |

## TUI note

Curses TUI does not run `GameWorld` heists yet. Play on **dev web**.
