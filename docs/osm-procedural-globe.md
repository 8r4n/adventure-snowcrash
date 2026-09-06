# Research: procedural globe from OpenStreetMap → ASCII Metaverse shards

Issue **#83** (parent campaign **#42**). Extends globe teleport (**#54**) and geo-placed daily news (**#51**) so region hops can land on shards that *feel* like real cities — without shipping Planet OSM in the binary, without proprietary map tiles, and without novel-copyrighted prose.

Spike script: [`scripts/osm_to_ascii_shard.py`](../scripts/osm_to_ascii_shard.py)  
Offline fixture: [`scripts/fixtures/tiny_downtown.osm.xml`](../scripts/fixtures/tiny_downtown.osm.xml)

---

## Executive summary

| Question | Finding |
|----------|---------|
| Can we generate a globe of playable ASCII shards from OSM? | **Yes**, at city / district scale first; planet scale only via lazy streaming of extracts. |
| What ships in-repo? | Pipeline code + tiny synthetic fixtures + attribution docs. **Not** full Geofabrik extracts. |
| License? | OSM data is **ODbL**; Produced Works (rendered ASCII maps) need attribution; Derivative Databases (substantial extracts we redistribute) stay share-alike. |
| Fit with current game? | Globe (#54) already lazy-loads `generate_world(shard_seed)`. Next step: optionally load `snowcrash_ascii_shard_v1` JSON tiles instead of pure procedural seeds. |
| Pilot path | Cache packs for themed LA / Tokyo / Lagos / Berlin bboxes → wire `regions.json` `shard_seed` / chunk path → expand. |

---

## Data sources

### Recommended by scale

| Scale | Source | Notes |
|-------|--------|-------|
| **District / small city bbox** (spike, CI, Overpass) | [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API) | Filtered queries only. Public instances: rate limits, no planet scraping, no stitching thousands of bboxes. Prefer own instance or Geofabrik for anything heavy. |
| **City / metro / country** | [Geofabrik extracts](https://download.geofabrik.de/) (`.osm.pbf`, daily) | Best default for build-time packs. Use Osmium / Pyosmium to clip further. |
| **Planet / multi-region vector tiles** | [Protomaps](https://docs.protomaps.com/) daily PMTiles + `pmtiles extract --bbox=…` | Good for basemap-style subsets; still ODbL for OSM-derived content. |
| **Full planet dump** | [planet.openstreetmap.org](https://planet.openstreetmap.org/) | Multi‑GB; ops concern only — never embed in the game client. |
| **Diffs / freshness** | Geofabrik daily `.osc.gz`, OSM minutely/hourly diffs | Feed shard rebuild jobs; see Update cadence. |

### What *not* to use

- Google / Apple / Mapbox **proprietary raster tiles** (license + “do not paste copyrighted map tiles”).
- Scraping rendered OSM.org PNG/JPEG tiles as art assets.
- Overpass as a planet CDN.

### Spike / CI

Bundled **synthetic** OSM-schema XML (`scripts/fixtures/tiny_downtown.osm.xml`) exercises the converter offline. Live `--bbox` Overpass is optional and expected to fail gracefully in CI.

```bash
python scripts/osm_to_ascii_shard.py --preview-only
python scripts/osm_to_ascii_shard.py -o /tmp/shard.json --width 64 --height 40
# optional live (network, etiquette-bound):
# python scripts/osm_to_ascii_shard.py --bbox -118.252,34.048,-118.246,34.052
```

---

## ODbL / license notes

OSM data is licensed under the **Open Database License (ODbL)** by the OpenStreetMap Foundation. Practical guidance (OSMF Attribution Guidelines + [openstreetmap.org/copyright](https://www.openstreetmap.org/copyright)):

1. **Credit OpenStreetMap** in any public Produced Work (game maps, globe UI when showing OSM-derived shards).
2. **Make ODbL clear** — typically link `https://www.openstreetmap.org/copyright` (covers ODbL + upstream credits OSM itself must give).
3. **Safe harbour for games:** splash / credits / About / in-map corner notice. Historical forms `© OpenStreetMap contributors` or `© OpenStreetMap` (with license link) are acceptable.
4. **Derivative Database** (substantial extracts we redistribute as data packs): keep notices; share-alike under ODbL (or publish the transform). In-repo tiny fixtures that are *invented* geometry are **not** OSM data — label them clearly; swap to real extracts before claiming geo fidelity.
5. **Do not** imply OSM endorses the game; qualify as “Map data from OpenStreetMap” when we restyle heavily.
6. **MIT game code** (this repo) stays MIT; **OSM-derived databases** remain under ODbL obligations separately. Document both in README / About when packs ship.

**Attribution string to use in UI / shard JSON:**

> © OpenStreetMap contributors — https://www.openstreetmap.org/copyright  
> Map data available under the Open Database License (ODbL).

Shard JSON from the spike already carries an `attribution` object (`scripts/osm_to_ascii_shard.py`).

---

## Pipeline: OSM → ASCII glyphs

```
OSM XML/PBF  →  filter tags  →  project WGS84→grid  →  raster paint  →  theme pass
                     │                                      │
                     ├─ highway=*                           ├─ snowcrash.constants glyphs
                     ├─ building=*                          ├─ landmarks J / U / &
                     ├─ water / park / landuse               └─ chunk JSON or mapgen seed
                     └─ amenity / shop POIs
```

### Stages

1. **Ingest** — fixture XML, clipped PBF, or Overpass XML.
2. **Project** — equirectangular within bbox → `width×height` cell grid (spike); later Web Mercator tile indices for streaming.
3. **Rasterize** (paint order): grass base → parks → water → building footprints (floor + wall ring) → highways (thin `=` strokes) → POIs last.
4. **Theme** — map OSM tags → Metaverse districts (neon club, Faraday industrial, uplink rim) **without** copying real brand names or novel text; invent flavored labels (`regions.json` already does this).
5. **Emit** — `snowcrash_ascii_shard_v1` JSON (`tiles[]` rows of glyphs, `landmarks`, `shard_seed`, `bbox`, `attribution`) and/or a deterministic `shard_seed` for today’s `generate_world(seed)` fallback.
6. **Load** — GlobeMixin (`snowcrash/systems/globe.py`) today builds shards via `generate_world(shard_seed)`. Future hook: if `regions.json` has `chunk_path` / embedded tiles, hydrate `GameMap` from the chunk instead.

### Zoom ladder (ties to #54)

| Zoom | Representation | Data |
|------|----------------|------|
| Globe pins | Schematic Earth + `regions.json` | Already shipped (#54 slice) |
| City overview | Coarse ASCII / district glyphs | Downsampled shard or separate low-res pack |
| Street FPV | Full walkable shard | OSM-derived or mapgen seed |
| Multiplane | UNDER / STREET / AIR | Infer tunnels from `tunnel=*`, bridges from `bridge=*`, rooftops from building height tags where useful |

---

## ASCII feature mapping table

Aligned with `snowcrash/constants.py` glyphs used by mapgen / FPV / Street GPS:

| OSM feature / tags | ASCII / game | Notes |
|--------------------|--------------|-------|
| `highway=motorway/trunk/primary/secondary` | `=` street | Wider paint in converters; walkable |
| `highway=residential/service/tertiary/…` | `=` / `.` alley | Thin stroke; service → alley feel |
| `highway=footway/path/pedestrian` | `.` | Optional; keep sparse |
| `building=*` footprint | `#` outline, `.` interior | Carve doors `+` at street adjacency (future) |
| `natural=water`, `waterway=*`, `landuse=basin` | `~` | Canals as 1-cell strokes |
| `leisure=park`, `landuse=grass` | `,` | Outdoor yards |
| Default undeveloped cell | `,` or `#` | Spike uses grass base |
| `amenity=internet_cafe` / telecom / “jack” POIs | `J` jackpoint | Metaverse theming of access kiosks |
| `amenity=bank/atm/bureau_de_change` / uplink-ish | `U` uplink | Fiction label; not a real bank brand |
| `amenity=bar/nightclub`, clubs | `&` NPC pad | Club district spawns |
| `shop=*`, markets, cafes | `&` vendor | Loot / dialogue pads |
| `landuse=industrial` | Faraday / undercity yards (`.`) | Heat / ICE theming hooks |
| `place=city/suburb/neighbourhood` | Globe `region_id` + flavored `label` | **Original** district names only |
| `bridge=yes` | STREET over water; AIR plane cue | Multiplane later |
| `tunnel=yes`, `highway` underground | UNDER plane corridors | Multiplane later |
| `railway=*` | Optional `#` or `=` | Low priority v1 |
| `building:levels` / `height` | AIR rooftop walkability | Optional |

Entity glyphs (`@`, `i`, `t`, `d`, `*`) stay gameplay — not OSM-derived.

---

## Theming into Metaverse (no novel text)

- **Structure from OSM, fiction from us.** Street topology and coastlines inform the grid; names in `regions.json` / NPC lines remain original Snowcrash-inspired Metaverse copy (courier hubs, Flotilla rim, Faraday yards).
- **No copyrighted map art.** We never ship OSM.org / Google tile imagery; only geometries → our glyphs.
- **Brand scrub.** Drop or rewrite `name=*` that are real trademarks when surfacing to players; keep geometry.
- **District skins.** Tag aggregates → neon club blocks, burbclave residential, uplink rim, industrial Faraday — cosmetic + spawn tables, not scraped slogans.
- **News (#51).** `attach_news_geo` already stamps `region_id` / lat-lon; OSM shards make those pins *playable* without pasting headlines.

---

## Streaming / shards

Current (#54): `GlobeMixin.globe_shards` lazy-builds one mapgen world per visited `region_id`; home stays the live shared MMORPG world; AI ticks only loaded shards.

Proposed OSM-aware evolution:

1. **Interest management** — load chunk when a courier teleports in; unload / freeze after idle TTL (credits / housing stay in durable store, not in RAM tiles).
2. **Pack layout** — `packs/<region_id>/shard.json` (+ optional `.osm.pbf` build artifact ignored by git LFS policy as needed).
3. **Tile pyramid** — z0–z6 overview from Protomaps or downsampled ASCII; z14–z16 street shards from Geofabrik clips.
4. **Do not hold Earth in RAM** — hard rule; planet dump is an offline build input only.
5. **AOI** — reuse existing `snowcrash/systems/aoi.py` snapshot limits per shard.

---

## Pilot cities

Match / extend `regions.json` fiction IDs (examples):

| Pilot | Fiction region id | Why |
|-------|-------------------|-----|
| Greater LA basin clip | `fractured_la` (home) | Campaign hub; validate overlay vs current hand-tuned mapgen |
| Tokyo metro clip | `neo_tokyo` (or equiv. in regions) | Dense street graph stress test |
| Lagos metro clip | African city pin in regions | Coastal + informal fabric variety |
| Berlin metro clip | European pin | Gridded + waterways |

**Offline packs:** commit only tiny fixtures + hashes; store large PBF/chunks on a build cache or release asset, not in git history.

---

## Update cadence

| Cadence | Action |
|---------|--------|
| **Daily / weekly CI** (optional) | Pull Geofabrik region extract or apply `.osc` diffs → rebuild pilot shard JSON → publish artifact. |
| **On teleport miss** | If pack missing, fall back to `generate_world(shard_seed)` (today’s behavior). |
| **Player housing / durable state** | Key by `region_id` + cell or building id **stable hash** of OSM `way id` when possible; on geometry regen, snap housing to nearest surviving footprint or refund — never silent wipe without migration note. |
| **Content freeze windows** | Season events (#51 arcs) pin shard build id in metadata so mid-week OSM edits don’t reshuffle quest anchors. |

---

## Risks

| Risk | Mitigation |
|------|------------|
| ODbL share-alike misunderstood | Document Produced Work vs Derivative Database; attribute in UI; don’t mix incompatible closed data into OSM packs. |
| Overpass abuse / CI flakes | Fixture-first spike; Overpass optional; Geofabrik for builds. |
| Huge RAM / download | Lazy shards; clip PBF; never embed planet. |
| Geo fidelity vs fun | Prefer “recognizable topology” over cadastral accuracy; hand-tune pilots. |
| PII / contributor metadata | Geofabrik public extracts already strip user/changeset fields — prefer those. |
| Real brand / defamation in POI names | Scrub `name=*` for player-facing strings. |
| Regenerating shards wipes bases | Stable IDs + migration policy (above). |
| Legal confusion with MIT repo license | Dual notice: code MIT, OSM data ODbL. |

---

## Spike status

| Deliverable | Status |
|-------------|--------|
| Research doc (this file) | **Done** |
| `scripts/osm_to_ascii_shard.py` | **Done** — fixture → ASCII grid + `snowcrash_ascii_shard_v1` JSON + `shard_seed` |
| Fixture `scripts/fixtures/tiny_downtown.osm.xml` | **Done** — synthetic schema, CI-safe |
| Live Overpass `--bbox` | Implemented; optional; not required for CI |
| Wire chunk → `GlobeMixin` / live teleport | **Not in this issue** — follow-up after #54 remaining zoom work |
| Full pilot city packs | **Out of scope** for #83 research |

Acceptance for **#83 research**: documented path + mapping table + license notes + working offline spike. Leave production globe OSM wiring to a child issue when ready.

---

## Links

- Parent campaign: **#42**
- Globe teleport stub: **#54** · [`docs/globe.md`](globe.md)
- Daily news geo: **#51**
- Map tools: **#37** (hot-reload / data-driven)
- OSMF attribution guidelines: https://osmfoundation.org/wiki/Licence/Attribution_Guidelines
- OSM copyright: https://www.openstreetmap.org/copyright
- ODbL: https://opendatacommons.org/licenses/odbl/
- Geofabrik downloads: https://download.geofabrik.de/
- Overpass API wiki: https://wiki.openstreetmap.org/wiki/Overpass_API
