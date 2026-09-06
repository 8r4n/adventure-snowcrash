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
| `enter_flotilla` / `flotilla` / `signal_finale` | — (need 3 Signal Keys near pad) | #45 |
| `leave_flotilla` / Esc (in room) | — | #45 |
| `signal_keys` / `signal_status` | — | #45 |

Player docs: [ice-probes.md](ice-probes.md), [cyberspace.md](cyberspace.md), [signal-keys.md](signal-keys.md).

## Snapshot fields
`skills`, `loadout`, `skill_picks_available`, `shop`, `events`, `party`, `dead`, `respawn_options`, `kill_feed`, `journal`, `district`, `boss`, `craft`, `housing`, `weather`, `tod`, `crew`, `contracts`, `reputation`, `pvp`, `season`, `spectating`, `auth_nick`, `raid`, `economy`, `aoi_radius`, `ice` (probes / nearby / focus), `cyberspace` (active node or `can_jack_in`), `signal_keys` (keys / finale / pad)
