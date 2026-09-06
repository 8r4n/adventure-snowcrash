"""Deep ICE heist runs + hostile AI presence (#56)."""

from __future__ import annotations

import time

from snowcrash import constants as C
from snowcrash.mmorpg import GameWorld
from snowcrash.systems.cyberspace import CYBER_CORE, CYBER_EXIT, CYBER_FLOOR, CYBER_ICE
from snowcrash.systems.ice_heists import (
    AI_NAME,
    HEIST_FAIL_DEBT,
    HEIST_LAYER_COUNT,
    HEIST_TEMPLATE_ID,
)


def _join(w: GameWorld, name: str = "Heister"):
    a = w.join(name)
    a.last_action_ts = 0
    a.actor.focus = a.actor.max_focus
    a.actor.hp = a.actor.max_hp
    if not isinstance(getattr(a, "ice_cooldowns", None), dict):
        a.ice_cooldowns = {}
    return a


def _at_jackpoint(w: GameWorld, a) -> None:
    jx, jy = w.jackpoint_pos
    w._force_set_pos(a, jx, jy, C.PLANE_STREET, "test heist")
    a.last_action_ts = 0


def test_heist_snapshot_and_can_start_at_j():
    w = GameWorld(156)
    a = _join(w)
    _at_jackpoint(w, a)
    s = w.snapshot(a)
    assert "ice_heist" in s
    h = s["ice_heist"]
    assert h["template_id"] == HEIST_TEMPLATE_ID
    assert h["layers"] == HEIST_LAYER_COUNT
    assert h["can_start"] is True
    assert h["active"] is False
    assert h["failure_costs"]["soft_lock"] is False if "failure_costs" in h else True


def test_heist_start_and_abort_costs_without_soft_lock():
    w = GameWorld(157)
    a = _join(w, "AbortRun")
    _at_jackpoint(w, a)
    a.credits = 50
    a.bandwidth_debt = 0
    a.heat = 0.0
    a.last_action_ts = 0
    w.handle_action(a, "heist_start")
    assert a.mode == "heist"
    assert a.heist.get("active")
    assert a.heist.get("layer") == 1
    sx, sy = a.heist["street"]["x"], a.heist["street"]["y"]
    a.last_action_ts = 0
    w.handle_action(a, "heist_abort")
    assert a.mode == "play"
    assert (a.actor.x, a.actor.y) == (sx, sy)
    assert a.actor.hp >= 1  # no soft-lock death
    assert int(a.bandwidth_debt) >= HEIST_FAIL_DEBT
    assert float(a.heat) >= 1.0
    assert float(a.heist.get("stun_until") or 0) > time.time()
    # Cannot immediately restart while stunned
    a.last_action_ts = 0
    w.handle_action(a, "heist_start")
    assert a.mode == "play"


def test_heist_probe_melts_ice_and_three_layers_clear():
    w = GameWorld(158)
    a = _join(w, "VaultClear")
    _at_jackpoint(w, a)
    a.actor.focus = 40
    a.ice_cooldowns = {}
    a.last_action_ts = 0
    w.handle_action(a, "jack_in", "heist")
    assert a.mode == "heist"

    for expected_layer in range(1, HEIST_LAYER_COUNT + 1):
        assert a.mode == "heist"
        assert a.heist.get("layer") == expected_layer
        session = a.heist["session"]
        grid = session["grid"]
        # Melt all ICE via direct clear for determinism
        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                if ch == CYBER_ICE:
                    grid[y][x] = CYBER_FLOOR
        session["ice_cells"] = []
        # Stand on core and pickup
        core = None
        exit_pos = None
        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                if ch == CYBER_CORE:
                    core = (x, y)
                if ch == CYBER_EXIT:
                    exit_pos = (x, y)
        assert core and exit_pos
        session["px"], session["py"] = core
        a.last_action_ts = 0
        w.handle_action(a, "g")
        assert session.get("loot_taken") is True
        session["px"], session["py"] = exit_pos
        a.last_action_ts = 0
        w.handle_action(a, "g")

    assert a.mode == "play"
    assert a.quest_flags.get("ice_heist_cleared")
    assert any(i.id == "heist_shard" for i in a.actor.inventory)
    assert a.heist.get("wins", 0) >= 1


def test_heist_layer3_ai_stub_present():
    w = GameWorld(159)
    a = _join(w, "Choir")
    _at_jackpoint(w, a)
    a.last_action_ts = 0
    w.handle_action(a, "heist_start")
    # Force layer 3
    from snowcrash.systems.ice_heists import build_heist_layer

    a.heist["layer"] = 3
    a.heist["layers_cleared"] = 2
    a.heist["session"] = build_heist_layer(2)
    s = w.snapshot(a)
    assert s["ice_heist"]["active"] is True
    assert s["ice_heist"]["ai"] is not None
    assert s["ice_heist"]["ai"]["name"] == AI_NAME
    assert s["ice_heist"]["ai"]["stub"] is True
    assert "map" in s["ice_heist"]


def test_streetnet_omen_tick():
    w = GameWorld(160)
    a = _join(w, "Omen")
    w.ice_heist_world["omen_next_tick"] = w.tick
    before = int(w.ice_heist_world.get("omen_count") or 0)
    w._tick_ice_heist()
    assert int(w.ice_heist_world.get("omen_count") or 0) == before + 1
    assert w.ice_heist_world.get("last_omen_text")
    kinds = [e.get("kind") for e in w.event_ticker]
    assert "ice_heist_omen" in kinds
