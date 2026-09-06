"""StreetNet Empathy Audit + synth bounty contracts (#63)."""

from __future__ import annotations

import time

from snowcrash.mmorpg import GameWorld
from snowcrash.systems.empathy import (
    AUDIT_FAIL_HEAT,
    AUDIT_FAIL_REP,
    AUDIT_PASS_REP,
    AUDIT_QUESTIONS,
    BOUNTY_TYPES,
    SYNTH_GLYPH,
)


def _join(w: GameWorld, name: str = "EmpathyCourier"):
    a = w.join(name)
    a.last_action_ts = 0
    a.reputation = 10
    a.heat = 20.0
    a.credits = 50
    return a


def test_bounty_types_at_least_two():
    assert len(BOUNTY_TYPES) >= 2
    assert "retire" in BOUNTY_TYPES
    assert "reclaim" in BOUNTY_TYPES


def test_snapshot_and_panel():
    w = GameWorld(630)
    a = _join(w)
    s = w.snapshot(a)
    assert "empathy" in s
    em = s["empathy"]
    assert em["synth_glyph"] == SYNTH_GLYPH
    assert len(em["types"]) >= 2
    assert len(em["bounties"]) >= 2
    assert w.handle_year_action(a, "empathy", "")
    assert a.empathy["panel_open"] is True


def test_audit_pass_raises_rep_sheds_heat(monkeypatch):
    w = GameWorld(631)
    a = _join(w)
    rep0 = a.reputation
    heat0 = float(a.heat)
    assert w.handle_year_action(a, "empathy_audit", "")
    assert a.empathy["audit_active"] is True
    # Always pick empathic choice "a"
    for _ in AUDIT_QUESTIONS:
        assert w.handle_year_action(a, "empathy_answer", "a")
    assert a.empathy["audit_active"] is False
    assert a.empathy["last_result"] == "pass"
    assert a.empathy["passed_once"] is True
    assert a.reputation == rep0 + AUDIT_PASS_REP
    assert float(a.heat) < heat0


def test_audit_fail_moral_heat(monkeypatch):
    w = GameWorld(632)
    a = _join(w)
    rep0 = a.reputation
    heat0 = float(a.heat)
    assert w.handle_year_action(a, "empathy_audit", "")
    for _ in AUDIT_QUESTIONS:
        assert w.handle_year_action(a, "empathy_answer", "c")
    assert a.empathy["last_result"] == "fail"
    assert a.reputation == rep0 + AUDIT_FAIL_REP
    assert float(a.heat) >= heat0 + AUDIT_FAIL_HEAT - 0.1


def test_retire_bounty_kill_and_turnin(monkeypatch):
    w = GameWorld(633)
    a = _join(w)
    # Force a predictable spawn near player
    def fake_spawn(agent, radius=14):
        g = w.gmap
        ax, ay = agent.actor.x, agent.actor.y
        for dx, dy in ((3, 0), (0, 3), (-3, 0), (0, -3), (4, 1), (2, 2)):
            x, y = ax + dx, ay + dy
            if g.walkable(x, y) and not w.actor_at(x, y, z=0):
                return (x, y)
        return (ax + 1, ay)

    monkeypatch.setattr(w, "_empathy_find_spawn", fake_spawn)
    assert w.handle_year_action(a, "bounty_accept", "retire")
    row = next(b for b in a.empathy["bounties"] if b["type"] == "retire" and b["status"] == "active")
    synth = next(
        m for m in w.npcs_enemies if getattr(m, "synth_bounty_id", None) == row["id"] and m.alive
    )
    assert synth.glyph == SYNTH_GLYPH
    credits0 = a.credits
    rep0 = a.reputation
    # Simulate kill via year_on_kill
    synth.alive = False
    synth.hp = 0
    w.year_on_kill(a, synth)
    assert row["status"] == "ready"
    assert w.handle_year_action(a, "bounty_turnin", "retire")
    assert row["status"] == "done"
    assert a.credits > credits0
    assert a.reputation >= rep0


def test_reclaim_bind_and_turnin(monkeypatch):
    w = GameWorld(634)
    a = _join(w)
    a.empathy["passed_once"] = True

    def fake_spawn(agent, radius=14):
        return (agent.actor.x + 1, agent.actor.y)

    monkeypatch.setattr(w, "_empathy_find_spawn", fake_spawn)
    # Ensure adjacent tile walkable — if not, patch actor position after spawn
    assert w.handle_year_action(a, "bounty_accept", "reclaim")
    row = next(b for b in a.empathy["bounties"] if b["type"] == "reclaim" and b["status"] == "active")
    synth = next(m for m in w.npcs_enemies if getattr(m, "synth_bounty_id", None) == row["id"] and m.alive)
    # Place player adjacent
    a.actor.x, a.actor.y = synth.x, synth.y
    # Move player onto same tile then shift
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = synth.x + dx, synth.y + dy
        if w.gmap.walkable(nx, ny):
            a.actor.x, a.actor.y = nx, ny
            break
    credits0 = a.credits
    rep0 = a.reputation
    heat0 = float(a.heat)
    assert w.handle_year_action(a, "bounty_reclaim", "")
    assert row["status"] == "ready"
    assert synth.alive is False
    assert w.handle_year_action(a, "bounty_turnin", "reclaim")
    assert row["status"] == "done"
    assert a.credits > credits0
    assert a.reputation > rep0
    assert float(a.heat) <= heat0  # reclaim sheds heat when warm lattice
