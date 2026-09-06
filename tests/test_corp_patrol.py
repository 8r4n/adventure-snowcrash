"""Corp patrol pressure / heat meter (#50)."""

from __future__ import annotations

from snowcrash.mmorpg import GameWorld
from snowcrash.systems.corp_patrol import (
    HEAT_CREW_SAFEHOUSE_BONUS,
    HEAT_MAX,
    HEAT_PER_KEY,
    HEAT_PER_KILL,
    HEAT_SAFEHOUSE_SHED,
    HEAT_SPAWN_THRESHOLD,
)


def _join(w: GameWorld, name: str = "HotCourier"):
    a = w.join(name)
    a.last_action_ts = 0
    return a


def test_heat_in_snapshot_and_kill_raises():
    w = GameWorld(360)
    a = _join(w)
    s = w.snapshot(a)
    assert "heat" in s
    assert s["heat"]["value"] == 0
    assert s["heat"]["max"] == HEAT_MAX
    assert s["heat"]["tier"] == "cool"
    # Simulate a normal kill heat bump
    from snowcrash.entities import make_thug

    victim = make_thug(a.actor.x + 2, a.actor.y)
    w.year_on_kill(a, victim)
    assert a.heat >= HEAT_PER_KILL
    s2 = w.snapshot(a)
    assert s2["heat"]["value"] >= HEAT_PER_KILL


def test_patrol_spawns_when_heat_high():
    w = GameWorld(361)
    a = _join(w, "Marked")
    assert w.handle_year_action(a, "corp_patrol_force", "dev")
    assert a.corp_patrol_id
    assert a.corp_patrol_id in w.corp_patrols
    patrol = w.corp_patrols[a.corp_patrol_id]
    assert patrol["units_alive"] >= 1
    assert a.heat >= HEAT_SPAWN_THRESHOLD
    s = w.snapshot(a)
    assert s["heat"]["patrol"] is not None
    assert s["heat"]["patrol"]["hunting_you"] is True
    assert s["corp_patrol"] is not None
    kinds = [e.get("kind") for e in w.event_ticker]
    assert "corp_patrol" in kinds
    # Units exist as corp enemies
    units = [e for e in w.npcs_enemies if getattr(e, "corp_patrol", False) and e.alive]
    assert len(units) >= 1
    assert all(getattr(u, "hunt_agent_id", None) == a.id for u in units)


def test_safehouse_crew_shed_bonus():
    w = GameWorld(362)
    a = _join(w, "Cooler")
    b = _join(w, "Crewmate")
    w.handle_year_action(a, "crew_create", "FaradayFoxes")
    cid = a.crew_id
    w.handle_year_action(b, "crew_join", cid)
    a.heat = 40.0
    # Solo safehouse rate
    a.housing["at_home"] = True
    # Temporarily leave crew to measure base
    a.crew_id = None
    solo = w._shed_rate_for(a)
    assert solo >= HEAT_SAFEHOUSE_SHED
    a.crew_id = cid
    crew_rate = w._shed_rate_for(a)
    assert crew_rate >= solo + HEAT_CREW_SAFEHOUSE_BONUS - 0.01
    assert w.snapshot(a)["heat"]["crew_shed_bonus"] is True
    # Tick sheds
    before = a.heat
    w._tick_corp_patrol()
    assert a.heat < before


def test_contest_patrol_and_status():
    w = GameWorld(363)
    a = _join(w, "Hunted")
    b = _join(w, "Backup")
    w.handle_year_action(a, "crew_create", "RimRats")
    w.handle_year_action(b, "crew_join", a.crew_id)
    w.handle_year_action(a, "corp_patrol_force", "dev")
    assert w.handle_year_action(b, "contest_patrol")
    patrol = w.corp_patrols[a.corp_patrol_id]
    assert patrol["contested"] is True
    assert patrol["contest_crew_id"] == a.crew_id
    assert w.handle_year_action(a, "heat")
    assert w.handle_year_action(a, "corp_patrol")


def test_signal_key_raises_heat():
    w = GameWorld(364)
    a = _join(w, "KeySleeve")
    from snowcrash.systems.signal_keys import make_signal_key, SIGNAL_KEY_IDS

    kid = SIGNAL_KEY_IDS[0]
    before = float(a.heat)
    w._on_signal_key_pickup(a, make_signal_key(kid))
    assert a.heat >= before + HEAT_PER_KEY
