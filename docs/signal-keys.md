# Signal Keys scavenger hunt

Issue **#45** (parent campaign **#42**). Layered district key hunt inspired by OASIS-style multi-key progression (mechanics only — **original Metaverse prose**, no copyrighted riddles). Collect three Signal Keys across **Burbclave**, **Club Glassline**, and **Uplink Rim**; sleeved together they unlock a **Flotilla finale uplink room** and StreetNet broadcast.

Source of truth: `snowcrash/systems/signal_keys.py` (`SignalKeysMixin`), mixed into `YearFeaturesMixin` / `GameWorld`. Compass hook in `mmorpg._quest_objective`; pickup hook in `mmorpg._pickup`.

## Keys

| Id | Name | District | Floor drop |
|----|------|----------|------------|
| `signal_key_burbclave` | Signal Key · Burbclave | `burbclave` | Walkable tile sampled inside district AABB |
| `signal_key_club` | Signal Key · Club Glassline | `club` | Same |
| `signal_key_uplink_rim` | Signal Key · Uplink Rim | `uplink_rim` | Same |

Items are `kind=quest` (`glyph=*`). Positions live in `world.signal_key_positions` and appear as landmarks in the snapshot.

## District-gated clues

On `year_tick`, if a courier is on the street plane inside a key district and still missing that district’s key, they hear a **one-time** StreetNet rumor (`clues_seen`). Clue text is original fiction only. Journal `notes` get a short hint; the main Payload-Zero compass is **not** stolen by clues alone.

## Journal + compass

- Side quest `signal_keys` is seeded on agent bootstrap (`journal.side`).
- Each pickup appends a journal note, sets `quest_flags[<key_id>]`, and updates side-quest progress (`N/3`).
- After **≥1 key** sleeved (or Payload-Zero cleared / won), `objective` / compass points at the **next missing key**, then the **Flotilla pad** near uplink.
- Status action: `signal_keys` / `signal_status` / `keys_status`.

## Finale — Flotilla uplink room

1. Holding all three keys unlocks the finale (`signal_finale_unlocked`, season XP +12, ticker broadcast).
2. Stand within Manhattan distance **2** of `flotilla_pad` (seeded adjacent to uplink `U`).
3. Action: `enter_flotilla` / `flotilla` / `signal_finale`.
4. Mode → `flotilla` (street verbs muted). Broadcast fires once: +40 credits, season XP +25, `quest_flags.signal_broadcast`, side quest marked done.
5. Leave with `leave_flotilla` / Esc / `q`.

Snapshot field `signal_keys` exposes held flags, pad coords, and `can_enter_finale`.

## How to find the keys (player)

1. Jack in on **dev web** (`./scripts/run_dev.sh`, port 8766).
2. Wander **Burbclave** / **Club District** / **Uplink Rim** — listen for district rumor lines; open **Shift+J** journal for hints.
3. Walk over a glowing `*` Signal Key tile and press **`g`** (get).
4. Compass retargets after the first key (or after scrubbing Payload-Zero).
5. With all three, approach uplink `U`, run `enter_flotilla` (chat/action), enjoy the broadcast, then leave.

Dev shortcut: teleport via tests / `_force_set_pos` to `world.signal_key_positions[id]`.

## TUI note

Curses TUI does not run `GameWorld` year Signal Keys yet. Play on **dev web**.
