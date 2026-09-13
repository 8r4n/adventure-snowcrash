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

    def _daily_storylines_fire_pending(self) -> None:
        active = getattr(self, "daily_storylines_active", None) or {}
        for beat in list(active.get("beats") or []):
            bid = str(beat.get("id") or "")
            if not bid or bid in self._daily_storylines_fired:
                continue
            self._daily_storylines_fire_beat(beat)
            self._daily_storylines_fired.add(bid)
        self.daily_storylines_active["fired_ids"] = sorted(self._daily_storylines_fired)

    def _daily_storylines_fire_beat(self, beat: Dict[str, Any]) -> Dict[str, Any]:
        text = str(beat.get("text") or beat.get("summary") or "StreetNet allegory beat")
        kind_key = str(beat.get("kind") or "broadcast").strip().lower()
        event_kind = KIND_TO_EVENT.get(kind_key, "broadcast")
        region_id = beat.get("region_id")
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
            )
        elif hasattr(self, "attach_news_geo"):
            stamped = self.attach_news_geo(
                payload,
                region_id=str(region_id) if region_id else None,
            )
            if hasattr(self, "_push_event"):
                self._push_event(event_kind, text, beat_id=beat.get("id"), region_id=region_id)
        else:
            if hasattr(self, "_push_event"):
                self._push_event(event_kind, text, beat_id=beat.get("id"), region_id=region_id)

        # Always surface the player-facing beat on the ticker (attach_news_arc
        # already pushes a forecast line; add the allegory line too).
        if hasattr(self, "_push_event"):
            self._push_event(
                event_kind,
                text,
                beat_id=beat.get("id"),
                region_id=stamped.get("region_id") or region_id,
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
            self.system_chat("StreetNet daily: %s — %s" % (headline, text[:140]))

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
