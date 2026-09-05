"""Spawn-pad fairness: thinning, grace, contested bias, snapshot shield (#43)."""

from __future__ import annotations

import time

from snowcrash import constants as C
from snowcrash.entities import make_infected
from snowcrash.mapgen import generate_world
from snowcrash.mmorpg import GameWorld


def test_spawn_pads_are_thinned():
    world = generate_world(7)
    n = len(world.spawn_points)
    assert C.SPAWN_PAD_MIN <= n <= C.SPAWN_PAD_MAX, n
    # Separation: most pairs should respect min sep (allow a few relaxations)
    pts = world.spawn_points
    too_close = 0
    for i, (x, y) in enumerate(pts):
        for x2, y2 in pts[i + 1 :]:
            if abs(x - x2) + abs(y - y2) < 8:
                too_close += 1
    assert too_close < n, "pads still clustered too tightly"


def test_safe_zone_not_citywide():
    w = GameWorld(7)
    walk = sum(
        1
        for y in range(w.gmap.height)
        for x in range(w.gmap.width)
        if w.gmap.walkable(x, y)
    )
    safe = sum(
        1
        for y in range(w.gmap.height)
        for x in range(w.gmap.width)
        if w.gmap.walkable(x, y) and w._near_any_spawn(x, y)
    )
    pct = 100.0 * safe / max(1, walk)
    assert pct < 55.0, "safe coverage still too high: %.1f%%" % pct
    assert len(w.spawn_points) <= C.SPAWN_PAD_MAX


def test_join_grants_spawn_shield_and_snapshot():
    w = GameWorld(11)
    a = w.join("Shielded")
    assert a.is_invulnerable()
    assert a.spawn_shield_remaining() > 5.0
    snap = w.snapshot(a)
    assert snap["invulnerable"] is True
    assert snap["spawn_shield"] is True
    assert snap["spawn_shield_remaining"] > 5.0
    # year roadmap fields still present
    assert "skills" in snap and "kill_feed" in snap and "respawn_options" in snap


def test_enemies_ignore_invuln_and_pad():
    w = GameWorld(13)
    a = w.join("PadSafe")
    # Plant a hostile adjacent if possible just outside safe bubble edge
    sx, sy = a.actor.x, a.actor.y
    mon = make_infected(sx + 1, sy)
    mon.z = C.PLANE_STREET
    w.npcs_enemies.append(mon)
    hp_before = a.actor.hp
    for _ in range(5):
        w.enemy_tick()
    assert a.actor.alive
    assert a.actor.hp == hp_before


def test_find_spawn_prefers_quieter_pad():
    w = GameWorld(17)
    # Pack hostiles around first spawn point
    if not w.spawn_points:
        return
    hx, hy = w.spawn_points[0]
    for i in range(8):
        mon = make_infected(hx + 9, hy + (i % 3))
        mon.z = C.PLANE_STREET
        if w.gmap.walkable(mon.x, mon.y):
            w.npcs_enemies.append(mon)
    picks = [w._find_spawn() for _ in range(12)]
    # Majority of picks should not be the heavily contested pad itself
    contested_hits = sum(1 for p in picks if p == (hx, hy))
    assert contested_hits <= 4, contested_hits


def test_melee_blocked_by_spawn_shield():
    w = GameWorld(19)
    a = w.join("Bubble")
    mon = make_infected(a.actor.x, a.actor.y)
    # Place beside player
    mon.x, mon.y, mon.z = a.actor.x + 1, a.actor.y, C.PLANE_STREET
    hp = a.actor.hp
    w.melee_attack(mon, a.actor, observer=a)
    assert a.actor.hp == hp
    assert a.is_invulnerable()
    # Expire shield and confirm damage can apply (cap still softens)
    a.invuln_until = time.time() - 1
    w.melee_attack(mon, a.actor, observer=a)
    assert a.actor.hp < hp
