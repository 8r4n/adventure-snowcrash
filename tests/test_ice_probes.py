"""ICE probe quickhacks (#46) — Focus cost, cooldowns, effects."""

from __future__ import annotations

import time

from snowcrash import constants as C
from snowcrash.mmorpg import GameWorld


def _join_ready(w: GameWorld, name: str = "Probe"):
    a = w.join(name)
    a.last_action_ts = 0
    a.actor.focus = a.actor.max_focus
    if not isinstance(getattr(a, "ice_cooldowns", None), dict):
        a.ice_cooldowns = {}
    return a


def test_ice_snapshot_fields():
    w = GameWorld(46)
    a = _join_ready(w, "SnapIce")
    s = w.snapshot(a)
    assert "ice" in s
    ice = s["ice"]
    assert "probes" in ice and "nearby" in ice
    ids = {p["id"] for p in ice["probes"]}
    assert {"stun", "reveal", "scramble"} <= ids
    assert len(getattr(w, "ice_cameras", [])) >= 1


def test_reveal_costs_focus_and_cools_down():
    w = GameWorld(46)
    a = _join_ready(w)
    before = a.actor.focus
    cost = int(C.ICE_PROBES["reveal"]["focus_cost"])
    a.last_action_ts = 0
    w.handle_action(a, "ice_probe", "reveal")
    assert a.actor.focus == before - cost
    assert a.ice_cooldowns.get("reveal", 0) > time.time()
    # cooldown blocks second cast
    focus_mid = a.actor.focus
    a.last_action_ts = 0
    w.handle_action(a, "ice_probe", "reveal")
    assert a.actor.focus == focus_mid  # no second spend


def test_stun_freezes_nearest_target():
    w = GameWorld(47)
    a = _join_ready(w, "Stunner")
    # Place a thug next to the player
    thugs = [e for e in w.npcs_enemies if e.alive and e.glyph == C.ENEMY_THUG]
    assert thugs, "need a thug in world"
    t = thugs[0]
    w._force_set_pos(a, t.x, max(0, t.y - 1), 0, "t")
    # ensure adjacent
    t.x, t.y = a.actor.x + 1, a.actor.y
    a.actor.focus = 20
    a.last_action_ts = 0
    w.handle_action(a, "ice_probe", "stun")
    assert float(getattr(t, "stunned_until", 0) or 0) > time.time()
    # enemy_tick should not move stunned target
    ox, oy = t.x, t.y
    w.enemy_tick()
    assert (t.x, t.y) == (ox, oy)


def test_scramble_sets_flag():
    w = GameWorld(48)
    a = _join_ready(w, "Scram")
    drones = [e for e in w.npcs_enemies if e.alive and e.glyph == C.ENEMY_DRONE]
    if not drones:
        # force one near player
        from snowcrash.entities import make_drone
        d = make_drone(a.actor.x + 2, a.actor.y)
        d.z = 0
        w.npcs_enemies.append(d)
        drones = [d]
    d = drones[0]
    w._force_set_pos(a, d.x - 1, d.y, 0, "t")
    a.actor.focus = 20
    a.last_action_ts = 0
    w.handle_action(a, "probe", "scramble")
    assert float(getattr(d, "scrambled_until", 0) or 0) > time.time()


def test_insufficient_focus():
    w = GameWorld(49)
    a = _join_ready(w, "LowFocus")
    a.actor.focus = 0
    a.last_action_ts = 0
    w.handle_action(a, "ice_stun")
    assert a.actor.focus == 0
    assert not any("Stun Spike" in m and "Focus" in m and "−" in m for m in a.messages[-3:])

def test_scramble_no_hostiles_keeps_focus():
    """Street Cam alone must not burn Focus on Aggro Scramble (playtest #88)."""
    w = GameWorld(50)
    a = _join_ready(w, "CamOnly")
    # Park on spawn where cameras are seeded; strip living hostiles from range
    for e in list(w.npcs_enemies):
        if e.alive and e.faction == "enemy":
            e.x, e.y = 0, 0
            e.alive = False
    # Ensure at least one camera near the courier
    assert getattr(w, "ice_cameras", None)
    cam = w.ice_cameras[0]
    w._force_set_pos(a, int(cam["x"]), int(cam["y"]), int(cam.get("z", 0) or 0), "t")
    nearby = w._ice_nearby_targets(a, radius=int(C.ICE_PROBES["scramble"]["radius"]))
    assert any(t["kind"] == "camera" for t in nearby), "camera should be in range"
    assert not any(t["kind"] in ("drone", "thug_deck") for t in nearby)
    before = a.actor.focus
    a.last_action_ts = 0
    w.handle_action(a, "ice_probe", "scramble")
    assert a.actor.focus == before
    assert any("Focus kept" in m or "hostile trail" in m for m in a.messages[-4:])


def test_stun_no_target_keeps_focus():
    w = GameWorld(51)
    a = _join_ready(w, "EmptyStun")
    for e in list(w.npcs_enemies):
        if e.alive and e.faction == "enemy":
            e.alive = False
    # Move cameras far away
    for cam in getattr(w, "ice_cameras", []) or []:
        cam["x"], cam["y"] = 0, 0
    # Place courier away from 0,0
    w._force_set_pos(a, min(w.gmap.width - 2, 40), min(w.gmap.height - 2, 40), 0, "t")
    before = a.actor.focus
    a.last_action_ts = 0
    w.handle_action(a, "ice_probe", "stun")
    assert a.actor.focus == before
    assert any("Focus kept" in m or "Stun range" in m for m in a.messages[-4:])

