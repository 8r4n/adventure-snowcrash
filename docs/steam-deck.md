# Steam Deck Verified checklist (Godot export path)

Issue **#132** (parent Steam quality bar **#130** · packaging **#67** · Godot client **#118** / docks **#127** · mobile/PWA **#75** — not a substitute).

Living checklist for shipping adventure-snowcrash as a **Steam Deck–ready Godot native Linux** SKU. Maps Valve’s [Deck / Steam Hardware compatibility](https://partner.steamgames.com/doc/steamhardware/compat) criteria to our thin WebSocket client.

**Honesty gate:** this doc is a **plan + self-QA checklist**. We have **not yet run a Deck (or Deck-like) hardware pass**. Do **not** claim Steam Deck Verified on the store page until Valve’s review (or an equivalent device pass with notes filed) succeeds.

**Non-goals (same as #67 / #130):** paying Steam Direct, uploading builds, or marketing Verified without a real device pass.

Sources checked 2026-09-13:

- [Steamworks — Deck / Steam Machine compatibility](https://partner.steamgames.com/doc/steamhardware/compat)
- [steamdeck.com/en/verified](https://www.steamdeck.com/en/verified) (four customer-facing boxes)
- In-repo: [steam-quality-bar.md](steam-quality-bar.md), [steam-packaging.md](steam-packaging.md), [godot-client.md](godot-client.md), [`godot_client/`](../godot_client/)

---

## Acceptance checklist

| Item | Status | Where |
|------|--------|-------|
| Valve categories mapped to Godot export | Done | § Verified categories |
| Native **Linux** depot plan (not Proton-only) | Done | § Native Linux depot plan |
| Gamepad / Steam Input map (courier loop) | Done | § Input map · `project.godot` InputMap |
| Default UI scale / 1280×800 readable glyphs | Done | § Display & UI scale |
| Suspend/resume + WS reconnect | Done | § Suspend / resume · `net_client.gd` |
| Device QA section + blockers | Done | § Device QA · § Blockers |
| Links from quality-bar / packaging | Done | those docs → this file |

---

## Why Godot native Linux (not Proton-only)

| Path | Deck story | Verdict for us |
|------|------------|----------------|
| **Godot 4 Linux x86_64 export** | SteamOS runs it natively; Valve prefers testing Linux when present | **Primary Deck SKU** |
| Windows export + Proton | Works for many Godot titles; extra Proton risk (overlay, input, filesystem) | Fallback / Win depot only — **not** the Deck launch path |
| Tauri / Electron + webview (#67) | Webview + localhost + Deck sleep is a known risk | Calendar fallback; weaker Verified story |
| PWA / Chrome (#75) | Companion / phone bridge | **Not** the Steam SKU |

Theme 8 of [steam-quality-bar.md](steam-quality-bar.md): stable on mid PC + Deck; **no Chrome-in-a-box** as the shipped path.

---

## Verified categories → our Godot export

Valve’s customer-facing “four boxes” and the Steamworks checklist map as follows. Ratings: **Verified** / **Playable** / **Unsupported** / **Unknown**. We target **Verified** via native Linux; we do **not** self-badge until a device pass + Valve review.

### 1. Input

| Valve criterion | Our Godot plan | Status |
|-----------------|----------------|--------|
| Full default-controller access to all content | Map Deck sticks / face / shoulders / Select·Start to courier intents (move, turn, get, fire, docks, StreetNet) — see § Input map | **Mapped in InputMap**; device QA pending |
| No “enable controller in settings” step | Default `project.godot` InputMap + joypad polling in `main.gd`; no options gate | Planned / light code |
| Controller glyphs match active device | Prefer **Steam Input API** via GodotSteam later; until then Xbox-style labels in docs/hints (avoid KBM-only glyphs when a pad is active) | **Gap** — glyphs not dynamic yet |
| Text entry opens Steam OSK or pad-navigable entry | Courier name / StreetNet chat: call Steamworks floating keyboard when GodotSteam lands; interim: Deck touchscreen + OSK, or on-screen soft keys | **Gap** — needs GodotSteam or built-in OSK |
| External Bluetooth pads | Prefer Steam Input so Deck built-in stays default; avoid grabbing only the first XInput pad | Follow-up with GodotSteam |

**Courier loop actions to cover (all content for Verified):** move, look/turn, interact (get / fire / use / look), inventory, respawn, FPV↔map, year docks accordion, StreetNet send, mute/audio, jack-in / disconnect.

### 2. Display (Deck-specific)

| Valve criterion | Our Godot plan | Status |
|-----------------|----------------|--------|
| Native resolution **1280×800** (preferred) or 1280×720 | `project.godot` viewport **1280×800**; stretch `canvas_items` + `keep` aspect | Done (stub) |
| Playable default performance (≥ **30 fps @ 800p**) | GL Compatibility renderer; ASCII FPV is cheap; target 30–40 fps locked later | Device QA pending |
| Text ≥ **9 px** tall @ 1280×800 (aim **12 px**) | HUD / FPV / docks use ≥12 px mono / UI fonts; Catppuccin contrast | Guidance in § Display; device QA pending |
| Good defaults (no manual resolution tweak) | Export fullscreen / borderless; no launcher resolution dialog | Export preset notes |

### 3. Seamlessness

| Valve criterion | Our Godot plan | Status |
|-----------------|----------------|--------|
| No “unsupported GPU / Linux” warnings | Godot export must not show Wine/Proton or GPU blacklist dialogs; no custom launcher | Plan: single exported binary |
| Launcher fully pad-navigable (or none) | **No third-party launcher** — Godot main scene is the entry | Preferred |
| Clean exit / Steam overlay | GodotSteam overlay in **exports** only; quit via Start → system or in-game disconnect | Follow-up GodotSteam |

### 4. System Support / Proton

| Valve criterion | Our Godot plan | Status |
|-----------------|----------------|--------|
| Proton middleware / anti-cheat OK | We ship **native Linux** → Proton tests are secondary. No kernel anti-cheat. | Prefer native |
| Recommended runtime | Steamworks “Recommended Runtime” should be **Steam Linux Runtime** / native, not Proton, once Linux depot ships | Depot plan below |

Valve note: if a Linux build exists they test it first; only fall back to Windows+Proton if Linux fails. That is why the Linux depot is non-negotiable for Verified intent.

### Performance (checklist sibling)

Default config must hold **~30 fps at 800p** on Deck. Our ASCII FPV + Control HUD is light; risk is unbounded log/`RichTextLabel` growth and unthrottled WS paint — keep snapshot paint cheap (already snapshot-driven).

---

## Native Linux depot plan

Preferred SteamPipe layout once Godot export exists (extends [steam-packaging.md](steam-packaging.md); Godot replaces Tauri as primary SKU):

| Depot | Content | Platforms | Deck role |
|-------|---------|-----------|-----------|
| **Linux64 Godot** | `Snowcrash.x86_64` + `.pck` + optional `libsteam_api.so` (GodotSteam) | Linux | **Primary Deck path** |
| Win64 Godot | `.exe` + `.pck` + `steam_api64.dll` | Windows | Desktop + Proton fallback |
| Shared (optional) | Example mods, licenses, `steam_appid.txt` **dev only** | All | Do not ship `steam_appid.txt` |
| Sidecar (optional later) | PyInstaller `snowcrash-server` for offline Mode B | Win + Linux | Offline SKU; not required for hosted Mode A |

**Launch config (Steamworks):**

```
Snowcrash (Desktop)     → Snowcrash.x86_64   # Linux depot
Snowcrash (Desktop)     → Snowcrash.exe      # Windows depot
```

**Build steps (local / CI sketch — no live upload):**

1. Install Godot **4.3+** export templates (4.4.1+ if GodotSteam).
2. Open `godot_client/project.godot` → Export → **Linux/X11** preset (see `export_presets.cfg.example` stub).
3. Export to `build/linux/Snowcrash.x86_64` (executable + `.pck`).
4. Smoke: run under Steam Linux Runtime or plain SteamOS desktop mode; jack in to hosted `wss://…/ws` or local sidecar.
5. Stage into SteamPipe content root; upload only after explicit approval (#67 gate).

**Proton:** keep Windows depot healthy, but **do not** ship Deck as Proton-only. Document Proton as emergency if a Linux export regresses.

---

## Input map (courier loop)

Canonical intents are the same strings as web / `main.gd` (`forward`, `turn_left`, `g`, `f`, …).

### Keyboard (already shipped)

See [`godot_client/README.md`](../godot_client/README.md) — WASD, Q/E, G/F, docks via UI, etc.

### Gamepad / Steam Deck defaults (InputMap + joypad)

| Deck / pad control | Godot InputMap action | Server intent / UI |
|--------------------|-----------------------|--------------------|
| Left stick / D-pad | `move_*` (quantize 8-way, deadzone ~0.35) | `forward` / `back` / `strafe_*` / diagonals |
| L1 / R1 (or stick click) | `turn_left` / `turn_right` | `turn_left` / `turn_right` |
| A (South) | `interact_get` | `g` (get / pickup) |
| X (West) | `interact_fire` | `f` (fire / hack) |
| B (East) | `look_wait` | `look` / `.` |
| Y (North) | `inventory` | `i` |
| Select / View | `toggle_view` | FPV ↔ map |
| Start / Menu | `toggle_docks` | Focus / cycle year dock bar |
| L2 | `use_item` | `u` |
| R2 | `respawn` (hold or chord later if accidental) | `r` — **confirm on device**; may remapped to long-press |
| D-pad while docks open | UI navigate | Year dock accordion / StreetNet |
| Steam + X (system) | — | Steam overlay (GodotSteam) |

Steam Input: publish a **default official configuration** in Steamworks once AppID exists (recommended over community-only configs for Verified). Until GodotSteam: Godot’s built-in joypad API + InputMap is enough for self-QA.

Implementation: actions declared in `godot_client/project.godot`; hold-to-move at `HOLD_HZ` (8) mirrors keyboard in `main.gd`.

---

## Display & UI scale (1280×800)

| Setting | Value | Why |
|---------|-------|-----|
| Viewport | **1280×800** | Deck native preferred |
| Stretch mode | `canvas_items` | UI scales cleanly |
| Stretch aspect | `keep` | No non-uniform glyph squash |
| Renderer | `gl_compatibility` | Broader Deck/older GPU path |
| Min UI / FPV glyph height | **≥12 px** @ 800p (hard floor 9 px) | Valve text legibility |
| HUD contrast | Catppuccin Mocha on crust/base | Readable outdoors / OLED |

**Guidance for artists / UI:** ASCII FPV columns and dock labels must remain legible at arm’s length (~30 cm). Prefer fewer, larger glyphs over dense web-HUD soup (theme 3 of the quality bar). Optional later: user font-scale slider (Recommended, not blocking Verified).

---

## Suspend / resume + WebSocket reconnect

Deck sleep kills or freezes TCP. Same class of bug as mobile background tabs ([mobile.md](mobile.md)).

| Event | Expected behavior |
|-------|-------------------|
| Jack-in | `join` with name + optional resume `id` (already in `net_client.gd`) |
| Socket close while session wanted | HUD `reconnecting…`; backoff 1.2s → max 8s (existing) |
| **Application pause / focus out** (sleep, Steam overlay long pause) | Pause ping timer; keep `_want_open` |
| **Application resume / focus in** | If socket not `OPEN`: **immediate reconnect nudge** (reset delay to 1.2s); if still open: ping once |
| Explicit Disconnect | `_want_open = false` — no auto-reconnect |
| Offline sidecar (Mode B, later) | Sidecar may also freeze; on resume health-check `/health` then WS |

Light code: `godot_client/scripts/net_client.gd` handles `NOTIFICATION_APPLICATION_PAUSED` / `RESUMED` and focus in/out — see source comments. Server treats a dropped socket as leave; rejoin with the same courier `id` restores the avatar (same as web).

---

## Device QA (Deck pass)

**Status: not yet run on hardware.** No Steam Deck (LCD/OLED) or SteamOS device was available for this ticket. Do not mark Verified.

### Pre-hardware smoke (desktop stand-in)

- [ ] Export Linux preset; binary launches windowed at 1280×800
- [ ] Jack in to local `ws://127.0.0.1:8766/ws` and hosted realm
- [ ] Keyboard courier loop + dock accordion still work
- [ ] Gamepad (Xbox pad) moves / turns / get / fire / docks via InputMap
- [ ] Kill Wi-Fi mid-session → reconnect recovers with same `id`
- [ ] Simulate suspend: `kill -STOP` / continue or laptop lid — reconnect nudge fires

### On-Deck checklist (file notes when run)

- [ ] Install from Linux depot (or sideload export) under Game Mode
- [ ] Default config: no keyboard required for move / interact / docks / jack-in name (OSK or soft entry)
- [ ] Glyphs: no stuck KBM icons when using Deck controls
- [ ] 1280×800 default; text ≥12 px readable at ~30 cm
- [ ] Sustained ≥30 fps on street + ICE jack-in music bed
- [ ] Sleep 60s+ → resume → HUD reconnects without manual Disconnect/Jack-in
- [ ] Steam overlay (with GodotSteam) open/close does not brick input
- [ ] Battery / thermal: 30–40 min courier loop acceptable
- [ ] OLED + LCD if both available (Valve rates both)

File results under this doc (§ Device QA results) or a linked issue comment before requesting Valve’s Steam Hardware Compatibility Review.

### Device QA results

| Date | Device | Build | Outcome | Notes |
|------|--------|-------|---------|-------|
| — | — | — | **Not run** | #132 docs/code only |

---

## Blockers for real device QA

Tracked honestly so Verified is not claimed early:

| Blocker | Impact | Mitigation |
|---------|--------|------------|
| **No Deck hardware in CI / this agent** | Cannot complete on-device checklist | Borrow / buy Deck; or SteamOS VM is **not** a substitute for Verified |
| **No exported release build in CI yet** | Nothing to install on Deck | Add export job later; local export templates required |
| **GodotSteam not integrated** | Overlay, Steam Input glyphs, floating keyboard gaps → risk **Playable** not Verified | Integrate on Godot 4.4+ before review request |
| **Name / chat text entry** | OSK auto-invoke required for Verified text-input rule | Soft on-screen keys or Steamworks keyboard API |
| **Hosted WS only (Mode A)** | Sleep + flaky Wi-Fi needs solid reconnect (code path exists) | Device pass must include sleep test |
| **Offline sidecar not shipped** | Airplane / offline Deck weaker | Mode B post-Verified path; not blocking checklist doc |
| **Dynamic controller glyphs** | Hint bar still KBM-oriented | Swap hints when joypad detected; Steam Input later |

---

## Related docs

- [steam-quality-bar.md](steam-quality-bar.md) — #130 theme 8 / child #132
- [steam-packaging.md](steam-packaging.md) — Direct fee, depots, store assets; Deck section points here
- [godot-client.md](godot-client.md) — thin client architecture + packaging
- [godot-onboarding.md](godot-onboarding.md) — first 10 minutes (#133)
- [audio.md](audio.md) — audio buses (#134)
- [mobile.md](mobile.md) — PWA suspend/WS notes (pattern source, not Steam SKU)
