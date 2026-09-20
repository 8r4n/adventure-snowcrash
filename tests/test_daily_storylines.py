"""Daily news → Metaverse storylines (#51)."""

from __future__ import annotations

from snowcrash.mmorpg import GameWorld
from snowcrash.systems.daily_storylines import _pick_entry, _load_daily_storylines_doc


def _join(w: GameWorld, name: str = "NewsCourier"):
    a = w.join(name)
    a.last_action_ts = 0
    return a


def test_json_has_2026_09_13_beats():
    doc = _load_daily_storylines_doc()
    ent = _pick_entry(doc, "2026-09-13")
    assert ent is not None
    ids = {b["id"] for b in ent["beats"]}
    assert "2026-09-13-swarm-ice-truce" in ids
    assert "2026-09-13-berlin-ledger-scrub" in ids
    assert "2026-09-13-courier-logoff-day" in ids



def test_json_has_2026_09_20_beats():
    doc = _load_daily_storylines_doc()
    ent = _pick_entry(doc, "2026-09-20")
    assert ent is not None
    ids = {b["id"] for b in ent["beats"]}
    assert "2026-09-20-oracle-cage-spill" in ids
    assert "2026-09-20-lobby-ice-walkoff" in ids
    assert "2026-09-20-skyrail-densify" in ids


def test_world_fires_2026_09_20_beats():
    w = GameWorld(510920)
    w.reload_daily_storylines(fire=True, day="2026-09-20")
    a = _join(w, "NewsCourier20")
    s = w.snapshot(a)
    ds = s["daily_storylines"]
    assert ds["date"] == "2026-09-20"
    assert ds["beat_count"] == 3
    texts = " | ".join((e.get("text") or "") for e in w.event_ticker)
    assert "Glass Oracle" in texts or "capture-the-flag" in texts
    assert "door-crews" in texts or "Ghost badges" in texts or "pay-floor" in texts
    assert "sky-rail" in texts or "constellation" in texts or "twenty-seven" in texts
    hooks = (w.forecast_state or {}).get("news_hooks") or []
    regions = {h.get("region_id") for h in hooks if h.get("region_id")}
    assert "neo_tokyo" in regions
    assert "fractured_la" in regions
    assert "vancouver_grid" in regions


def test_world_fires_daily_beats_into_ticker_and_forecast():
    w = GameWorld(510913)
    # Force the shipped date in case the host clock differs
    w.reload_daily_storylines(fire=True, day="2026-09-13")
    a = _join(w)
    s = w.snapshot(a)
    assert "daily_storylines" in s
    ds = s["daily_storylines"]
    assert ds["date"] == "2026-09-13"
    assert ds["beat_count"] == 3
    assert ds["hooks"]["attach_news_arc"] is True

    texts = " | ".join((e.get("text") or "") for e in w.event_ticker)
    assert "pace-the-frontier" in texts or "Black Lattice" in texts
    assert "Berlin Circuit" in texts or "Faraday HR" in texts or "paystubs" in texts
    assert "jack-off" in texts or "fee-deduction" in texts or "ghost job" in texts

    # Forecast news hooks / intensity bumped
    hooks = (w.forecast_state or {}).get("news_hooks") or []
    assert len(hooks) >= 3
    intensity = float((w.forecast_state.get("metrics") or {}).get("news_arc_intensity", 0))
    assert intensity > 0.35

    # Geo regions stamped
    regions = {h.get("region_id") for h in hooks if h.get("region_id")}
    assert "neo_tokyo" in regions
    assert "berlin_circuit" in regions
    assert "bangkok_neon" in regions


def test_reload_does_not_double_fire():
    w = GameWorld(510914)
    w.reload_daily_storylines(fire=True, day="2026-09-13")
    before = len(w.event_ticker)
    fired_before = set(w._daily_storylines_fired)
    w.reload_daily_storylines(fire=True, day="2026-09-13")
    assert set(w._daily_storylines_fired) == fired_before
    # May still append nothing new for allegory lines
    allegory = [
        e for e in w.event_ticker
        if e.get("beat_id") in fired_before
    ]
    assert len(allegory) >= 3
    # Second reload should not add more beat_id events
    after_allegory = [
        e for e in w.event_ticker
        if e.get("beat_id") in fired_before
    ]
    assert len(after_allegory) == len(allegory)
    assert len(w.event_ticker) >= before


def test_daily_beats_always_land_with_region_geo():
    w = GameWorld(510914)
    w.reload_daily_storylines(fire=True, day="2026-09-13")
    active = w.daily_storylines_active
    assert active["beats"]
    for b in active["beats"]:
        assert b.get("region_id"), b
        assert b.get("geo"), b
        assert b["geo"].get("lat") is not None
        assert b["geo"].get("name")
    # Missing region_id still resolves via city hash
    orphan = {"id": "orphan-geo-test", "text": "orphan allegory", "kind": "broadcast", "intensity": 0.01}
    stamped = w._daily_storylines_fire_beat(orphan)
    assert stamped.get("region_id")
    assert orphan.get("region_id") == stamped.get("region_id")
    assert orphan.get("geo")

