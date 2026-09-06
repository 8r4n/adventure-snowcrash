"""Globe map zoom-out + region teleport (#54)."""

from __future__ import annotations

from snowcrash.mmorpg import GameWorld


def _join(w: GameWorld, name: str = "GlobeHop"):
    a = w.join(name)
    a.last_action_ts = 0
    a.credits = max(int(a.credits), 200)
    return a


def test_regions_cover_earth_and_snapshot():
    w = GameWorld(5401)
    a = _join(w)
    assert w.handle_year_action(a, "globe")
    s = w.snapshot(a)
    g = s["globe"]
    assert g["panel_open"] is True
    assert g["news_geo_hook"] is True
    assert g["region_id"] == w.globe_home_id
    assert len(g["regions"]) >= 30
    continents = {r["continent"] for r in g["regions"]}
    for need in ("na", "eu", "af", "ea", "oc", "antarctica"):
        assert need in continents
    kinds = {r["kind"] for r in g["regions"]}
    assert "city" in kinds and "continent" in kinds


def test_teleport_lands_on_shard_map():
    w = GameWorld(5402)
    a = _join(w)
    home_seed = w.seed
    assert w.handle_year_action(a, "teleport", "neo_tokyo")
    assert a.globe["region_id"] == "neo_tokyo"
    assert "neo_tokyo" in w.globe_shards
    shard_seed = w.globe_shards["neo_tokyo"]["seed"]
    assert shard_seed != home_seed
    s = w.snapshot(a)
    assert s["globe"]["region_id"] == "neo_tokyo"
    assert s["globe"]["shard_seed"] == shard_seed
    x0, y0 = a.actor.x, a.actor.y
    a.last_action_ts = 0
    w.handle_action(a, "forward")
    assert a.globe["region_id"] == "neo_tokyo"
    assert a.credits < 200


def test_teleport_cooldown_and_cost():
    w = GameWorld(5403)
    a = _join(w)
    a.credits = 10
    assert w.handle_year_action(a, "teleport", "london_fog")
    assert a.globe["region_id"] == w.globe_home_id
    a.credits = 100
    a.last_action_ts = 0
    assert w.handle_year_action(a, "teleport", "london_fog")
    assert a.globe["region_id"] == "london_fog"
    before = a.credits
    a.last_action_ts = 0
    w.handle_year_action(a, "teleport", "neo_tokyo")
    assert a.globe["region_id"] == "london_fog"
    assert a.credits == before


def test_recall_and_failsafe():
    w = GameWorld(5404)
    a = _join(w)
    w.handle_year_action(a, "teleport", "sydney_reef")
    a.globe["cooldown_until"] = 0
    a.last_action_ts = 0
    w.handle_year_action(a, "globe_recall")
    assert a.globe["region_id"] == w.globe_home_id
    a.globe["cooldown_until"] = 0
    a.last_action_ts = 0
    w.handle_year_action(a, "teleport", "neo_tokyo")
    a.last_action_ts = 0
    w.handle_year_action(a, "globe_failsafe")
    assert a.globe["region_id"] in w.globe_regions


def test_attach_news_geo_hook():
    w = GameWorld(5405)
    beat = w.attach_news_geo({"text": "allegory"}, region_id="neo_tokyo")
    assert beat["region_id"] == "neo_tokyo"
    assert beat["geo"]["lat"]
    assert beat["geo"]["name"]
    near = w.attach_news_geo({}, lat=35.68, lon=139.69)
    assert near["region_id"] == "neo_tokyo"
