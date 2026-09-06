"""Catppuccin theme helpers (#90)."""

from __future__ import annotations

import snowcrash.theme as theme


def test_normalize_and_default():
    assert theme.resolve_theme_name(None) == "mocha"
    assert theme.normalize_theme("catppuccin-mocha") == "mocha"
    assert theme.normalize_theme("Frappé") == "frappe"
    assert theme.normalize_theme("LATTE") == "latte"
    assert theme.normalize_theme("nope") == "mocha"


def test_palette_hex_and_roles():
    mocha = theme.palette("mocha")
    assert mocha["base"] == "#1e1e2e"
    assert mocha["teal"] == "#94e2d5"
    assert theme.role_hex("player", "mocha") == mocha["teal"]
    assert theme.role_hex("danger", "mocha") == mocha["red"]
    assert theme.role_hex("water", "latte").startswith("#")


def test_css_variables_semantic():
    css = theme.css_variables("mocha")
    assert css["--accent"] == "#89dceb"
    assert css["--bg"] == "#11111b"
    assert css["--ok"] == "#a6e3a1"
    latte = theme.css_variables("latte")
    assert latte["--fg"] == "#4c4f69"


def test_env_theme(monkeypatch):
    monkeypatch.setenv("SNOWCRASH_THEME", "macchiato")
    assert theme.resolve_theme_name() == "macchiato"
    monkeypatch.setenv("SNOWCRASH_THEME", "catppuccin-frappe")
    assert theme.resolve_theme_name() == "frappe"


def test_xterm256_mapping_stable():
    idx = theme._rgb_to_xterm256(148, 226, 213)  # teal
    assert 16 <= idx <= 255


def test_init_curses_respects_no_color(monkeypatch):
    class FakeCurses:
        error = Exception
        COLORS = 256
        COLOR_CYAN = 6
        COLOR_GREEN = 2
        COLOR_YELLOW = 3
        COLOR_MAGENTA = 5
        COLOR_BLUE = 4
        COLOR_WHITE = 7
        COLOR_RED = 1
        COLOR_BLACK = 0

        @staticmethod
        def has_colors():
            return True

        @staticmethod
        def start_color():
            pass

        @staticmethod
        def use_default_colors():
            pass

        @staticmethod
        def can_change_color():
            return False

        @staticmethod
        def init_pair(n, fg, bg):
            pass

        @staticmethod
        def init_color(n, r, g, b):
            pass

    monkeypatch.setenv("SNOWCRASH_NO_COLOR", "1")
    assert theme.init_curses_colors(FakeCurses, no_color=False) is False
    monkeypatch.delenv("SNOWCRASH_NO_COLOR", raising=False)
    assert theme.init_curses_colors(FakeCurses, no_color=True) is False
    assert theme.init_curses_colors(FakeCurses, no_color=False, theme="mocha") is True
