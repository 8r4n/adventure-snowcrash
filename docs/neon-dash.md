# Neon Dash timed street race

Issue **#48** (parent campaign **#42**). Periodic **StreetNet** world-event broadcast opens a timed checkpoint dash through a district (Burbclave / Club Glassline / Uplink Rim). Finishers earn **credits + a cosmetic trail** only — **no P2W combat power**. Mechanics inspired by arcade timed routes / street-race fantasy; prose is original Metaverse fiction only.

Source of truth: `snowcrash/systems/neon_dash.py` (`NeonDashMixin`), mixed into `YearFeaturesMixin` / `GameWorld`. Tick hook in `year_tick`; checkpoint probe in `mmorpg._try_move`; landmarks while live.

## Lifecycle

1. After an idle gap (`next_start_tick`, first event ~tick 25), `_tick_neon_dash` starts a race.
2. World ticker + system chat: `kind=neon_dash`, `phase=start` (district named).
3. Four ordered checkpoints (`+` landmarks) seed on walkable tiles inside the district AABB.
4. Timer: **100 world ticks** (`timer_remaining` in snapshot).
5. Couriers auto-join by stepping the **Start gate**; later gates must be hit **in order** (Manhattan radius 1).
6. Clearing the finish gate grants rewards and pushes `phase=finish` to the ticker.
7. On timer expiry: `phase=end` ticker + chat; route glyphs clear; next start scheduled ~90–160 ticks later.

## Snapshot field `neon_dash`

| Field | Meaning |
|-------|---------|
| `active` | Race live |
| `district_id` / `district_name` | Active district |
| `timer_remaining` | Ticks left |
| `checkpoints` | `[{id,x,y,label,index}, …]` |
| `hit` / `hit_count` | This courier’s ordered progress |
| `next_checkpoint` | Next gate to stand on (or null) |
| `joined` / `finished` | Per-courier flags for this `event_id` |
| `reward` | Credits + cosmetic id (`p2w: false`) |
| `next_start_tick` | When idle, approx next start |

Also mirrored on the world events ticker (`events` / `world_events`).

## Rewards (no P2W)

| Reward | Amount |
|--------|--------|
| Street credits | +35 |
| Season XP | +10 (cosmetic track only) |
| Cosmetic | `trail_neon_dash` — **Neon Dash Afterimage** (`season.unlocked`; `season_equip trail_neon_dash`) |

No attack / defense / HP / focus combat grants from finishing.

## Actions

| Action | Effect |
|--------|--------|
| `neon_dash` / `dash_status` / `dash` | Log live timer + progress (or idle next-start hint) |
| `neon_dash_force` + arg `dev` | Dev/test force-start (not for normal play) |

## How to race (player)

1. Jack in on **dev web** (`./scripts/run_dev.sh`, port 8766).
2. Watch the **world events** ticker / StreetNet system lines for a Neon Dash start.
3. Open status with chat/action `neon_dash` — note district + next checkpoint coords.
4. Run the ordered `+` gates before the timer hits zero.
5. On finish: credits + unlock **Neon Dash Afterimage**; equip via `season_equip trail_neon_dash`.

Dev shortcut: `neon_dash_force` with arg `dev`, then `_force_set_pos` onto each checkpoint in order.

## TUI note

Curses TUI does not surface the year Neon Dash HUD yet. Play on **dev web**.
