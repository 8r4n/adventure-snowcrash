"""Neon Dash timed street race (#48)."""

from __future__ import annotations

from snowcrash.mmorpg import GameWorld
from snowcrash.systems.neon_dash import (
    NEON_DASH_CHECKPOINT_COUNT,
    NEON_DASH_COSMETIC,
    NEON_DASH_REWARD_CREDITS,
)


def _join(w: GameWorld, name: str = "Dasher"):
    a = w.join(name)
    a.last_action_ts = 0
    return a


def test_neon_dash_starts_and_ticker():
    w = GameWorld(348)
    a = _join(w)
    # Force start
    assert w.handle_year_action(a, "neon_dash_force", "dev")
    assert w.neon_dash["active"] is True
    assert len(w.neon_dash["checkpoints"]) >= 2
    assert len(w.neon_dash["checkpoints"]) <= NEON_DASH_CHECKPOINT_COUNT
    kinds = [e.get("kind") for e in w.event_ticker]
    assert "neon_dash" in kinds
    start_ev = [e for e in w.event_ticker if e.get("kind") == "neon_dash" and e.get("phase") == "start"]
    assert start_ev
    s = w.snapshot(a)
    assert "neon_dash" in s
    assert s["neon_dash"]["active"] is True
    assert s["neon_dash"]["timer_remaining"] > 0
    assert len(s["neon_dash"]["checkpoints"]) == len(w.neon_dash["checkpoints"])
    assert s["neon_dash"]["reward"]["p2w"] is False


def test_checkpoints_and_finish_reward():
    w = GameWorld(349)
    a = _join(w, "Finisher")
    credits0 = int(a.credits)
    atk0 = a.actor.attack
    def0 = a.actor.defense
    hp0 = a.actor.max_hp
    w.handle_year_action(a, "neon_dash_force", "dev")
    cps = list(w.neon_dash["checkpoints"])
    assert len(cps) >= 2
    for cp in cps:
        a.last_action_ts = 0
        w._force_set_pos(a, cp["x"], cp["y"], 0, "dash cp")
        w._neon_dash_on_move(a)
    assert a.neon_dash["finished"] is True
    assert a.credits == credits0 + NEON_DASH_REWARD_CREDITS
    assert NEON_DASH_COSMETIC["id"] in a.season["unlocked"]
    # No combat P2W
    assert a.actor.attack == atk0
    assert a.actor.defense == def0
    assert a.actor.max_hp == hp0
    s = w.snapshot(a)
    assert s["neon_dash"]["finished"] is True
    assert s["neon_dash"]["hit_count"] == len(cps)
    finish_ev = [
        e for e in w.event_ticker
        if e.get("kind") == "neon_dash" and e.get("phase") == "finish"
    ]
    assert finish_ev


def test_neon_dash_ends_on_timer():
    w = GameWorld(350)
    a = _join(w, "Late")
    w.handle_year_action(a, "neon_dash_force", "dev")
    assert w.neon_dash["active"]
    # Advance ticks past ends_tick via year_tick path
    w.tick = int(w.neon_dash["ends_tick"])
    w._tick_neon_dash()
    assert w.neon_dash["active"] is False
    end_ev = [
        e for e in w.event_ticker
        if e.get("kind") == "neon_dash" and e.get("phase") == "end"
    ]
    assert end_ev
    s = w.snapshot(a)
    assert s["neon_dash"]["active"] is False
    assert s["neon_dash"]["next_start_tick"] is not None


def test_ordered_checkpoints_required():
    w = GameWorld(351)
    a = _join(w, "Skipper")
    w.handle_year_action(a, "neon_dash_force", "dev")
    cps = list(w.neon_dash["checkpoints"])
    assert len(cps) >= 2
    # Skip first — stand on second
    w._force_set_pos(a, cps[1]["x"], cps[1]["y"], 0, "skip")
    w._neon_dash_on_move(a)
    assert a.neon_dash["hit"] == []
    # Hit first then second
    w._force_set_pos(a, cps[0]["x"], cps[0]["y"], 0, "first")
    w._neon_dash_on_move(a)
    assert a.neon_dash["hit"] == [cps[0]["id"]]
    w._force_set_pos(a, cps[1]["x"], cps[1]["y"], 0, "second")
    w._neon_dash_on_move(a)
    assert cps[1]["id"] in a.neon_dash["hit"]


def test_status_action():
    w = GameWorld(352)
    a = _join(w, "Status")
    assert w.handle_year_action(a, "neon_dash")
    w.handle_year_action(a, "neon_dash_force", "dev")
    assert w.handle_year_action(a, "dash_status")
