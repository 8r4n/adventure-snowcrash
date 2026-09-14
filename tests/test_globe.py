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


def test_osm_ascii_shard_loads_on_teleport():
    w = GameWorld(5410)
    a = _join(w)
    assert w.handle_year_action(a, "teleport", "neo_tokyo")
    assert a.globe["region_id"] == "neo_tokyo"
    pack = w.globe_shards["neo_tokyo"]
    assert pack.get("shard_source") == "osm_ascii"
    assert pack.get("chunk_path")
    # Landmark glyphs from ASCII pack should appear on the street plane
    gmap = pack["gmap"]
    jx, jy = pack["jackpoint_pos"]
    assert gmap.tiles[jy][jx] == "J"
    s = w.snapshot(a)
    assert s["globe"]["shard_source"] == "osm_ascii"
    assert s["globe"]["zoom"] == "street"
    assert any(r.get("id") == "neo_tokyo" and r.get("has_ascii_shard") for r in s["globe"]["regions"])


def test_berlin_ascii_pilot_and_mapgen_fallback():
    w = GameWorld(5411)
    a = _join(w)
    assert w.handle_year_action(a, "teleport", "berlin_circuit")
    assert w.globe_shards["berlin_circuit"].get("shard_source") == "osm_ascii"
    a.globe["cooldown_until"] = 0
    a.last_action_ts = 0
    # moscow_static has no chunk_path → mapgen
    assert w.handle_year_action(a, "teleport", "moscow_static")
    assert a.globe["region_id"] == "moscow_static"
    assert w.globe_shards["moscow_static"].get("shard_source") == "mapgen"


def test_globe_zoom_ladder():
    w = GameWorld(5412)
    a = _join(w)
    assert w.handle_year_action(a, "globe")
    assert a.globe["panel_open"] is True
    assert a.globe["zoom"] in ("globe", "region")
    assert w.handle_year_action(a, "globe_zoom", "region")
    s = w.snapshot(a)
    assert s["globe"]["zoom"] == "region"
    assert "region" in s["globe"]["zoom_levels"]
    assert w.handle_year_action(a, "globe_zoom", "street")
    s = w.snapshot(a)
    assert s["globe"]["zoom"] == "street"
    assert s["globe"]["panel_open"] is False


def test_globe_search_and_ascii_filter():
    w = GameWorld(5413)
    a = _join(w)
    assert w.handle_year_action(a, "globe_search", "tokyo")
    assert a.globe["search"] == "tokyo"
    hits = w._globe_search_regions("tokyo")
    assert any(r["id"] == "neo_tokyo" for r in hits)
    assert w.handle_year_action(a, "globe_filter", "ascii")
    assert a.globe["filter_ascii"] is True
    ascii_hits = w._globe_search_regions("", ascii_only=True)
    assert len(ascii_hits) >= 6
    ids = {r["id"] for r in ascii_hits}
    for need in ("neo_tokyo", "berlin_circuit", "neo_nyc", "london_fog", "singapore_core", "sydney_reef"):
        assert need in ids
    s = w.snapshot(a)
    assert s["globe"]["search"] == "tokyo"
    assert s["globe"]["filter_ascii"] is True
    assert s["globe"]["ascii_shard_count"] >= 6
    # Full catalog still present in snapshot (UI filters client-side)
    assert len(s["globe"]["regions"]) >= 30


def test_new_ascii_pilots_load_on_teleport():
    w = GameWorld(5414)
    a = _join(w)
    for rid in ("neo_nyc", "london_fog", "singapore_core", "sydney_reef"):
        a.globe["cooldown_until"] = 0
        a.last_action_ts = 0
        a.credits = max(int(a.credits), 200)
        assert w.handle_year_action(a, "teleport", rid)
        assert a.globe["region_id"] == rid
        assert w.globe_shards[rid].get("shard_source") == "osm_ascii"
        assert w.globe_shards[rid].get("chunk_path")


