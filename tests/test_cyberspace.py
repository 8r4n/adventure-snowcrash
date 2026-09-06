"""Jack-in cyberspace puzzle layer (#47)."""

from __future__ import annotations

import time

from snowcrash import constants as C
from snowcrash.mmorpg import GameWorld
from snowcrash.systems.cyberspace import CYBER_EXIT, CYBER_FLOOR, CYBER_ICE, CYBER_LOOT


def _join(w: GameWorld, name: str = "Jacker"):
    a = w.join(name)
    a.last_action_ts = 0
    a.actor.focus = a.actor.max_focus
    if not isinstance(getattr(a, "ice_cooldowns", None), dict):
        a.ice_cooldowns = {}
    return a


def _at_jackpoint(w: GameWorld, a) -> None:
    jx, jy = w.jackpoint_pos
    w._force_set_pos(a, jx, jy, C.PLANE_STREET, "test jack")
    a.last_action_ts = 0


def test_cyber_snapshot_can_jack_near_j():
    w = GameWorld(147)
    a = _join(w)
    _at_jackpoint(w, a)
    s = w.snapshot(a)
    assert "cyberspace" in s
    assert s["cyberspace"]["can_jack_in"] is True


def test_jack_in_out_restores_street_pos():
    w = GameWorld(148)
    a = _join(w, "PadKeep")
    _at_jackpoint(w, a)
    sx, sy = a.actor.x, a.actor.y
    facing = a.actor.facing
    a.last_action_ts = 0
    w.handle_action(a, "jack_in", "maze")
    assert a.mode == "cyberspace"
    assert a.cyber.get("active")
    # Move inside node — street body coords must stay parked
    a.last_action_ts = 0
    w.handle_action(a, "forward")
    assert (a.actor.x, a.actor.y) == (sx, sy)
    a.last_action_ts = 0
    w.handle_action(a, "jack_out")
    assert a.mode == "play"
    assert (a.actor.x, a.actor.y) == (sx, sy)
    assert a.actor.facing % 4 == facing % 4
    assert int(getattr(a.actor, "z", 0) or 0) == C.PLANE_STREET


def test_maze_clear_grants_loot_and_journal():
    w = GameWorld(149)
    a = _join(w, "MazeClear")
    _at_jackpoint(w, a)
    a.last_action_ts = 0
    w.handle_action(a, "jack_in", "maze")
    session = a.cyber
    # Teleport to loot then exit inside node
    grid = session["grid"]
    loot = None
    exit_pos = None
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch == CYBER_LOOT:
                loot = (x, y)
            if ch == CYBER_EXIT:
                exit_pos = (x, y)
    assert loot and exit_pos
    session["px"], session["py"] = loot
    a.last_action_ts = 0
    w.handle_action(a, "g")
    assert session["loot_taken"] is True
    before_inv = len(a.actor.inventory)
    session["px"], session["py"] = exit_pos
    a.last_action_ts = 0
    w.handle_action(a, "g")
    assert a.mode == "play"
    assert a.quest_flags.get("cyber_maze_cleared")
    assert any(i.id == "cyber_key" for i in a.actor.inventory)
    assert len(a.actor.inventory) >= before_inv + 1
    notes = (a.journal or {}).get("notes") or []
    assert any("Cyberspace maze cleared" in n for n in notes)


def test_ice_gate_probe_melts_and_clears():
    w = GameWorld(150)
    a = _join(w, "IceGate")
    _at_jackpoint(w, a)
    a.last_action_ts = 0
    w.handle_action(a, "jack_in", "ice_gate")
    assert a.cyber.get("node_type") == "ice_gate"
    session = a.cyber
    grid = session["grid"]
    # Find an ICE cell and stand beside it
    ice = None
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch == CYBER_ICE:
                ice = (x, y)
                break
        if ice:
            break
    assert ice
    ix, iy = ice
    # Stand on adjacent floor
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nx, ny = ix + dx, iy + dy
        if 0 <= ny < len(grid) and 0 <= nx < len(grid[0]) and grid[ny][nx] == CYBER_FLOOR:
            session["px"], session["py"] = nx, ny
            break
    a.actor.focus = 20
    a.ice_cooldowns = {}
    a.last_action_ts = 0
    w.handle_action(a, "ice_probe", "stun")
    assert grid[iy][ix] == CYBER_FLOOR
    # Grab core + exit
    core = None
    exit_pos = None
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch == "%":
                core = (x, y)
            if ch == CYBER_EXIT:
                exit_pos = (x, y)
    assert core and exit_pos
    session["px"], session["py"] = core
    a.last_action_ts = 0
    w.handle_action(a, "g")
    session["px"], session["py"] = exit_pos
    a.last_action_ts = 0
    w.handle_action(a, "g")
    assert a.quest_flags.get("cyber_ice_gate_cleared")
    assert a.mode == "play"


def test_jack_in_requires_jackpoint():
    w = GameWorld(151)
    a = _join(w, "FarAway")
    # Place far from jackpoint
    sx, sy = w.spawn_xy
    w._force_set_pos(a, sx, sy, C.PLANE_STREET, "spawn")
    a.last_action_ts = 0
    w.handle_action(a, "jack_in")
    assert a.mode != "cyberspace"


def test_cyberspace_not_aggro_target():
    w = GameWorld(152)
    a = _join(w, "GhostJack")
    _at_jackpoint(w, a)
    a.last_action_ts = 0
    w.handle_action(a, "jack_in", "maze")
    assert a.mode == "cyberspace"
    # Place thug on player tile-adjacent
    thugs = [e for e in w.npcs_enemies if e.alive and e.glyph == C.ENEMY_THUG]
    if not thugs:
        from snowcrash.entities import make_thug
        t = make_thug(a.actor.x + 1, a.actor.y)
        t.z = 0
        w.npcs_enemies.append(t)
        thugs = [t]
    t = thugs[0]
    t.x, t.y, t.z = a.actor.x + 1, a.actor.y, 0
    hp_before = a.actor.hp
    for _ in range(5):
        w.enemy_tick()
    assert a.actor.hp == hp_before



def test_ice_gate_templates_solvable_after_melt():
    """ICE-gate nodes must be reachable: start → melt all I → core → exit."""
    from collections import deque
    from snowcrash.systems.cyberspace import (
        build_node,
        walkable_cyber,
        CYBER_CORE,
        CYBER_EXIT,
        CYBER_ICE,
        CYBER_FLOOR,
    )
    import random

    def reachable(session):
        q = deque([(session["px"], session["py"])])
        seen = set(q)
        while q:
            x, y = q.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if (nx, ny) in seen:
                    continue
                if walkable_cyber(session, nx, ny):
                    seen.add((nx, ny))
                    q.append((nx, ny))
        return seen

    for seed in range(8):
        session = build_node("ice_gate", random.Random(seed))
        grid = session["grid"]
        # Melt all ICE
        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                if ch == CYBER_ICE:
                    grid[y][x] = CYBER_FLOOR
        reach = reachable(session)
        core = exit_pos = None
        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                if ch == CYBER_CORE:
                    core = (x, y)
                if ch == CYBER_EXIT:
                    exit_pos = (x, y)
        assert core in reach, "core unreachable after melt seed=%s type=%s" % (seed, session["node_type"])
        assert exit_pos in reach, "exit unreachable after melt seed=%s" % seed
