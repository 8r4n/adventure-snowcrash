# Mobile playability

Issue **#75** (parent campaign **#42**). Make the web client **genuinely playable on phone/tablet**: touch controls, readable FPV/HUD, safe-area aware chrome, and installable PWA shell. Builds on **#31** (mobile HUD / virtual joystick stub).

This doc tracks **slice progress** — #75 stays open until the full acceptance list lands.

## What’s in this slice (v1)

| Area | Status | Notes |
|------|--------|-------|
| Web manifest + icons + `theme-color` | **Done** | `snowcrash/static/manifest.webmanifest`, neon icons under `static/icons/` |
| Apple mobile web-app meta | **Done** | Capable / status-bar / title + apple-touch-icon |
| Light service worker (offline shell) | **Done** | `/sw.js` precaches shell assets only; live play still needs network/WS |
| Mobile HUD visible on narrow / coarse pointer | **Done** | CSS `@media (max-width: 720px)` and coarse-pointer tablet rule |
| Panel scroll (Journal / ICE / dock) | **Partial** | Single scroll owner on `#side`; nested `.panel-body` scroll removed on narrow |
| Toasts vs HP / Focus | **Partial** | Sticky stats + toasts parked under topbar (not over HUD / sticky HP row) |
| Safe-area insets | **Done** | `#app`, mobile HUD, minimap / toast offsets use `env(safe-area-inset-*)` |
| Joystick scroll bleed | **Done** | `touch-action: none` + non-passive `touchmove` preventDefault on pads |
| FPV large-type / scale | **Partial** | Auto fewer cols / larger glyphs on narrow or `body.large-type`; no settings toggle UI yet |
| One-handed portrait + landscape polish | **Open** | Needs device playtest |
| No critical hover/keyboard-only paths | **Open** | Dock + chords cover common acts; wish / some modals still desktop-leaning |
| Minimap / compass at small sizes | **Partial** | Existing compact minimap; more tuning TBD |
| Stable 30fps+ / battery / RAF | **Open** | Not measured this slice |
| WS reconnect + background tab docs | **Open** | Document in a later pass |
| Ghost input / touch leave | **Partial** | Scroll bleed addressed; pointer cancel / leave cleanup TBD |
| Deep link / QR join | **Open** | Out of critical path for installability |
| App Store / Play wrappers | **Out of scope (v1)** | Track under packaging epics |

## PWA

- **Manifest:** `/static/manifest.webmanifest` (also served at `/manifest.webmanifest`)
- **Icons:** 192 / 512 / apple-touch 180 / favicon 32
- **Display:** `standalone`, theme/background `#05080c`
- **Service worker:** root `/sw.js` — caches HTML shell + core static CSS/JS/icons. Does **not** offline the MMORPG world (WebSocket + `/api/*` bypass the cache).

Install: Chrome/Edge (Android) or “Add to Home Screen” on iOS Safari after visiting over HTTPS (or localhost).

### Large type

On viewports ≤720px the client opts into larger FPV glyphs (fewer ASCII columns). Override:

| `localStorage.snowcrash_large_type` | Effect |
|-------------------------------------|--------|
| `"1"` | Force large type |
| `"0"` | Force default density |
| unset | Auto on narrow viewports |

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

1. Jack in with `?name=MobileTest`
2. Virtual stick moves; page does not rubber-band scroll behind the pad
3. FIRE / GET / ICE chords respond
4. Open Jrnl + ICE from dock — one scroll surface, readable rows
5. HP / Focus sticky row remains readable when toasts fire
6. Notch / home-indicator devices: chrome clear of unsafe edges
7. (Optional) Install PWA; cold start shows shell; online play still works

## Related

- #31 Mobile-friendly HUD (shipped stub)
- #68 FPV contrast / readability (`docs/fpv.md`)
- #67 Steam / desktop packaging (separate)
- Campaign log: #42

## Remaining for full #75 acceptance

See open checkboxes on **#75**. Highest leverage next slices:

1. Device matrix playtest + chord layout for true one-handed portrait
2. Explicit large-type toggle in UI + minimap/compass density pass
3. Touch leave / pointercancel ghost-input cleanup
4. Perf pass (RAF idle, battery) + document WS background behavior
5. Optional QR / deep-link join helper
