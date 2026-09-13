# Godot client research + spike

Issue **#109** (related **#67** Steam · **#75** mobile · **#72** modding · **#78** TUI FPV · **#54** globe · **#90** Catppuccin). Evaluate Godot as a **native desktop/mobile shell** around the existing Python MMORPG server — not a replacement for the web or TUI clients.

**Decision (this ticket):** **GO** on a **Godot 4.x thin client** (UI + WebSocket to existing `snowcrash.web` `/ws`). **NO-GO** on rewriting the Python authority server or abandoning web/TUI. Spike lives in [`godot_client/`](../godot_client/). First-10 Steam beat: [godot-onboarding.md](godot-onboarding.md) (**#133**).

**Steam presentation goal (#141 / #130):** the shipped SKU is a **3D Metaverse street** (`Node3D` meshes + courier camera), not ASCII-as-product. ASCII FPV / map stay as overlay / accessibility / debug. Design + slice progress: [godot-3d.md](godot-3d.md).

Godot **was not installed** on the research box (2026-09-13). Project files are still valid Godot 4.3+; open them in the editor locally (see [`godot_client/README.md`](../godot_client/README.md)).

Sources checked 2026-09-13:

- [Godot 4 WebSocket tutorial](https://docs.godotengine.org/en/stable/tutorials/networking/websocket.html) — `WebSocketPeer` (Godot 3 `WebSocketClient` is gone)
- [WebSocketPeer class](https://docs.godotengine.org/en/stable/classes/class_websocketpeer.html)
- [GodotSteam GDExtension](https://godotsteam.com/) — Steamworks for Godot 4.4+
- In-repo: `snowcrash/web/app.py`, `snowcrash/static/game.js` (`Net`), `snowcrash/mmorpg.py` (`snapshot` / `handle_action`), [steam-packaging.md](steam-packaging.md), [steam-quality-bar.md](steam-quality-bar.md), [mobile.md](mobile.md), [modding.md](modding.md), [fpv.md](fpv.md), [tui-fpv.md](tui-fpv.md), [theme-catppuccin.md](theme-catppuccin.md), [year_backend_actions.md](year_backend_actions.md)

---

## Acceptance checklist

| Research question | Status | Where answered |
|-------------------|--------|----------------|
| Godot 4.x vs 3.x | Done | § Engine version |
| Thin vs embedded vs full rewrite | Done | § Architecture — **thin first** |
| Port / reuse: FPV, StreetNet, docks, globe, Catppuccin | Done | § Feature mapping |
| Input: keyboard + gamepad + touch | Done | § Input |
| Packaging: export templates + Steam depots; Proton | Done | § Packaging (Steam #67, mobile #75) |
| Multiplayer: Python authority, Godot presentation | Done | § Architecture · § WS protocol |
| Modding (#72): Godot addons vs JSON plugins | Done | § Modding |
| Effort + risks + go/no-go | Done | § Effort · § Risks · § Go / no-go |
| Spike: connect `:8766/ws`, name gate, snapshot/map | Done | [`godot_client/`](../godot_client/) |

---

## Engine version

**Recommend Godot 4.x — specifically 4.3+ (prefer 4.4.1+ if using GodotSteam).**

| | Godot 3.x | Godot 4.x |
|--|-----------|-----------|
| Status | Legacy; 3.6 maintenance only | Current (4.3 LTS-ish / 4.4–4.6 line in 2026) |
| WebSocket | `WebSocketClient` (removed) | `WebSocketPeer.connect_to_url` + `poll()` |
| 2D / UI | Fine | Better theme/Control tooling, TextServer |
| Mobile | Weaker iOS/Android story | First-class export; Android needs `INTERNET` permission |
| Steam | Older GodotSteam modules | [GodotSteam GDExtension](https://godotsteam.com/) targets **4.4+** (4.4 GDExtension is **not** compatible with 4.3) |
| HTML5 | Possible | Possible; mixed-content forces `wss://` |

Spike `project.godot` declares `config/features=PackedStringArray("4.3", "Forward Plus")` (desktop) with `rendering_method.mobile=mobile` for Deck; a 4.3 editor can open it. If you adopt GodotSteam immediately, bump the feature string to 4.4 and pin the editor.

**Language:** GDScript is enough for a thin client (JSON + UI). C# / GDExtension only if we later embed a sidecar or Steam helper.

---

## Architecture

The Python process is already the **authority**: one `GameWorld`, WebSocket `/ws`, HTTP `/api/*` fallback, ~`TICK_HZ` enemy tick + on-action AOI broadcast (`interested_player_ids`). Clients are presentation. `game.js` `Net` is ~110 lines of join / action / chat / ping. That is the contract a Godot client should clone.

```
┌─────────────────────────────────────────┐
│  Godot 4 thin client (this path)        │
│  3D street · HUD · FPV/ASCII · docks    │
│  WebSocketPeer  →  ws(s)://host:port/ws │
└──────────────────┬──────────────────────┘
                   │ JSON text frames
┌──────────────────▼──────────────────────┐
│  snowcrash.web (FastAPI + Uvicorn)      │
│  /ws  ·  /api/*  ·  /health             │
│  GameWorld (Python, shared with TUI)    │
└─────────────────────────────────────────┘

Additive today:  web JS client  ·  curses TUI
Not this ticket: replace server · drop web/TUI
```

### Options compared

| Option | What it is | Verdict |
|--------|------------|---------|
| **Thin client** | Godot UI + `WebSocketPeer` to existing `/ws`. Python stays authority. | **Do this first.** Matches how web already works. Fastest path to Steam/mobile *feel* without forking sim. |
| **Embedded** | Godot process hosts Python (GDExtension / sidecar pipe) and also talks WS or in-process. | Useful later for **offline Steam SKU** (same sidecar idea as Tauri + PyInstaller in #67). Not needed to validate the client. |
| **Full rewrite** | Port `GameWorld` / year mixins to GDScript or C#. | **No-go.** Months of work; splits TUI; abandons Python mods/hot-reload; out of scope for #109. |

Thin-client rule: **Godot never simulates the street.** It sends intents (`action` / `chat`) and paints `snapshot.state`. Same anti-cheat / AOI / rate-limit story as the browser.

---

## Feature mapping

Everything below is already in the snapshot or the action table. Godot does not need new server APIs for v1.

### FPV ASCII

Three existing pipelines:

| Surface | How it draws | Godot reuse |
|---------|--------------|-------------|
| **Web** ([fpv.md](fpv.md)) | Offscreen neon raycast canvas → `ascii-video.js` luminance → colored glyphs | Port `FpvEngine` + `AsciiRenderer` (2–3 wks) **or** skip video and do TUI-style |
| **TUI** ([tui-fpv.md](tui-fpv.md)) | Raycast map+facing straight to ASCII columns (`snowcrash/tui/fpv.py`) | **Preferred Godot v1.** Port the column raycaster to GDScript; draw with `Label` / `RichTextLabel` (monospace) or a tiny `TextEdit`. No ffmpeg, no canvas sample. |
| **Spike (now)** | Raw `state.map` rows in a `Label` | Proves the socket; not a player-facing FPV |

Keep Catppuccin wall/entity roles (teal walls, peach thugs, …). A later pass can add scanlines as a `CanvasItem` shader — optional chrome, not blocking.

### StreetNet

Snapshot fields: `chat` (lines), `irc` (`channel`, `channels`, `topics`, `nicks`), plus `messages` (system log).

Client send: `{ "type": "chat", "text": "…" }` — `/say`, `/join`, etc. are server-parsed the same as web. Rate-limit error comes back as `{ "type": "error", "error": "chat rate limited" }`.

Godot: one dock (`ItemList` or `RichTextLabel` + `LineEdit`). No IRC protocol to implement.

### Docks (Year UI)

Web `YearUI` is a snapshot renderer: journal, ICE, shop, party, crew, contracts, globe, ecology, sleeves, primer, jaunte, empathy, forecast, raid, housing, craft, season, heat, mods `ui_panel`. Accordion (one open) is a mobile/#75 constraint — reuse it.

Godot: `TabContainer` or a dock button row + one `Panel`. Each panel binds to the matching snapshot key (see [year_backend_actions.md](year_backend_actions.md)). Buttons call `Net.action(name, arg)` — same strings as web (`globe`, `ice_probe`, `primer_start`, …).

Do **not** re-implement year logic client-side.

### Globe (#54)

Snapshot `globe`: region, pins, zoom, cooldown, credits cost. Actions: `globe` / `globe_zoom` / `teleport` / `globe_recall` / `globe_failsafe`.

Godot: schematic Control (lat/lon → x/y) or ASCII region list first; OSM shard research (#83) stays server-side. Teleport is one action; the next snapshot swaps `map`.

### Catppuccin (#90)

Copy hex from `snowcrash/theme.py` `PALETTES` into a Godot `Theme` (or a `catppuccin.gd` const dict). Mocha default; Macchiato / Frappé / Latte as option buttons.

| Role | Mocha token | Hex |
|------|-------------|-----|
| Window / FPV crust | crust | `#11111b` |
| Panels | base / mantle | `#1e1e2e` / `#181825` |
| Text | text | `#cdd6f4` |
| Accent / player | teal / sky | `#94e2d5` / `#89dceb` |
| Warn | yellow | `#f9e2af` |
| Danger | red / pink | `#f38ba8` / `#f5c2e7` |
| OK | green | `#a6e3a1` |

Attribution: Catppuccin MIT — same note as [theme-catppuccin.md](theme-catppuccin.md). Spike uses these colors in the main scene.

---

## Input

Server movement is **facing-relative** on web (`forward` / `back` / `strafe_left` / `strafe_right` / `turn_left` / `turn_right`) plus absolute `n`…`nw`. Rate-limited at `ACTION_RATE_HZ` (extra intents dropped). Godot should send the **named relative actions**, not raw key codes.

| Device | Map to | Notes |
|--------|--------|-------|
| **Keyboard** | WASD → forward/strafe; Q/E or ←/→ → turn; G get; F fire/hack; I inventory; Enter chat focus | Match [README controls](../README.md). TUI `q`=quit vs web `q`=turn — Godot follows **web**. |
| **Gamepad** | Left stick / d-pad → relative move (quantize to 8-way); shoulder or face → turn; A/South → get; X/West → fire; Start → docks | Godot `InputMap` + `InputEventJoypadMotion` deadzone ~0.35. Hold-to-move at ≤ action rate. |
| **Touch** | Virtual stick + chord pad (FIRE / GET / ICE) | Port #75 HUD: `touch-action` equivalent is Godot `_gui_input` + `accept_event()` so the map does not scroll. Safe-area: `DisplayServer.get_display_safe_area()`. Large-type toggle = font size. |

Spike wires WASD/QE after a successful join so a courier can walk without the browser.

---

## Packaging

### Steam (#67)

[#67](https://github.com/8r4n/adventure-snowcrash/issues/67) recommended **Tauri 2 + PyInstaller sidecar** as the **fastest v1** because the **web client is already complete**. That still stands if the goal is “ship the current game on Steam this quarter.” Per **#130** / [steam-quality-bar.md](steam-quality-bar.md), the **preferred marketable SKU** is still this Godot client — Tauri is the calendar fallback, not the north star.

Godot is the **better mid-term native SKU** once the thin client reaches playable FPV + docks:

| | Tauri + web | Godot thin client |
|--|-------------|-------------------|
| Time to first Steam exe | Weeks (wrap what we have) | Months (rebuild UI) |
| Overlay / Deck | Webview overlay is weak | Vulkan/GL export; GodotSteam overlay works in **exports** (not editor) |
| Input | Browser focus quirks | Native InputMap, gamepad, Steam Input |
| Installer size | Small (OS webview) | ~40–80 MB export + optional Python sidecar |
| Always-online hosted WS | Works | Works (spike default) |
| Offline / local server | Sidecar | Same sidecar, spawned from Godot `OS.create_process` |

**Steam path if Godot is the SKU:**

1. Export Windows + Linux with official templates (macOS later / notarization).
2. Add [GodotSteam GDExtension](https://store.godotengine.org/asset/godotsteam/godotsteam-gdextension/) (Godot **4.4+**; use **vanilla** export templates, not GodotSteam custom editor builds). Ship `steam_api64.dll` / `.so` beside the exe. Dev: `steam_appid.txt` (do not ship).
3. **Mode A (hosted):** client default URL `wss://<public-host>/ws` — matches current `adventure-dev`. Always-online; needs infra + refund policy.
4. **Mode B (local authority):** Godot launches the PyInstaller `snowcrash.web` sidecar on `127.0.0.1:<ephemeral>`, waits for `/health`, connects `ws://127.0.0.1:<port>/ws`. Same lifecycle pitfalls as Tauri (kill the child, not only the bootloader).
5. Depots: Win64 / Linux64 first; Proton can run the Windows build on Deck if Linux lags. Cloud saves = optional later (server already holds avatar by name/`id`).

Proton: Godot 4 Windows exports generally run on Deck; test input + fullscreen early.

**Deck Verified checklist (#132):** [steam-deck.md](steam-deck.md) — native Linux depot, InputMap, 1280×800 UI scale, suspend/reconnect. Device QA not yet run.

Do **not** pay Steam Direct or upload builds from this ticket (same gate as #67).

### Mobile (#75)

PWA remains the **shipped** phone path. Godot is the **store-native** path:

- **Android:** official export; enable **Internet** permission or all sockets die. ARM64. Virtual stick is first-class.
- **iOS:** export + signing / Apple developer account; later (same as #75 “store submission out of scope”).
- Orientation: support both; reserve bottom safe area for pads (parity with `docs/mobile.md`).
- Background: pause `_process` poll on `NOTIFICATION_APPLICATION_FOCUS_OUT`; reconnect like `game.js` (`wantOpen` + 1.2s retry).
- Do not block #75 on Godot. PWA and Godot can coexist.

---

## Modding (#72)

**Keep the existing JSON plugin API as the only player-facing mod surface.** Godot addons are for *our* engine plugins (GodotSteam, maybe a monospace font), not courier content.

| Mod kind | Where it runs | Godot job |
|----------|---------------|-----------|
| Items, events, journal, StreetNet, ICE, globe pins | Python registry (`docs/modding.md`, API 1.2) | Render whatever appears in the snapshot |
| `ui_panel` (markdown + allowlisted actions) | Server sanitizes; web paints HTML | Parse the same markdown fields into `RichTextLabel`; buttons → `action` |
| Hot-reload `/api/reload_defs` | Server | Optional HTTP button in a debug overlay |
| Godot `.pck` / addon | Client-only skins | **Later, optional.** Skins/themes only — never simulate items the server does not know |
| Lua / WASM / mod JS | Denied in v1 | Still denied. A Godot client must not grow a second RCE surface |

If Steam Workshop happens, distribute **server JSON mods** (and maybe a client theme pack). Two ecosystems (Python JSON + Godot addon) would split #72.

`SNOWCRASH_DISABLE_MODS=1` remains a server flag; Godot does not need a copy.

---

## WS protocol notes

Authoritative code: `snowcrash/web/app.py` (`ws_endpoint`) and `snowcrash/static/game.js` (`Net`). All frames are **JSON text** (not binary).

### Connect

- URL: `ws://127.0.0.1:8766/ws` on **dev** (`./scripts/run_dev.sh`). Production default is **8765**.
- TLS: `wss://` when the page/app would otherwise be mixed-content (Godot HTML5 export) or when the host terminates TLS.
- Server `accept()` then **waits 60s for the first message**. If it is not `type: "join"`, it sends `{type:"error", error:"expected join"}` and closes.

### Client → server

| `type` | Fields | When |
|--------|--------|------|
| `join` | `name` (str), optional `id` (reconnect player id), optional `soft_hardcore` / `hardcore` (bool). Web also sends `nick` (ignored by current `app.py` — nick is `YearUI` / `auth_nick`). | **First message only.** |
| `action` | `action` (str), `arg` (str or null) | Movement, get, fire, year actions — see [year_backend_actions.md](year_backend_actions.md) + `REL_MOVE_ACTIONS` |
| `chat` | `text` | StreetNet; server `world.say` |
| `ping` | `t` (client timestamp) | Web: every 2.5s |
| `respawn` | — | Same as action `"r"` |

### Server → client

| `type` | Fields | When |
|--------|--------|------|
| `welcome` | `you` (player id), `state` (full snapshot) | After successful join |
| `snapshot` | `state` | Tick (if anyone connected) and after actions/chat (AOI-filtered for actions) |
| `pong` | `t` (echo), `server_t` | Reply to ping |
| `error` | `error` | Bad first message, chat rate limit, … |

### Snapshot (paint these; do not invent)

Minimum for a playable stub: `map` (row strings), `width`/`height`, `player` (`name`, `x`, `y`, `hp`, `max_hp`, `focus`, `facing_name`, `glyph`), `online_count`, `tick`/`turn`, `mode`, `objective`, `won`/`lost`.

Also present (web already consumes): `players`, `entities`, `inventory`, `messages`, `chat`, `irc`, `visible`/`explored` (2D bool arrays — **heavy**), `sfx`, `cutscenes`, `jackpoint`, `uplink`, year keys (`globe`, `ice`, `primer`, `mods`, …). Cyberspace / heist **replace** `map` while active.

### Client implementation (Godot 4)

```gdscript
var socket := WebSocketPeer.new()

func _ready() -> void:
    var err := socket.connect_to_url("ws://127.0.0.1:8766/ws")
    if err != OK:
        push_error("connect_to_url failed")

func _process(_delta: float) -> void:
    socket.poll()
    if socket.get_ready_state() == WebSocketPeer.STATE_OPEN:
        while socket.get_available_packet_count():
            var text := socket.get_packet().get_string_from_utf8()
            var msg = JSON.parse_string(text)
            # welcome / snapshot / pong / error
        # after first OPEN: send_text join once

func send_action(action: String, arg = null) -> void:
    socket.send_text(JSON.stringify({ "type": "action", "action": action, "arg": arg }))
```

Keep polling through `STATE_CLOSING` for a clean close. Spike reconnects ~1.2s like `game.js`.

### REST fallback

`POST /api/action`, `POST /api/new`, `GET /api/state` still exist for bootstrap. Live play should use `/ws`. `/health` is the sidecar readiness probe.

---

## Effort estimate

| Slice | Time | Notes |
|-------|------|-------|
| Research + spike (this issue) | Done | Doc + `godot_client/` |
| Playable thin client (join, move, ASCII map, chat, HP/objective) | **2–3 weeks** | Spike + input + StreetNet line |
| Year docks + globe + ICE + primer (parity-ish HUD) | **4–6 weeks** | Snapshot binding, not new sim |
| ASCII FPV (TUI-style raycast) | **1–2 weeks** | Faster than porting web canvas |
| Web-fidelity video→ASCII FPV | **2–3 weeks** extra | Only if TUI look is not enough |
| Gamepad + touch parity | **1–2 weeks** | Overlaps #75 UX |
| Steam export + GodotSteam (no store upload) | **1–2 weeks** | After playable |
| Android export (sideload) | **1–2 weeks** | iOS signing extra |
| **Full rewrite of GameWorld** | **4–8 months** | No-go |

**Calendar:** a focused engineer can put a **Steam-demo-worthy** thin client (ASCII FPV + core docks + hosted WS) in about **6–8 weeks**. Tauri-wrapping the current web client remains faster if the only goal is a Steam exe this month.

---

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Dual-client drift (JS vs GDScript) | High | Treat `app.py` + snapshot schema as the contract; add a tiny protocol fixture test; do not special-case Godot on the server |
| Fat snapshots (`visible` / `explored`) | Medium | Spike ignores FOV arrays; later, optional “slim” snapshot flag if bandwidth hurts mobile |
| FPV looks worse than web | Medium | Ship TUI-style FPV first; video pipeline is optional chrome |
| Always-online stigma / refunds | Medium | Document Mode A vs sidecar Mode B; don’t ship hosted-only without infra |
| GodotSteam / Vulkan overlay | Medium | Test **exported** builds on Win + Deck; overlay does not work in the editor |
| Snapshot field churn (year mixins) | Medium | Docks fail soft when a key is missing |
| No Godot in CI / this box | Low | Version-control `project.godot` + scenes; CI does not need to export yet |
| Second mod API temptation | High | Refuse Godot addons as content mods (#72 JSON only) |
| Input map clash (TUI `q` vs web turn) | Low | Document: Godot follows web |

---

## Go / no-go

**GO — thin Godot 4 client as an additive packaging path.**

Reasons:

1. `/ws` is already client-agnostic; the spike can join a live dev world without server changes.
2. Native input, Steam overlay, and mobile export are strictly better than a browser shell *once UI exists*.
3. Python authority + JSON mods stay intact; web and TUI remain.

**NO-GO (still):**

- Rewriting `GameWorld` in Godot
- Dropping the web or TUI clients
- Making Godot the *only* Steam plan before FPV/HUD exist (use Tauri + current web if a Steam exe is urgent)
- Paying Steam Direct / store submission from this ticket
- Godot addons as the #72 plugin API

**Success signal for #109:** this doc + a Godot 4 project that connects to `ws://127.0.0.1:8766/ws`, joins by name, and shows status + snapshot summary / ASCII map. Met.

---

## Spike

| Path | Role |
|------|------|
| [`godot_client/README.md`](../godot_client/README.md) | How to open in Godot Editor + run against dev `:8766` |
| `godot_client/project.godot` | Godot 4.3+ project |
| `godot_client/scenes/main.tscn` | Name gate + status + map label |
| `godot_client/scripts/net_client.gd` | `WebSocketPeer` Net clone |
| `godot_client/scripts/main.gd` | UI + WASD/QE after join |

---

## Implementation progress

Tracked under epic **#118** (leave the epic open; slice PRs use `Refs #118`). Child slice issues may `Closes #<slice>`.

### Slice 1 — reliable core play loop (**done**, #118 play-loop PR)

| Item | Status |
|------|--------|
| Join / rejoin by name (+ `id` on reconnect); connection status; disconnect recovery with backoff | Done — `godot_client/scripts/net_client.gd` |
| Intents: move (WASD/QE + chords), look, wait, combat (`f`), pickup (`g`) | Done — `main.gd` |
| Inventory select (`inv_select` / digits) + use (`u`) | Done |
| Live HUD: HP/Focus/XP/credits, objective, scrolling log | Done |
| ASCII map crop + FPV text view (TUI-style raycast on snapshot map) | Done — `fpv_ascii.gd`, `V` toggle |
| Catppuccin Mocha colors where easy | Done — `catppuccin.gd` + scene |
| Docs / how-to | Done — this section + `godot_client/README.md` |
| Optional Python WS harness mirroring Godot envelopes | Done — `scripts/godot_ws_harness.py`, `tests/test_godot_ws_protocol.py` |

### Slice 2 — StreetNet + year docks (**done**, #127)

| Item | Status |
|------|--------|
| StreetNet/IRC: chat send/receive + channel list (`/join`) | Done — `year_docks.gd` + `NetClient.send_chat` |
| Open/close docks from structured snapshot fields (no DOM) | Done — accordion dock bar |
| Journal | Done — quest/steps paint + `journal_track` |
| ICE probes + jack in/out | Done — `ice_probe` buttons + Jack dock control |
| Globe / teleport | Done — zoom/search/filter/recall + `teleport` |
| Primer, Jaunte, Sleeves, Forecast, Ecology, Empathy | Done — core actions matching web |
| Hello Courier / mod `ui_panel` host | Done — dynamic dock from `mods.panels` |
| Catppuccin styling consistent with play-loop | Done |
| Docs checklist + protocol smoke for dock/chat envelopes | Done |

### Slice 3D — street vertical slice (**done this PR**, #141 — epic stays OPEN)

| Item | Status |
|------|--------|
| Snapshot glyphs → Node3D meshes (walls/floor/props, Catppuccin neon) | Done — `street_3d.gd` + `scenes/street.tscn` |
| Courier camera (close 3rd / 1st) + existing WS intents + gamepad look | Done — `V` view cycle, `C` / R3 cam, right-stick turn |
| Other entities as meshes/billboards; highlight J / U | Done |
| Control HUD / docks / ASCII overlay or toggle (ASCII path kept) | Done — default **3D** |
| Forward+ desktop / Mobile Deck renderer + budget notes | Done — [godot-3d.md](godot-3d.md) |
| Docs: 3D is the Steam presentation goal | Done — this file + [steam-quality-bar.md](steam-quality-bar.md) |

Remaining #141 slices (do **not** close the issue): globe 3D, lighting/particles/Deck QA, optional ASCII overlay. Street = slice 1 (#142). Entities = slice 2 (#143). Cyberspace / ICE 3D = slice 3 (this PR — see [godot-3d.md](godot-3d.md)).

### Remaining epic items (later slices)

**Core loop leftovers**

- [ ] Street GPS / minimap (respect #116 hide-GPS)
- [ ] Death / respawn UX polish beyond `R` + HUD flag
- [ ] Gamepad mapping

**Social & meta**

- [x] StreetNet / IRC dock (**#127**)
- [x] Quest journal (+ track; compass bearing still HUD-only) (**#127**)
- [ ] Party / crew / contracts surfaces
- [ ] Shop / craft / stash / season pass

**Systems docks**

- [x] ICE probes (+ list; heists UX still thin) (**#127**)
- [x] Cyberspace jack-in / jack-out control (**#127**)
- [x] Cyberspace / ICE **3D lattice** while jacked (**#141** slice 3; web overlay still exists)
- [x] Globe / teleport (**#127**; schematic Earth SVG left to later)
- [x] Primer, Jaunte, Sleeves, Forecast, Ecology, Empathy (**#127**)
- [x] Hello Courier / mod `ui_panel` host (**#127**)
- [ ] Catppuccin theme throughout (Theme resource, not just consts)
- [x] ICE heists 3D layer indicators + lattice (**#141** slice 3; dock UX still thin)

**Polish & ship**

- [ ] Opening intro / jack-in cutscene
- [x] SFX + mute + music beds / volume sliders (**#134** / [audio.md](audio.md))
- [x] Settings: audio volumes + mute persist (ConfigFile; **#134**); name remember via onboarding
- [ ] Settings remaining (theme, GPS hide, large type)
- [ ] Export: Linux/Windows/macOS desktop builds
- [ ] Docs: mark client “implemented” for player how-to when parity is real
- [ ] Optional: Steam packaging path (#67 / #130) using Godot export

Suggested next slice: **#141 globe 3D**, or lighting/particles/Deck QA, or GPS minimap + death UX, or desktop export toward Steam (#130).

---
## Related

- [audio.md](audio.md) — #134 SFX/music buses + trailer bed
- [godot-3d.md](godot-3d.md) — #141 3D Metaverse street (Steam presentation goal)
- [steam-quality-bar.md](steam-quality-bar.md) — #130 Steam comps + quality bar; **3D Godot** is the Steam presentation goal
- [steam-packaging.md](steam-packaging.md) — #67 Direct / depots / assets; Tauri = calendar fallback wrap of web
- [mobile.md](mobile.md) — #75 PWA; Godot is store-native later
- [modding.md](modding.md) — #72 JSON plugins; Godot only renders
- [fpv.md](fpv.md) / [tui-fpv.md](tui-fpv.md) — FPV pipelines to port
- [theme-catppuccin.md](theme-catppuccin.md) — palette attribution
- [year_backend_actions.md](year_backend_actions.md) — action + snapshot dictionary
- [globe.md](globe.md) — #54 hop / pins
