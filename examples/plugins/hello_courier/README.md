# Hello Courier (example mod)

Bundled example for issue **#72**. Adds:

- Item `hello_courier.badge` — equippable trinket (+1 hack)
- Street event `hello_courier.ping` — weighted broadcast

## Enable

Example plugins load by default from `examples/plugins/` (set `SNOWCRASH_EXAMPLE_PLUGINS=0` to skip).

Or copy / symlink into the user mods root:

```bash
mkdir -p mods
ln -sfn ../examples/plugins/hello_courier mods/hello_courier
```

Grant the badge in-game (web action / chat):

```text
mod_item hello_courier.badge
```

List loaded mods:

```text
mods
```

Hot-reload after edits: `POST /api/reload_defs` (also reloads district/recipe/season JSON).

See [`docs/modding.md`](../../../docs/modding.md).
