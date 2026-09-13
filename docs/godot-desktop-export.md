# Godot desktop export (Linux / Windows) for Steam SKU

Issue **#149** (parent **#141** 3D street · **#130** quality bar · **#132** Deck · packaging **#67**).

Produce **native** Linux x86_64 and Windows Desktop binaries of [`godot_client/`](../godot_client/) — the preferred Steam presentation client — not web-in-a-box.

**Non-goals:** paying Steam Direct, uploading SteamPipe builds, claiming Deck Verified, macOS export (optional later).

---

## Acceptance (#149)

| Item | Status | Where |
|------|--------|-------|
| Tracked `export_presets.cfg` Linux x86_64 + Windows | Done | [`godot_client/export_presets.cfg`](../godot_client/export_presets.cfg) (+ `.example` twin) |
| Export templates + headless commands documented | Done | § Templates · § Headless export |
| How exported client talks to Python `/ws` | Done | § Connecting to `/ws` |
| Steam depot layout notes → #67 / packaging / Deck | Done | § Steam depot layout |
| `scripts/export_godot_client.sh` (clear fail if no Godot) | Done | [`scripts/export_godot_client.sh`](../scripts/export_godot_client.sh) |
| Links from godot-client / godot-3d | Done | those docs → this file |

---

## Prerequisites

