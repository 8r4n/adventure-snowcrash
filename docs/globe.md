# Globe map + region teleport

Issue **#54** (parent campaign **#42**). First playable slice: zoom out to a schematic Earth, pick a region, **uplink-hop** onto a mapgen shard for that locale. Enables daily news (#51) to stamp `region_id` / geo on story beats.

Source: `snowcrash/systems/globe.py` (`GlobeMixin`), data `snowcrash/systems/data/regions.json`, web panel in `game.js` / `index.html`.

## Player fantasy (this slice)

1. Open **Globe** dock (or **Shift+G** / action `globe`)
2. Schematic Earth + region list (continents + major cities — full coverage model as data)
3. **Hop** / `teleport <region_id>` — credits + cooldown
4. Land on a **playable street shard** seeded from the region's `shard_seed` (home = live Fractured LA world)

## Actions

| Action | Arg | Effect |
|--------|-----|--------|
| `globe` / `open_globe` | — | Open overlay; snapshot `panel_open` |
| `globe_close` | — | Close overlay |
| `globe_status` / `where` | — | Log current region + cooldown |
| `teleport` / `tp` / `uplink_hop` | `region_id` | Hop to region shard |
| `globe_recall` / `recall` | — | Hop home (half cost) |
| `globe_failsafe` | — | Return to last safe region (no soft-lock) |

Defaults (overridable in `regions.json`): **15 credits**, **45s** cooldown. Home recall costs half.

Blocked while `cyberspace` / `heist` / `flotilla` / dead — jack out first.

## Regions data

`regions.json` lists continents + cities with `id`, `name`, `kind`, `continent`, `lat`, `lon`, `label`, optional `home`, `shard_seed`.

- **Home** (`fractured_la`): live shared MMORPG world (server seed).
- **Other regions**: lazy `generate_world(shard_seed)` shards, streamed only when a courier is present (interest / shard streaming).

Hot-reload: `world.reload_region_defs()`.

## Snapshot (`globe`)

`panel_open`, `region_id`, `region` (name/lat/lon/...), `home_region_id`, `regions[]`, `cost_credits`, `cooldown_sec`, `cooldown_remaining`, `teleports`, `shards_loaded`, `shard_seed`, `zoom`, `news_geo_hook`, `hint`.

## News geo hook (#51)

```python
beat = world.attach_news_geo(
    {"text": "StreetNet allegory beat..."},
    region_id="neo_tokyo",  # or lat=..., lon=...
)
# beat["region_id"], beat["geo"] = {region_id, name, lat, lon, continent}
```

Nearest-region snap when only lat/lon is provided.

Season forecasts (#58) prefer `world.attach_news_arc(...)` which stamps geo via this hook and bumps news-arc intensity. Geo-only stamps still soft-bump intensity when the forecast lattice is online.

## Web UI

Dock **Globe** · schematic SVG Earth with pins · region list **Hop** buttons · **Recall home**. Shift+G opens panel + `globe` action.

## Remaining (#54 — leave open)

Not claimed done in this slice:

- [ ] Multi-level zoom UX (street → district → continent → globe) beyond open/close
- [ ] Search / pin filters; StreetNet / journal / compass pointing at cross-region geo objectives
- [ ] Hand-authored locale flavor beyond mapgen seeds
- [ ] Photoreal / licensed Earth art (explicitly out of scope)
- [ ] Daily news pipeline (#51) consuming `attach_news_geo` in production automation

This stub is enough for news to attach `region_id` and for players to hop onto playable shards.

## Ecology overlay (#57)

Scarce resource nodes (bandwidth / water / uplink spectrum) appear on globe pins via `ecology_nodes` and per-region `has_ecology`. See [ecology.md](ecology.md).
