# Year backend actions & snapshot fields

## New / extended actions
| Action | Arg | Issue |
|--------|-----|-------|
| `skill_pick` | skill id | #12 |
| `set_loadout` | — | #12 |
| `buy` / `sell` | item id / inv idx | #13 |
| `party_invite` / `party_accept` / `party_leave` / `party_ping` | name / id | #15 |
| `respawn` | `safe_pad` \| `district` \| `housing` | #16 |
| `craft` / `craft_list` | recipe id | #21 |
| `house` / `stash_put` / `stash_take` | idx | #22 |
| `crew_create` / `crew_join` / `crew_leave` / `crew_stash` | … | #26 |
| `contract_list` / `contract_accept` / `contract_turnin` | id | #27 |
| `pvp_optin` / `pvp_optout` / `pvp_arena` | enter\|leave | #28 |
| `spectate` / `unspectate` / `replay_dump` | name | #29 |
| `mute` / `unmute` / `report` / `kick` | nick | #30 |
| `season_equip` | cosmetic id | #33 |
| `repair` / `pay_bandwidth` | — | #36 |
| `raid_start` / `raid_leave` | — | #35 |
| `auth_nick` | nick | #25 |
| `ice_probe` / `probe` / `ice` | `stun` \| `reveal` \| `scramble` (or `list`) | #46 |
| `ice_stun` / `probe_reveal` / … | — (id in action name) | #46 |
| `jack_in` / `jackin` / `cyberspace` | optional `maze` \| `ice_gate` | #47 |
| `jack_out` / `unjack` / `escape` (while jacked) | — | #47 |
| `heist_start` / `deep_heist` / `ice_heist` | — (at jackpoint J) | #56 |
| `jack_in heist` | `heist` \| `vault` \| `deep` | #56 |
| `heist` / `heist_status` | — | #56 |
| `heist_abort` / Esc (in heist) | — (stun/debt/heat, no soft-lock) | #56 |
| `enter_flotilla` / `flotilla` / `signal_finale` | — (need 3 Signal Keys near pad) | #45 |
| `leave_flotilla` / Esc (in room) | — | #45 |
| `signal_keys` / `signal_status` | — | #45 |
| `neon_dash` / `dash_status` / `dash` | — | #48 |
| `heat` / `heat_status` / `corp_heat` | — | #50 |
| `corp_patrol` / `patrol_status` | — | #50 |
| `contest_patrol` / `crew_contest` | — (need crew) | #50 |
| `hardcore` / `soft_hardcore` / `hardcore_on` / `hardcore_off` | on\|off | #49 |
| `pay_hardcore_debt` / `hardcore_debt` | — | #49 |

Player docs: [ice-probes.md](ice-probes.md), [cyberspace.md](cyberspace.md), [ice-heists.md](ice-heists.md), [signal-keys.md](signal-keys.md), [neon-dash.md](neon-dash.md), [soft-hardcore.md](soft-hardcore.md).

## Snapshot fields
`skills`, `loadout`, `skill_picks_available`, `shop`, `events`, `party`, `dead`, `respawn_options`, `kill_feed`, `journal`, `district`, `boss`, `craft`, `housing`, `weather`, `tod`, `crew`, `contracts`, `reputation`, `pvp`, `season`, `spectating`, `auth_nick`, `raid`, `economy`, `aoi_radius`, `ice` (probes / nearby / focus), `cyberspace` (active node or `can_jack_in`), `ice_heist` (vault layers / omen / AI stub), `signal_keys` (keys / finale / pad), `neon_dash` (timer / checkpoints / progress), `heat` (meter / shed / patrol), `corp_patrol` (patrol card), `soft_hardcore`, `death_cause`
