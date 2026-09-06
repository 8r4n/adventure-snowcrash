# Catppuccin theme (#90)

Snowcrash uses **[Catppuccin](https://github.com/catppuccin/catppuccin)** as the terminal / HUD color system for both the curses TUI and the web ASCII chrome.

**Default flavor:** **Mocha** (dark). Optional: Macchiato, Frappé, Latte.

Palette hex values are taken from the official Catppuccin palette (`palette.json` v1.8.0) and are © Catppuccin contributors, licensed under the **MIT License**. See [catppuccin/catppuccin](https://github.com/catppuccin/catppuccin) for the full license text. Snowcrash does not claim ownership of the palette.

## Role → palette mapping

| Game role | Catppuccin color | Notes |
|-----------|------------------|-------|
| Player / near walls / accent | Teal / Sky | HUD accent uses Sky; walls lean Teal |
| Enemy: infected (`i`) | Green | Success / infected share Green |
| Enemy: thug (`t`) | Peach | Warm hostile |
| Enemy: drone (`d`) | Mauve | Magenta-family on 16-color |
| NPC (`&`) | Lavender | Soft ally / talk |
| Wall (near) | Sky / Teal | Bright FPV columns |
| Wall (far) / explored dim | Overlay 1 | Low-contrast fog |
| Street / floor | Subtext 0–1 | Readable midtones |
| Water (`~`) | Sapphire | Distinct from walls |
| Door / item / warning | Yellow | Doors, loot, alerts |
| HUD text | Text | Status / chrome |
| Success | Green | Win / OK |
| Danger / crosshair core | Red / Pink | Death banner, neon punch |
| Ceiling | Blue | FPV sky band |
| Reverse / highlight | Text on Surface 0 | Pair 9 |

Semantic CSS variables (`--bg`, `--panel`, `--fg`, `--dim`, `--accent`, `--neon`, `--ok`, `--warn`, …) map onto these roles for HUD, dock, minimap, and FPV chrome. Raw `--ctp-*` tokens expose the palette for future chrome.

## TUI (curses)

- Entry: `python -m snowcrash` (optional `--theme mocha|macchiato|frappe|latte`)
- Env: `SNOWCRASH_THEME=macchiato` (same aliases as web)
- Color pipeline (`snowcrash/theme.py` → `tui/app.py`):
  1. **Truecolor / redefinable** — `can_change_color()` + `init_color` when the terminal supports it
  2. **256-color** — nearest xterm-256 indices for Catppuccin RGB
  3. **16-color fallback** — ANSI cyan/green/yellow/magenta/blue/white/red (Catppuccin-friendly roles)
  4. **`--no-color` / `SNOWCRASH_NO_COLOR=1`** — unchanged monochrome path

FPV pair ids `1`–`9` are stable (`snowcrash/tui/fpv.py`).

## Web

- CSS: `snowcrash/static/style.css` — `:root` / `html[data-theme=…]` Catppuccin variables
- JS: `snowcrash/static/game.js` — applies theme, tints FPV walls/entities from the active palette while keeping the prior contrast boost
- Selectors (first match wins):
  1. Query `?theme=mocha` (also `catppuccin-mocha`, `macchiato`, `frappe`, `latte`, …)
  2. `localStorage.snowcrash_theme`
  3. Server default from `SNOWCRASH_THEME` (injected as `<meta name="snowcrash-theme">` + `html[data-theme]`)
  4. Mocha

Toolbar **Theme** `<select>` persists the choice to `localStorage`.

FPV canvas backgrounds use **crust** (deep) so recent contrast/readability work is not washed out by lighter Mocha *base*.

## How to select

```bash
# TUI
python -m snowcrash --theme mocha
SNOWCRASH_THEME=latte python -m snowcrash
python -m snowcrash --no-color   # ignore theme colors

# Web server default
SNOWCRASH_THEME=macchiato python -m snowcrash.web
# Browser: http://127.0.0.1:8765/?theme=frappe
# Or use the Theme dropdown in the HUD toolbar
```

## Out of scope

Arbitrary user CSS themes remain under modding (#72). Catppuccin **refines** the neon Metaverse look; it should not make FPV pastel-unreadable.
