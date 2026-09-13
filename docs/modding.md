# Modder plugin framework

Issue **#72** (related **#37** editor/map tools · **#67** Steam packaging · **#42** campaign). External developers can extend adventure-snowcrash with **data-driven** content without forking core.

**Stack:** JSON manifests + defs loaded by a Python registry. **No arbitrary Python, Lua, WASM, or mod JavaScript** — justified below. Workshop distribution remains later (issue stays open).

Source: `snowcrash/systems/modding.py` (`ModdingMixin`), discovery roots `mods/` and `examples/plugins/`, example `examples/plugins/hello_courier/`.

**Plugin API:** `1.2.0` (additive: `ui_panel` over 1.1 hooks / 1.0 items).

## Acceptance map

| Criterion | Status |
|-----------|--------|
| Documented plugin API (path, manifest, versioning, capabilities) | This doc |
| Safe sandbox: no host FS/network by default; explicit permissions | Fail closed — see Security |
| Hooks: custom items + street events | Implemented (API 1.0) |
| Hooks: journal beats / quest steps | **Implemented (API 1.1)** |
| Hooks: StreetNet / world broadcasts | **Implemented (API 1.1)** |
| Hooks: ICE probes + lightweight cyberspace nodes | **Implemented (API 1.1)** |
| Hooks: globe pins / region metadata | **Implemented (API 1.1)** |
| Hooks: web UI dock panels | **Implemented (API 1.2)** |
| Hot-reload aligned with `/api/reload_defs` | `reload_mods()` inside reload path |
| Example `hello_courier` | Items + street events + journal + StreetNet + ICE + globe pin + **UI panel** |
| Semver + broken mods fail closed | `api_version` + hard errors skip the mod |
| Web UI dock (`ui_panel`) | **Implemented (API 1.2)** — CSP-safe markdown + allowlisted actions |
| WASM / Lua | **Not in this slice** — remains on #72 |

## Why JSON-first (not Lua/WASM yet)

| Option | Pros | Cons for v1 |
|--------|------|-------------|
| **JSON defs + Python loader** | Matches existing `districts.json` / ecology / storylines; easy to audit; no RCE surface | No custom scripted logic |
| Python entrypoints | Familiar | Arbitrary code = host compromise unless heavily sandboxed |
| Lua / WASM | Strong sandbox story | Larger runtime + packaging cost; defer to later phase / #67 |

Declarative content only for now. Scripted hooks can be added later behind explicit `exec`/`wasm` permissions that are **denied** today.

## Security model (fail closed)

1. **No code execution.** Only `json.load` of files under the mod directory. Web `ui_panel` bodies are escaped/sanitized markdown — **no mod JavaScript**.
2. **Path jail.** Entry paths must be relative; `..` and absolute paths rejected.
3. **Permissions allowlist.** Manifest must list capabilities. Unknown or denied permissions (`network`, `fs_write`, `exec`, `python`, `wasm`, …) **reject the whole mod**.
4. **API semver.** `api_version` major must match host `PLUGIN_API_VERSION` (`1.1.0`); required version must be `<=` host. Incompatible → skip mod, record error.
5. **Validation.** Ids, kinds, grids, lat/lon, and numeric ranges are sanitized; invalid defs reject the mod (not partial apply).
6. **No core overwrite.** Item / probe / region ids cannot collide with core factories or other mods. Globe metadata overlays are non-teleportable by default.
7. **Defaults.** No unsigned auto-download. No host FS/network. Mods must use **original** prose (no novel text).
8. **Disable.** `SNOWCRASH_DISABLE_MODS=1` skips discovery entirely.

Broken mods never crash the world: errors land in the registry / snapshot `mods.errors` and logs.

## Plugin API sketch

### Discovery

Ordered roots (deduped):

1. `SNOWCRASH_MODS_PATH` (os.pathsep-separated), if set
2. `<repo>/mods/`
3. `<repo>/examples/plugins/` unless `SNOWCRASH_EXAMPLE_PLUGINS=0`

Each immediate subdirectory with `mod.json` (or `manifest.json`) is a candidate.

### Manifest (`mod.json`)

