# FPV ASCII view

Live **video→ASCII** first-person view for the web client (`#fpv-canvas`).

## Pipeline

1. `FpvEngine` (`snowcrash/static/game.js`) raycasts a neon scene onto an offscreen canvas.
2. Shared `AsciiRenderer` / `VideoAsciiCanvas` (`snowcrash/static/ascii-video.js`) samples luminance → dense charset glyphs with per-glyph RGB.

## Contrast / readability (#68)

Playtest found the continuous FPV nearly unreadable (muddy midtones). Current tuning:

| Knob | Role |
|------|------|
| `brightness` / `contrast` | Lift and stretch channel levels before glyph pick |
| `gamma` (&lt; 1) | Pull dark midtones into denser glyphs |
| `saturate` (&gt; 1) | Neon chroma punch without washing luminance |
| Scene walls / floor / ceiling | Brighter cyan/amber base colors |
| Scanlines | Very light (`~0.045` alpha, every 4th row) |
| Vignette | Soft edge-only (`~0.22` at corners) |

Adjust FPV-specific opts in `FpvEngine.ensureAscii()`; sampler defaults live on `AsciiRenderer`.

## Related hotkeys

| Key | Action |
|-----|--------|
| `j` | Jack in at map glyph `J` / jack out in cyberspace (else absolute south) |
| `Shift+J` | Open **quest journal** (Shift avoids clash with jack-in) |
| `z` / `x` / `c` | ICE **Stun** / **Reveal** / **Scramble** |
| `p` | Open ICE dock (buttons labeled Stun / Reveal / Scramble) |

Map tile `J` remains the jackpoint landmark; it is not a journal hotkey.
