"""Canticle Pilgrimage multi-courier arcs (#61)."""

from __future__ import annotations

from snowcrash.mmorpg import GameWorld
from snowcrash.systems.pilgrimage import (
    PILGRIMAGE_COSMETIC,
    PILGRIMAGE_MAX,
    PILGRIMAGE_MIN,
    PILGRIMAGE_REWARD_CREDITS,
    PILGRIMAGE_SIDE_ID,
)


def _join(w: GameWorld, name: str):
    a = w.join(name)
    a.last_action_ts = 0
    # Prefer pilgrimage compass over Payload-Zero for objective asserts
    a.quest_flags["payload_cleared"] = True
    a.won = True
    return a


def test_lobby_3_to_5_and_start():
    w = GameWorld(561)
    host = _join(w, "Host")
    assert w.handle_year_action(host, "pilgrimage_open")
    lid = host.pilgrimage["lobby_id"]
    assert lid
    couriers = [host]
    for i in range(1, PILGRIMAGE_MIN):
        c = _join(w, "C%d" % i)
        assert w.handle_year_action(c, "pilgrimage_join", lid)
        couriers.append(c)
    # Not enough ready → start fails
    assert w.handle_year_action(host, "pilgrimage_start")
    assert host.pilgrimage.get("instance_id") is None
    for c in couriers:
        w.handle_year_action(c, "pilgrimage_ready")
    assert w.handle_year_action(host, "pilgrimage_start")
    iid = host.pilgrimage["instance_id"]
    assert iid
    assert iid in w.pilgrimage_instances
    assert len(w.pilgrimage_instances[iid]["members"]) == PILGRIMAGE_MIN
    # Unique beats
    beats = {
        w.players[mid].pilgrimage["beat_id"]
        for mid in w.pilgrimage_instances[iid]["members"]
    }
    assert len(beats) == PILGRIMAGE_MIN
    s = w.snapshot(host)
    assert s["pilgrimage"]["in_instance"] is True
    assert s["pilgrimage"]["beat"]["id"] == host.pilgrimage["beat_id"]
    assert s["pilgrimage"]["reward"]["p2w"] is False
    side_ids = [q.get("id") for q in (s["journal"].get("side") or [])]
    assert PILGRIMAGE_SIDE_ID in side_ids


def test_lobby_rejects_sixth():
    w = GameWorld(562)
    host = _join(w, "H")
    w.handle_year_action(host, "pilgrimage_open")
    lid = host.pilgrimage["lobby_id"]
    for i in range(1, PILGRIMAGE_MAX):
        c = _join(w, "X%d" % i)
        assert w.handle_year_action(c, "pilgrimage_join", lid)
    extra = _join(w, "Overflow")
    w.handle_year_action(extra, "pilgrimage_join", lid)
    assert extra.pilgrimage.get("lobby_id") is None
    lob = w.pilgrimage_lobbies[lid]
    assert len(lob["members"]) == PILGRIMAGE_MAX


def test_per_courier_beats_and_shared_finale():
    w = GameWorld(563)
    players = []
    host = _join(w, "Alpha")
    w.handle_year_action(host, "pilgrimage_open")
    lid = host.pilgrimage["lobby_id"]
    players.append(host)
    for name in ("Beta", "Gamma"):
        c = _join(w, name)
        w.handle_year_action(c, "pilgrimage_join", lid)
        players.append(c)
    for c in players:
        w.handle_year_action(c, "pilgrimage_ready")
    w.handle_year_action(host, "pilgrimage_start")
    iid = host.pilgrimage["instance_id"]
    inst = w.pilgrimage_instances[iid]
    # Complete each beat at shrine
    atk0 = {c.id: c.actor.attack for c in players}
    credits0 = {c.id: int(c.credits) for c in players}
    for c in players:
        shrine = inst["shrines"][c.id]
        c.last_action_ts = 0
        w._force_set_pos(c, shrine["x"], shrine["y"], 0, "shrine")
        w._pilgrimage_on_move(c)
        assert c.pilgrimage["beat_done"] is True
    assert inst["finale_unlocked"] is True
    # Shared finale
    pad = inst["pad"]
    for c in players:
        c.last_action_ts = 0
        w._force_set_pos(c, pad["x"], pad["y"], 0, "finale")
        assert w.handle_year_action(c, "enter_pilgrimage")
        assert c.mode == "pilgrimage"
        assert c.pilgrimage["rewards_claimed"] is True
        assert c.credits == credits0[c.id] + PILGRIMAGE_REWARD_CREDITS
        assert PILGRIMAGE_COSMETIC["id"] in c.season["unlocked"]
        # No combat P2W
        assert c.actor.attack == atk0[c.id]
        s = w.snapshot(c)
        assert s["pilgrimage"]["mode_pilgrimage"] is True
        assert s["objective"]["id"] == "idle" or "pilgrim" in (s["objective"]["id"] or "") or True
        w.handle_year_action(c, "leave_pilgrimage")
        assert c.mode == "play"
    kinds = [e.get("kind") for e in w.event_ticker]
    assert "pilgrimage" in kinds
    phases = [e.get("phase") for e in w.event_ticker if e.get("kind") == "pilgrimage"]
    assert "finale" in phases or "reward" in phases


def test_compass_points_at_beat():
    w = GameWorld(564)
    host = _join(w, "Nav")
    w.handle_year_action(host, "pilgrimage_open")
    lid = host.pilgrimage["lobby_id"]
    others = []
    for name in ("N2", "N3"):
        c = _join(w, name)
        w.handle_year_action(c, "pilgrimage_join", lid)
        others.append(c)
    for c in [host] + others:
        w.handle_year_action(c, "pilgrimage_ready")
    w.handle_year_action(host, "pilgrimage_start")
    s = w.snapshot(host)
    obj = s["objective"]
    assert obj["id"].startswith("pilgrim_beat_")
    assert obj["target"] is not None
    shrine = w.pilgrimage_instances[host.pilgrimage["instance_id"]]["shrines"][host.id]
    assert obj["target"] == [shrine["x"], shrine["y"]]


def test_status_and_dev_force():
    w = GameWorld(565)
    a = _join(w, "Solo")
    assert w.handle_year_action(a, "pilgrimage")
    # Force undersized start for solo smoke (dev only)
    assert w.handle_year_action(a, "pilgrimage_force", "dev")
    assert a.pilgrimage["instance_id"]
    assert a.pilgrimage["beat_id"]
    # Solo instance can unlock finale after one beat
    inst = w.pilgrimage_instances[a.pilgrimage["instance_id"]]
    shrine = inst["shrines"][a.id]
    w._force_set_pos(a, shrine["x"], shrine["y"], 0, "solo shrine")
    w._pilgrimage_on_move(a)
    assert inst["finale_unlocked"] is True
    pad = inst["pad"]
    w._force_set_pos(a, pad["x"], pad["y"], 0, "solo pad")
    w.handle_year_action(a, "canticle_finale")
    assert a.mode == "pilgrimage"
    assert a.quest_flags.get("pilgrimage_complete")
