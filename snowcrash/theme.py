"""Catppuccin terminal / HUD themes for Snowcrash (#90).

Palette values from https://github.com/catppuccin/catppuccin (MIT).
Mocha is the default; Macchiato, Frappé, and Latte are optional variants.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

# Official Catppuccin hex (palette.json v1.8.0) — keep in sync with docs/theme-catppuccin.md
PALETTES: Dict[str, Dict[str, str]] = {
    "mocha": {
        "rosewater": "#f5e0dc",
        "flamingo": "#f2cdcd",
        "pink": "#f5c2e7",
        "mauve": "#cba6f7",
        "red": "#f38ba8",
        "maroon": "#eba0ac",
        "peach": "#fab387",
        "yellow": "#f9e2af",
        "green": "#a6e3a1",
        "teal": "#94e2d5",
        "sky": "#89dceb",
        "sapphire": "#74c7ec",
        "blue": "#89b4fa",
        "lavender": "#b4befe",
        "text": "#cdd6f4",
        "subtext1": "#bac2de",
        "subtext0": "#a6adc8",
        "overlay2": "#9399b2",
        "overlay1": "#7f849c",
        "overlay0": "#6c7086",
        "surface2": "#585b70",
        "surface1": "#45475a",
        "surface0": "#313244",
        "base": "#1e1e2e",
        "mantle": "#181825",
        "crust": "#11111b",
    },
    "macchiato": {
        "rosewater": "#f4dbd6",
        "flamingo": "#f0c6c6",
        "pink": "#f5bde6",
        "mauve": "#c6a0f6",
        "red": "#ed8796",
        "maroon": "#ee99a0",
        "peach": "#f5a97f",
        "yellow": "#eed49f",
        "green": "#a6da95",
        "teal": "#8bd5ca",
        "sky": "#91d7e3",
        "sapphire": "#7dc4e4",
        "blue": "#8aadf4",
        "lavender": "#b7bdf8",
        "text": "#cad3f5",
        "subtext1": "#b8c0e0",
        "subtext0": "#a5adcb",
        "overlay2": "#939ab7",
        "overlay1": "#8087a2",
        "overlay0": "#6e738d",
        "surface2": "#5b6078",
        "surface1": "#494d64",
        "surface0": "#363a4f",
        "base": "#24273a",
        "mantle": "#1e2030",
        "crust": "#181926",
    },
    "frappe": {
        "rosewater": "#f2d5cf",
        "flamingo": "#eebebe",
        "pink": "#f4b8e4",
        "mauve": "#ca9ee6",
        "red": "#e78284",
        "maroon": "#ea999c",
        "peach": "#ef9f76",
        "yellow": "#e5c890",
        "green": "#a6d189",
        "teal": "#81c8be",
        "sky": "#99d1db",
        "sapphire": "#85c1dc",
        "blue": "#8caaee",
        "lavender": "#babbf1",
        "text": "#c6d0f5",
        "subtext1": "#b5bfe2",
        "subtext0": "#a5adce",
        "overlay2": "#949cbb",
        "overlay1": "#838ba7",
        "overlay0": "#737994",
        "surface2": "#626880",
        "surface1": "#51576d",
        "surface0": "#414559",
        "base": "#303446",
        "mantle": "#292c3c",
        "crust": "#232634",
    },
    "latte": {
        "rosewater": "#dc8a78",
        "flamingo": "#dd7878",
        "pink": "#ea76cb",
        "mauve": "#8839ef",
        "red": "#d20f39",
        "maroon": "#e64553",
        "peach": "#fe640b",
        "yellow": "#df8e1d",
        "green": "#40a02b",
        "teal": "#179299",
        "sky": "#04a5e5",
        "sapphire": "#209fb5",
        "blue": "#1e66f5",
        "lavender": "#7287fd",
        "text": "#4c4f69",
        "subtext1": "#5c5f77",
        "subtext0": "#6c6f85",
        "overlay2": "#7c7f93",
        "overlay1": "#8c8fa1",
        "overlay0": "#9ca0b0",
        "surface2": "#acb0be",
        "surface1": "#bcc0cc",
        "surface0": "#ccd0da",
        "base": "#eff1f5",
        "mantle": "#e6e9ef",
        "crust": "#dce0e8",
    },
}

# Aliases accepted by SNOWCRASH_THEME / ?theme=
THEME_ALIASES = {
    "mocha": "mocha",
    "catppuccin": "mocha",
    "catppuccin-mocha": "mocha",
    "macchiato": "macchiato",
    "catppuccin-macchiato": "macchiato",
    "frappe": "frappe",
    "frappé": "frappe",
    "catppuccin-frappe": "frappe",
    "latte": "latte",
    "catppuccin-latte": "latte",
}

DEFAULT_THEME = "mocha"

# Game role → Catppuccin color name (documented in docs/theme-catppuccin.md)
ROLE_COLORS = {
    "player": "teal",
    "enemy_infected": "green",
    "enemy_thug": "peach",
    "enemy_drone": "mauve",
    "npc": "lavender",
    "wall_near": "sky",
    "wall_far": "overlay1",
    "street": "subtext0",
    "water": "sapphire",
    "door": "yellow",
    "item": "yellow",
    "hud": "text",
    "warning": "yellow",
    "success": "green",
    "danger": "red",
    "ceiling": "blue",
    "floor": "subtext1",
    "crosshair": "red",
}

# Curses pair ids used by tui/fpv.py + tui/app.py (stable ABI)
PAIR_PLAYER = 1
PAIR_INFECTED = 2
PAIR_THUG_DOOR_ITEM = 3
PAIR_DRONE = 4
PAIR_NPC_CEILING = 5
PAIR_FLOOR = 6
PAIR_FAR = 7
PAIR_DANGER = 8
PAIR_REVERSE = 9


def normalize_theme(name: Optional[str]) -> str:
    if not name:
        return DEFAULT_THEME
    key = name.strip().lower().replace("_", "-")
    return THEME_ALIASES.get(key, DEFAULT_THEME)


def resolve_theme_name(explicit: Optional[str] = None) -> str:
    """Resolve theme: explicit arg → SNOWCRASH_THEME env → Mocha default."""
    if explicit:
        return normalize_theme(explicit)
    return normalize_theme(os.environ.get("SNOWCRASH_THEME", ""))


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def palette(name: Optional[str] = None) -> Dict[str, str]:
    return dict(PALETTES[resolve_theme_name(name)])


def role_hex(role: str, theme: Optional[str] = None) -> str:
    pal = palette(theme)
    color_name = ROLE_COLORS.get(role, "text")
    return pal.get(color_name, pal["text"])


def css_variables(theme: Optional[str] = None) -> Dict[str, str]:
    """Map Catppuccin → Snowcrash CSS custom properties (HUD / chrome)."""
    pal = palette(theme)
    # Prefer crust for FPV stage darkness (contrast) while chrome uses base/mantle.
    return {
        "--bg": pal["crust"],
        "--panel": pal["mantle"],
        "--panel-2": pal["base"],
        "--fg": pal["text"],
        "--dim": pal["overlay0"],
        "--accent": pal["sky"],
        "--neon": pal["pink"],
        "--ok": pal["green"],
        "--warn": pal["yellow"],
        "--danger": pal["red"],
        "--water": pal["sapphire"],
        "--wall": pal["teal"],
        "--surface": pal["surface0"],
        "--border": pal["surface1"],
        "--ctp-base": pal["base"],
        "--ctp-mantle": pal["mantle"],
        "--ctp-crust": pal["crust"],
        "--ctp-text": pal["text"],
        "--ctp-teal": pal["teal"],
        "--ctp-sky": pal["sky"],
        "--ctp-mauve": pal["mauve"],
        "--ctp-peach": pal["peach"],
        "--ctp-yellow": pal["yellow"],
        "--ctp-green": pal["green"],
        "--ctp-red": pal["red"],
        "--ctp-blue": pal["blue"],
        "--ctp-sapphire": pal["sapphire"],
        "--ctp-lavender": pal["lavender"],
        "--ctp-pink": pal["pink"],
        "--ctp-overlay0": pal["overlay0"],
        "--ctp-surface0": pal["surface0"],
        "--ctp-surface1": pal["surface1"],
    }


def _rgb_to_xterm256(r: int, g: int, b: int) -> int:
    """Nearest xterm-256 color index for (r,g,b) 0–255."""
    # Greyscale ramp 232–255
    gray = (r + g + b) // 3
    if abs(r - g) < 8 and abs(g - b) < 8 and abs(r - b) < 8:
        if gray < 8:
            return 16
        if gray > 238:
            return 231
        return 232 + max(0, min(23, (gray - 8) // 10))
    # 6×6×6 color cube (16–231)
    def _q(v: int) -> int:
        if v < 48:
            return 0
        if v < 115:
            return 1
        return (v - 35) // 40

    return 16 + 36 * _q(r) + 6 * _q(g) + _q(b)


def _curses_rgb_1000(r: int, g: int, b: int) -> Tuple[int, int, int]:
    return int(r * 1000 / 255), int(g * 1000 / 255), int(b * 1000 / 255)


def init_curses_colors(curses_mod, no_color: bool = False, theme: Optional[str] = None) -> bool:
    """Initialize Catppuccin color pairs. Returns True if colors are usable.

    Prefer truecolor/redefinable palette when available; else 256-color indices;
    else classic 16-color ANSI pairs. ``--no-color`` / SNOWCRASH_NO_COLOR unchanged.
    """
    if no_color or os.environ.get("SNOWCRASH_NO_COLOR", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return False
    if not curses_mod.has_colors():
        return False
    try:
        curses_mod.start_color()
    except curses_mod.error:
        return False

    try:
        curses_mod.use_default_colors()
        default_bg = -1
    except curses_mod.error:
        default_bg = curses_mod.COLOR_BLACK

    theme_name = resolve_theme_name(theme)
    pal = palette(theme_name)

    def _pair(n: int, fg: int, bg: int = default_bg) -> None:
        try:
            curses_mod.init_pair(n, fg, bg)
        except curses_mod.error:
            pass

    # --- Truecolor / redefinable ---
    ncolors = getattr(curses_mod, "COLORS", 8) or 8
    can_change = bool(getattr(curses_mod, "can_change_color", lambda: False)())

    # Reserve slots 10–18 for Catppuccin redefined colors when possible.
    role_slots: List[Tuple[int, str]] = [
        (10, ROLE_COLORS["player"]),  # teal → pair 1
        (11, ROLE_COLORS["enemy_infected"]),
        (12, ROLE_COLORS["door"]),
        (13, ROLE_COLORS["enemy_drone"]),
        (14, ROLE_COLORS["npc"]),
        (15, ROLE_COLORS["floor"]),
        (16, ROLE_COLORS["wall_far"]),
        (17, ROLE_COLORS["danger"]),
        (18, "surface0"),
    ]

    if can_change and ncolors > 18:
        for slot, cname in role_slots:
            r, g, b = hex_to_rgb(pal[cname])
            rr, gg, bb = _curses_rgb_1000(r, g, b)
            try:
                curses_mod.init_color(slot, rr, gg, bb)
            except curses_mod.error:
                can_change = False
                break

    if can_change and ncolors > 18:
        _pair(PAIR_PLAYER, 10)
        _pair(PAIR_INFECTED, 11)
        _pair(PAIR_THUG_DOOR_ITEM, 12)
        _pair(PAIR_DRONE, 13)
        _pair(PAIR_NPC_CEILING, 14)
        _pair(PAIR_FLOOR, 15)
        _pair(PAIR_FAR, 16)
        _pair(PAIR_DANGER, 17)
        try:
            _pair(PAIR_REVERSE, 15, 18)  # text on surface0
        except Exception:
            _pair(PAIR_REVERSE, curses_mod.COLOR_BLACK, curses_mod.COLOR_WHITE)
        return True

    # --- 256-color ---
    if ncolors >= 256:
        def _fg(cname: str) -> int:
            return _rgb_to_xterm256(*hex_to_rgb(pal[cname]))

        _pair(PAIR_PLAYER, _fg(ROLE_COLORS["player"]))
        _pair(PAIR_INFECTED, _fg(ROLE_COLORS["enemy_infected"]))
        _pair(PAIR_THUG_DOOR_ITEM, _fg(ROLE_COLORS["door"]))
        _pair(PAIR_DRONE, _fg(ROLE_COLORS["enemy_drone"]))
        _pair(PAIR_NPC_CEILING, _fg(ROLE_COLORS["npc"]))
        _pair(PAIR_FLOOR, _fg(ROLE_COLORS["floor"]))
        _pair(PAIR_FAR, _fg(ROLE_COLORS["wall_far"]))
        _pair(PAIR_DANGER, _fg(ROLE_COLORS["danger"]))
        _pair(PAIR_REVERSE, _fg("text"), _rgb_to_xterm256(*hex_to_rgb(pal["surface0"])))
        return True

    # --- 16-color ANSI fallback (Catppuccin-friendly mapping) ---
    _pair(PAIR_PLAYER, curses_mod.COLOR_CYAN)
    _pair(PAIR_INFECTED, curses_mod.COLOR_GREEN)
    _pair(PAIR_THUG_DOOR_ITEM, curses_mod.COLOR_YELLOW)
    _pair(PAIR_DRONE, curses_mod.COLOR_MAGENTA)
    _pair(PAIR_NPC_CEILING, curses_mod.COLOR_BLUE)
    _pair(PAIR_FLOOR, curses_mod.COLOR_WHITE)
    _pair(PAIR_FAR, curses_mod.COLOR_WHITE)
    _pair(PAIR_DANGER, curses_mod.COLOR_RED)
    _pair(PAIR_REVERSE, curses_mod.COLOR_BLACK, curses_mod.COLOR_WHITE)
    return True
