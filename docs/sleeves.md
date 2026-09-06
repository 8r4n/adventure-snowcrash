# Sleeves / avatar hop

Issue **#59** (parent campaign **#42**). Swap courier **shells** (street / club / undercity kits) with clear stat tradeoffs. Hop only at **safehouse / housing**. Premium shells optionally **rent for street credits**. Mechanics inspired by body-sleeving / class-immortality tropes from cyberpunk roundups — prose is **original Metaverse fiction only**.

Source of truth: `snowcrash/systems/sleeves.py` (`SleevesMixin`), mixed into `YearFeaturesMixin` / `GameWorld`. Web panel in `game.js` / `index.html` (dock **Sleeve**, **Shift+H**).

## Shells (≥3)

| Id | Name | Rent | Tradeoffs |
|----|------|------|-----------|
| `street` | Street Courier | **free** (owned) | Balanced START stats — jack-of-all-routes |
| `club` | Club Glassline | **25 cr** / session rent | +hack +focus / −hp −defense −attack — neon peacock |
| `undercity` | Undercity Tunnel Rat | **20 cr** / session rent | +hp +defense +attack / −focus −hack — tunnel armor |

Baseline starts: HP 30 · Focus 20 · ATK 4 · DEF 2 · HACK 3 (`constants.START_*`).

## How to swap in-game

1. Enter safehouse: action `house` / `housing` (toggles `housing.at_home`), or **Toggle safehouse** in the Sleeves panel.
2. Open locker: dock **Sleeve**, **Shift+H**, or action `sleeves` / `sleeve`.
3. Hop: `sleeve street` · `sleeve club` · `sleeve undercity` (aliases `sleeve_hop`, `shell`, `sleeve_club`, …).
4. Premium: if not yet rented this session, hop **auto-rents** when you have enough credits, or pay first with `sleeve_rent club` / `sleeve_rent undercity`.

Blocked while dead / cyberspace / heist / flotilla — jack out or respawn first. Hop heals to the new shell’s max HP / focus.

## Actions

| Action | Arg | Effect |
|--------|-----|--------|
| `sleeves` / `sleeve` / `open_sleeves` / `shells` | — | Open panel + catalog log |
| `sleeve` / `sleeve_hop` / `shell` | `street`\|`club`\|`undercity` | Hop (safehouse; auto-rent premium) |
| `sleeve_rent` / `rent_sleeve` | `club`\|`undercity` | Pay rent without hopping |
| `sleeve rent <id>` | — | Same as `sleeve_rent` |
| `sleeve_status` / `shell_status` | — | Current shell + tradeoffs |
| `sleeve_close` | — | Close panel flag |
| `sleeve_street` / `sleeve_club` / `sleeve_undercity` | — | Direct hop shortcuts |
| `house` / `housing` | — | Toggle safehouse (required for hop) |

## Snapshot (`sleeves`)

| Field | Meaning |
|-------|---------|
| `current` / `current_name` | Active shell id / display name |
| `stats` | Live ATK / DEF / HACK / max_hp / max_focus |
| `shells[]` | Catalog rows (`premium`, `rent_credits`, `accessible`, `owned`, `rented`, `current`, tradeoffs) |
| `at_safehouse` | `housing.at_home` |
| `hops` | Successful hops this session |
| `last_rent` | Last rent card (`shell_id`, `credits`) |
| `panel_open` | UI hint |
| `hint` | Short player guidance |

## Web UI

Dock **Sleeve** · side panel lists all three shells with **Hop** / **Rent** / **Rent+Hop** · **Toggle safehouse** · **Shift+H** opens panel + `sleeves` action.

## Design notes

- Street is always owned; club / undercity rent is **optional** — you can stay on street forever.
- Rent is per-session access (not a permanent unlock), so rich couriers keep paying for peacock / tunnel kits.
- Skill bumps (`streetwise`, `jacker`, …) are re-applied after each hop so sleeve bases stay consistent.
