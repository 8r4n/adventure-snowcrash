# Steam packaging research

Issue **#67** (parent campaign **#42**; related **#72** modding / future Workshop). Research only: how to **package and sell** adventure-snowcrash on Steam.

**Out of scope for this ticket (honored):** paying the Steam Direct fee, uploading builds, or publishing without explicit approval. Final store trailer production is also out of scope.

Sources checked 2026-09-13 (partner docs + public Steamworks pages):

- [Steam Direct Fee](https://partner.steamgames.com/doc/gettingstarted/appfee)
- [Onboarding](https://partner.steamgames.com/doc/gettingstarted/onboarding)
- [Graphical Assets](https://partner.steamgames.com/doc/store/assets)
- [Uploading / SteamPipe](https://partner.steamgames.com/doc/sdk/uploading)
- [Steamworks API Overview](https://partner.steamgames.com/doc/sdk/api)
- [Content Survey](https://partner.steamgames.com/doc/gettingstarted/contentsurvey)
- [Steam Overlay](https://partner.steamgames.com/doc/features/overlay)

---

## Acceptance checklist

| Research question | Status | Where answered |
|-------------------|--------|----------------|
| Steam Direct / partner account, fees, tax/identity | Done | § Steam Direct & partner account |
| Packaging for Python + FastAPI web + optional TUI | Done | § Recommended packaging |
| Steamworks SDK needs vs our WS model | Done | § Steamworks |
| Build/CI: Windows/macOS/Linux depots, Proton | Done | § Build / CI / depots |
| Store page assets checklist | Done | § Store assets checklist |
| Licensing / IP (MIT + original prose theme) | Done | § Licensing & IP |
| Offline vs always-online; dedicated server story | Done | § Offline vs online |
| Rough cost/timeline + open questions / go-no-go | Done | § Cost & timeline · § Open questions |

---

## Product shape (what we would ship)

Adventure-snowcrash today:

| Surface | Stack | Entry |
|---------|-------|--------|
| **Web MMORPG** (primary) | Python 3.11+ · FastAPI · Uvicorn · Jinja2 · WebSocket · static JS/CSS/ASCII FPV | `python -m snowcrash.web` (default port 8765) |
| **TUI single-player** | curses · shared `engine.py` | `python -m snowcrash` |
| **PWA shell** | manifest + SW (shell cache only; live play needs WS) | see [mobile.md](mobile.md) |
| **Mods** | JSON-first plugins (`mods/`, `examples/plugins/`) | see [modding.md](modding.md) |

Steam buyers expect a **double-click desktop app**, not “install Python and run uvicorn.” Packaging must hide the interpreter and either embed a browser UI or open a local URL cleanly.

**SKU posture update (#130):** prefer a **Godot 4** native client as the Steam-marketable product; see [steam-quality-bar.md](steam-quality-bar.md). Tauri + web remains the fastest calendar fallback documented below.

---

## Steam Direct & partner account

### Fee (current)

- **$100 USD (or local equivalent) per app** — the Steam Direct Fee / app credit.
- Payable with Steam-supported methods in your country; **Steam Wallet funds are excluded**.
- **Not refundable**, but **recoupable** after the product reaches **$1,000 Adjusted Gross Revenue** (shown as a line item in the monthly report). Charge-backs / fraud can withhold payout and fee repayment.
- VAT/GST may apply on the fee depending on jurisdiction; invoice goes to the **individual Steam account** that paid.

### Onboarding requirements

1. Sign NDA + Steam Distribution Agreement (electronic).
2. Pay the app fee (creates an app credit; Admin permission needed on existing partners).
3. **Legal identity** matching bank/tax docs (individual = Sole Proprietorship with legal name; no DBA-as-legal-name).
4. **Bank account** in the same legal name for payouts.
5. **Tax questionnaire** (W-9-like for US; W-8BEN-like for treaty countries). Third-party verification often **2–7 business days**; extra docs may be requested by email.
6. After approval: configure store page, builds, Steamworks features, pricing.

### Timing gates (first titles)

| Gate | Duration | Notes |
|------|----------|--------|
| Fee → first release | **≥ 30 days** | Identity / business review window |
| Public Coming Soon page | **≥ 2 weeks** | Wishlist + copy practice |
| Build + store review | typically **1–5 days** | Valve runs the game, checks store config / harm |

### Revenue share (planning assumption)

Publicly known Steam Distribution Agreement tiers (confirm against the signed agreement):

| Lifetime revenue (per title) | Developer share | Valve share |
|------------------------------|-----------------|-------------|
| First $10M | ~70% | ~30% |
| $10M–$50M | ~75% | ~25% |
| Above $50M | ~80% | ~20% |

Most indie titles never leave the 70/30 band. Net after VAT, regional pricing, discounts, and refunds is lower than list × 0.7.

### Content rules (go/no-go filter)

Do not ship content you don’t own rights to; adult content must be labeled; no malware, credential harvesting, ad-supported models, crypto/NFT apps, etc. (full list on Onboarding / Rules & Guidelines). Our MIT + original prose posture aligns if marketing stays clear of novel IP (see § Licensing).

---

## Recommended packaging

### Decision (v1 Steam SKU)

**Recommend: Tauri 2 wrapper + PyInstaller FastAPI sidecar**, launched by Steam as one native executable.

```
Steam launch
  └─ Tauri shell (system webview)
       ├─ spawns PyInstaller sidecar → uvicorn/FastAPI on 127.0.0.1:<ephemeral>
       ├─ loads web UI (bundled static or localhost)
       └─ optional: Steamworks via Rust plugin or thin FFI
```

Why this fits our stack:

- Web client is already the feature-complete surface (FPV, HUD, MMORPG WS).
- Tauri sidecars are the documented pattern for bundling Python/FastAPI ([Tauri external binaries](https://v2.tauri.app/develop/sidecar/); community examples use PyInstaller + FastAPI).
- Smaller installers than Electron (no Chromium bundle); uses OS webview.
- Steam gets a normal Win/Linux/macOS binary; Proton can run the Windows build on Steam Deck if we ship Win first.

### Options compared

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| **Tauri + PyInstaller sidecar** | Small; native; lifecycle for Python server; OS webview | Need Rust toolchain; webview quirks per OS; kill PyInstaller bootloader carefully | **Preferred v1** |
| **Electron + PyInstaller** | Familiar; Chromium parity with browser | Large downloads (~100MB+); higher RAM | Fallback if webview breaks ASCII/canvas |
| **PyInstaller only + open system browser** | Fastest spike | Overlay/friends weak; UX feels “not a game”; port conflicts | Spike only |
| **Native rewrite (no Python)** | Clean Steamworks | Months of work; abandons shared engine | Out of scope |
| **TUI-as-Steam-app** | Tiny | Curses on Windows is painful; loses FPV web features | Optional **bonus depot tool**, not primary SKU |
| **Always-online only (hosted server)** | Matches current `adventure-dev` | Needs paid infra; Steam refunds if auth fails; always-online stigma | Mode B, not sole SKU |

### Packaging details (implementation sketch)

1. **PyInstaller** one-file/one-folder for `snowcrash.web` + templates/static/mods defaults. Bind **127.0.0.1** only; pick free port; write port to a small file or stdout for the shell.
2. **Tauri** `bundle.externalBin` points at `snowcrash-server-$TARGET_TRIPLE`.
3. Shell waits for `/health`, then navigates webview to `http://127.0.0.1:$PORT/`.
4. On quit: graceful shutdown of sidecar (known PyInstaller one-file pitfall: kill the child, not only the bootloader — prefer one-folder or documented sidecar shutdown protocol).
5. Persist saves under **OS app-data** (or Steam cloud paths), not the install dir.
6. Ship **Windows + Linux** first; macOS when notarization + webview QA budget allows.

### TUI on Steam

Ship as an optional **“Terminal Courier”** launch option / second executable in the same app (separate launch config in Steamworks), or a free companion tool later. Windows Terminal / ConPTY support needs explicit QA; Linux/macOS are natural.

---

## Steamworks

Steamworks API is **not required** to ship, but recommended for overlay, achievements, cloud, and friends.

### Godot SKU — GodotSteam stub (#173)

Preferred host for SteamAPI on the Godot path is the **Godot process** via [GodotSteam GDExtension](https://godotsteam.com/) (not SteamworksPy / Tauri):

1. Drop the GDExtension into `godot_client/addons/godotsteam/` (see that folder’s README) — Godot **4.4.1+**.
2. Autoload `SteamBridge` no-ops without the addon so **4.3 headless export / CI stay green**.
3. Dev: `steam_appid.txt` (example checked in as `godot_client/steam_appid.txt.example`, real file gitignored) or env `SteamAppId` / `SteamGameId`. **Never** put `steam_appid.txt` in a SteamPipe depot.
4. Deck / Big Picture → `GraphicsSettings` Low first-run hint (`SteamBridge.suggest_low_quality()`).
5. Achievement/stat API is a **placeholder** until a real App ID + Steamworks definitions exist. Overlay works in **exports** only (not editor).

Details: [godot-client.md § GodotSteam integration stub](godot-client.md#godotsteam-integration-stub-173). Do not pay Steam Direct / upload from this issue (same gate as #67).


### Priority integration map

| Feature | Need for v1? | Notes for our stack |
|---------|--------------|---------------------|
| **SteamAPI_Init / RunCallbacks** | Yes if any feature | Call from Tauri/Rust host or a tiny helper DLL that the Python process loads. Dev: `steam_appid.txt` beside exe (do not ship). |
| **Overlay** | Nice | Hooks D3D/GL/Vulkan/Metal/OpenGL. **Software / pure HTML webview may get weak or no overlay.** Electron Chromium often works better; Tauri webview is OS-dependent — **verify on Win10/11 + Deck early.** |
| **Achievements / stats** | Nice | Map courier milestones (Payload-Zero delivered, first heist, etc.) via `ISteamUserStats`. Can drive from Python over a local IPC to the host that owns SteamAPI. |
| **Cloud saves** | Nice for SP/TUI | Auto-Cloud path rules, or `ISteamRemoteStorage`. MMORPG progress is server-authoritative today — cloud helps **offline/single-player** profiles more than shared-world. |
| **Friends / Rich Presence** | Later | “On the street / in ICE heist” strings; invites need a join story (lobby → dedicated or listen server). |
| **Multiplayer networking** | **Do not replace WS with Steam Networking for v1** | Keep authoritative FastAPI + WebSocket. Optional: Steam auth ticket → server validates `ISteamUser.GetAuthSessionTicket` so Steam accounts map to courier nicks. Dedicated server can use Game Server API later. |
| **DRM / VAC** | Optional | Steam’s custom DRM wrapper is available; not required. VAC is for anti-cheat genres — low value for ASCII courier sim. |
| **Workshop** | Notes now (#72) · upload later | Pack contract + no-unsigned-auto-download: [modding-workshop.md](modding-workshop.md). JSON mods + path jail already fail-closed. Steam Subscribe → unpack → `reload_mods()`. |

### SteamworksPy note

Issue comment suggests [SteamworksPy](https://github.com/philippj/SteamworksPy). Viable if the **Python sidecar** owns SteamAPI; alternatively keep SteamAPI in the **Tauri/Rust** process and talk over localhost IPC (cleaner process ownership, easier overlay timing). Evaluate maintenance status of SteamworksPy vs `steamworks` Rust crates before locking in.

---

## Build / CI / depots

### Depot layout (proposed)

**Preferred SKU (#130 / #149):** Godot native exports — see [godot-desktop-export.md](godot-desktop-export.md). Tauri rows remain the calendar fallback.

| Depot | Content | Platforms |
|-------|---------|-----------|
| **Linux64 Godot** | `Snowcrash.x86_64` + `.pck` from `./scripts/export_godot_client.sh linux` | Linux (primary Deck) |
| **Win64 Godot** | `Snowcrash.exe` + `.pck` | Windows (+ Proton fallback) |
| Depot Tauri Win (fallback) | Windows Tauri app + sidecar | Windows |
| Depot Tauri Linux (fallback) | Linux Tauri build | Linux |
| macOS (optional) | Godot or Tauri `.app` | macOS |
| Shared (optional) | Mods examples, licenses (no `steam_appid.txt` in ship) | All |

SteamPipe: SDK `tools/ContentBuilder` + VDF `app_build_*.vdf` / `depot_build_*.vdf`; upload via `steamcmd +login … +run_app_build …`.

### CI sketch (GitHub Actions)

Existing CI doc: [ci-github-actions.yml](ci-github-actions.yml) (lint/test only). Extend later with:

1. Matrix: `windows-latest`, `ubuntu-latest` (macOS optional).
2. Build PyInstaller artifact → stage into Tauri `binaries/`.
3. `tauri build` → platform installer / loose files for Steam content root.
4. On tag / manual workflow: [game-ci/steam-deploy](https://github.com/game-ci/steam-deploy) or raw steamcmd with **config.vdf** or TOTP secrets (never commit).
5. Upload to a **beta branch** (`staging`) first; promote to default after QA.

Secrets: `STEAM_USERNAME`, `STEAM_CONFIG_VDF` or shared_secret TOTP — store in GitHub Actions secrets only.

### Proton / Steam Deck

- Prefer a **native Linux** depot for Deck (Godot export is the preferred SKU — see [steam-deck.md](steam-deck.md) / #132).
- **Do not** ship Deck as Proton-only. Windows+Proton remains a fallback depot only.
- Controllers / UI scale / suspend-reconnect / device QA checklist: **[steam-deck.md](steam-deck.md)**.
- Tauri/webview path (#67 historical): still budget a Deck pass if used as calendar fallback — webview + sleep is a Verified risk.

### Launch options (Steamworks)

Example:

```
Snowcrash (Desktop)     → Snowcrash.exe
Snowcrash (Terminal)    → snowcrash-tui.exe   # optional
```

---

## Store assets checklist

Dimensions from current Steamworks templates (Aug 2024+ sizes; old capsules rejected):

### Store

| Asset | Required? | Size |
|-------|-----------|------|
| Header capsule | Yes | 920×430 |
| Small capsule | Yes | 462×174 |
| Main capsule | Yes | 1232×706 |
| Vertical capsule | Yes | 748×896 |
| Screenshots | Yes (≥5) | ≥1920×1080, 16:9, **gameplay** (not concept art / awards) |
| Page background | Optional | 1438×810 |
| Trailer | Strongly expected | Store review expects a trailer; production out of scope for #67 |

Capsules: logo + artwork only (no update banners / time-sensitive copy in evergreen assets).

### Library / client

| Asset | Required? | Size |
|-------|-----------|------|
| Library capsule | Yes | 600×900 |
| Library hero | Yes | 3840×1240 |
| Library logo | Yes | 1280 wide and/or 720 tall PNG |
| Library header | Yes | 920×430 |
| Shortcut icon | Yes | 256×256 .ico/.png |
| App icon | Yes | 184×184 .jpg |

### Copy & metadata

- [ ] Short description + about-the-game (original prose; see IP)
- [ ] Tags (e.g. Cyberpunk, Roguelike, MMORPG, Indie, Retro, Text-based — finalize with wishlist tests)
- [ ] Supported languages / OS / controllers
- [ ] Pricing + regional defaults
- [ ] **Content Survey** (ratings questionnaire + mature content + AI disclosure) — required before review
- [ ] Age ratings via Steam questionnaire / IARC path; **Germany** needs a valid rating for new-customer visibility
- [ ] Coming Soon page live ≥2 weeks before release

Repo already has animated GIFs under `docs/screenshots/` suitable as **reference** for trailer/screenshot framing, not as final Steam assets.

---

## Licensing & IP

### Code & assets we ship

| Asset | License / origin | Steam note |
|-------|------------------|------------|
| Game code | **MIT** (`LICENSE`, © 2026 8r4n) | Redistributable; keep license text in install |
| Catppuccin palette | **MIT** (upstream) | Already attributed in [theme-catppuccin.md](theme-catppuccin.md) |
| SFX / tiles / cutscenes | Procedural / synthetic scripts in-repo | Keep generators; no third-party sample packs found |
| Fonts | System / CSS stacks (`system-ui`, mono vars) | No bundled commercial fonts spotted — re-audit before ship |
| Python deps | FastAPI, Uvicorn, Jinja2, etc. | Include notices for bundled wheels in PyInstaller build |

### “Snow Crash” theme = original prose only

`STORY.md` states themes echo cyberpunk Metaverse vibes at a **high level only** — no novel text, no borrowed character names. Cast (Rin Vale, Relay Tran, Cassian Vox, …) and Payload-Zero arc are **original to this repo**.

**Marketing rules for Steam:**

1. Do **not** claim this is an adaptation of Neal Stephenson’s novel *Snow Crash*, or use “based on the novel.”
2. Avoid distinctive novel trademarks/characters (Hiro, Y.T., Raven, specific brand pastiches that are expressive of the book) in store copy, tags, or capsules.
3. “Metaverse,” “avatar,” cyberpunk courier tropes are **ideas/genre** — generally safer than copying plot, dialogue, or character names; still avoid implying affiliation.
4. Product title **Snowcrash** / repo name may attract trademark or confusion risk — **open question** for a legal clearance search before paying the Direct fee. Consider a distinct store title if clearance is weak.
5. Mods must continue to require **original prose** ([modding.md](modding.md)).

This is **not legal advice**; a cheap trademark knockout search + counsel review is part of go/no-go cost.

---

## Offline vs online

| Mode | Feasibility | Steam positioning |
|------|-------------|-------------------|
| **Single-player offline** (local FastAPI or TUI engine, no shared world) | High — engine already supports seeded SP | Primary honest SKU; works on planes / Deck offline |
| **Listen / LAN host** (one player’s sidecar is the server) | Medium — need host discovery + firewall docs | Nice stretch |
| **Always-online shared Metaverse** (current `adventure-dev` style) | Needs dedicated host + ops | Market as optional “StreetNet Online” or free weekend servers; don’t make purchase useless if servers die |
| **Steam Networking rewrite** | Low priority | Keep WS; add Steam auth later |

**Recommendation:** Steam build defaults to **local offline/single-player (or small private server)**. Optional connect-to-official-realm is a feature flag, not a hard requirement for boot. Document dedicated-server binary later if MMORPG becomes a selling point.

PWA service worker already caches shell only — same philosophy: shell offline, world may need network.

---

## Cost & timeline (rough)

### Money (order of magnitude, USD)

| Item | Estimate | Notes |
|------|----------|-------|
| Steam Direct fee | **$100** | Recoupable after $1k AGR |
| Tax/bank setup | $0–200 | Entity / accountant if needed |
| Trademark / name clearance | $0–500+ | Knockout vs attorney letter |
| Art (capsules, hero, icons) | $200–2,000 | Or DIY from ASCII neon stills |
| Trailer | $0–1,500 | Out of scope for #67; still needed to ship |
| macOS Apple Developer (if shipping Mac) | ~$99/yr | Notarization |
| Hosting (optional online realm) | $5–40/mo | Only if always-online mode |
| **Cash to press “Coming Soon”** | **~$100–800** | Fee + minimal art + clearance |

### Time (calendar, one experienced indie)

| Phase | Duration | Depends on |
|-------|----------|------------|
| Packaging spike (Tauri + sidecar boots web UI) | 1–2 weeks | Webview/overlay unknowns |
| Steamworks thin slice (init + 3 achievements + cloud path) | 1 week | After spike |
| Win+Linux CI → SteamPipe beta | 1 week | Secrets + VDF |
| Store assets + Coming Soon | 1–2 weeks | Art |
| Fee wait + Coming Soon gate | **≥ 30 days + 14 days** | Can overlap with polish |
| Deck/Proton QA + review | 1 week | Device access |
| **Earliest plausible release after go** | **~8–12 weeks** | Not a commitment |

### Go / no-go (research recommendation)

**Soft go for a Steam path**, contingent on:

1. Successful Tauri+sidecar spike proving FPV/WS on Win + Deck (or Proton).
2. Store title / trademark comfort.
3. Willingness to ship **offline-capable** first (not server-hostage).
4. Explicit approval before paying the $100 fee or uploading builds.

---

## Open questions

1. **Store title:** keep “Snowcrash” vs rename to reduce novel/trademark confusion?
2. **Overlay quality** in Tauri webview vs Electron — which to lock after spike?
3. **Steamworks owner process:** Rust host vs SteamworksPy in sidecar?
4. **MMORPG realm:** official hosted servers in scope for launch, or post-1.0?
5. **Pricing:** premium one-time vs free+DLC vs free demo + paid?
6. **macOS:** launch platforms Win+Linux only?
7. **Achievements list** + whether MP-only achievements are acceptable if offline is default.
8. **Workshop:** timeline relative to #72 JSON mods.
9. **Age rating content survey answers** for violence (drones/thugs), language, etc. — fill with design, not guesses, at submission time.
10. **Legal:** who is the Steamworks partner entity (individual vs company)?

---

## Implementation backlog (post-#67, not started)

- [ ] Spike: Tauri 2 + PyInstaller `snowcrash.web` sidecar on Windows
- [ ] Spike: same on Linux; Deck/Proton check
- [ ] Godot Linux export → Deck device QA per [steam-deck.md](steam-deck.md) (#132)
- [ ] Decide Electron fallback criteria
- [ ] Steamworks init + achievement stub
- [x] `steam_appid.txt` dev workflow documented (#173 · `godot_client/steam_appid.txt.example` + gitignore)
- [ ] Depot VDFs + GH Action dry-run (no live upload without approval)
- [ ] Capsule / hero art pass + ≥5 1080p screenshots
- [ ] Trailer brief (separate ticket)
- [ ] Trademark knockout on chosen store name
- [ ] Explicit user approval → pay Steam Direct

---

## Related docs

- [steam-quality-bar.md](steam-quality-bar.md) — #130 north star, comps, gaps; **Godot preferred Steam SKU** (Tauri = calendar fallback)
- [steam-deck.md](steam-deck.md) — #132 Steam Deck Verified checklist + Linux depot plan
- [godot-desktop-export.md](godot-desktop-export.md) — #149 Godot Linux/Windows export + SteamPipe staging paths
- [godot-client.md](godot-client.md) — #109/#118 Godot 4 thin client (preferred native SKU per #130; Tauri remains fastest wrap of current web)
- [modding.md](modding.md) — Workshop precursor (#72)
- [mobile.md](mobile.md) — PWA shell; not a Steam substitute
- [ci-github-actions.yml](ci-github-actions.yml) — current test CI
- [STORY.md](../STORY.md) — originality statement
- [theme-catppuccin.md](theme-catppuccin.md) — third-party palette attribution
