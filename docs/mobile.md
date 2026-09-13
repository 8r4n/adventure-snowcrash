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

### Slice 2 (PR #105)

| Area | Status | Notes |
|------|--------|-------|
| Explicit in-UI large-type toggle | **Done** | Toolbar **Aa** cycles Auto → Large (`Aa+`) → Compact (`Aa−`); persists `localStorage.snowcrash_large_type` |
| One-handed portrait / landscape pads | **Improved** | Viewport padding reserves space for vjoy + chord pad; higher HUD z-index; tighter `#side` max-height so docks don’t bury FPV |
| Ghost input / pointercancel | **Improved** | Hold-to-move on vjoy with `pointerup` / `pointercancel` / `lostpointercapture` / blur / `visibilitychange` / `pagehide` cleanup; WASD `moveKeysHeld` cleared the same way; ghost click blocked on pads |
| Minimap / compass at small sizes | **Improved** | ≤420px denser GPS + ellipsis compass pills; portrait/landscape offsets clear of pads |
| Copy join link | **Done** | Name-gate **Copy join link** copies URL with `?name=` (clipboard + fallback) |

### Slice 3 (this branch)

| Area | Status | Notes |
|------|--------|-------|
| RAF / battery throttle | **Done (code)** | Hidden tab cancels FPV + weather RAF; coarse/narrow idle ~9fps (desktop ~12.5); `prefers-reduced-motion` ~5fps; phone FPV scene 320×180 vs 480×270 |
| QR join helper | **Done** | Name-gate **Show QR** (vendored `qrcode-generator` 1.4.4 → `/static/qrcode.min.js`) |
| WS reconnect + background tab | **Documented + light code** | Ping paused while hidden; reconnect on `onclose` (~1.2s); foreground resumes ping or nudges connect |
| Jaunte globe hop (no `prompt`) | **Done** | Inline region input + chips; last known `window.prompt` critical path removed |
| Device matrix | **Stub + DevTools notes** | Real iOS/Android playtest still open |
| Toast / modal safe-area | **Improved** | Tighter toast stack on ≤720px; year-modals use `100dvh` + insets; name-gate card scrolls under QR |

## PWA

- **Manifest:** `/static/manifest.webmanifest` (also served at `/manifest.webmanifest`)
- **Icons:** 192 / 512 / apple-touch 180 / favicon 32
- **Display:** `standalone`, theme/background `#05080c`
- **Service worker:** root `/sw.js` — caches HTML shell + core static CSS/JS/icons (including `qrcode.min.js`). Does **not** offline the MMORPG world (WebSocket + `/api/*` bypass the cache). Cache name `snowcrash-shell-v3` after slice 3.

Install: Chrome/Edge (Android) or “Add to Home Screen” on iOS Safari after visiting over HTTPS (or localhost).

### Large type

Toolbar **Aa** control (and `localStorage`):

| `localStorage.snowcrash_large_type` | Button | Effect |
|-------------------------------------|--------|--------|
| unset | `Aa` | **Auto** — large type on viewports ≤720px |
| `"1"` | `Aa+` | Force large type (fewer ASCII columns / larger glyphs) |
| `"0"` | `Aa−` | Force default density |

Changing the toggle calls `FpvBridge.kick()` so the FPV canvas reflows immediately.

## WebSocket reconnect + background tabs

The client (`Net` in `snowcrash/static/game.js`) is a single `/ws` socket.

| Event | Behavior |
|-------|----------|
| First jack-in | `join` with display name / optional StreetNet nick / resume `id` |
| Keepalive | `ping` every **2.5s** while the tab is **visible** and the socket is open |
| Tab hidden / `pagehide` | Ping interval **stops** (saves radio + battery). Socket is left open if the OS allows it. FPV + weather **RAF loops cancel**. Touch hold-to-move clears (no idle drift). |
| Tab visible / `pageshow` | If socket still `OPEN`: ping restarts + immediate ping. If closed and a name is set: **nudge reconnect** (200ms). FPV / weather RAF resume. |
| Socket `onclose` while we still want the session | HUD shows `reconnecting…`; `connect()` retries after **~1.2s** (fixed, not exponential). |
| Explicit leave / `Net.disconnect()` | `wantOpen = false` — no auto-reconnect. |

**OS caveats (not fully playtested on device):**

- **iOS Safari** often freezes or drops WebSockets after ~30s in the background. Returning should reconnect via `onclose` or the visibility nudge. Standalone PWA may keep the socket slightly longer.
- **Android Chrome** is usually more lenient; lock-screen still eventually parks the tab.
- Server-side: a dropped socket is a normal leave; resume uses the same courier `id` on the next `join`.
- Live play **never** works fully offline — the SW only shells the HTML/CSS/JS.

