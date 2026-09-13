# Globe map + region teleport

Issue **#54** (parent campaign **#42**). Playable Earth zoom + uplink-hop onto locale shards. Daily news (#51) can stamp `region_id` / geo on story beats.

Source: `snowcrash/systems/globe.py` (`GlobeMixin`), data `snowcrash/systems/data/regions.json`, ASCII packs `snowcrash/systems/data/shards/`, loader `snowcrash/systems/ascii_shard.py`, web panel in `game.js` / `index.html`.

OSM research + converter: **#83** · [osm-procedural-globe.md](osm-procedural-globe.md) · `scripts/osm_to_ascii_shard.py`.

## Player fantasy (this slice)

1. Open **Globe** dock (or **Shift+G** / action `globe`)
2. Zoom ladder: **Street** → **Regions** → schematic **Globe** (`globe_zoom`)
3. **Hop** / `teleport <region_id>` — credits + cooldown
4. Land on a **playable street shard**:
   - Prefer prebuilt `snowcrash_ascii_shard_v1` when `regions.json` has `chunk_path` (OSM→ASCII pilots)
   - Else `generate_world(shard_seed)` mapgen
   - Home (`fractured_la`) = live shared MMORPG world

## Actions

| Action | Arg | Effect |
|--------|-----|--------|
| `globe` / `open_globe` | — | Open overlay; zoom out from street if needed |
| `globe_close` | — | Close overlay; zoom → street |
| `globe_zoom` / `zoom_globe` | `street` \| `region` \| `globe` | Zoom ladder |
| `globe_status` / `where` | — | Log current region + cooldown |
| `teleport` / `tp` / `uplink_hop` | `region_id` | Hop to region shard |
| `globe_recall` / `recall` | — | Hop home (half cost) |
| `globe_failsafe` | — | Return to last safe region (no soft-lock) |

Defaults (overridable in `regions.json`): **15 credits**, **45s** cooldown. Home recall costs half.

Blocked while `cyberspace` / `heist` / `flotilla` / dead — jack out first.

## Regions data

`regions.json` lists continents + cities with `id`, `name`, `kind`, `continent`, `lat`, `lon`, `label`, optional `home`, `shard_seed`, optional **`chunk_path`**.

- **Home** (`fractured_la`): live shared MMORPG world (server seed).
- **ASCII pilots** (v1): `neo_tokyo`, `berlin_circuit` → `shards/*.json` via `ascii_shard.try_load_region_shard`.
- **Other regions**: lazy `generate_world(shard_seed)` shards, streamed only when a courier is present.

Hot-reload: `world.reload_region_defs()` (keeps loaded shards until next teleport rebuild).

### How shards load on teleport

```
teleport(region_id)
  → _globe_ensure_shard(region_id)
      if region.chunk_path and snowcrash_ascii_shard_v1 loads:
          world_from_ascii_shard(chunk)   # scale stamp into MAP_WIDTH×MAP_HEIGHT
          pack.shard_source = "osm_ascii"
      else:
          generate_world(shard_seed)
          pack.shard_source = "mapgen"
  → bind world pack, place courier near spawn
```

Rebuild pilot JSON offline:

```bash
python3 scripts/osm_to_ascii_shard.py \
  --input scripts/fixtures/tiny_downtown.osm.xml \
  --width 64 --height 40 \
  -o snowcrash/systems/data/shards/neo_tokyo.json
```

(Then set `"region_id"` / `chunk_path` in the pack + `regions.json`.)

## Snapshot (`globe`)

`panel_open`, `region_id`, `region`, `home_region_id`, `regions[]` (incl. `has_ascii_shard`), `cost_credits`, `cooldown_sec`, `cooldown_remaining`, `teleports`, `shards_loaded`, `shard_seed`, `shard_source`, `chunk_path`, `zoom`, `zoom_levels`, `news_geo_hook`, `hint`.

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

Dock **Globe** · zoom ladder **Street / Regions / Globe** · schematic SVG Earth with pins (ASCII pilots highlighted) · region list **Hop** · **Recall home**. Shift+G opens panel + `globe` action.

## Remaining (#54 — leave open)

Not claimed done in this slice:

- [ ] Full continent intermediate zoom / search / pin filters
- [ ] StreetNet / journal / compass pointing at cross-region geo objectives
- [ ] Live Geofabrik / Overpass pilot city packs (still fixture-derived ASCII for CI)
- [ ] Photoreal / licensed Earth art (explicitly out of scope)
- [ ] Daily news pipeline (#51) consuming `attach_news_geo` in production automation
- [ ] Full-Earth coverage of OSM shards (only pilot `chunk_path`s today)

Enough for news to attach `region_id`, players to hop onto playable shards, and OSM ASCII packs to land where wired.

## Ecology overlay (#57)

Scarce resource nodes (bandwidth / water / uplink spectrum) appear on globe pins via `ecology_nodes` and per-region `has_ecology`. See [ecology.md](ecology.md).