```json
{
  "id": "hello_courier",
  "name": "Hello Courier",
  "version": "1.2.0",
  "api_version": "1.2.0",
  "description": "…",
  "author": "you",
  "license": "MIT",
  "attribution": "crediting assets / inspiration (original fiction only)",
  "permissions": [
    "items",
    "street_events",
    "journal",
    "streetnet",
    "ice_nodes",
    "globe_regions",
    "ui_panel"
  ],
  "entry": {
    "items": "items.json",
    "street_events": "street_events.json",
    "journal": "journal.json",
    "streetnet": "streetnet.json",
    "ice_nodes": "ice_nodes.json",
    "globe_regions": "globe_regions.json",
    "ui_panel": "ui_panel.json"
  }
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | `^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$` |
| `api_version` | yes | Semver of host plugin API this mod targets |
| `version` | yes | Mod package semver (informational) |
| `permissions` | yes | Subset of known capabilities |
| `entry` | no | Relative file map; defaults shown above |
| `attribution` | strongly recommended | Third-party credit; keep game text original |

### Permissions

| Permission | API | Effect |
|------------|-----|--------|
| `items` | 1.0 | Load `items.json` into item registry |
| `street_events` | 1.0 | Load weighted street broadcasts into year ticker |
| `journal` | **1.1** | Journal arcs + beats (`journal.json`) |
| `streetnet` | **1.1** | StreetNet / world broadcasts (`streetnet.json`) |
| `ice_nodes` | **1.1** | ICE probes + lightweight cyberspace nodes (`ice_nodes.json`) |
| `globe_regions` | **1.1** | Globe pins + metadata regions (`globe_regions.json`) |
| `ui_panel` | **1.2** | CSP-friendly YearUI dock panel (`ui_panel.json`) |
| `network` / `fs_*` / `exec` / `python` / `wasm` | **denied** | Always fail closed |

### Items (`items.json`)

```json
{
  "items": [
    {
      "id": "hello_courier.badge",
      "name": "Hello Courier Badge",
      "glyph": "*",
      "kind": "trinket",
      "description": "Original prop text.",
      "hack_bonus": 1,
      "equippable": true
    }
  ]
}
```

Kinds: `misc`, `med`, `weapon`, `armor`, `datachip`, `quest`, `trinket`. Prefer **namespaced** ids (`modid.name`).

### Street events (`street_events.json`)

```json
{
  "events": [
    {
      "id": "hello_courier.ping",
      "kind": "broadcast",
      "weight": 2.0,
      "messages": ["Hello Courier — example ping."],
      "player_log": "Mod event: ping."
    }
  ]
}
```

When the year street-event ticker fires, weighted mod street events / StreetNet broadcasts may take the band.

### Journal (`journal.json`) — API 1.1

```json
{
  "arcs": [
    {
      "id": "hello_courier.delivery",
      "title": "Hello Courier Delivery",
      "auto_offer": true,
      "steps": [
        {"id": "accept", "text": "Accept the delivery arc."},
        {"id": "badge", "text": "Sleeve the Hello Courier Badge."}
      ]
    }
  ],
  "beats": [
    {
      "id": "hello_courier.welcome",
      "trigger": "join",
      "text": "Journal: Hello Courier mesh handshake."
    }
  ]
}
```

- **Arcs** land in `agent.journal.mod_arcs` on join (`auto_offer`).
- Step ids matching inventory item ids (or `accept`/`brief`/`start` for step 0) advance the arc.
- **Beats** fire on `join` / `always` / `payload` triggers (once per agent via `mod_beats_seen`).

### StreetNet (`streetnet.json`) — API 1.1

```json
{
  "broadcasts": [
    {
      "id": "hello_courier.streetnet_hello",
      "channel": "streetnet",
      "weight": 2.0,
      "fire_on_load": true,
      "messages": ["StreetNet // HELLO_COURIER: uplink live."],
      "player_log": "StreetNet mod hello."
    }
  ]
}
```

`fire_on_load` pushes once at init / `reload_mods`. Weighted picks also compete on the street ticker.

### ICE / cyberspace (`ice_nodes.json`) — API 1.1

```json
{
  "probes": [
    {
      "id": "hello_courier.ping_probe",
      "name": "Courier Ping",
      "desc": "Soft reveal ping.",
      "effect": "reveal",
      "focus_cost": 2,
      "cooldown": 9.0,
      "radius": 9,
      "duration": 5.0
    }
  ],
  "nodes": [
    {
      "id": "hello_courier.tutorial_node",
      "weight": 2.0,
      "hint": "Tutorial node — grab * then X.",
      "grid": ["#######", "#@...X#", "#######"]
    }
  ]
}
```

- Probe `effect` must be `stun` | `reveal` | `scramble` (reuses core street/in-node behavior). Ids must be namespaced (cannot overwrite `stun`/`reveal`/`scramble`).
- Custom `grid` glyphs: `#.@I*%X` with required `@` start and `X` exit (max 24×24). ~35% of jack-ins prefer a weighted mod node when any are loaded.

### Globe pins / regions (`globe_regions.json`) — API 1.1

