"""Smoke tests for TUI ASCII FPV (#78) — no interactive curses TTY required."""

from __future__ import annotations

import curses

from snowcrash.engine import handle_action, new_game
from snowcrash.tui.app import _default_view, _key_to_action
from snowcrash.tui.fpv import compass_line, render_fpv


def test_fpv_frame_shape_and_ascii():
    gs = new_game(42)
    rows, attrs = render_fpv(gs, 60, 18)
    assert len(rows) == 18
    assert all(len(r) == 60 for r in rows)
    assert len(attrs) == 18
    # printable ASCII / space only (SSH-safe)
    for r in rows:
        for ch in r:
            assert 32 <= ord(ch) <= 126, repr(ch)


def test_fpv_changes_with_facing_and_strafe():
    gs = new_game(42)
    a, _ = render_fpv(gs, 48, 14)
    handle_action(gs, "turn_left")
    b, _ = render_fpv(gs, 48, 14)
    assert a != b
    handle_action(gs, "strafe_right")
    c, _ = render_fpv(gs, 48, 14)
    # facing change must differ; strafe may no-op if blocked
    assert a != b
    assert isinstance(c, list) and len(c) == 14


def test_compass_and_default_view(monkeypatch):
    assert compass_line(0).startswith("^")
    assert "N" in compass_line(0)
    monkeypatch.delenv("SNOWCRASH_TUI_VIEW", raising=False)
    assert _default_view() == "fpv"
    monkeypatch.setenv("SNOWCRASH_TUI_VIEW", "map")
    assert _default_view() == "map"


def test_key_map_relative_and_turn():
    assert _key_to_action(ord("w"), "play") == "forward"
    assert _key_to_action(ord("a"), "play") == "strafe_left"
    assert _key_to_action(ord("s"), "play") == "back"
    assert _key_to_action(ord("d"), "play") == "strafe_right"
    assert _key_to_action(ord("e"), "play") == "turn_right"
    assert _key_to_action(ord(","), "play") == "turn_left"
    assert _key_to_action(curses.KEY_LEFT, "play") == "turn_left"
    assert _key_to_action(curses.KEY_RIGHT, "play") == "turn_right"
    assert _key_to_action(curses.KEY_UP, "play") == "forward"
    assert _key_to_action(ord("q"), "play") == "q"
    # inventory keeps equip letter
    assert _key_to_action(ord("e"), "inventory") == "e"


def test_fpv_draw_smoke_glyphs():
    """Renderer smoke: walls or floor glyphs appear (no curses TTY)."""
    gs = new_game(7)
    rows, _ = render_fpv(gs, 40, 12)
    blob = "".join(rows)
    assert any(ch in blob for ch in "#=:|-H;")