1. **Godot 4.3+** editor/binary ([download](https://godotengine.org/download)). Prefer **4.4.1+** if you later add [GodotSteam](https://godotsteam.com/).
2. Matching **export templates** for that exact minor (see § Templates).
3. Repo checkout with `godot_client/project.godot` and `godot_client/export_presets.cfg`.

The Godot binary is **not** vendored in this repo. CI boxes without Godot will see a clear exit from the export script (code 127).

---

## Export templates

### Editor (recommended once)

1. Open Godot → **Editor → Manage Export Templates…**
2. **Download and Install** for the running version (e.g. 4.3.stable / 4.4.1.stable).
3. Confirm **Project → Export** lists **Linux/X11** and **Windows Desktop** without a red “templates missing” banner.

### Headless / CI sketch

Templates live under the user data dir (OS-specific), e.g. Linux:

```text
~/.local/share/godot/export_templates/<version>/
```

Official zips: [Godot export templates](https://godotengine.org/download) (“Export templates” link next to the editor). Unpack so `version.txt` matches `godot --version`.

GodotSteam: use **vanilla** export templates with the GodotSteam **GDExtension** — do not swap in custom GodotSteam editor templates unless you know you need them ([godot-client.md](godot-client.md) § Steam).

---

## Presets

Tracked file: [`godot_client/export_presets.cfg`](../godot_client/export_presets.cfg)  
Fallback copy: `godot_client/export_presets.cfg.example`

| Preset name | Platform | Architecture | Artifact path (from repo root) |
|-------------|----------|--------------|--------------------------------|
| `Linux/X11 (Steam Deck / desktop)` | Linux/X11 | x86_64 | `build/linux/Snowcrash.x86_64` + `Snowcrash.pck` |
| `Windows Desktop` | Windows Desktop | x86_64 | `build/windows/Snowcrash.exe` + `Snowcrash.pck` |

Notes:

- `binary_format/embed_pck=false` → ship the `.pck` beside the executable (Steam depot friendly).
- Linux preset is **runnable** and the **primary Deck / Linux depot** path ([steam-deck.md](steam-deck.md)).
- Windows preset is the Win64 depot / Proton fallback — **not** the Deck launch path.
- `build/` is gitignored (root `.gitignore`).

The editor may rewrite `export_presets.cfg` when you touch Export UI. Prefer committing intentional preset changes; avoid committing encryption keys if you ever enable PCK encryption.

---

## Headless export

### Script (preferred)

```bash
cd /path/to/adventure-snowcrash
./scripts/export_godot_client.sh          # both platforms
./scripts/export_godot_client.sh linux    # Linux only
./scripts/export_godot_client.sh windows  # Windows only
```

Point at a specific binary:

```bash
export GODOT=/path/to/Godot_v4.3-stable_linux.x86_64
./scripts/export_godot_client.sh linux
```

If Godot is missing, the script prints install hints and exits **127**.

### Manual Godot CLI

```bash
# From repo root — export paths are relative to godot_client/
godot4 --headless --path godot_client \
  --export-release "Linux/X11 (Steam Deck / desktop)" \
  ../build/linux/Snowcrash.x86_64

godot4 --headless --path godot_client \
  --export-release "Windows Desktop" \
  ../build/windows/Snowcrash.exe
```

First-time tip: open the project once in the editor so `.godot/` imports exist; some headless exports fail on a cold checkout.

### Artifact smoke

```bash
# Local Python authority (dev port 8766)
./scripts/run_dev.sh   # separate terminal

SNOWCRASH_WS_URL=ws://127.0.0.1:8766/ws ./build/linux/Snowcrash.x86_64
# or edit the URL field in the connection row after launch
```

---

## Connecting to `/ws` (exported client)

The client is a **thin** WebSocket peer. Python `snowcrash.web` remains authority. Same contract as the web client and editor play (`join` / `action` / `chat` / snapshots).

### Precedence (highest first)

1. **Environment** `SNOWCRASH_WS_URL` (or alias `SNOWCRASH_WS`)
2. **ConfigFile** `user://snowcrash_client.cfg` → section `[net]` key `ws_url` (written on successful Jack in)
3. **UI** `UrlEdit` default in `scenes/main.tscn` → `ws://127.0.0.1:8766/ws`
4. Optional CLI user args: `--ws-url=…` or `--snowcrash-ws=…` (Godot user args after `--`)

### Mode A — hosted (Steam always-online)

```bash
# Production-style public host (TLS)
SNOWCRASH_WS_URL=wss://play.example.com/ws ./Snowcrash.x86_64
```

Ship store builds with a sensible default URL in the scene or a first-run config; players can still override via env or the URL field.

### Mode B — local authority (sidecar / offline later)

```bash
./scripts/run_dev.sh          # or PyInstaller sidecar on 127.0.0.1:<port>
SNOWCRASH_WS_URL=ws://127.0.0.1:8766/ws ./build/linux/Snowcrash.x86_64
# prod uvicorn default port is 8765:
SNOWCRASH_WS_URL=ws://127.0.0.1:8765/ws ./build/linux/Snowcrash.x86_64
```

Sidecar lifecycle (launch child, wait `/health`, kill on quit) is documented as future work in [godot-client.md](godot-client.md) § Steam and [steam-packaging.md](steam-packaging.md) — not required to export the client binary.

### Persist path

| OS | Typical `user://` |
|----|-------------------|
| Linux | `~/.local/share/godot/app_userdata/Snowcrash/` (or project name) |
| Windows | `%APPDATA%\Godot\app_userdata\Snowcrash\` |

File: `snowcrash_client.cfg` — also stores onboarding name, view mode, audio, quality.

---

## Steam depot layout (links #67)

Extends [steam-packaging.md](steam-packaging.md) § Build / CI / depots and [steam-deck.md](steam-deck.md) § Native Linux depot plan. Godot replaces Tauri as the **preferred** SKU ([steam-quality-bar.md](steam-quality-bar.md) / #130); Tauri remains the calendar fallback wrap of the web client.

| Depot | Content (from this export) | Platforms | Role |
|-------|----------------------------|-----------|------|
| **Linux64 Godot** | `Snowcrash.x86_64` + `Snowcrash.pck` (+ optional `libsteam_api.so` later) | Linux | **Primary Deck + Linux desktop** |
| **Win64 Godot** | `Snowcrash.exe` + `Snowcrash.pck` (+ optional `steam_api64.dll`) | Windows | Desktop + Proton fallback |
| Shared (optional) | Licenses, example mods | All | No `steam_appid.txt` in ship |
| Sidecar (optional later) | PyInstaller `snowcrash-server` for Mode B | Win + Linux | Offline SKU |

**Steamworks launch configs (sketch):**

```text
Snowcrash (Desktop)  → Snowcrash.x86_64   # Linux depot
Snowcrash (Desktop)  → Snowcrash.exe      # Windows depot
```

**Staging into SteamPipe content roots (local only — no upload):**

```text
content/linux64/Snowcrash.x86_64
content/linux64/Snowcrash.pck
content/win64/Snowcrash.exe
content/win64/Snowcrash.pck
```

Gate: do **not** pay Steam Direct or run `steamcmd +run_app_build` from this ticket (same as #67).

After GodotSteam: place `libsteam_api.so` / `steam_api64.dll` beside the binary; keep vanilla templates.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Script exit 127 / “Godot 4 binary not found” | Install Godot 4.3+; set `GODOT=` or put `godot4` on PATH |
| “No export template found” | Install templates matching `godot --version` |
| Empty / missing `.pck` | Confirm `embed_pck=false` and ship both files |
| Connect fails on hosted URL | Use `wss://` behind TLS; check CORS is N/A (native WS); firewall |
| Deck sleep drops session | Expected — reconnect is in `net_client.gd` ([steam-deck.md](steam-deck.md)) |
| Editor rewrote presets | Diff `export_presets.cfg`; restore from `.example` if needed |

---

## Related

- [godot-client.md](godot-client.md) — thin-client architecture + Steam Mode A/B
- [godot-3d.md](godot-3d.md) — #141 3D Metaverse street (Steam presentation goal)
- [steam-packaging.md](steam-packaging.md) — #67 Direct / SteamPipe / assets
- [steam-deck.md](steam-deck.md) — #132 Verified checklist + Linux depot
- [steam-quality-bar.md](steam-quality-bar.md) — #130 comps; Godot preferred SKU
- [`godot_client/README.md`](../godot_client/README.md) — open in editor / controls