```json
{
  "pins": [
    {
      "id": "hello_courier.drop_pin",
      "name": "Courier Drop",
      "lat": 34.12,
      "lon": -118.28,
      "label": "Example drop pin",
      "region_id": "fractured_la",
      "kind": "mod_pin"
    }
  ],
  "regions": [
    {
      "id": "hello_courier.rim_cache",
      "name": "Rim Cache",
      "kind": "poi",
      "continent": "na",
      "lat": 33.95,
      "lon": -118.35,
      "label": "Metadata only",
      "metadata_only": true
    }
  ]
}
```

Pins appear in globe snapshot `mod_pins`. Metadata regions overlay the globe list but **reject teleport** (visible pins only in this slice).


### UI panels (`ui_panel.json`) — API 1.2

CSP-friendly YearUI dock extensions. **No arbitrary JavaScript from mods** — the host renders title + sanitized text/markdown and buttons that call **allowlisted existing game actions** only.

```json
{
  "panels": [
    {
      "id": "hello_courier.desk",
      "title": "Hello Courier Desk",
      "dock_label": "Hello",
      "body_format": "markdown",
      "body": "## Hello\n\nExample **CSP-safe** panel.",
      "actions": [
        {"label": "List mods", "action": "mods"},
        {"label": "Grant badge", "action": "mod_item", "arg": "hello_courier.badge"}
      ]
    }
  ]
}
```

| Field | Notes |
|-------|-------|
| `id` | Namespaced panel id |
| `title` | Side accordion summary |
| `dock_label` | Short dock button label (≤24) |
| `body_format` | `markdown` (default) or `text` |
| `body` | Original prose; markdown subset: headings, lists, `code`, **bold**, *italic* — HTML escaped first |
| `actions` | ≤8 buttons; `action` must be allowlisted (`mods`, `mod_item`, `globe`, `ice_probe`, …); optional `arg` sanitized |

Snapshot: `mods.panels` (+ `mods.ui_panel_count`). YearUI injects dock buttons into `#mod-dock-host` and side panels into `#mod-panels-host`.

### Host integration

| Hook | Behavior |
|------|----------|
| `_year_init` → `_modding_init` | Discover + load + StreetNet `fire_on_load` + globe overlays |
| `reload_district_defs` / `POST /api/reload_defs` | Also `reload_mods()` |
| Agent bootstrap | `_modding_offer_journal` |
| `_year_update_journal` | `_modding_update_journal` |
| `_item_from_shop_id` / `mod_item` | Resolve mod items |
| `_tick_street_events` | Weighted mod street + StreetNet |
| `_all_ice_probes` / `ice_probe` | Core + mod probes |
| `jack_in` | Optional weighted mod cyberspace node |
| `_globe_snapshot` | `mod_pins` / `mod_regions` |
| Snapshot `mods` | Registry summary + `panels` + errors |
| YearUI dock | Renders `mods.panels` (CSP markdown + action buttons) |
| Actions `mods`, `mod_item <id>`, `mod_reload` | List / grant / reload |

### Compatibility policy

- **Host** `PLUGIN_API_VERSION` is the contract (`1.2.0`).
- **Additive** hooks → bump **minor**; mods on older minors keep working (`1.0.0` still loads).
- **Breaking** manifest/fields → bump **major**; old mods fail closed with a clear error.
- Partial apply of a single mod is never done: one bad def skips that mod entirely.

## How to write a mod

1. Copy `examples/plugins/hello_courier/` to `mods/my_mod/`.
2. Edit `mod.json` (`id`, attribution, permissions, `api_version`).
3. Add original JSON for the hooks you need (no copyrighted novel text).
4. Run the web server; confirm snapshot `mods.mod_count` and `mods` action.
5. Grant test items with `mod_item <id>`; try `ice_probe`, `globe`, journal on join.
6. Iterate with `POST /api/reload_defs` or `mod_reload`.

## Enable the example

Example plugins load by default. To force only user `mods/`:

```bash
export SNOWCRASH_EXAMPLE_PLUGINS=0
```

Or symlink:

```bash
mkdir -p mods
ln -sfn ../examples/plugins/hello_courier mods/hello_courier
```

In-game / web:

```text
mods
mod_item hello_courier.badge
ice_probe hello_courier.ping_probe
globe
```

Open the **Hello** button on the YearUI panel dock (injected from `hello_courier.desk`) to try the sample `ui_panel`.

## Attribution

- Mods must credit authors/licenses in `attribution` / `license`.
- Game content and mod text must remain **original Metaverse / StreetNet fiction** — do not paste or paraphrase protected novel prose.
- Bundled example is MIT alongside the repo; third-party mods keep their own licenses.

## Later phases (still on #72)

- Optional sandboxed WASM/Lua if JSON is insufficient
- Teleportable mod regions with shard packs (beyond metadata pins)
- Steam Workshop-style distribution notes under #67
