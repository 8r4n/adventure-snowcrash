# Hello Courier (example mod)

Bundled example for issue **#72** (plugin API **1.1.0**). Adds:

- Item `hello_courier.badge` — equippable trinket (+1 hack)
- Street event `hello_courier.ping` — weighted broadcast
- Journal arc `hello_courier.delivery` + join beat
- StreetNet broadcast `hello_courier.streetnet_hello` (fires on load)
- ICE probe `hello_courier.ping_probe` (reveal effect) + tutorial cyberspace node
- Globe pin `hello_courier.drop_pin` + metadata region `hello_courier.rim_cache`

## Enable

Example plugins load by default from `examples/plugins/` (set `SNOWCRASH_EXAMPLE_PLUGINS=0` to skip).

Or copy / symlink into the user mods root:

```bash
mkdir -p mods
ln -sfn ../examples/plugins/hello_courier mods/hello_courier
```

## Try it

```text
mods
mod_item hello_courier.badge
ice_probe hello_courier.ping_probe
globe
```

Journal: on join you get the delivery arc + welcome beat; sleeve the badge to advance.

StreetNet: watch the ticker / system chat for `HELLO_COURIER` uplink lines (also fires once on load / reload).

Jack in at **J** — ~35% chance to enter the Hello Courier tutorial node when mod nodes are loaded.

Hot-reload after edits: `POST /api/reload_defs` (or `mod_reload`).

See [`docs/modding.md`](../../../docs/modding.md).
