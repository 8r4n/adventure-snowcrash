# Daily news → Metaverse storylines

Issue **#51** (related **#54** geo, **#58** forecasts). Each morning an agent remixed real-world headlines into **original** StreetNet / courier allegory beats — never pasted news copy.

## Source of truth

- Data: `snowcrash/systems/data/daily_storylines.json`
- Runtime: `snowcrash/systems/daily_storylines.py` (`DailyStorylinesMixin`)
- Hooks: `ForecastMixin.attach_news_arc` + `GlobeMixin.attach_news_geo`

## Shape

```json
{
  "version": 1,
  "entries": [
    {
      "date": "YYYY-MM-DD",
      "beats": [
        {
          "id": "unique-id",
          "kind": "streetnet_broadcast | journal | street_event",
          "region_id": "neo_tokyo",
          "intensity": 0.05,
          "headline": "Short title",
          "text": "Player-facing allegory line",
          "summary": "One-line summary"
        }
      ]
    }
  ]
}
```

On world init (and `reload_daily_storylines()`), today's entry fires each beat once: **region resolve** (explicit `region_id` → lat/lon nearest → stable city hash), geo stamp via `attach_news_arc` / `attach_news_geo`, news-arc intensity bump, event ticker line, hottest beat → `system_chat` (includes region name). Live beats keep `region_id` + `geo` for journal / globe compass (`globe_track`).

## Snapshot

`daily_storylines`: `{ date, beat_count, beats[], fired_ids[], hooks }`.


Latest shipped calendar day: **2026-09-24** (Civic stats scrape / Query-relay forge / Rack-permit freeze).

## Ops

Append a new `entries[]` object for each calendar day. Dedup against the last 7 days of comments on #51 before shipping.