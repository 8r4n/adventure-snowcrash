# Modder plugin framework

Issue **#72** (related **#37** editor/map tools · **#67** Steam packaging · **#42** campaign). External developers can extend adventure-snowcrash with **data-driven** items and street events without forking core.

**v1 stack:** JSON manifests + defs loaded by a Python registry. **No arbitrary Python, Lua, or WASM execution** in this slice — justified below. Web UI dock extensions and Workshop distribution are later phases (issue stays open).

Source: `snowcrash/systems/modding.py` (`ModdingMixin`), discovery roots `mods/` and `examples/plugins/`, example `examples/plugins/hello_courier/`.

## Acceptance map (this slice)

| Criterion | Status |
|-----------|--------|
| Documented plugin API (path, manifest, versioning, capabilities) | This doc |
| Safe sandbox: no host FS/network by default; explicit permissions | Fail closed — see Security |
| Hooks: custom items + street events | Implemented |
| Hooks: journal / ICE / globe / StreetNet / UI panels | Declared permissions only (warned, not hooked yet) |
| Hot-reload aligned with `/api/reload_defs` | `reload_mods()` inside reload path |
| Example `hello_courier` (1 item + 1 event) | `examples/plugins/hello_courier/` |
| Semver + broken mods fail closed | `api_version` + hard errors skip the mod |
| Web UI / WASM | **Not in this slice** — remains on #72 |

## Why JSON-first (not Lua/WASM yet)

| Option | Pros | Cons for v1 |
|--------|------|-------------|
| **JSON defs + Python loader** | Matches existing `districts.json` / ecology / storylines; easy to audit; no RCE surface | No custom scripted logic |
| Python entrypoints | Familiar | Arbitrary code = host compromise unless heavily sandboxed |
| Lua / WASM | Strong sandbox story | Larger runtime + packaging cost; defer to later phase / #67 |

v1 therefore ships **declarative content only**. Scripted hooks can be added later behind explicit `exec`/`wasm` permissions that are **denied** today.

## Security model (fail closed)

1. **No code execution.** Only `json.load` of files under the mod directory.
2. **Path jail.** Entry paths must be relative; `..` and absolute paths rejected.
3. **Permissions allowlist.** Manifest must list capabilities. Unknown or denied permissions (`network`, `fs_write`, `exec`, `python`, `wasm`, …) **reject the whole mod**.
4. **API semver.** `api_version` major must match host `PLUGIN_API_VERSION` (`1.0.0`); required version must be `<=` host. Incompatible → skip mod, record error.
5. **Validation.** Item/event ids, kinds, and numeric ranges are sanitized; invalid defs reject the mod (not partial apply).
6. **No core overwrite.** Item ids cannot collide with core factories or other mods.
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
  "version": "1.0.0",
  "api_version": "1.0.0",
  "description": "…",
  "author": "you",
  "license": "MIT",
  "attribution": " crediting assets / inspiration (original fiction only)",
  "permissions": ["items", "street_events"],
  "entry": {
    "items": "items.json",
    "street_events": "street_events.json"
  }
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | `^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$` |
| `api_version` | yes | Semver of host plugin API this mod targets |
| `version` | yes | Mod package semver (informational) |
| `permissions` | yes | Subset of known capabilities |
| `entry` | no | Relative file map; defaults `items.json` / `street_events.json` |
| `attribution` | strongly recommended | Third-party credit; keep game text original |

### Permissions

| Permission | v1 | Effect |
|------------|----|--------|
| `items` | **yes** | Load `items.json` into item registry |
| `street_events` | **yes** | Load weighted street broadcasts into year ticker |
| `journal` | declared only | Future journal beats |
| `ice_nodes` | declared only | Future ICE/cyberspace nodes |
| `globe_regions` | declared only | Future globe regions (#54) |
| `streetnet` | declared only | Future StreetNet commands |
| `ui_panel` | declared only | Future CSP-friendly web dock (later) |
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

When the year street-event ticker fires, a weighted mod event may replace the vanilla broadcast band (~40% when any mod events are loaded).

### Host integration

| Hook | Behavior |
|------|----------|
| `_year_init` → `_modding_init` | Discover + load |
| `reload_district_defs` / `POST /api/reload_defs` | Also `reload_mods()` |
| `_item_from_shop_id` / `mod_item` | Resolve mod items |
| `_tick_street_events` | Weighted mod broadcasts |
| Snapshot `mods` | Registry summary + errors |
| Actions `mods`, `mod_item <id>` | List / grant for playtest |

### Compatibility policy

- **Host** `PLUGIN_API_VERSION` is the contract.
- **Additive** hooks → bump **minor**; mods on older minors keep working.
- **Breaking** manifest/fields → bump **major**; old mods fail closed with a clear error.
- Partial apply of a single mod is never done: one bad def skips that mod entirely.

## How to write a mod

1. Copy `examples/plugins/hello_courier/` to `mods/my_mod/`.
2. Edit `mod.json` (`id`, attribution, permissions).
3. Add original item / event JSON (no copyrighted novel text).
4. Run the web server; confirm snapshot `mods.mod_count` and `mods` action.
5. Grant test items with `mod_item <id>`; wait for street ticks or advance time.
6. Iterate with `POST /api/reload_defs`.

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

In-game:

```text
mods
mod_item hello_courier.badge
```

## Attribution

- Mods must credit authors/licenses in `attribution` / `license`.
- Game content and mod text must remain **original Metaverse / StreetNet fiction** — do not paste or paraphrase protected novel prose.
- Bundled example is MIT alongside the repo; third-party mods keep their own licenses.

## Later phases (still on #72)

- Journal / ICE / globe / StreetNet hook coverage
- CSP-friendly web UI extension points (`ui_panel`)
- Optional sandboxed WASM/Lua if JSON is insufficient
- Steam Workshop-style distribution notes under #67
