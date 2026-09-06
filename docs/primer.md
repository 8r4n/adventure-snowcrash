# StreetNet Primer (interactive teaching tablet)

Issue **#60** (parent campaign **#42**). Inventory **quest tablet** that opens adaptive mini-quests teaching **ICE probes**, **globe travel**, and **crews**. Chapters unlock / grow with courier level. Completing grants **cosmetics + soft utility skills + credits** only — **no P2W wall** and no paywall. Mechanics inspired by adaptive teaching-primer tropes; prose is **original Metaverse fiction only** (StreetNet Primer — not Diamond Age text).

Source of truth: `snowcrash/systems/primer.py` (`PrimerMixin`), mixed into `YearFeaturesMixin` / `GameWorld`. Item factory `make_streetnet_primer()`. Web panel in `game.js` / `index.html` (dock **Primer**, **Shift+P**).

## Item

| Field | Value |
|-------|-------|
| Id | `streetnet_primer` |
| Name | StreetNet Primer |
| Kind | `quest` (soft-hardcore protected) |
| Glyph | `▣` |
| Grant | Auto-sleeved on join / bootstrap |

**Use** the item from inventory (`u` / web click), or action `primer` / dock **Primer**.

## Teaching quests (≥3)

| Id | Title | Teaches | Unlock | Goal | Rewards (no P2W) |
|----|-------|---------|--------|------|------------------|
| `ice_101` | ICE Sparks 101 | ICE probes | Lv 1 | 1 successful probe (2 at Lv≥4) | +15 cr · **Primer ICE Afterglow** · skill **Faraday Mind** · season XP |
| `globe_101` | Uplink Globe Hop | Globe travel | Lv 1 | 1 teleport / recall | +20 cr · **Primer Orbit Ribbon** · season XP |
| `crew_101` | Crew Channel Drill | Crews | Lv 2 | Create or join a crew | +18 cr · **Primer Crew Sigil** · skill **Burb Charm** · season XP |

Voice copy switches to “advanced” blurbs at courier **level ≥ 4**. Completing is free — rewards never gate combat power behind payment.

## How to play

1. Jack in (dev web `./scripts/run_dev.sh`, port 8766). Primer is already in inventory.
2. Open: dock **Primer**, **Shift+P**, action `primer`, or **use** the tablet.
3. **Start** a chapter (`primer_start ice_101` or panel button).
4. Complete the linked system action:
   - ICE: dock ICE / `z` `x` `c` / `ice_probe <type>` near a camera, drone, or thug.
   - Globe: dock Globe / `Shift+G` → `teleport <region>` or `globe_recall`.
   - Crew: `crew_create <name>` or `crew_join <id>` (needs Lv 2+).
5. Collect cosmetics via `season_equip <id>`; soft skills appear in `skills`.

## Actions

| Action | Arg | Effect |
|--------|-----|--------|
| `primer` / `open_primer` / `streetnet_primer` | optional chapter id | Open panel + log chapters |
| `primer_start` / `start_primer` | `ice_101` \| `globe_101` \| `crew_101` (or `ice`/`globe`/`crew`) | Activate chapter |
| `primer_status` / `primer_list` | — | Same as open |
| `primer_close` | — | Close panel flag |
| Inventory **use** on tablet | — | Opens Primer |

## Snapshot (`primer`)

| Field | Meaning |
|-------|---------|
| `owned` / `item_id` | Tablet present |
| `panel_open` | UI hint |
| `active_quest` | Current chapter id |
| `voice_level` / `player_level` | Adaptive voice |
| `lessons_done` / `quest_count` | Progress |
| `quests[]` | Title, status, progress/goal, blurb, hint, reward (`p2w: false`) |
| `completed` | Finished chapter ids |
| `hint` | Short player guidance |

## Design notes

- Progress only counts while a chapter is **active** (Start from the panel / `primer_start`).
- Soft skills (`faraday_mind`, `burb_charm`) are utility / economy — not a mandatory combat unlock wall.
- Cosmetics land in `season.unlocked` like Neon Dash trails.
