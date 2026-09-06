# Corp patrol pressure vs courier crews

Issue **#50** (parent campaign **#42**). Named franchise **corp patrols** hunt high-heat couriers; crews can **contest**. Heat rises with street **kills** and **Signal Key** pickups. Safehouses shed heat; **crew members in a safehouse** shed faster. Mechanics inspired by corporate-swarm / courier-pressure fantasy; prose is **original Metaverse fiction only**.

Source of truth: `snowcrash/systems/corp_patrol.py` (`CorpPatrolMixin`), mixed into `YearFeaturesMixin` / `GameWorld`. Tick hook in `year_tick`; hunt preference in `mmorpg.enemy_tick`; kill/key hooks via `year_on_kill` + Signal Key pickup.

## Heat meter

| Event | Heat delta |
|-------|------------|
| Kill (non-patrol enemy) | +8 |
| Signal Key sleeved | +15 |
| Flatline a corp patrol unit | −12 (applied to hunted courier; helpers shed half) |
| Crew-contested patrol unit kill | extra −8 |
| Natural decay (per tick) | −0.12 |
| Safehouse (`house` / `at_home`) | −1.2 / tick |
| Safehouse **+ crew** | −1.2 − **1.3** = **−2.5** / tick |

Heat clamps to **0–100**. Tier labels: `cool` / `warm` / `hot` / `burning`.

Patrols **spawn** when heat ≥ **55** (and no active hunt / cooldown). They **peel off** when heat falls ≤ **22**. After a clear, ~80 ticks before re-hunt.

## Named corps

Roster rotates (StreetNet fiction):

- Franchise Enforcement · Theta
- Burbclave Compliance Patrol
- Rim Wardens · Cable Baron
- Neon Grid Asset Recovery
- StreetNet Audit Squad

Each spawn drops **3** chase units (`glyph=C`) near the hot courier. Units prefer their heat target in `enemy_tick`.

## Crew contest

1. Form or join a crew (`crew_create` / `crew_join`).
2. When a patrol is live (on you or a crewmate / nearby), action **`contest_patrol`**.
3. Flatline contested units → bonus heat shed + **+15 credits** to the hunted courier when the patrol is wiped.

## Snapshot

Field **`heat`** (meter + shed + nested patrol). Top-level **`corp_patrol`** mirrors `heat.patrol` for clients that want a short handle.

| Field | Meaning |
|-------|---------|
| `value` / `max` / `tier` | Meter |
| `spawn_threshold` / `despawn_threshold` | Hunt gates |
| `in_safehouse` | `housing.at_home` |
| `crew_shed_bonus` | Safehouse **and** in crew |
| `shed_per_tick` | Current cool rate |
| `patrol` | Active hunt card (`corp_name`, `units`, `contested`, `hunting_you`, …) |

Ticker events: `kind=corp_patrol`, `phase=spawn|contest|end`.

## Actions

| Action | Effect |
|--------|--------|
| `heat` / `heat_status` / `corp_heat` | Log meter + patrol summary |
| `corp_patrol` / `patrol_status` | Patrol-focused status |
| `contest_patrol` / `patrol_contest` / `crew_contest` | Crew marks patrol contested |
| `corp_patrol_force` + arg `dev` | Dev: spike heat and force spawn |

## How to play

1. Jack in on **dev web** (`./scripts/run_dev.sh`, port 8766).
2. Raise heat: street kills and/or Signal Keys (`docs/signal-keys.md`).
3. Watch ticker / `heat` status when a named corp locks on.
4. `house` to enter safehouse and cool; with a crew, shed is faster.
5. Or fight: crew `contest_patrol`, flatline the `C` units.

Dev shortcut: `corp_patrol_force` with arg `dev`.


## Web HUD

Dev web surfaces heat + patrol live from the snapshot (no extra action needed):

| UI | Source | Notes |
|----|--------|-------|
| **Heat meter** (`#heat-hud`) | `heat.value` / `max` / `tier` | Side panel under vitals; spawn-threshold tick on the bar |
| **Cool / contest hints** (`#heat-hint`) | `in_safehouse`, `crew_shed_bonus`, `shed_per_tick`, patrol | Safehouse/crew shed rates + imminent-patrol copy |
| **Corp patrol banner** (`#corp-patrol-banner`) | `corp_patrol` (or `heat.patrol`) | Name, hunter count, hunting-you / contested, tip |
| **Contest button** | action `contest_patrol` | Shown while a live patrol is not yet contested |

Toaster stack sits on the **left** under the kill feed so it does not cover sticky HP/Focus in `#side`.

## TUI note

Curses TUI does not surface the year heat HUD yet. **Dev web** shows the heat meter + corp patrol banner from snapshot fields above.
