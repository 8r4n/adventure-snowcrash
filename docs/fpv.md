# FPV ASCII view

Live **video→ASCII** first-person view for the web client (`#fpv-canvas`).

## Pipeline

1. `FpvEngine` (`snowcrash/static/game.js`) raycasts a neon scene onto an offscreen canvas.
2. Shared `AsciiRenderer` / `VideoAsciiCanvas` (`snowcrash/static/ascii-video.js`) samples luminance → dense charset glyphs with per-glyph RGB.

## Contrast / readability (#68 → pass 2 #88)

Playtest found the continuous FPV nearly unreadable (muddy midtones). Pass 1 (#69) lifted the palette; pass 2 (#88) is a **light** second bump — keep the neon look, improve midtone glyphs.

| Knob | Pass 2 (approx) | Role |
|------|-----------------|------|
| `brightness` / `contrast` | `1.58` / `1.62` | Lift and stretch channel levels before glyph pick |
| `gamma` (&lt; 1) | `0.74` | Pull dark midtones into denser glyphs |
| `saturate` (&gt; 1) | `1.62` | Neon chroma punch without washing luminance |
| Scene walls / floor / ceiling | Slightly brighter cyan street gradients | Base readability before ASCII sample |
| Scanlines | Very light (`~0.035` alpha, every 4th row) | CRT flavor without mud |
| Vignette | Softer edge-only (`~0.16` at corners) | Center stays bright/neon |

Adjust FPV-specific opts in `FpvEngine.ensureAscii()`; sampler defaults live on `AsciiRenderer`.

## Related hotkeys

| Key | Action |
|-----|--------|
| `j` | Jack in at map glyph `J` / jack out in cyberspace (else absolute south) |
| `Shift+J` | Open **quest journal** (Shift avoids clash with jack-in) |
| `z` / `x` / `c` | ICE **Stun** / **Reveal** / **Scramble** |
| `p` | Open ICE dock (buttons labeled Stun / Reveal / Scramble) |

Map tile `J` remains the jackpoint landmark; it is not a journal hotkey.