def test_reload_region_defs_drops_stale_shard():
    w = GameWorld(5415)
    a = _join(w)
    assert w.handle_year_action(a, "teleport", "neo_tokyo")
    assert "neo_tokyo" in w.globe_shards
    dropped = w.reload_shard_packs(force=True)
    assert "neo_tokyo" in dropped
    assert "neo_tokyo" not in w.globe_shards
    # Ensure shard rebuilds on next hop
    a.globe["cooldown_until"] = 0
    a.last_action_ts = 0
    a.credits = 200
    # Already in neo_tokyo — force via failsafe home then hop
    w.handle_year_action(a, "globe_recall")
    a.globe["cooldown_until"] = 0
    a.last_action_ts = 0
    assert w.handle_year_action(a, "teleport", "neo_tokyo")
    assert w.globe_shards["neo_tokyo"].get("shard_source") == "osm_ascii"


def test_geo_objective_and_track():
    w = GameWorld(5416)
    w.reload_daily_storylines(fire=True, day="2026-09-13")
    a = _join(w)
    # No payload → globe geo objective can own compass
    objs = w._globe_geo_objectives()
    assert objs
    assert any(o.get("region_id") == "neo_tokyo" for o in objs)
    assert w.handle_year_action(a, "globe_track", "neo_tokyo")
    assert a.globe["tracked_geo_region"] == "neo_tokyo"
    obj = w._quest_objective(a)
    assert obj.get("geo") is True
    assert obj.get("region_id") == "neo_tokyo"
    assert "teleport" in (obj.get("text") or "") or obj.get("cross_region")
    s = w.snapshot(a)
    assert s["globe"]["tracked_geo_region"] == "neo_tokyo"
    assert s["globe"]["geo_objectives"]
    sides = (s.get("journal") or {}).get("side") or []
    assert any(str(x.get("id") or "").startswith("geo_daily_") for x in sides)


def test_globe_preview_and_hop_quote():
    w = GameWorld(5420)
    a = _join(w)
    assert w.handle_year_action(a, "globe_preview", "neo_tokyo")
    assert a.globe["preview_region_id"] == "neo_tokyo"
    s = w.snapshot(a)
    g = s["globe"]
    pv = g["preview"]
    assert pv["id"] == "neo_tokyo"
    assert pv.get("street_flavor")
    assert pv.get("has_ascii_shard") is True
    assert pv.get("landmarks")
    assert pv.get("ascii_strip")
    assert g["credits"] >= 200
    assert g["can_afford_hop"] is True
    assert g["recall_cost_credits"] == max(0, int(g["cost_credits"]) // 2)
    neo = next(r for r in g["regions"] if r["id"] == "neo_tokyo")
    assert neo.get("street_flavor")
    # Credits block
    a.credits = 2
    a.last_action_ts = 0
    card = w._globe_preview_card(a, "berlin_circuit")
    assert card["blocked_reason"] == "credits"
    assert card["hop_ready"] is False
    # Cooldown block after hop
    a.credits = 200
    a.last_action_ts = 0
    assert w.handle_year_action(a, "teleport", "neo_tokyo")
    a.last_action_ts = 0
    card = w._globe_preview_card(a, "berlin_circuit")
    assert card["blocked_reason"] == "cooldown"
    assert w.handle_year_action(a, "globe_preview", "clear")
    assert a.globe["preview_region_id"] is None


def test_news_geo_pins_prefer_beat_lat_lon():
    w = GameWorld(5421)
    # Stamp a beat with explicit lat/lon slightly off region centroid
    beat = w.attach_news_geo(
        {"id": "test_pin", "text": "pin test", "headline": "Pin test"},
        region_id="neo_tokyo",
        lat=35.70,
        lon=139.80,
    )
    assert beat["geo"]["lat"] == 35.70
    # Inject into active daily so geo objectives see it
    w.daily_storylines_active = {
        "date": "2026-09-13",
        "beats": [beat],
        "fired_ids": ["test_pin"],
    }
    objs = w._globe_geo_objectives()
    hit = next(o for o in objs if o.get("beat_id") == "test_pin")
    assert abs(float(hit["lat"]) - 35.70) < 1e-6
    assert abs(float(hit["lon"]) - 139.80) < 1e-6
    assert hit.get("pin_lat") == 35.70
    a = _join(w)
    w.handle_year_action(a, "globe_preview", "neo_tokyo")
    s = w.snapshot(a)
    neo = next(r for r in s["globe"]["regions"] if r["id"] == "neo_tokyo")
    assert neo.get("has_news") is True
    assert neo.get("news_lat") == 35.70
    pv = s["globe"]["preview"]
    assert pv.get("has_news") is True
    assert pv["news"]
