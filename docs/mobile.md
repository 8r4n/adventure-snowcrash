# Mobile playability

Issue **#75** (parent campaign **#42**). Make the web client **genuinely playable on phone/tablet**: touch controls, readable FPV/HUD, safe-area aware chrome, and installable PWA shell. Builds on **#31** (mobile HUD / virtual joystick stub).

This doc tracks **slice progress** — #75 stays open until the full acceptance list lands.

## What’s shipped

### Slice 1 (PR #77)

| Area | Status | Notes |
|------|--------|-------|
| Web manifest + icons + `theme-color` | **Done** | `snowcrash/static/manifest.webmanifest`, neon icons under `static/icons/` |
| Apple mobile web-app meta | **Done** | Capable / status-bar / title + apple-touch-icon |
| Light service worker (offline shell) | **Done** | `/sw.js` precaches shell assets only; live play still needs network/WS |
| Mobile HUD visible on narrow / coarse pointer | **Done** | CSS `@media (max-width: 720px)` and coarse-pointer tablet rule |
| Panel scroll (Journal / ICE / dock) | **Improved (#88)** | Year-panel accordion (one open); `#side` single scroll on narrow; dock wrap on mid widths |
| Toasts vs HP / Focus | **Partial** | Sticky stats + toasts parked under topbar (not over HUD / sticky HP row) |
| Safe-area insets | **Done** | `#app`, mobile HUD, minimap / toast offsets use `env(safe-area-inset-*)` |
| Joystick scroll bleed | **Done** | `touch-action: none` + non-passive `touchmove` preventDefault on pads |

### Slice 2 (this branch)

| Area | Status | Notes |
|------|--------|-------|
| Explicit in-UI large-type toggle | **Done** | Toolbar **Aa** cycles Auto → Large (`Aa+`) → Compact (`Aa−`); persists `localStorage.snowcrash_large_type` |
| One-handed portrait / landscape pads | **Improved** | Viewport padding reserves space for vjoy + chord pad; higher HUD z-index; tighter `#side` max-height so docks don’t bury FPV |
| Ghost input / pointercancel | **Improved** | Hold-to-move on vjoy with `pointerup` / `pointercancel` / `lostpointercapture` / blur / `visibilitychange` / `pagehide` cleanup; WASD `moveKeysHeld` cleared the same way; ghost click blocked on pads |
| Minimap / compass at small sizes | **Improved** | ≤420px denser GPS + ellipsis compass pills; portrait/landscape offsets clear of pads |
| Copy join link | **Done** | Name-gate **Copy join link** copies URL with `?name=` (clipboard + fallback) |
| QR join | **Open** | Deferred — copy-link covers the easy path |
| Stable 30fps+ / battery / RAF | **Open** | Not measured this slice |
| WS reconnect + background tab docs | **Open** | Document in a later pass |
| No critical hover/keyboard-only paths | **Open** | Dock + chords cover common acts; wish / some modals still desktop-leaning |
| Device test matrix fill-in | **Open** | Stub table below |

## PWA

- **Manifest:** `/static/manifest.webmanifest` (also served at `/manifest.webmanifest`)
- **Icons:** 192 / 512 / apple-touch 180 / favicon 32
- **Display:** `standalone`, theme/background `#05080c`
- **Service worker:** root `/sw.js` — caches HTML shell + core static CSS/JS/icons. Does **not** offline the MMORPG world (WebSocket + `/api/*` bypass the cache). Cache name `snowcrash-shell-v2` after slice 2.

Install: Chrome/Edge (Android) or “Add to Home Screen” on iOS Safari after visiting over HTTPS (or localhost).

### Large type

Toolbar **Aa** control (and `localStorage`):

| `localStorage.snowcrash_large_type` | Button | Effect |
|-------------------------------------|--------|--------|
| unset | `Aa` | **Auto** — large type on viewports ≤720px |
| `"1"` | `Aa+` | Force large type (fewer ASCII columns / larger glyphs) |
| `"0"` | `Aa−` | Force default density |

Changing the toggle calls `FpvBridge.kick()` so the FPV canvas reflows immediately.

## Test matrix (stub)

Fill in on device as playtests land. Target: courier can move, fight/ICE, open journal, finish a short objective (Signal Key or Neon Dash) without a keyboard.

| Device / browser | OS | Portrait move | Landscape | Journal/ICE panels | Toast vs HP | Install PWA | Notes |
|------------------|----|---------------|-----------|--------------------|-------------|-------------|-------|
| iPhone Safari | iOS 17+ | | | | | | |
| iPhone Chrome | iOS | | | | | | A2HS via Safari share sheet |
| Pixel / Android Chrome | Android 14+ | | | | | | |
| Tablet (coarse pointer) | — | | | | | | HUD should show via coarse media query |
| Desktop narrow (<720) | — | | | | | | DevTools device mode |

### Smoke checklist

1. Jack in with `?name=MobileTest` (or **Copy join link** from the gate)
2. Virtual stick moves (hold repeats); page does not rubber-band scroll behind the pad
3. Lift finger / rotate / background the tab — no idle drift
4. FIRE / GET / ICE chords respond
5. Toolbar **Aa** cycles Auto / Large / Compact and FPV density updates
6. Open Jrnl + ICE from dock — one scroll surface; FPV + pads still reachable in portrait
7. HP / Focus sticky row remains readable when toasts fire
8. Notch / home-indicator devices: chrome clear of unsafe edges
9. (Optional) Install PWA; cold start shows shell; online play still works

## Related

- #31 Mobile-friendly HUD (shipped stub)
- #68 FPV contrast / readability (`docs/fpv.md`)
- #67 Steam / desktop packaging (separate)
- #109 Godot thin client — store-native Android/iOS later; does not block this PWA path ([godot-client.md](godot-client.md))
- Campaign log: #42

## Remaining for full #75 acceptance

See open checkboxes on **#75**. Highest leverage next slices:

1. Device matrix playtest + remaining hover/keyboard-only audit
2. Perf pass (RAF idle, battery) + document WS background / reconnect behavior
3. Optional QR join helper (copy-link already shipped)
4. Further one-handed polish from real device feedback
