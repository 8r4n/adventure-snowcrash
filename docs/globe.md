# Globe map + region teleport

Issue **#54** (parent campaign **#42**). Playable Earth zoom + uplink-hop onto locale shards. Daily news (#51) can stamp `region_id` / geo on story beats.

Source: `snowcrash/systems/globe.py` (`GlobeMixin`), data `snowcrash/systems/data/regions.json`, ASCII packs `snowcrash/systems/data/shards/`, loader `snowcrash/systems/ascii_shard.py`, web panel in `game.js` / `index.html`.

OSM research + converter: **#83** · [osm-procedural-globe.md](osm-procedural-globe.md) · `scripts/osm_to_ascii_shard.py`.

## Player fantasy (this slice)

1. Open **Globe** dock (or **Shift+G** / action `globe`)
2. Zoom ladder: **Street** → **Regions** → schematic **Globe** (`globe_zoom`)
3. **Search** / ASCII filter in the panel (or `globe_search` / `globe_filter`)
4. **Preview** a pin (`globe_preview`) — street flavor / ASCII strip / hop quote
5. **Hop** / `teleport <region_id>` — credits + cooldown (UI shows when blocked)
6. Land on a **playable street shard**:
   - Prefer prebuilt `snowcrash_ascii_shard_v1` when `regions.json` has `chunk_path` (OSM→ASCII pilots)
   - Else `generate_world(shard_seed)` mapgen
   - Home (`fractured_la`) = live shared MMORPG world
7. StreetNet daily geo beats (#51) show on journal + retarget compass (`globe_track`); news pins use beat lat/lon when stamped

## Actions

| Action | Arg | Effect |
|--------|-----|--------|
| `globe` / `open_globe` | — | Open overlay; zoom out from street if needed |
| `globe_close` | — | Close overlay; zoom → street |
| `globe_zoom` / `zoom_globe` | `street` \| `region` \| `globe` | Zoom ladder |
| `globe_search` / `region_search` | query | Filter catalog by id/name/continent/label |
| `globe_filter` | `ascii` \| `all` | Toggle ASCII-shard pilot filter |
| `globe_track` / `track_geo` | `region_id` \| `clear` | Point compass / journal at geo objective |
| `globe_preview` / `preview_region` | `region_id` \| `clear` | Pin preview card (street flavor + hop quote) |
| `globe_status` / `where` | — | Log current region + cooldown |
| `teleport` / `tp` / `uplink_hop` | `region_id` | Hop to region shard |
| `globe_recall` / `recall` | — | Hop home (half cost) |
| `globe_failsafe` | — | Return to last safe region (no soft-lock) |

Defaults (overridable in `regions.json`): **15 credits**, **45s** cooldown. Home recall costs half.

Blocked while `cyberspace` / `heist` / `flotilla` / dead — jack out first.

## Regions data

`regions.json` lists continents + cities with `id`, `name`, `kind`, `continent`, `lat`, `lon`, `label`, optional `home`, `shard_seed`, optional **`chunk_path`**.

- **Home** (`fractured_la`): live shared MMORPG world (server seed).
- **ASCII pilots** (fixture-derived OSM schema, CI-safe): `neo_tokyo`, `berlin_circuit`, `neo_nyc`, `london_fog`, `singapore_core`, `sydney_reef` → `shards/*.json` via `ascii_shard.try_load_region_shard`.
- **Other regions**: lazy `generate_world(shard_seed)` shards, streamed only when a courier is present.

Hot-reload: `world.reload_region_defs()` reloads JSON and drops cached shards whose `chunk_path` changed; `world.reload_shard_packs(force=True)` forces a full cache drop (next hop rebuilds).

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

`panel_open`, `region_id`, `region`, `home_region_id`, `regions[]` (incl. `has_ascii_shard`, `street_flavor`, `has_news`, `news_lat`/`news_lon`), `cost_credits`, `recall_cost_credits`, `credits`, `can_afford_hop`, `hop_ready`, `hop_block_reason` / `hop_block_message`, `cooldown_sec`, `cooldown_remaining`, `teleports`, `shards_loaded`, `shard_seed`, `shard_source`, `chunk_path`, `zoom`, `zoom_levels`, `search`, `filter_ascii`, `ascii_shard_count`, `geo_objectives[]` (prefer beat `lat`/`lon` when stamped), `tracked_geo_region`, `preview_region_id`, `preview` (street flavor + ASCII strip + hop quote + news), `news_geo_hook`, `hint`.

## News geo hook (#51)

Daily storylines (`DailyStorylinesMixin`) **always** resolve a `region_id` before firing:

1. Explicit `beat.region_id` if it exists in `regions.json`
2. Else nearest region from `lat` / `lon`
3. Else stable hash of beat id across city regions

Then `attach_news_arc` / `attach_news_geo` stamps `geo`, the live beat is mutated, journal gets a `geo_daily_*` side quest, and compass can retarget via `_globe_objective` / `globe_track`.

```python
beat = world.attach_news_geo(
    {"text": "StreetNet allegory beat..."},
    region_id="neo_tokyo",  # or lat=..., lon=...
)
# beat["region_id"], beat["geo"] = {region_id, name, lat, lon, continent}
```

Nearest-region snap when only lat/lon is provided.

Season forecasts (#58) prefer `world.attach_news_arc(...)` which stamps geo via this hook and bumps news-arc intensity. Geo-only stamps still soft-bump intensity when the forecast lattice is online.

Ops notes: [daily-storylines.md](daily-storylines.md) — append dated `entries[]`; production agent should keep calling `reload_daily_storylines()` (already stamps geo).

## Web UI

Dock **Globe** · zoom ladder **Street / Regions / Globe** · **search box** + **ASCII / All** filter · StreetNet geo chips · schematic SVG Earth with pins (ASCII / **NEWS** / selected) · **pin preview** card (street flavor, landmarks, ASCII strip, hop cost/cooldown) before **Hop** · credits + cooldown meter · region list **Preview** / **Hop** · **Recall home**. Godot dock + 3D globe mirror preview / hop-block reasons. Shift+G opens panel + `globe` action. Touch-friendly search (`inputmode=search`, min tap height).

## Remaining (#54 — leave open)

Not claimed done in this slice:

- [ ] Full continent intermediate zoom (beyond street/region/globe ladder)
- [ ] Live Geofabrik / Overpass city packs (pilots remain fixture-derived for CI)
- [ ] Photoreal / licensed Earth art (explicitly out of scope)
- [ ] Full-Earth coverage of OSM shards (six pilots today — not the whole globe)
- [ ] Richer pin filters (ecology / faction / fog) beyond search + ASCII toggle
- [ ] Production daily-news agent automation beyond in-server `reload_daily_storylines` hook

Shipped earlier: region search + ASCII catalog UX, city ASCII pilots, daily beats land with `region_id` / geo, journal + compass cross-region geo track.

Shipped in this slice: **pin preview / street flavor** before hop (`globe_preview`), hop **cost/cooldown UX** (credits meter, blocked reasons) on web + Godot dock/3D globe, **news-geo pins** prefer stamped beat lat/lon on the schematic Earth.

## Ecology overlay (#57)

Scarce resource nodes (bandwidth / water / uplink spectrum) appear on globe pins via `ecology_nodes` and per-region `has_ecology`. See [ecology.md](ecology.md).
