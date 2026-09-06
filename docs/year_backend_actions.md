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
| `globe` / `open_globe` / `globe_status` | — | #54 |
| `teleport` / `tp` / `uplink_hop` | region_id | #54 |
| `globe_recall` / `recall` | — | #54 |
| `globe_failsafe` | — | #54 |
| `sleeves` / `sleeve` / `sleeve_rent` / `sleeve_status` | street|club|undercity | #59 |
| `sleeve_street` / `sleeve_club` / `sleeve_undercity` | — | #59 |
| `primer` / `open_primer` / `primer_start` / `primer_close` | chapter id | #60 |
| `jaunte` / `street_jaunt` / `jaunt` | short\|district\|globe … | #62 |
| `jaunte_short` / `jaunte_district` / `jaunte_globe` | dir\|id\|region | #62 |
| `jaunte_train` / `jaunte_status` / `jaunte_close` | — | #62 |
| `skill_pick` | `uplink_jaunte` (rank +1) | #62 · #12 |
| `empathy` / `bounty_board` / `empathy_status` | — | #63 |
| `empathy_audit` / `audit` | — | #63 |
| `empathy_answer` | `a` | `b` | `c` | #63 |
| `bounty_accept` | `retire` | `reclaim` | #63 |
| `bounty_reclaim` / `empathy_bind` | — (adjacent) | #63 |
| `bounty_turnin` / `bounty_abandon` / `bounty_list` | optional type | #63 |
| `forecast` / `forecast_status` / `forecast_close` | — | #58 |
| `forecast_nudge` / `nudge` | metric [up|down] | #58 |
| `nudge_ambush` / `nudge_flotilla` / `nudge_news` | optional up|down | #58 |
| `pilgrimage_open` / `pilgrim_lobby` | — | #61 |
| `pilgrimage_join` | lobby id | #61 |
| `pilgrimage_ready` / `pilgrimage_unready` | — | #61 |
| `pilgrimage_start` | optional `dev` | #61 |
| `pilgrimage` / `pilgrimage_status` | — | #61 |
| `pilgrim_complete` / `seal_canticle` | — (at shrine) | #61 |
| `enter_pilgrimage` / `canticle_finale` | — (shared Spire) | #61 |
| `leave_pilgrimage` / Esc (in Spire) | — | #61 |
| `ecology` / `ecology_list` / `ecology_status` | — | #57 |
| `ecology_contract` / `resource_contract` | optional node_id | #57 |
| `ecology_claim` / `claim_resource` | node_id \| region_id | #57 |
| `ecology_raid` / `resource_raid` | node_id \| region_id | #57 |
| `ecology_raid_resolve` | optional raid id | #57 |

Player docs: [ice-probes.md](ice-probes.md), [cyberspace.md](cyberspace.md), [ice-heists.md](ice-heists.md), [signal-keys.md](signal-keys.md), [neon-dash.md](neon-dash.md), [soft-hardcore.md](soft-hardcore.md), [globe.md](globe.md), [sleeves.md](sleeves.md), [primer.md](primer.md), [jaunte.md](jaunte.md), [empathy-bounties.md](empathy-bounties.md), [season-forecasts.md](season-forecasts.md), [pilgrimage.md](pilgrimage.md), [ecology.md](ecology.md).

## Snapshot fields
`skills`, `loadout`, `skill_picks_available`, `shop`, `events`, `party`, `dead`, `respawn_options`, `kill_feed`, `journal`, `district`, `boss`, `craft`, `housing`, `weather`, `tod`, `crew`, `contracts`, `reputation`, `pvp`, `season`, `spectating`, `auth_nick`, `raid`, `economy`, `aoi_radius`, `ice` (probes / nearby / focus), `cyberspace` (active node or `can_jack_in`), `ice_heist` (vault layers / omen / AI stub), `signal_keys` (keys / finale / pad), `neon_dash` (timer / checkpoints / progress), `heat` (meter / shed / patrol), `corp_patrol` (patrol card), `soft_hardcore`, `globe` (region / Earth pins / cooldown / news_geo_hook), `sleeves`, `primer` (teaching chapters / rewards), `jaunte` (Uplink Hop ranks / cooldown / feedback), `empathy` (audit / synth bounties / heat·rep), `forecast` (week / 3 metrics / nudge / season·news hooks), `pilgrimage` (lobby 3–5 / Canticle beat / Spire finale), `ecology` (scarce nodes / controllers / StreetNet / weather), `death_cause`
