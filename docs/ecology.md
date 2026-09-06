# Scarce resource ecology wars

Issue **#57** (parent campaign **#42** · related **#54** **#51** **#27** **#35**). Globe regions host contested **scarce resource nodes**. Crews and corps flip control via **contracts** and **raids**; weather / ecology labels shift with control. Visible on the **globe** and **StreetNet**.

Inspiration is Dune-style planetary ecology / resource control as a *playable loop* — remixed as original StreetNet lore only:

| Resource | Fantasy (original) |
|----------|--------------------|
| **Bandwidth** | Packet wells / mesh tolls — who owns the pipe owns the rumor |
| **Water** | Condensate / desal towers / fog nets — urban thirst, not desert prophecy |
| **Uplink spectrum** | Licensed Faraday channels — globe hops burn spectrum like fuel |

No Arrakis clones, spice, or copied proper nouns.

Source: `snowcrash/systems/ecology.py` (`EcologyMixin`), data `snowcrash/systems/data/ecology.json`, globe overlay in `globe.py` / `game.js`, dock **Ecology** · **Shift+R**.

## Acceptance map

| Criterion | How |
|-----------|-----|
| Resource nodes on ≥3 regions | `ecology.json` seeds 8 nodes across Fractured LA, Neo Tokyo, Lagos, Dubai, Sydney, London, Cairo, Singapore |
| Control flips via contracts/raids | `ecology_claim` (contract) · `ecology_raid` (raid instance) |
| Visible on globe + StreetNet | Globe pins + scarce-node strip; Ecology dock + event ticker `kind: ecology` + IRC on flips |
| docs + README | This file + README feature row |
| Tests | `tests/test_ecology.py` |

## Player loop

1. Open **Ecology** dock (**Shift+R**) or `ecology` / `ecology_list`
2. Optional: `ecology_contract <node_id>` — accept a scarce-resource claim contract
3. **Teleport** to the node region (`teleport neo_tokyo`, etc.)
4. Contest:
   - **Claim (contract):** `ecology_claim <node_id>` — spend Focus + credits in-region; flips control to your **crew** (or solo sleeve)
   - **Raid:** `ecology_raid <node_id>` — stages an ecology raid (#35 surface), resolves flip for party/crew
5. Watch **weather** label shift (mesh clarity / packet drought / condensate mist / dry signal / clean spectrum / spectrum hash)
6. StreetNet ticker + IRC announce flips; globe pins tint by resource

## Actions

| Action | Arg | Effect |
|--------|-----|--------|
| `ecology` / `open_ecology` | — | Open overlay |
| `ecology_close` | — | Close overlay |
| `ecology_list` / `scarce_list` | — | Log nodes |
| `ecology_status` | — | Local node + cooldown |
| `ecology_contract` / `resource_contract` | optional node_id | Offer/accept claim contract |
| `ecology_claim` / `claim_resource` | node_id or region_id | Contract flip (in-region) |
| `ecology_raid` / `resource_raid` | node_id or region_id | Raid flip (in-region) |
| `ecology_raid_resolve` | optional raid id | Seal active ecology raid |

Defaults (overridable in `ecology.json`): claim **3 Focus / 20 cr**, raid **4 Focus / 25 cr**, contest cooldown **~40s**. Home LA Packet Well is claimable without a hop.

Blocked while `cyberspace` / `heist` / `flotilla` / `pilgrimage` / dead.

## Snapshot (`ecology`)

`panel_open`, `nodes[]` (resource, controller, pressure, region lat/lon), `resources[]`, `local_node_ids`, `faction`, `claims` / `raids`, `cooldown_*`, costs, `streetnet[]`, `weather` (ecology-tied), `hooks`, `hint`.

Globe snapshot also carries `ecology_nodes[]` and per-region `ecology` / `has_ecology` for pins.

## Design notes

- Call it **StreetNet ecology** / **scarce nodes** — never trademarked desert-planet names in player strings.
- Controllers are `commons` · `corp` · `crew` · `courier` (solo micro-corp).
- Ambient `_tick_ecology` drifts pressure and soft-pushes StreetNet beats; high corp pressure biases hostile ecology weather.
- Hot-reload: `world.reload_ecology_defs()`.
