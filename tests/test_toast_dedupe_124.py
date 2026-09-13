"""#124 — flash/journal toast dedupe (web client + server event coalesce)."""

from __future__ import annotations

import time
from pathlib import Path

from snowcrash.mmorpg import GameWorld

ROOT = Path(__file__).resolve().parents[1]
GAME_JS = ROOT / "snowcrash" / "static" / "game.js"


def test_game_js_has_toast_dedupe_helpers():
    src = GAME_JS.read_text(encoding="utf-8")
    assert "TOAST_DEDUPE_MS" in src
    assert "lastToastText" in src
    assert "seenEventKeys" in src
    assert "function eventToastKey" in src
    # Must not re-toast the whole top slice on every sig change
    assert "events.slice(0, 3)" not in src
    assert "fresh.slice(-3)" in src


def test_push_event_coalesces_identical_text_within_window():
    w = GameWorld(seed=124)
    before = len(w.event_ticker)
    line = "Journal: Hello Courier mesh handshake — test #124"
    w._push_event("journal", line)
    w._push_event("journal", line)
    assert len(w.event_ticker) == before + 1
    # Distinct content still lands
    w._push_event("broadcast", "Flotilla propaganda washes the rim. (#124)")
    assert len(w.event_ticker) == before + 2
    assert "Flotilla" in w.event_ticker[-1]["text"]


def test_push_event_allows_same_text_after_window():
    w = GameWorld(seed=124)
    before = len(w.event_ticker)
    line = "Flotilla propaganda washes the rim. (#124 window)"
    w._push_event("broadcast", line)
    # Force last event outside the coalesce window
    w.event_ticker[-1]["t"] = time.time() - 5.0
    w._push_event("broadcast", line)
    assert len(w.event_ticker) == before + 2
