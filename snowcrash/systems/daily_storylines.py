"""Daily news → Metaverse storylines (#51).

Loads original StreetNet / courier allegory beats from JSON and injects them
into the event ticker + Forecast news-arc hook (`attach_news_arc`). Inspiration
headlines live on GitHub issue #51 — never paste article bodies into player strings.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_DIR = Path(__file__).resolve().parent / "data"

KIND_TO_EVENT = {
    "streetnet_broadcast": "broadcast",
    "broadcast": "broadcast",
    "journal": "journal",
    "street_event": "street",
    "street": "street",
    "npc": "npc",
    "job": "job",
}


def _load_daily_storylines_doc() -> Dict[str, Any]:
    path = DATA_DIR / "daily_storylines.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _today_iso(now: Optional[datetime] = None) -> str:
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.date().isoformat()


def _pick_entry(doc: Dict[str, Any], day: str) -> Optional[Dict[str, Any]]:
    entries = list(doc.get("entries") or [])
    for ent in entries:
        if str(ent.get("date") or "") == day:
            return ent
    # Fallback: latest dated entry (keeps servers playable if clock drifts)
    dated = [e for e in entries if e.get("date")]
    if not dated:
        return None
    dated.sort(key=lambda e: str(e.get("date")), reverse=True)
    return dated[0]


class DailyStorylinesMixin:
    """Mixed into YearFeaturesMixin / GameWorld — daily allegory beats (#51)."""

    def _daily_storylines_init(self) -> None:
        self.daily_storylines_defs: Dict[str, Any] = {}
        self.daily_storylines_active: Dict[str, Any] = {
            "date": None,
            "beats": [],
            "fired_ids": [],
        }
        self._daily_storylines_fired: set = set()
        self.reload_daily_storylines(fire=True)

    def reload_daily_storylines(
        self,
        fire: bool = True,
        day: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Hot-reload daily_storylines.json; optionally fire unmatched beats."""
        doc = _load_daily_storylines_doc()
        self.daily_storylines_defs = doc
        target_day = day or _today_iso()
        entry = _pick_entry(doc, target_day)
        beats: List[Dict[str, Any]] = []
        entry_date = target_day
        if entry:
            entry_date = str(entry.get("date") or target_day)
            for raw in entry.get("beats") or []:
                if not isinstance(raw, dict):
                    continue
                bid = str(raw.get("id") or "").strip()
                if not bid:
                    continue
                beats.append(dict(raw))
                beats[-1]["id"] = bid

        self.daily_storylines_active = {
            "date": entry_date,
            "beats": beats,
            "fired_ids": sorted(self._daily_storylines_fired),
        }

        if fire:
            self._daily_storylines_fire_pending()

        return dict(self.daily_storylines_active)

    def _daily_storylines_stamp_geo_only(self, beat: Dict[str, Any]) -> None:
        """Ensure region_id + geo on a beat without re-firing ticker / intensity."""
        rid = self._daily_storylines_resolve_region(beat)
        beat["region_id"] = rid
        if hasattr(self, "attach_news_geo"):
            stamped = self.attach_news_geo(
                {
                    "id": beat.get("id"),
                    "text": beat.get("text") or beat.get("summary") or "",
                    "region_id": rid,
                    "_forecast_bumped": True,  # no soft intensity bump on re-stamp
                },
                region_id=str(rid) if rid else None,
                lat=beat.get("lat"),
                lon=beat.get("lon"),
            )
            if stamped.get("geo"):
                beat["geo"] = dict(stamped["geo"])
                return
        if rid and hasattr(self, "_globe_region"):
            reg = self._globe_region(str(rid)) or {}
            beat["geo"] = {
                "region_id": rid,
                "name": reg.get("name"),
                "lat": reg.get("lat"),
                "lon": reg.get("lon"),
                "continent": reg.get("continent"),
            }

    def _daily_storylines_fire_pending(self) -> None:
        active = getattr(self, "daily_storylines_active", None) or {}
        for beat in list(active.get("beats") or []):
            bid = str(beat.get("id") or "")
            if not bid:
                continue
            if bid in self._daily_storylines_fired:
                # Reload path: keep geo landed without double-firing events
                if not beat.get("geo") or not beat.get("region_id"):
                    self._daily_storylines_stamp_geo_only(beat)
                continue
            self._daily_storylines_fire_beat(beat)
            self._daily_storylines_fired.add(bid)
        self.daily_storylines_active["fired_ids"] = sorted(self._daily_storylines_fired)

    def _daily_storylines_resolve_region(self, beat: Dict[str, Any]) -> Optional[str]:
        """Ensure every beat lands on a globe region (#54 / #51).

        Prefer explicit region_id, then lat/lon nearest snap, then stable hash
        of beat id across city regions (never continents-only).
        """
        rid = beat.get("region_id")
        if rid and hasattr(self, "_globe_region") and self._globe_region(str(rid)):
            return str(rid)
        lat, lon = beat.get("lat"), beat.get("lon")
        if lat is not None and lon is not None and hasattr(self, "_globe_nearest_region"):
            try:
                return self._globe_nearest_region(float(lat), float(lon))
            except (TypeError, ValueError):
                pass
        cities: List[str] = []
        for r in getattr(self, "globe_defs", {}).get("regions", []) or []:
            if not isinstance(r, dict):
                continue
            if r.get("kind") == "city" and r.get("id"):
                cities.append(str(r["id"]))
        if not cities:
            return str(getattr(self, "globe_home_id", "fractured_la"))
        bid = str(beat.get("id") or beat.get("headline") or "beat")
        # Stable day-agnostic pick so reloads do not thrash placement
        idx = sum(ord(c) for c in bid) % len(cities)
        return cities[idx]

    def _daily_storylines_fire_beat(self, beat: Dict[str, Any]) -> Dict[str, Any]:
        text = str(beat.get("text") or beat.get("summary") or "StreetNet allegory beat")
        kind_key = str(beat.get("kind") or "broadcast").strip().lower()
        event_kind = KIND_TO_EVENT.get(kind_key, "broadcast")
        region_id = self._daily_storylines_resolve_region(beat)
        intensity = beat.get("intensity")
        payload = {
            "id": beat.get("id"),
            "kind": kind_key,
            "headline": beat.get("headline"),
            "text": text,
            "summary": beat.get("summary"),
            "region_id": region_id,
            "date": (self.daily_storylines_active or {}).get("date"),
        }

        stamped = payload
        if hasattr(self, "attach_news_arc"):
            stamped = self.attach_news_arc(
                payload,
                intensity=float(intensity) if intensity is not None else None,
                region_id=str(region_id) if region_id else None,
                lat=beat.get("lat"),
                lon=beat.get("lon"),
            )
        elif hasattr(self, "attach_news_geo"):
            stamped = self.attach_news_geo(
                payload,
                region_id=str(region_id) if region_id else None,
                lat=beat.get("lat"),
                lon=beat.get("lon"),
            )
            if hasattr(self, "_push_event"):
                self._push_event(
                    event_kind,
                    text,
                    beat_id=beat.get("id"),
                    region_id=stamped.get("region_id") or region_id,
                )
        else:
            if hasattr(self, "_push_event"):
                self._push_event(event_kind, text, beat_id=beat.get("id"), region_id=region_id)

        # Persist geo onto the live beat so journal / compass / snapshot see it
        landed = stamped.get("region_id") or region_id
        beat["region_id"] = landed
        if stamped.get("geo"):
            beat["geo"] = dict(stamped["geo"])
        elif landed and hasattr(self, "_globe_region"):
            reg = self._globe_region(str(landed)) or {}
            beat["geo"] = {
                "region_id": landed,
                "name": reg.get("name"),
                "lat": reg.get("lat"),
                "lon": reg.get("lon"),
                "continent": reg.get("continent"),
            }

        # Always surface the player-facing beat on the ticker (attach_news_arc
        # already pushes a forecast line; add the allegory line too).
        if hasattr(self, "_push_event"):
            self._push_event(
                event_kind,
                text,
                beat_id=beat.get("id"),
                region_id=landed,
                headline=beat.get("headline"),
            )

        # Hottest beat gets a system chat ping once
        try:
            intensity_f = float(intensity) if intensity is not None else 0.0
        except (TypeError, ValueError):
            intensity_f = 0.0
        active_beats = list((self.daily_storylines_active or {}).get("beats") or [])
        max_i = 0.0
        for b in active_beats:
            try:
                max_i = max(max_i, float(b.get("intensity") or 0.0))
            except (TypeError, ValueError):
                pass
        if intensity_f >= max_i - 1e-9 and hasattr(self, "system_chat"):
            headline = beat.get("headline") or "Daily StreetNet arc"
            where = ""
            if landed and hasattr(self, "_globe_region"):
                rname = (self._globe_region(str(landed)) or {}).get("name") or landed
                where = " @ %s" % rname
            self.system_chat("StreetNet daily%s: %s — %s" % (where, headline, text[:140]))

        return stamped

    def _daily_storylines_snapshot(self, agent=None) -> Dict[str, Any]:
        active = getattr(self, "daily_storylines_active", None) or {}
        beats = []
        for b in active.get("beats") or []:
            beats.append(
                {
                    "id": b.get("id"),
                    "kind": b.get("kind"),
                    "headline": b.get("headline"),
                    "summary": b.get("summary"),
                    "region_id": b.get("region_id"),
                    "geo": b.get("geo"),
                    "fired": str(b.get("id") or "") in self._daily_storylines_fired,
                }
            )
        return {
            "date": active.get("date"),
            "beat_count": len(beats),
            "beats": beats,
            "fired_ids": list(active.get("fired_ids") or sorted(self._daily_storylines_fired)),
            "hooks": {
                "attach_news_arc": hasattr(self, "attach_news_arc"),
                "attach_news_geo": hasattr(self, "attach_news_geo"),
                "forecast": hasattr(self, "forecast_state"),
            },
        }
