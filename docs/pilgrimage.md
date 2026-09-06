# Canticle Pilgrimage (multi-courier story arcs)

Issue **#61** (parent campaign **#42**). Party pilgrimage across street districts with **rotating POV journal beats** and a **shared finale** — Hyperion / Canterbury *structure* only. All prose is **original Metaverse fiction** (no copyrighted pilgrim text).

Source of truth: `snowcrash/systems/pilgrimage.py` (`PilgrimageMixin`), mixed into `YearFeaturesMixin` / `GameWorld`. Compass hook in `mmorpg._quest_objective`; shrine probe in `mmorpg._try_move`; mode gate like Flotilla.

## Lobby (3–5 couriers)

| Action | Effect |
|--------|--------|
| `pilgrimage_open` / `pilgrim_lobby` | Host opens a lobby |
| `pilgrimage_join <id>` | Join an open lobby (max **5**) |
| `pilgrimage_ready` / `pilgrimage_unready` | Ready check |
| `pilgrimage_start` | Host starts when **3–5** members are all ready |
| `pilgrimage_leave` | Leave lobby / instance / Spire |
| `pilgrimage` / `pilgrimage_status` | Status line |

StreetNet ticker `kind=pilgrimage` fires on lobby open and start.

## Per-courier journal beats

On start, each member is assigned a unique **Canticle** beat (title + original prose + district shrine `P`):

| Beat id | Title | District (default) |
|---------|-------|--------------------|
| `latch_neon` | Canticle of the Faraday Latch | `burbclave` |
| `glassline_bass` | Canticle of the Glassline Bass | `club` |
| `rim_frost` | Canticle of Rim Frost | `uplink_rim` |
| `street_oath` | Canticle of the Street Oath | `burbclave` |
| `spawn_wake` | Canticle of the Spawn Wake | `club` |

- Journal side quest `canticle_pilgrimage` + `notes` get the personal page.
- Compass / `objective` points at your shrine while the beat is open.
- Stand on the shrine (Manhattan radius **1**) — auto-seal via move probe, or `pilgrim_complete` / `seal_canticle`.

## Shared finale — Canticle Spire

1. When **all** party beats are sealed → `finale` ticker + pad unlock (`pilgrimage_pad` near uplink `U`, glyph `P`).
2. Approach pad (radius **2**) and run `enter_pilgrimage` / `canticle_finale` / `enter_spire`.
3. Mode → `pilgrimage` (street verbs muted). Shared reward once per courier.
4. Leave with `leave_pilgrimage` / Esc / `q`.

### Rewards (no P2W)

| Reward | Amount |
|--------|--------|
| Street credits | +45 |
| Season XP | +18 (cosmetic track) |
| Cosmetic | `trail_canticle_ash` — **Canticle Ash Trail** (`season_equip trail_canticle_ash`) |

No attack / defense / HP / focus combat grants from the Spire.

Snapshot field `pilgrimage` exposes lobby, beat, finale pad, and reward flags.

## How to start a pilgrimage (player)

1. Jack in on **dev web** (`./scripts/run_dev.sh`, port **8766**) with **3–5** browsers/couriers.
2. One courier: chat/action `pilgrimage_open` — note lobby id.
3. Others: `pilgrimage_join <id>`.
4. Everyone: `pilgrimage_ready`. Host: `pilgrimage_start`.
5. Follow your personal shrine on the compass / `pilgrimage` status; step the `P` landmark.
6. When the Spire unlocks, gather at the pad and `enter_pilgrimage`.

Dev shortcut: `pilgrimage_force` + arg `dev` starts an undersized instance for solo tests.

## TUI note

Curses TUI does not surface the year Pilgrimage HUD yet. Play on **dev web**.
