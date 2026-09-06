# Soft hardcore — opt-in death tax

Issue **#49** (parent campaign **#42**). Optional **soft hardcore** mode: on flatline you burn a percentage of street credits and shed **one** non-quest inventory item onto the asphalt. **Levels and XP stay.** Quest gear, Payload-Zero, Signal Keys, and wish tokens never drop. Default is **OFF** — casual death is unchanged. Mechanics inspired by soft-permadeath / loot-risk fantasy; prose is **original Metaverse fiction only**.

Source of truth: `snowcrash/systems/soft_hardcore.py` (`SoftHardcoreMixin`), mixed into `YearFeaturesMixin` / `GameWorld`. Death hook runs inside `_year_on_player_death` (after combat marks the courier dead).

## Opt-in

| Path | How |
|------|-----|
| Action | `hardcore on` / `hardcore off` (aliases: `soft_hardcore`, `hardcore_on`, `hardcore_off`) |
| Status | `hardcore` / `hardcore_status` |
| Join (WS) | `{ "type": "join", "name": "…", "soft_hardcore": true }` (or `"hardcore": true`) |
| Join (API) | `GameWorld.join(name, soft_hardcore=True)` |

Toggle anytime from the street or settings-style action surface. Reconnect does not force the flag; use the action to change mid-session.

## Death tax (when enabled)

| Effect | Detail |
|--------|--------|
| Credits | **20%** of current credits burned (direct loss) |
| Empty wallet | If credits are already 0, **+5 hardcore debt** is banked instead (clear with `pay_hardcore_debt`) |
| Item | One **non-protected** inventory item dropped as a floor item at the death tile (prefers unequipped) |
| Levels / XP | **Unchanged** |
| Repair | Existing repair_needed bump from year death still applies |

### Protected (never dropped)

- `item.quest == True`
- `kind` in `quest`, `wish`
- ids: `payload_zero`, any `signal_key*`
- `extra.signal_key` / `extra.quest_flag`

## Overlay / messaging

Snapshot field **`death_cause`** feeds the SIGNAL LOST overlay (`#death-cause`). Soft-hardcore deaths append the tax summary (credits burned / item shed). Player log also prints the same lines. Kill feed may mark `via=soft-hardcore`.

## Snapshot

Field **`soft_hardcore`**:

| Field | Meaning |
|-------|---------|
| `enabled` | Opt-in flag |
| `debt` | Accumulated empty-wallet hardcore debt |
| `deaths` | Soft-hardcore deaths this session |
| `credit_loss_pct` | Configured burn rate (0.20) |
| `last_penalty` | Last tax card (`credits_lost`, `item_dropped`, `summary`, …) |

Also: top-level **`death_cause`** string while dead.

## Actions

| Action | Effect |
|--------|--------|
| `hardcore` / `soft_hardcore` / `hardcore_status` | Status log; arg `on`\|`off` toggles |
| `hardcore_on` / `hardcore_off` | Explicit toggle |
| `pay_hardcore_debt` / `hardcore_debt` | Pay down empty-wallet debt with credits |

## Design notes

- **Direct % loss** is the primary tax (clear UI). Debt is only a broke-courier fallback, not the default path.
- Spawn fairness / invuln / respawn pad selection are untouched.
- Year snapshot fields from other systems are preserved; this only adds `soft_hardcore` + `death_cause`.