## Performance notes (slice 3)

Idle FPV is **not** a locked 30fps world sim — the expensive work is the raycast → ASCII pass. Snapshot-driven movement already updates on WS messages via `render()` (immediate, not throttled).

| Viewport | Idle scanline RAF | Offscreen scene |
|----------|-------------------|-----------------|
| Desktop fine pointer | ~80ms (~12.5fps) | 480×270 |
| Coarse pointer or ≤720px | ~110ms (~9fps) | 320×180 |
| `prefers-reduced-motion` | ~200ms (~5fps) | as above |
| `document.hidden` | **RAF stopped** | last frame kept |

Weather overlay uses the same visibility + interval idea (~8fps on phones).

**Still open:** measured 30fps+ on a mid-range phone during combat / neon rain. This slice removes the obvious battery leak (RAF + ping in background) and cuts per-frame ray columns ~33% on phones.

## QR / join link

Name gate:

1. **Copy join link** — clipboard (or `execCommand` fallback) of the current origin with `?name=`
2. **Show QR** — same URL as a scannable SVG. Updates when the courier name field changes.

Deep-link format: `https://<host>/?name=CourierName`. Optional StreetNet nick is **not** encoded (the joiner can type it).

## Test matrix

Fill in on device as playtests land. Target: courier can move, fight/ICE, open journal, finish a short objective (Signal Key or Neon Dash) without a keyboard.

| Device / browser | OS | Portrait move | Landscape | Journal/ICE | Toast vs HP | PWA | Notes |
|------------------|----|---------------|-----------|-------------|-------------|-----|-------|
| iPhone Safari | iOS 17+ | *untested* | *untested* | *untested* | *untested* | A2HS | Expect WS drop after ~30s background; QR + copy should work over HTTPS |
| iPhone Chrome | iOS | *untested* | *untested* | *untested* | *untested* | via Safari | Chrome iOS is WKWebView |
| Pixel / Android Chrome | Android 14+ | *untested* | *untested* | *untested* | *untested* | Install prompt | Coarse-pointer HUD + 320×180 FPV should engage |
| Tablet (coarse pointer) | — | *untested* | *untested* | *untested* | *untested* | — | HUD via `(pointer: coarse)` even if width >720 |
| Desktop narrow (<720) | DevTools | **smoke** | **smoke** | **smoke** | **smoke** | n/a | Device mode: pads reserved; QR toggles; jaunte hop has chips (no `prompt`) |

### Smoke checklist

1. Jack in with `?name=MobileTest` (or **Copy join link** / **Show QR** from the gate)
2. Virtual stick moves (hold repeats); page does not rubber-band scroll behind the pad
3. Lift finger / rotate / background the tab — no idle drift; HUD eventually `reconnecting…` then recovers
4. FIRE / GET / ICE chords respond
5. Toolbar **Aa** cycles Auto / Large / Compact and FPV density updates
6. Open Jrnl + ICE from dock — one scroll surface; FPV + pads still reachable in portrait
7. HP / Focus sticky row remains readable when toasts fire
8. Notch / home-indicator devices: chrome clear of unsafe edges
9. Uplink Hop **Globe** — type or tap a region chip (no native `prompt`)
10. (Optional) Install PWA; cold start shows shell; online play still works

## Hover / keyboard audit (partial)

| Path | Touch status |
|------|----------------|
| Move / turn / GET / FIRE / ICE / INV / plane | Chord pad + vjoy |
| Journal / ICE / StreetNet / dock | Buttons + accordion |
| Wish | Toolbar **Wish** focuses chat with `/wish ` (soft keyboard) |
| Jaunte globe hop | Inline input + chips (was `window.prompt`) |
| Chat / slash commands | Soft keyboard — acceptable |
| Remaining | Some year-modals / globe map pins are still small; crew invite text entry; no hover-only menus left in the critical jack-in → move → fight path |

## Related

- #31 Mobile-friendly HUD (shipped stub)
- #68 FPV contrast / readability (`docs/fpv.md`)
- #67 Steam / desktop packaging (separate)
- #109 Godot thin client — store-native Android/iOS later; does not block this PWA path ([godot-client.md](godot-client.md))
- Campaign log: #42

## Remaining for full #75 acceptance

See open checkboxes on **#75**. Highest leverage next slices:

1. **Real-device matrix** (iPhone Safari + Android Chrome) — portrait one-handed + landscape combat
2. Measured 30fps+ / battery on a mid-range phone during neon rain / ICE
3. Finish hover/keyboard audit for leftover year-modals / globe pin hit targets
4. Further one-handed polish from that device feedback
