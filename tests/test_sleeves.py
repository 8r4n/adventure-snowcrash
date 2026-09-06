"""Sleeve / avatar hop with stat tradeoffs (#59)."""

from __future__ import annotations

from snowcrash import constants as C
from snowcrash.mmorpg import GameWorld
from snowcrash.systems.sleeves import SHELL_CATALOG, DEFAULT_SHELL_ID


def _join(w: GameWorld, name: str = "SleeveCourier"):
    a = w.join(name)
    a.last_action_ts = 0
    return a


def _enter_safehouse(w: GameWorld, agent):
    assert w.handle_year_action(agent, "house", "")
    assert agent.housing["at_home"] is True


def test_catalog_has_three_shells_with_tradeoffs():
    assert len(SHELL_CATALOG) >= 3
    assert "street" in SHELL_CATALOG
    assert "club" in SHELL_CATALOG
    assert "undercity" in SHELL_CATALOG
    street = SHELL_CATALOG["street"]["stats"]
    club = SHELL_CATALOG["club"]["stats"]
    under = SHELL_CATALOG["undercity"]["stats"]
    assert club["hack"] > street["hack"]
    assert club["defense"] < street["defense"]
    assert club["max_hp"] < street["max_hp"]
    assert under["defense"] > street["defense"]
    assert under["max_hp"] > street["max_hp"]
    assert under["hack"] < street["hack"]
    assert SHELL_CATALOG["street"]["rent_credits"] == 0
    assert SHELL_CATALOG["club"]["premium"] is True
    assert SHELL_CATALOG["undercity"]["premium"] is True


def test_default_street_snapshot_and_panel_action():
    w = GameWorld(590)
    a = _join(w)
    s = w.snapshot(a)
    assert "sleeves" in s
    sl = s["sleeves"]
    assert sl["current"] == DEFAULT_SHELL_ID
    assert len(sl["shells"]) >= 3
    assert sl["at_safehouse"] is False
    assert any(x["id"] == "club" and x["premium"] for x in sl["shells"])
    assert w.handle_year_action(a, "sleeves", "")
    assert a.sleeves["panel_open"] is True
    assert any("Sleeves locker" in m for m in a.messages)


def test_hop_blocked_outside_safehouse():
    w = GameWorld(591)
    a = _join(w)
    a.credits = 100
    assert w.handle_year_action(a, "sleeve", "club")
    assert a.sleeves["current"] == "street"
    assert any("safehouse" in m.lower() for m in a.messages)


def test_street_hop_free_at_safehouse():
    w = GameWorld(592)
    a = _join(w, "StreetHop")
    _enter_safehouse(w, a)
    a.credits = 100
    assert w.handle_year_action(a, "sleeve", "club")
    assert a.sleeves["current"] == "club"
    credits_after_rent = a.credits
    assert credits_after_rent == 100 - SHELL_CATALOG["club"]["rent_credits"]
    assert w.handle_year_action(a, "sleeve", "street")
    assert a.sleeves["current"] == "street"
    assert a.credits == credits_after_rent
    assert a.actor.max_hp >= C.START_HP - 2


def test_club_and_undercity_rent_and_stats():
    w = GameWorld(593)
    a = _join(w, "Premium")
    _enter_safehouse(w, a)
    a.credits = 100
    assert w.handle_year_action(a, "sleeve_rent", "club")
    assert "club" in a.sleeves["rented"]
    assert a.credits == 100 - 25
    assert w.handle_year_action(a, "sleeve", "club")
    assert a.sleeves["current"] == "club"
    assert a.actor.hack >= SHELL_CATALOG["club"]["stats"]["hack"]
    assert a.actor.max_hp == SHELL_CATALOG["club"]["stats"]["max_hp"]
    assert a.actor.hp == a.actor.max_hp

    assert w.handle_year_action(a, "sleeve", "undercity")
    assert a.sleeves["current"] == "undercity"
    assert a.credits == 100 - 25 - 20
    assert a.actor.defense >= SHELL_CATALOG["undercity"]["stats"]["defense"]
    assert a.actor.max_hp == SHELL_CATALOG["undercity"]["stats"]["max_hp"]
    s = w.snapshot(a)
    assert s["sleeves"]["current"] == "undercity"
    assert s["sleeves"]["hops"] >= 2


def test_broke_cannot_rent_premium():
    w = GameWorld(594)
    a = _join(w, "BrokeShell")
    _enter_safehouse(w, a)
    a.credits = 5
    assert w.handle_year_action(a, "sleeve", "club")
    assert a.sleeves["current"] == "street"
    assert a.credits == 5
    assert any("credit" in m.lower() for m in a.messages)


def test_blocked_while_dead():
    w = GameWorld(595)
    a = _join(w, "DeadShell")
    _enter_safehouse(w, a)
    a.credits = 100
    a.dead = True
    a.mode = "dead"
    assert w.handle_year_action(a, "sleeve", "club")
    assert a.sleeves["current"] == "street"
