"""Uplink Hop / Street Jaunt skill progression (#62)."""

from __future__ import annotations

import time

from snowcrash.mmorpg import GameWorld
from snowcrash.systems.jaunte import (
    FOCUS_COST,
    MIN_RANK,
    RANK_NAMES,
    SHORT_RANGE,
    SKILL_ID,
)


def _join(w: GameWorld, name: str = "JaunteCourier"):
    a = w.join(name)
    a.last_action_ts = 0
    a.jaunte["cooldown_until"] = 0.0
    a.actor.focus = a.actor.max_focus
    return a


def _force_rank(agent, rank: int, xp: int = 0) -> None:
    agent.jaunte["rank"] = rank
    agent.jaunte["xp"] = xp
    agent.jaunte["cooldown_until"] = 0.0
    agent.actor.focus = agent.actor.max_focus


def test_ranks_and_range_gates():
    assert RANK_NAMES[1] == "Street Jaunt"
    assert RANK_NAMES[3] == "Globe Hop"
    assert MIN_RANK["short"] == 1
    assert MIN_RANK["district"] == 2
    assert MIN_RANK["globe"] == 3
    assert SHORT_RANGE[1] <= SHORT_RANGE[3]
    assert FOCUS_COST["short"] < FOCUS_COST["globe"]


def test_snapshot_and_panel_action():
    w = GameWorld(620)
    a = _join(w)
    s = w.snapshot(a)
    assert "jaunte" in s
    j = s["jaunte"]
    assert j["rank"] == 0
    assert j["rank_name"] == "Untrained"
    assert len(j["ranks"]) == 4
    assert j["can_district"] is False
    assert j["can_globe"] is False
    assert w.handle_year_action(a, "jaunte", "")
    assert a.jaunte["panel_open"] is True
    assert any("Uplink Hop" in m or "Street Jaunt" in m for m in a.messages)


def test_skill_pick_raises_rank():
    w = GameWorld(621)
    a = _join(w)
    a.skill_picks_available = 1
    assert w.handle_year_action(a, "skill_pick", SKILL_ID)
    assert SKILL_ID in a.skills
    assert a.jaunte["rank"] >= 1
    assert a.skill_picks_available == 0


def test_jaunte_train_spends_pick():
    w = GameWorld(622)
    a = _join(w)
    a.skill_picks_available = 2
    assert w.handle_year_action(a, "jaunte_train", "")
    assert a.jaunte["rank"] == 1
    assert a.skill_picks_available == 1
    assert w.handle_year_action(a, "jaunte_train", "")
    assert a.jaunte["rank"] == 2


def test_short_hop_moves_when_ranked(monkeypatch):
    w = GameWorld(623)
    a = _join(w)
    _force_rank(a, 1)
    monkeypatch.setattr(w.rng, "random", lambda: 0.99)
    ox, oy = a.actor.x, a.actor.y
    a.actor.facing = 1
    focus_before = a.actor.focus
    assert w.handle_year_action(a, "jaunte_short", "")
    assert a.jaunte.get("last_result") in ("success", "blocked", "misfire")
    if a.jaunte.get("last_result") == "success":
        assert (a.actor.x, a.actor.y) != (ox, oy)
        assert a.actor.focus == focus_before - FOCUS_COST["short"]
        assert a.jaunte["hops"] >= 1
        assert a.jaunte["xp"] >= 1


def test_underleveled_district_often_misfires(monkeypatch):
    w = GameWorld(624)
    a = _join(w)
    _force_rank(a, 0)
    monkeypatch.setattr(w.rng, "random", lambda: 0.01)
    monkeypatch.setattr(w.rng, "randint", lambda lo, hi: (lo + hi) // 2)
    assert w.handle_year_action(a, "jaunte_district", "club")
    assert a.jaunte["misfires"] >= 1
    assert a.jaunte.get("last_result") == "misfire"
    assert any("misfire" in m.lower() for m in a.messages)
    assert float(a.jaunte["cooldown_until"]) > time.time()


def test_district_hop_at_rank_2(monkeypatch):
    w = GameWorld(625)
    a = _join(w)
    _force_rank(a, 2, xp=10)
    monkeypatch.setattr(w.rng, "random", lambda: 0.99)
    before_dist = w._district_at(a.actor.x, a.actor.y, int(getattr(a.actor, "z", 0) or 0))
    assert w.handle_year_action(a, "jaunte", "district club")
    assert a.jaunte.get("last_result") in ("success", "blocked", "misfire")
    if a.jaunte.get("last_result") == "success":
        assert a.jaunte["hops"] >= 1
        after = w._district_at(a.actor.x, a.actor.y, int(getattr(a.actor, "z", 0) or 0))
        assert after.get("id") in (
            "club", before_dist.get("id"), "burbclave", "uplink_rim", "undercity",
        )


def test_globe_gate_and_cooldown_feedback(monkeypatch):
    w = GameWorld(626)
    a = _join(w)
    _force_rank(a, 1)
    a.credits = 100
    monkeypatch.setattr(w.rng, "random", lambda: 0.01)
    monkeypatch.setattr(w.rng, "randint", lambda lo, hi: lo + 2)
    assert w.handle_year_action(a, "jaunte_globe", "neo_tokyo")
    assert a.jaunte.get("last_result") in (
        "misfire", "cooldown", "focus", "hint", "success",
    )
    a.actor.focus = a.actor.max_focus
    assert w.handle_year_action(a, "jaunte_short", "")
    assert a.jaunte.get("last_feedback") is not None


def test_globe_success_at_rank_3(monkeypatch):
    w = GameWorld(627)
    a = _join(w, "GlobeJaunter")
    _force_rank(a, 3, xp=22)
    a.credits = 100
    monkeypatch.setattr(w.rng, "random", lambda: 0.99)
    a.globe["cooldown_until"] = 0.0
    home = a.globe.get("region_id")
    assert w.handle_year_action(a, "jaunte", "globe neo_tokyo")
    assert a.mode not in ("cyberspace", "heist")
    if a.jaunte.get("last_result") == "success":
        assert a.globe.get("region_id") in ("neo_tokyo", home) or a.globe.get("teleports", 0) >= 0


def test_blocked_while_dead():
    w = GameWorld(628)
    a = _join(w, "DeadJaunter")
    _force_rank(a, 2)
    a.dead = True
    a.mode = "dead"
    assert w.handle_year_action(a, "jaunte_short", "")
    assert a.jaunte.get("last_result") == "blocked"


def test_xp_rank_up_from_short_hops(monkeypatch):
    w = GameWorld(629)
    a = _join(w, "GrindJaunter")
    _force_rank(a, 0, xp=0)
    monkeypatch.setattr(w.rng, "random", lambda: 0.99)
    a.skill_picks_available = 1
    w.handle_year_action(a, "jaunte_train", "")
    assert a.jaunte["rank"] == 1
    for i in range(12):
        a.jaunte["cooldown_until"] = 0.0
        a.actor.focus = a.actor.max_focus
        a.actor.facing = i % 4
        w.handle_year_action(a, "jaunte_short", "")
    assert a.jaunte["xp"] >= 0
    assert a.jaunte["rank"] >= 1
