"""Season forecasts — psychohistory-lite street trends (#58)."""

from __future__ import annotations

import time

from snowcrash.mmorpg import GameWorld
from snowcrash.systems.forecasts import (
    FORECAST_METRICS,
    NUDGE_FOCUS_COST,
    WEEK_TICKS,
)


def _join(w: GameWorld, name: str = "OracleCourier"):
    a = w.join(name)
    a.last_action_ts = 0
    a.actor.focus = 20
    a.credits = 50
    return a


def test_three_metrics_in_snapshot():
    w = GameWorld(580)
    a = _join(w)
    s = w.snapshot(a)
    assert "forecast" in s
    fc = s["forecast"]
    assert len(fc["metrics"]) >= 3
    ids = {m["id"] for m in fc["metrics"]}
    for mid in FORECAST_METRICS:
        assert mid in ids
    assert fc["hooks"]["season"] is True
    assert fc["hooks"]["daily_news"] is True
    assert fc["season"]["season_id"] or fc["season"]["id"]


def test_panel_and_status():
    w = GameWorld(581)
    a = _join(w)
    assert w.handle_year_action(a, "forecast", "")
    assert a.forecast["panel_open"] is True
    assert w.handle_year_action(a, "forecast_status", "")
    assert w.handle_year_action(a, "forecast_close", "")
    assert a.forecast["panel_open"] is False


def test_player_nudge_shifts_metric():
    w = GameWorld(582)
    a = _join(w)
    before = float(w.forecast_state["metrics"]["ambush_density"])
    focus0 = int(a.actor.focus)
    season_xp0 = int(a.season.get("xp") or 0)
    assert w.handle_year_action(a, "forecast_nudge", "ambush_density down")
    after = float(w.forecast_state["metrics"]["ambush_density"])
    assert after < before
    assert int(a.actor.focus) == focus0 - NUDGE_FOCUS_COST
    assert int(a.forecast["nudges"]) == 1
    assert a.forecast["last_nudge_metric"] == "ambush_density"
    assert int(a.season.get("xp") or 0) >= season_xp0  # season hook (#33)


def test_nudge_cooldown():
    w = GameWorld(583)
    a = _join(w)
    assert w.handle_year_action(a, "forecast_nudge", "flotilla_pressure up")
    mid = float(w.forecast_state["metrics"]["flotilla_pressure"])
    assert w.handle_year_action(a, "forecast_nudge", "flotilla_pressure up")
    # Second nudge blocked — value unchanged
    assert float(w.forecast_state["metrics"]["flotilla_pressure"]) == mid


def test_attach_news_arc_bumps_intensity_and_geo():
    w = GameWorld(584)
    a = _join(w)
    before = float(w.forecast_state["metrics"]["news_arc_intensity"])
    beat = w.attach_news_arc(
        {"text": "StreetNet allegory: uplink tolls spike after rim blackout."},
        region_id="neo_tokyo",
        intensity=0.08,
    )
    assert beat.get("region_id") == "neo_tokyo"
    assert "geo" in beat
    assert beat["forecast"]["after"] > before
    assert float(w.forecast_state["metrics"]["news_arc_intensity"]) > before
    assert w.forecast_state["news_hooks"]
    s = w.snapshot(a)
    assert s["forecast"]["news_hooks"]


def test_forecast_week_rolls():
    w = GameWorld(585)
    _join(w)
    w.tick = WEEK_TICKS + 5
    w._forecast_ensure_week()
    assert int(w.forecast_state["week"]) >= 2


def test_ambush_weight_tracks_density():
    w = GameWorld(586)
    _join(w)
    w.forecast_state["metrics"]["ambush_density"] = 0.9
    high = w.forecast_ambush_weight()
    w.forecast_state["metrics"]["ambush_density"] = 0.1
    low = w.forecast_ambush_weight()
    assert high > low


def test_invalid_metric_refused():
    w = GameWorld(587)
    a = _join(w)
    before = dict(w.forecast_state["metrics"])
    focus0 = int(a.actor.focus)
    assert w.handle_year_action(a, "forecast_nudge", "not_a_real_metric")
    assert dict(w.forecast_state["metrics"]) == before
    assert int(a.actor.focus) == focus0
    assert int(a.forecast.get("nudges") or 0) == 0


def test_region_hints_stub_and_news_fill():
    w = GameWorld(588)
    a = _join(w)
    s = w.snapshot(a)
    assert "region_hints" in s["forecast"]
    assert isinstance(s["forecast"]["region_hints"], list)
    w.attach_news_arc({"text": "Rim blackout allegory"}, region_id="cont_eu", intensity=0.05)
    s2 = w.snapshot(a)
    assert any(h.get("region_id") == "cont_eu" for h in s2["forecast"]["region_hints"])
