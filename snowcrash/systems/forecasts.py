"""Season forecasts — psychohistory-lite street trends (#58).

Weekly/seasonal ticker: predicted ambush density, Flotilla pressure, and
news-arc intensity. Acting early (nudge) can shift one metric slightly.
Foundation-*inspired* prediction UI only — original StreetNet / Flotilla lore.
Ties into season pass (#33) and daily news geo hook (#51).
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

# Metrics players see / can nudge (0.0 – 1.0)
FORECAST_METRICS = (
    "ambush_density",
    "flotilla_pressure",
    "news_arc_intensity",
)

METRIC_LABELS = {
    "ambush_density": "Ambush density",
    "flotilla_pressure": "Flotilla pressure",
    "news_arc_intensity": "News-arc intensity",
}

METRIC_HINTS = {
    "ambush_density": "Street ambush roll weight — higher = denser hostiles.",
    "flotilla_pressure": "Rim propaganda / Flotilla event weight.",
    "news_arc_intensity": "Daily StreetNet allegory beats (#51) run hotter.",
}

# In-game week length (ticks). Street tick ~ often; ~90 ticks ≈ a “week” beat.
WEEK_TICKS = 90
NUDGE_DELTA = 0.07
NUDGE_COOLDOWN_SEC = 35.0
NUDGE_FOCUS_COST = 2
NUDGE_SEASON_XP = 3
DRIFT_PER_WEEK = 0.04  # natural weekly drift magnitude

DEFAULT_BASELINES = {
    "ambush_density": 0.42,
    "flotilla_pressure": 0.38,
    "news_arc_intensity": 0.35,
}


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _band(v: float) -> str:
    if v < 0.28:
        return "low"
    if v < 0.55:
        return "moderate"
    if v < 0.78:
        return "elevated"
    return "critical"


class ForecastMixin:
    """Mixed into YearFeaturesMixin / GameWorld — psychohistory-lite forecasts."""

    def _forecast_init(self) -> None:
        now = time.time()
        self.forecast_state: Dict[str, Any] = {
            "week": 1,
            "week_started_tick": 0,
            "week_ends_tick": WEEK_TICKS,
            "baselines": dict(DEFAULT_BASELINES),
            "metrics": dict(DEFAULT_BASELINES),
            "nudges": [],  # recent nudge log (world)
            "news_hooks": [],  # recent #51 beats that bumped intensity
            "region_hints": [],  # stub for #51 attach_news_geo / geography
            "season_hook": True,
            "news_hook": True,
            "updated_at": now,
            "headline": "StreetNet psychohistory lattice warming up…",
        }
        self._push_event(
            "broadcast",
            "StreetNet Forecast lattice online — ambush / Flotilla / news-arc trends (#58).",
        )

    def _forecast_bootstrap_agent(self, agent) -> None:
        fc = getattr(agent, "forecast", None)
        if not isinstance(fc, dict):
            fc = {}
        fc.setdefault("panel_open", False)
        fc.setdefault("nudges", 0)
        fc.setdefault("last_nudge_metric", None)
        fc.setdefault("last_nudge_at", 0.0)
        fc.setdefault("last_feedback", None)
        agent.forecast = fc

    def _forecast_feedback(self, agent, kind: str, text: str) -> None:
        self._forecast_bootstrap_agent(agent)
        agent.forecast["last_feedback"] = {
            "kind": kind,
            "text": text,
            "t": time.time(),
        }
        agent.log(text)

    def _forecast_season_context(self) -> Dict[str, Any]:
        """Tie into season pass (#33)."""
        defs = getattr(self, "season_defs", None) or {}
        return {
            "season_id": defs.get("season_id"),
            "season_name": defs.get("name"),
            "max_tier": int(defs.get("max_tier", 12) or 12),
            "xp_per_tier": int(defs.get("xp_per_tier", 50) or 50),
        }

    def _forecast_ensure_week(self) -> None:
        st = getattr(self, "forecast_state", None)
        if not isinstance(st, dict):
            self._forecast_init()
            st = self.forecast_state
        tick = int(getattr(self, "tick", 0) or 0)
        while tick >= int(st.get("week_ends_tick", WEEK_TICKS)):
            self._forecast_roll_week()

    def _forecast_roll_week(self) -> None:
        """Advance weekly forecast — slight natural drift + settle nudges."""
        st = self.forecast_state
        tick = int(getattr(self, "tick", 0) or 0)
        rng = getattr(self, "rng", None)
        metrics = dict(st.get("metrics") or DEFAULT_BASELINES)
        baselines = dict(st.get("baselines") or DEFAULT_BASELINES)
        for key in FORECAST_METRICS:
            base = float(baselines.get(key, DEFAULT_BASELINES[key]))
            cur = float(metrics.get(key, base))
            # Drift toward a new baseline roll
            if rng is not None:
                target = _clamp01(base + (rng.random() - 0.5) * 0.22)
            else:
                target = base
            baselines[key] = target
            # Pull current halfway toward target, keep some nudge residue
            metrics[key] = _clamp01(cur * 0.55 + target * 0.45)
        st["baselines"] = baselines
        st["metrics"] = metrics
        st["week"] = int(st.get("week", 1) or 1) + 1
        st["week_started_tick"] = tick
        st["week_ends_tick"] = tick + WEEK_TICKS
        st["updated_at"] = time.time()
        st["headline"] = self._forecast_compose_headline()
        self._push_event(
            "forecast",
            "Forecast week %d — %s" % (st["week"], st["headline"]),
        )

    def _forecast_compose_headline(self) -> str:
        m = (self.forecast_state or {}).get("metrics") or {}
        amb = _band(float(m.get("ambush_density", 0.4)))
        flo = _band(float(m.get("flotilla_pressure", 0.4)))
        news = _band(float(m.get("news_arc_intensity", 0.4)))
        parts = [
            "ambush %s" % amb,
            "Flotilla %s" % flo,
            "news-arc %s" % news,
        ]
        return "Street trends: " + " · ".join(parts)

    def _tick_forecasts(self) -> None:
        self._forecast_ensure_week()
        # Soft ambient ticker every ~45 ticks when Flotilla pressure high
        st = self.forecast_state
        tick = int(getattr(self, "tick", 0) or 0)
        if tick > 0 and tick % 45 == 0:
            pressure = float((st.get("metrics") or {}).get("flotilla_pressure", 0))
            if pressure >= 0.62:
                msg = (
                    "Forecast lattice: Flotilla pressure elevated — rim propaganda wash likely."
                    if pressure < 0.8
                    else "Forecast lattice: Flotilla pressure critical — expect signal storms on the rim."
                )
                self._push_event("forecast", msg)
                if hasattr(self, "system_chat") and pressure >= 0.8:
                    self.system_chat(msg)

    def forecast_ambush_weight(self) -> float:
        """Multiplier for street ambush branch (1.0 = baseline)."""
        self._forecast_ensure_week()
        dens = float(
            (self.forecast_state.get("metrics") or {}).get("ambush_density", 0.42)
        )
        # Map 0..1 → ~0.55..1.55 so high density favors ambushes
        return 0.55 + dens

    def forecast_flotilla_weight(self) -> float:
        self._forecast_ensure_week()
        p = float(
            (self.forecast_state.get("metrics") or {}).get("flotilla_pressure", 0.38)
        )
        return 0.55 + p

    def forecast_news_weight(self) -> float:
        self._forecast_ensure_week()
        n = float(
            (self.forecast_state.get("metrics") or {}).get("news_arc_intensity", 0.35)
        )
        return 0.5 + n

    def attach_news_arc(
        self,
        beat: Optional[Dict[str, Any]] = None,
        intensity: Optional[float] = None,
        region_id: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Hook for daily news (#51): stamp geo (via globe) + bump news-arc intensity.

        Prefer calling this from the daily storyline pipeline. Returns the beat
        with forecast + geo fields attached.
        """
        self._forecast_ensure_week()
        out: Dict[str, Any] = dict(beat or {})
        # Geo stamp when globe mixin present
        if hasattr(self, "attach_news_geo"):
            out["_forecast_bumped"] = True  # skip soft geo-only bump
            out = self.attach_news_geo(out, region_id=region_id, lat=lat, lon=lon)
            out.pop("_forecast_bumped", None)
        elif region_id:
            out["region_id"] = region_id

        bump = intensity
        if bump is None:
            bump = 0.04 + 0.03 * float(self.forecast_news_weight() - 0.5)
        bump = max(0.02, min(0.12, float(bump)))
        metrics = self.forecast_state.setdefault("metrics", dict(DEFAULT_BASELINES))
        before = float(metrics.get("news_arc_intensity", 0.35))
        after = _clamp01(before + bump)
        metrics["news_arc_intensity"] = after
        self.forecast_state["updated_at"] = time.time()
        self.forecast_state["headline"] = self._forecast_compose_headline()

        hook = {
            "t": time.time(),
            "text": (out.get("text") or out.get("summary") or "StreetNet allegory beat")[:120],
            "region_id": out.get("region_id"),
            "bump": round(bump, 3),
            "news_arc_intensity": round(after, 3),
        }
        hooks: List[Dict[str, Any]] = list(self.forecast_state.get("news_hooks") or [])
        hooks.append(hook)
        self.forecast_state["news_hooks"] = hooks[-12:]
        rid = out.get("region_id")
        if rid:
            hints = list(self.forecast_state.get("region_hints") or [])
            entry = {
                "region_id": rid,
                "t": time.time(),
                "lat": out.get("lat"),
                "lon": out.get("lon"),
            }
            hints = [h for h in hints if h.get("region_id") != rid] + [entry]
            self.forecast_state["region_hints"] = hints[-8:]
        out["forecast"] = {
            "metric": "news_arc_intensity",
            "before": round(before, 3),
            "after": round(after, 3),
            "bump": round(bump, 3),
        }
        self._push_event(
            "forecast",
            "News-arc intensity %+0.2f → %.0f%% (%s)"
            % (bump, after * 100, hook["text"][:48]),
        )
        return out


    def _forecast_soft_influence(self, agent, metric: str, delta: float, reason: str = "") -> None:
        """Tiny ambient drift from gameplay (neon dash / ICE / corp contest). Not OP."""
        self._forecast_ensure_week()
        key = (metric or "").strip().lower()
        if key not in FORECAST_METRICS:
            return
        metrics = self.forecast_state.setdefault("metrics", dict(DEFAULT_BASELINES))
        before = float(metrics.get(key, DEFAULT_BASELINES[key]))
        # Cap soft deltas hard so they cannot stack into OP swings
        d = max(-0.04, min(0.04, float(delta)))
        after = _clamp01(before + d)
        if abs(after - before) < 1e-6:
            return
        metrics[key] = after
        self.forecast_state["updated_at"] = time.time()
        self.forecast_state["headline"] = self._forecast_compose_headline()
        if reason and agent is not None and hasattr(agent, "log"):
            fc = getattr(agent, "forecast", None)
            if isinstance(fc, dict) and fc.get("panel_open"):
                agent.log(
                    "Forecast soft-shift: %s %+0.0f%% (%s)."
                    % (METRIC_LABELS.get(key, key), (after - before) * 100, reason)
                )

    def _forecast_nudge_efficacy(self, agent) -> float:
        """Season tier (#33) slightly improves early intervention."""
        season = getattr(agent, "season", None) or {}
        tier = int(season.get("tier") or 0)
        return 1.0 + min(0.25, tier * 0.02)

    def _forecast_nudge(self, agent, metric: str, direction: str = "down") -> bool:
        self._forecast_bootstrap_agent(agent)
        self._forecast_ensure_week()
        key = (metric or "").strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "ambush": "ambush_density",
            "density": "ambush_density",
            "ambush_density": "ambush_density",
            "flotilla": "flotilla_pressure",
            "pressure": "flotilla_pressure",
            "flotilla_pressure": "flotilla_pressure",
            "news": "news_arc_intensity",
            "arc": "news_arc_intensity",
            "news_arc": "news_arc_intensity",
            "news_arc_intensity": "news_arc_intensity",
            "intensity": "news_arc_intensity",
        }
        key = aliases.get(key, key)
        if key not in FORECAST_METRICS:
            self._forecast_feedback(
                agent,
                "info",
                "Nudge which metric? ambush_density | flotilla_pressure | news_arc_intensity "
                "(optional: up|down).",
            )
            return True

        now = time.time()
        last = float(agent.forecast.get("last_nudge_at") or 0)
        remain = NUDGE_COOLDOWN_SEC - (now - last)
        if remain > 0:
            self._forecast_feedback(
                agent,
                "warn",
                "Forecast nudge cooling down — %.0fs left (act early next week)." % remain,
            )
            return True

        actor = getattr(agent, "actor", None)
        focus = int(getattr(actor, "focus", 0) or 0) if actor else 0
        if focus < NUDGE_FOCUS_COST:
            self._forecast_feedback(
                agent,
                "warn",
                "Need %d Focus to push the forecast lattice (have %d)."
                % (NUDGE_FOCUS_COST, focus),
            )
            return True
        if actor is not None:
            actor.focus = focus - NUDGE_FOCUS_COST

        direction = (direction or "down").strip().lower()
        if direction in ("up", "+", "raise", "increase", "hot"):
            sign = 1.0
            dir_label = "up"
        else:
            sign = -1.0
            dir_label = "down"

        eff = self._forecast_nudge_efficacy(agent)
        delta = NUDGE_DELTA * eff * sign
        metrics = self.forecast_state.setdefault("metrics", dict(DEFAULT_BASELINES))
        before = float(metrics.get(key, DEFAULT_BASELINES[key]))
        after = _clamp01(before + delta)
        metrics[key] = after
        self.forecast_state["updated_at"] = now
        self.forecast_state["headline"] = self._forecast_compose_headline()

        agent.forecast["nudges"] = int(agent.forecast.get("nudges") or 0) + 1
        agent.forecast["last_nudge_metric"] = key
        agent.forecast["last_nudge_at"] = now

        entry = {
            "t": now,
            "agent": getattr(agent, "name", "?"),
            "metric": key,
            "direction": dir_label,
            "before": round(before, 3),
            "after": round(after, 3),
            "delta": round(after - before, 3),
        }
        nudges = list(self.forecast_state.get("nudges") or [])
        nudges.append(entry)
        self.forecast_state["nudges"] = nudges[-20:]

        if hasattr(self, "_grant_season_xp"):
            self._grant_season_xp(agent, NUDGE_SEASON_XP)

        label = METRIC_LABELS.get(key, key)
        self._forecast_feedback(
            agent,
            "pass",
            "Early intervention: nudged %s %s (%.0f%% → %.0f%%). Season XP +%d."
            % (label, dir_label, before * 100, after * 100, NUDGE_SEASON_XP),
        )
        self._push_event(
            "forecast",
            "%s nudged %s %s." % (getattr(agent, "name", "Courier"), label, dir_label),
            x=getattr(getattr(agent, "actor", None), "x", None),
            y=getattr(getattr(agent, "actor", None), "y", None),
        )
        return True

    def _forecast_snapshot(self, agent) -> Dict[str, Any]:
        self._forecast_bootstrap_agent(agent)
        self._forecast_ensure_week()
        st = self.forecast_state
        metrics = st.get("metrics") or {}
        tick = int(getattr(self, "tick", 0) or 0)
        ends = int(st.get("week_ends_tick", tick + WEEK_TICKS))
        season_ctx = self._forecast_season_context()
        season_agent = getattr(agent, "season", None) or {}
        now = time.time()
        cd = max(0.0, NUDGE_COOLDOWN_SEC - (now - float(agent.forecast.get("last_nudge_at") or 0)))
        rows = []
        for key in FORECAST_METRICS:
            v = float(metrics.get(key, DEFAULT_BASELINES.get(key, 0.4)))
            rows.append(
                {
                    "id": key,
                    "label": METRIC_LABELS[key],
                    "hint": METRIC_HINTS[key],
                    "value": round(v, 3),
                    "pct": int(round(v * 100)),
                    "band": _band(v),
                    "baseline": round(
                        float((st.get("baselines") or {}).get(key, v)), 3
                    ),
                }
            )
        return {
            "week": int(st.get("week") or 1),
            "week_ticks_left": max(0, ends - tick),
            "week_length": WEEK_TICKS,
            "headline": st.get("headline") or self._forecast_compose_headline(),
            "metrics": rows,
            "metric_ids": list(FORECAST_METRICS),
            "nudge_cooldown": round(cd, 1),
            "nudge_focus_cost": NUDGE_FOCUS_COST,
            "nudge_delta": NUDGE_DELTA,
            "player_nudges": int(agent.forecast.get("nudges") or 0),
            "last_nudge_metric": agent.forecast.get("last_nudge_metric"),
            "last_feedback": agent.forecast.get("last_feedback"),
            "panel_open": bool(agent.forecast.get("panel_open")),
            "recent_nudges": list(st.get("nudges") or [])[-5:],
            "news_hooks": list(st.get("news_hooks") or [])[-5:],
            "season": {
                **season_ctx,
                "tier": int(season_agent.get("tier") or 0),
                "xp": int(season_agent.get("xp") or 0),
                "id": season_agent.get("id") or season_ctx.get("season_id"),
            },
            "region_hints": list(st.get("region_hints") or []),
            "hooks": {
                "season": True,
                "daily_news": True,
                "attach_news_arc": True,
                "attach_news_geo": True,
            },
            "hint": (
                "Dock Forecast · Shift+F · nudge <metric> [up|down] — early action "
                "shifts street outcomes slightly. Season tier improves nudge efficacy."
            ),
        }

    def _forecast_action(self, agent, action: str, arg: str = "") -> bool:
        self._forecast_bootstrap_agent(agent)
        a = (action or "").strip().lower()
        arg = (arg or "").strip()
        arg_l = arg.lower()
        parts = arg_l.split()

        if a in (
            "forecast",
            "forecasts",
            "forecast_panel",
            "open_forecast",
            "psychohistory",
            "street_trends",
        ):
            agent.forecast["panel_open"] = True
            snap = self._forecast_snapshot(agent)
            bits = [
                "%s %d%% [%s]" % (m["label"], m["pct"], m["band"]) for m in snap["metrics"]
            ]
            agent.log(
                "Forecast week %d — %s | %s"
                % (snap["week"], snap["headline"], " · ".join(bits))
            )
            return True

        if a in ("forecast_close", "close_forecast"):
            agent.forecast["panel_open"] = False
            agent.log("Forecast panel closed.")
            return True

        if a in ("forecast_status", "trend_status", "psychohistory_status"):
            snap = self._forecast_snapshot(agent)
            agent.log(
                "Forecast w%d · ticks left %d · nudges %d · cd %.0fs · %s"
                % (
                    snap["week"],
                    snap["week_ticks_left"],
                    snap["player_nudges"],
                    snap["nudge_cooldown"],
                    snap["headline"],
                )
            )
            return True

        if a in ("forecast_nudge", "nudge_forecast", "nudge", "trend_nudge"):
            # arg: "<metric> [up|down]"
            if not parts:
                self._forecast_feedback(
                    agent,
                    "info",
                    "Usage: forecast_nudge <ambush_density|flotilla_pressure|news_arc_intensity> [up|down]",
                )
                return True
            metric = parts[0]
            direction = parts[1] if len(parts) > 1 else "down"
            return self._forecast_nudge(agent, metric, direction)

        # Convenience: forecast_nudge_ambush / etc. via action name
        if a.startswith("nudge_"):
            rest = a[len("nudge_") :]
            direction = parts[0] if parts else "down"
            return self._forecast_nudge(agent, rest, direction)

        return False
