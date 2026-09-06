"""StreetNet Primer interactive teaching tablet (#60)."""

from __future__ import annotations

from snowcrash.mmorpg import GameWorld
from snowcrash.systems.primer import (
    PRIMER_ITEM_ID,
    QUEST_ORDER,
    QUESTS,
    make_streetnet_primer,
)


def _join(w: GameWorld, name: str = "PrimerCourier"):
    a = w.join(name)
    a.last_action_ts = 0
    return a


def test_primer_item_factory_and_quest_catalog():
    item = make_streetnet_primer()
    assert item.id == PRIMER_ITEM_ID
    assert item.quest is True
    assert item.kind == "quest"
    assert len(QUEST_ORDER) >= 3
    assert set(QUEST_ORDER) <= set(QUESTS)
    for qid in QUEST_ORDER:
        assert QUESTS[qid]["reward_cosmetic"]
        assert QUESTS[qid].get("reward_cosmetic", {}).get("id")


def test_join_grants_primer_and_snapshot():
    w = GameWorld(601)
    a = _join(w)
    assert any(i.id == PRIMER_ITEM_ID for i in a.actor.inventory)
    s = w.snapshot(a)
    assert "primer" in s
    pr = s["primer"]
    assert pr["owned"] is True
    assert len(pr["quests"]) >= 3
    ice = next(q for q in pr["quests"] if q["id"] == "ice_101")
    assert ice["status"] in ("available", "active")
    assert ice["reward"]["p2w"] is False
    crew = next(q for q in pr["quests"] if q["id"] == "crew_101")
    assert crew["status"] == "locked"  # needs level 2
    assert w.handle_year_action(a, "primer", "")
    assert a.primer["panel_open"] is True


def test_use_item_opens_primer():
    w = GameWorld(602)
    a = _join(w)
    idx = next(i for i, it in enumerate(a.actor.inventory) if it.id == PRIMER_ITEM_ID)
    a.selected_inv = idx
    a.mode = "inventory"
    w.handle_action(a, "u")
    assert a.primer["panel_open"] is True
    assert any("StreetNet Primer" in m for m in a.messages)


def test_ice_quest_complete_grants_cosmetic_and_skill():
    w = GameWorld(603)
    a = _join(w)
    # Ensure cameras exist and agent can probe
    assert w.handle_year_action(a, "primer_start", "ice_101")
    assert a.primer["quests"]["ice_101"]["status"] == "active"
    # Force a successful reveal probe (works even with no targets)
    a.actor.focus = 99
    assert w.handle_year_action(a, "ice_probe", "reveal")
    row = a.primer["quests"]["ice_101"]
    assert row["status"] == "done"
    assert "ice_101" in a.primer["completed"]
    assert "trail_primer_ice" in a.season["unlocked"]
    assert "faraday_mind" in a.skills
    # No mandatory paywall — credits only as reward, not cost
    assert a.credits >= 15


def test_globe_and_crew_quests():
    w = GameWorld(604)
    a = _join(w)
    a.credits = 500
    assert w.handle_year_action(a, "primer_start", "globe_101")
    # Actual hop to another shard (home recall alone is a no-op when already home)
    assert w.handle_year_action(a, "teleport", "cont_eu")
    assert a.primer["quests"]["globe_101"]["status"] == "done"
    assert "trail_primer_orbit" in a.season["unlocked"]

    # Crew locked at level 1
    assert w.handle_year_action(a, "primer_start", "crew_101")
    assert a.primer["quests"]["crew_101"]["status"] == "locked"

    a.level = 2
    w._primer_refresh_availability(a)
    assert a.primer["quests"]["crew_101"]["status"] == "available"
    assert w.handle_year_action(a, "primer_start", "crew_101")
    assert w.handle_year_action(a, "crew_create", "PrimerFlotilla")
    assert a.primer["quests"]["crew_101"]["status"] == "done"
    assert "badge_primer_crew" in a.season["unlocked"]
    assert "burb_charm" in a.skills


def test_level_up_unlocks_crew_chapter_voice():
    w = GameWorld(605)
    a = _join(w)
    assert a.primer["quests"]["crew_101"]["status"] == "locked"
    a.level = 2
    w._primer_on_level_up(a)
    assert a.primer["quests"]["crew_101"]["status"] == "available"
    assert a.primer["voice_level"] == 2
