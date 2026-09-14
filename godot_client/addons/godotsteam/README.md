# GodotSteam install (optional · #173)

This folder is the **documented drop path** for the [GodotSteam GDExtension](https://godotsteam.com/).
The repo does **not** vendor Steamworks binaries — headless / CI / Godot **4.3** builds must keep working without them.

## Install (local / Steam SKU)

1. Use Godot **4.4.1+** when enabling GodotSteam (4.4 GDExtension is **not** compatible with 4.3).
2. Download [GodotSteam GDExtension](https://store.godotengine.org/asset/godotsteam/godotsteam-gdextension/) matching your editor minor.
3. Extract into this directory (`godot_client/addons/godotsteam/`) so the `.gdextension` + platform libs land here.
4. Restart the editor. Enabling the editor dock plugin is optional (Steamworks dock only).
5. Dev App ID: copy `../steam_appid.txt.example` → `godot_client/steam_appid.txt` (or project root / beside the editor). **Do not ship** `steam_appid.txt` in SteamPipe depots.
6. Export with **vanilla** Godot templates; ship `libsteam_api.so` / `steam_api64.dll` beside the binary ([docs/godot-client.md](../../../docs/godot-client.md) · [docs/steam-packaging.md](../../../docs/steam-packaging.md)).

Runtime entrypoint: autoload `SteamBridge` (`res://scripts/steam_bridge.gd`) — no-ops when the GDExtension / SteamAPI is missing.
