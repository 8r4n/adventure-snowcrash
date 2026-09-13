# Mod distribution (Steam Workshop-style)

Issue **#72** (distribution notes) · related **#67** Steam packaging. Authoring API: [modding.md](modding.md). Steam SKU research: [steam-packaging.md](steam-packaging.md).

These are **notes and a local pack contract**, not a live Workshop upload. The host still **never auto-downloads unsigned packs from the internet**.

**WASM / Lua runtimes stay deferred** — packs remain JSON manifests + defs (`docs/modding.md`).

## Why this exists

Steam Workshop (and similar storefronts) is how players will eventually subscribe to content. Until Steamworks is wired (#67), we need a **fail-closed** mapping:

1. A pack on disk looks the same whether it came from a zip, a git clone, or a future Workshop depot.
2. The game only loads from **local, user-consented** roots (`mods/`, optional `SNOWCRASH_MODS_PATH`, first-party `examples/plugins/`).
3. Reload is the same path as district JSON: `POST /api/reload_defs` / action `mod_reload`.

## Pack layout (the unit of distribution)

A **pack** is one directory (zip/tar root = that directory, not a pile of loose files):

```
hello_courier/                 # folder name should match manifest id
  mod.json                     # required (or manifest.json)
  items.json                   # if permission "items"
  street_events.json
  journal.json
  streetnet.json               # broadcasts + optional slash commands
  ice_nodes.json
  globe_regions.json
  ui_panel.json
  README.md                    # optional, human
  LICENSE                      # optional; also set license + attribution in mod.json
```

Rules:

| Rule | Why |
|------|-----|
| One pack = one `mod.json` | Discovery is **immediate subdirs only** — no recursive scan, no zip-in-zip |
| `id` is namespaced lowercase (`my_mod`) | Collision + overlay keys |
| Entry paths are **relative** | `..` / absolute paths reject the whole pack |
| No `.py` / `.wasm` / `.lua` required or executed | v1 is JSON-only; `exec` / `python` / `wasm` permissions are **denied** |
| Original prose only | Do not ship novel text or core quest IP |

Suggested zip name: `my_mod-1.0.0.zip` whose single top-level folder is `my_mod/`.

## How a pack becomes a live mod

```
consent (user drops / extracts / future Workshop Subscribe)
        │
        ▼
   mods/<id>/mod.json     ← or $SNOWCRASH_MODS_PATH/<id>/
        │
        ▼
   discover_mod_dirs()    ← also examples/plugins/ unless SNOWCRASH_EXAMPLE_PLUGINS=0
        │
        ▼
   load_mod()             ← fail closed per pack (semver, perms, validation)
        │
        ▼
   POST /api/reload_defs  ← or in-game `mod_reload` / restart
        │
        ▼
   snapshot mods.*        ← errors[] / skipped[] if a pack was rejected
```

### Local install (today)

```bash
# from a zip you already have on disk (you chose to open it)
mkdir -p mods
unzip my_mod-1.0.0.zip -d mods/
# or:
ln -sfn /path/to/hello_courier mods/hello_courier

# pick up changes without a full process restart
curl -sS -X POST http://127.0.0.1:8766/api/reload_defs
# or in-game / YearUI:  mod_reload
```

`POST /api/reload_defs` reloads **districts + recipes + season + mods** together. Response includes `mods` (registry snapshot: counts, `panels`, `errors`, `skipped`, `api_version`) and a `reload` object documenting what ran.

Disable everything: `SNOWCRASH_DISABLE_MODS=1`.

### Extra roots

```bash
export SNOWCRASH_MODS_PATH="$HOME/snowcrash-packs:/opt/shared-mods"
```

`os.pathsep`-separated. User `mods/` still wins for the same resolved path (deduped). **Do not** point this at a world-writable download cache.

## Consent, signing, and what we will not do

| Policy | v1 (now) | Later Workshop (#67) |
|--------|----------|----------------------|
| User consent | You place the folder / unzip it | Steam **Subscribe** is consent; we still do not fetch arbitrary URLs |
| Auto-download | **Never** | Steam client downloads the subscribed depot; game only sees the unpacked `mods/` path |
| Code signing | Not required (JSON, no exec) | Optional catalog checksums / Steam item IDs once we have an app id |
| Unsigned internet fetch | **Rejected by design** — no `http://` pack loader | Still rejected. Workshop is the only remote channel, via Steam |
| Permissions | Manifest allowlist; `network` / `fs_*` / `exec` / `wasm` fail closed | Same host policy; Workshop does not grant extra perms |
| Broken pack | Skip that id, keep the world up | Same |

**Hard rule (non-goal from #72):** no unsigned auto-download from the internet without user consent. A future “Update all mods” button must still go through Steam (or an equivalent consented client), then `reload_mods()` — never `urllib` a zip at runtime.

If we add checksums later, they belong in `mod.json` as optional `sha256` of entry files (informational) plus a **host-side** allowlist. A missing/invalid digest **fails closed** for that pack. Not implemented in this slice.

## Compatibility at the door

Host plugin API is semver (`PLUGIN_API_VERSION`, currently **1.3.0**). Packs declare `api_version`:

- Same **major**, required ≤ host → load (1.0 / 1.1 / 1.2 still work on 1.3).
- Higher minor/patch than host → **skip** (“requires newer host”).
- Different major → **skip** (“major mismatch”).
- Missing / unparseable `api_version` → **skip**.
- One bad def → **the whole pack is skipped** (no partial apply).

See [modding.md — Compatibility](modding.md#compatibility-policy).

## Steam Workshop sketch (when #67 is implemented)

Not built. Design so the first Workshop item is a zip of the pack above:

1. Steamworks Workshop item = uploaded zip (`mod.json` at the root of the extracted folder).
2. Install dir mapping: `$STEAM_WORKSHOP_CONTENT/<appid>/<itemid>/` → treat as an extra `SNOWCRASH_MODS_PATH` root **or** symlink into `mods/`.
3. On Subscribe / Unsubscribe / update: call `reload_mods()` (same as `/api/reload_defs`).
4. Visibility: only subscribed items appear. Unsubscribed folders are ignored (or deleted by Steam).
5. Overlay / friends do not need Workshop. Cloud saves are unrelated (server-authoritative MMORPG).
6. Depot 4 in [steam-packaging.md](steam-packaging.md) can ship first-party examples; user Workshop content stays out of the game depot.

**Legal / IP:** store + Workshop copy stays original StreetNet fiction (same rules as #67 licensing). Mods that paste novel text are rejected socially and, when we have review tools, by policy — the loader cannot detect copyright, so the contract is documented + fail-closed on *technical* violations only.

## Security recap (distribution-specific)

1. Discovery never follows URLs or archive-in-archive.
2. Path jail on every `entry` file.
3. No mod JavaScript / Python / WASM / Lua in v1.
4. UI panels and StreetNet slash commands may only fire **allowlisted** existing game actions.
5. `SNOWCRASH_DISABLE_MODS=1` is the kill switch for support / tournaments.

## Try the mapping locally

```text
mods
mod_reload
/hello
```

(`/hello` is the Hello Courier StreetNet command — API 1.3.) Then `POST /api/reload_defs` after you edit JSON.

## Still later (do not close #72 for these)

- Actual Steam Workshop upload / Subscribe UI
- Checksum catalog + publisher signatures
- Teleportable mod shards
- Optional sandboxed WASM/Lua if JSON is insufficient
