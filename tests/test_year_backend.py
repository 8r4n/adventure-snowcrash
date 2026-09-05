"""Smoke tests for year-backend systems (#12–#39)."""

from __future__ import annotations

from snowcrash.engine import check_win, handle_action, new_game
from snowcrash.items import make_payload_zero
from snowcrash.mapgen import FloorItem
from snowcrash.mmorpg import GameWorld
from snowcrash.systems.aoi import aoi_docs, interested_player_ids
from snowcrash.wishes import make_wish_origin_item


def test_snapshot_year_fields():
    w = GameWorld(7)
    a = w.join("Snap")
    s = w.snapshot(a)
    for key in (
        "skills",
        "loadout",
        "skill_picks_available",
        "events",
        "party",
        "dead",
        "respawn_options",
        "kill_feed",
        "journal",
        "district",
        "craft",
        "housing",
        "weather",
        "crew",
        "contracts",
        "reputation",
        "pvp",
        "season",
    ):
        assert key in s


def test_skill_pick_and_shop():
    w = GameWorld(7)
    a = w.join("Buyer")
    a.skill_picks_available = 1
    a.last_action_ts = 0
    w.handle_action(a, "skill_pick", "jacker")
    assert "jacker" in a.skills
    vx, vy = w.vendor_positions["burb_kiosk"]
    w._force_set_pos(a, vx, vy, 0, "t")
    a.credits = 50
    a.last_action_ts = 0
    w.handle_action(a, "buy", "focus_tab")
    assert any(i.id == "focus_tab" for i in a.actor.inventory)


def test_party_and_aoi():
    w = GameWorld(7)
    a = w.join("A")
    b = w.join("B")
    a.last_action_ts = 0
    w.handle_action(a, "party_invite", "B")
    b.last_action_ts = 0
    w.handle_action(b, "party_accept", a.party_id)
    assert a.party_id == b.party_id
    ids = interested_player_ids(w, a.id, force_all=False)
    assert a.id in ids and b.id in ids
    assert "AOI" in aoi_docs() or "Interest" in aoi_docs()


def test_craft_wish_origin():
    w = GameWorld(7)
    a = w.join("Crafter")
    a.credits = 40
    a.last_action_ts = 0
    w.handle_action(a, "craft", "wish_origin_lens")
    assert any(i.id == "wish_origin_lens" for i in a.actor.inventory)
    assert make_wish_origin_item().extra.get("wish_origin") is True


def test_mmorpg_payload_zero():
    w = GameWorld(99)
    a = w.join("Runner")
    for e in w.npcs_enemies:
        if abs(e.x - w.jackpoint_pos[0]) + abs(e.y - w.jackpoint_pos[1]) <= 2:
            e.alive = False
    w._force_set_pos(a, w.jackpoint_pos[0], w.jackpoint_pos[1], 0, "t")
    a.last_action_ts = 0
    w.handle_action(a, "g")
    assert a.has_payload()
    w._force_set_pos(a, w.uplink_pos[0], w.uplink_pos[1], 0, "t")
    w.check_win(a)
    assert a.won
    assert a.journal.get("completed") is True


def test_engine_payload_zero_tui_loop():
    gs = new_game(99)
    jx, jy = gs.jackpoint_pos
    for act in gs.actors:
        if act.alive and act.x == jx and act.y == jy and not act.is_player():
            act.alive = False
    gs.player.x, gs.player.y = jx, jy
    gs.floor_items = [
        fi for fi in gs.floor_items if not (fi.x == jx and fi.y == jy and fi.item.id == "payload_zero")
    ]
    gs.floor_items.append(FloorItem(jx, jy, make_payload_zero()))
    handle_action(gs, "g")
    assert gs.has_payload()
    gs.player.x, gs.player.y = gs.uplink_pos
    check_win(gs)
    assert gs.won
    assert gs.journal.get("completed") is True


def test_death_respawn_options():
    w = GameWorld(3)
    a = w.join("Doomed")
    a.actor.hp = 0
    a.actor.alive = False
    w._year_on_player_death(a, killer_name="Street Thug")
    assert a.dead and a.respawn_options
    a.last_action_ts = 0
    w.handle_action(a, "respawn", "safe_pad")
    assert a.actor.alive and not a.dead
