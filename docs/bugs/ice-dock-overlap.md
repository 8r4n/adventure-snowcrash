# ICE dock sidebar overlap (#114)

## Symptom

Opening the **ICE** year dock painted probe rows (Stun / Reveal / Scramble) over sibling accordion headers in the right sidebar (`GLOBE`, `SLEEVES`, `JAUNT`, …), making the panel illegible.

Evidence (from #111 playtest capture):

- [`ice-dock-sidebar-overlap-2026-09.png`](ice-dock-sidebar-overlap-2026-09.png)
- [`ice-dock-open-tour-2026-09.png`](ice-dock-open-tour-2026-09.png)

Duplicate report: #113 (closed as duplicate of #114).

## Root cause

`#side` is a column flex container with a capped height. Playtest polish (#88) set:

```css
#app.declutter .year-panel[open] {
  flex: 0 1 auto;
  min-height: 0;
}
```

That allowed the open `<details>` to shrink below its content height. The ICE `.panel-body` then overflowed (default `overflow: visible` on `<details>`) and stacked on later summaries. Exclusive accordion in `game.js` was already present; the paint bug was layout, not missing toggle logic.

## Fix

- Open (and closed) `.year-panel` use `flex: 0 0 auto` so `#side` scrolls instead of crushing the open panel.
- Open panels get `overflow: hidden` so any residual body scroll stays inside the panel.
- Panel body keeps a solid `background: var(--panel)` while open.

No redesign of the dock / year-panel chrome.

## Check

1. `./scripts/run_dev.sh` → open web client, skip intro.
2. Click dock **ICE** (or `p`).
3. Confirm probe controls are readable and sibling headers sit below (or scroll under `#side`), not under ICE text.
4. Open Journal / Globe / Empathy from the dock — still exclusive accordion, no overlap.

## Verification

After fix (headless Chrome, seed 42): `elementFromPoint` on Globe / Sleeves summaries hits those summaries, not ICE probe rows. Exclusive dock toggle Journal ↔ ICE still works.

After-fix captures:

- [`ice-dock-after-fix-114.png`](ice-dock-after-fix-114.png)
- [`ice-dock-after-fix-114-side.png`](ice-dock-after-fix-114-side.png)
