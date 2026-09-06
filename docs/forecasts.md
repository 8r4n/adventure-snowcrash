# Season Forecasts — psychohistory-lite street trends

Issue **#58** (parent campaign **#42** · related **#33** **#51** **#14**). Weekly/seasonal **forecast ticker** for predicted ambush density, Flotilla pressure, and news-arc intensity. Acting early (**nudge**) can shift one metric slightly. Inspired by long-arc societal prediction tropes as a **playable UI** — original StreetNet / Flotilla lore only (no copied math or prose).

Source of truth: `snowcrash/systems/forecasts.py` (`ForecastMixin`), mixed into `YearFeaturesMixin` / `GameWorld`. Web dock **Forecast** · **Shift+F**.

## Metrics (≥3)

| Metric | Meaning | Street effect |
|--------|---------|---------------|
| **Ambush density** | Predicted hostile street-event weight | Biases `_tick_street_events` toward ambushes |
| **Flotilla pressure** | Rim propaganda / signal pressure | Biases broadcasts toward Flotilla flavor; ambient ticker when elevated |
| **News-arc intensity** | Allegory beat heat from daily news | Raised by `attach_news_arc` / soft bump from `attach_news_geo` (#51) |

Values are **0–100%** with bands: low · moderate · elevated · critical. A new **forecast week** rolls every **90 ticks** with mild natural drift.

## Player nudge (early intervention)

Players can nudge **one metric** up or down:

| Input | Effect |
|-------|--------|
| Dock **Forecast** · **Shift+F** | Open panel |
| `forecast` / `psychohistory` | Open + log ticker |
| `forecast_nudge ambush_density down` | Spend **2 Focus**, shift metric (~7%, season tier improves efficacy) |
| `forecast_nudge flotilla_pressure up` | Same, raise Flotilla pressure |
| `forecast_nudge news_arc_intensity down` | Soften news-arc heat |
| `nudge_ambush` / `nudge_flotilla` / `nudge_news` | Shortcuts |
| `forecast_status` | Week / cooldown / headline |
| `forecast_close` | Close panel |

Cooldown **~35s**. Grants a little **season XP** (#33). Toast + event ticker on success.

## Season hook (#33)

Snapshot embeds current season id / name / tier / xp. Higher season tier slightly improves nudge efficacy. Nudges call `_grant_season_xp`.

## Daily news hook (#51)

```python
# Preferred — geo stamp + meaningful intensity bump
beat = world.attach_news_arc(
    {"text": "StreetNet allegory beat..."},
    region_id="neo_tokyo",  # or lat=..., lon=...
    intensity=0.05,         # optional
)

# Geo-only path still soft-bumps intensity when ForecastMixin is live
beat = world.attach_news_geo({"text": "..."}, region_id="neo_tokyo")
```

Recent news hooks appear in the Forecast panel.

## Snapshot (`forecast`)

| Field | Meaning |
|-------|---------|
| `week` / `week_ticks_left` | Forecast week clock |
| `headline` | Human-readable trend line |
| `metrics[]` | id, label, pct, band, hint, baseline |
| `nudge_cooldown` / `nudge_focus_cost` | Gate for early intervention |
| `player_nudges` / `last_nudge_metric` | Per-courier counters |
| `news_hooks[]` / `recent_nudges[]` | Recent #51 / nudge log |
| `season` | Season pass context (#33) |
| `hooks` | `{season, daily_news, attach_news_arc}` |
| `last_feedback` | `{kind, text, t}` for toasts |

## Web UI

Dock **Forecast** · metric bars with **− / +** nudge · season + news hook footer · **Shift+F**.

## Design notes

- Call it **StreetNet Forecast** / **psychohistory-lite** — never trademarked foundation/math names in player strings.
- Nudges are intentionally small; they bias odds, they do not delete danger.
- Ambush spawn still respects spawn-fairness (no ambush on fresh / shielded / on-pad couriers).
