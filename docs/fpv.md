# FPV ASCII view

Live **video→ASCII** first-person view for the web client (`#fpv-canvas`).

## Pipeline

1. `FpvEngine` (`snowcrash/static/game.js`) raycasts a neon scene onto an offscreen canvas.
2. Shared `AsciiRenderer` / `VideoAsciiCanvas` (`snowcrash/static/ascii-video.js`) samples luminance → dense charset glyphs with per-glyph RGB.

## Contrast / readability (#68 → pass 2 #88 → #95)

Playtest found the continuous FPV nearly unreadable (muddy midtones). Pass 1 (#69) lifted the palette; pass 2 (#88) bumped sampler knobs for midtone glyphs.

After Catppuccin (#90), many surfaces mapped to similar `themePal().teal` / sky hues. Combined with the pass-2 stretch (`brightness`/`contrast` ≈ 1.58/1.62), the sampler collapsed luminance into one dense charset index (solid teal `a` field — #95). Fix: **darker Catppuccin-scaled walls**, distinct floor/ceiling luminance bands, brighter entity billboards, and eased sampler knobs — theme stays Catppuccin.

| Knob | #95 (approx) | Role |
|------|--------------|------|
| `brightness` / `contrast` | `1.34` / `1.4` | Lift without crushing midtones into one glyph |
| `gamma` (&lt; 1) | `0.86` | Mild dark midtone lift |
| `saturate` (&gt; 1) | `1.48` | Neon chroma punch without washing luminance |
| Scene walls | Catppuccin teal/sapphire/yellow × ~0.58–0.72 scale | Hue kept; luminance spread restored |
| Floor / ceiling | Theme-mixed crust/mantle/teal/sky bands | Distinct from walls for sky/street glyphs |
| Entities | Billboard glow ≈ 1.18–1.35 | Pop above wall midtones |
| Scanlines | Very light (`~0.035` alpha, every 4th row) | CRT flavor without mud |
| Vignette | Softer edge-only (`~0.16` at corners) | Center stays bright/neon |

Adjust FPV-specific opts in `FpvEngine.ensureAscii()`; sampler defaults live on `AsciiRenderer`. Smoke: `node scripts/fpv_ascii_smoke.js` (glyph diversity over representative scene RGBs).

## Related hotkeys

| Key | Action |
|-----|--------|
| `j` | Jack in at map glyph `J` / jack out in cyberspace (else absolute south) |
| `Shift+J` | Open **quest journal** (Shift avoids clash with jack-in) |
| `z` / `x` / `c` | ICE **Stun** / **Reveal** / **Scramble** |
| `p` | Open ICE dock (buttons labeled Stun / Reveal / Scramble) |

Map tile `J` remains the jackpoint landmark; it is not a journal hotkey.
