# Uplink Hop / Street Jaunt

Issue **#62** (parent campaign **#42** · related **#54**). Learned teleport skill: **short hops → district hops → globe hops**, with **misfire risk** when underleveled. Mechanics inspired by trained-teleport progression tropes — prose is **original Metaverse fiction only** (no copyrighted names or quotes).

Source of truth: `snowcrash/systems/jaunte.py` (`JaunteMixin`), mixed into `YearFeaturesMixin` / `GameWorld`. Web dock **Jaunt** · **Shift+U**. Globe region teleports at rank 3 reuse `#54` uplink pads.

## Ranks

| Rank | Name | Unlocks | Short range (Manhattan) |
|------|------|---------|-------------------------|
| 0 | Untrained | Attempts allowed but **high misfire** | 4 |
| 1 | Street Jaunt | Reliable **short** hops | 6 |
| 2 | District Hop | Hop to another **district** center | 8 |
| 3 | Globe Hop | **Globe** region teleport channel (#54) | 10 |

XP from successful hops (short +1 · district +3 · globe +5). Thresholds to reach ranks 1 / 2 / 3: **3 / 10 / 22** XP.

Also train via:

- `skill_pick uplink_jaunte` (level-up pick — rank +1, floors at 1)
- `jaunte_train` (spends one skill pick for +1 rank)

## Costs & feedback

| Hop | Focus | Cooldown | Notes |
|-----|-------|----------|-------|
| short | 3 | ~4s | Facing or `n/s/e/w` |
| district | 6 | ~12s | Optional district id |
| globe | 8 (+ globe credits) | ~20s (+ globe CD) | Needs `region_id` |

**Misfire** (underleveled or bad luck): Focus still burns, short cooldown, scatter to a nearby standable tile, toast / log `Uplink misfire…`. Ranked hops keep a small spice misfire chance.

Cooldown / Focus / blocked-mode messages surface as `jaunte.last_feedback` for web toasts.

## Player controls

| Input | Effect |
|-------|--------|
| Dock **Jaunt** · **Shift+U** | Open panel + `jaunte` |
| `jaunte` / `street_jaunt` / `jaunt` | Open status panel |
| `jaunte short` · `jaunte_short` · `jaunte n` | Short hop (facing or cardinal) |
| `jaunte district` · `jaunte_district [id]` | District hop (`burbclave` / `club` / `uplink_rim` / `undercity`) |
| `jaunte globe <region>` · `jaunte_globe` | Globe hop (rank 3; e.g. `neo_tokyo`) |
| `jaunte_train` / `jaunte train` | Spend skill pick → +1 rank |
| `jaunte_status` | Rank / XP / cooldown log |
| `skill_pick uplink_jaunte` | Learn skill (+1 rank) |

Blocked while dead / cyberspace / heist / flotilla. Does **not** replace sleeve hops (#59) or raw `teleport` / `uplink_hop` globe aliases (#54) — those stay available; jaunte adds the **trained** progression gate + short/district layers.

## Snapshot (`jaunte`)

| Field | Meaning |
|-------|---------|
| `rank` / `rank_name` | 0–3 ladder |
| `xp` / `xp_next` | Progression |
| `hops` / `misfires` | Counters |
| `cooldown` / `ready` | Seconds left / clear |
| `focus_costs` | short / district / globe |
| `can_district` / `can_globe` | Rank gates |
| `ranks[]` | Ladder rows for UI |
| `last_feedback` | `{kind, text, t}` for toasts (`success` / `misfire` / `cooldown` / `rankup`) |
| `hint` | Short guidance |

## Web UI

Dock **Jaunt** · panel lists ranks, Focus costs, **Short** / **District** / **Globe** buttons · toasts on success / misfire / cooldown · **Shift+U**.

## TUI

`?` help lists `jaunte` / `jaunte_train`. Send the same actions over the MMORPG action channel.

## Design notes

- Original StreetNet theming only — call it **Uplink Hop** or **Street Jaunt**.
- Rank 3 ties into globe geography so news storylines (#51) and Earth shards (#54) stay coherent.
- Prefer training by play (hop XP) so skill picks are optional accelerators, not a hard wall.
