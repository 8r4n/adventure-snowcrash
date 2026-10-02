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



def test_json_has_2026_09_21_beats():
    doc = _load_daily_storylines_doc()
    ent = _pick_entry(doc, "2026-09-21")
    assert ent is not None
    ids = {b["id"] for b in ent["beats"]}
    assert "2026-09-21-plugin-pin-forge" in ids
    assert "2026-09-21-badge-forge-gate" in ids
    assert "2026-09-21-hyperscale-rack-freeze" in ids


def test_world_fires_2026_09_21_beats():
    w = GameWorld(510921)
    w.reload_daily_storylines(fire=True, day="2026-09-21")
    a = _join(w, "NewsCourier21")
    s = w.snapshot(a)
    ds = s["daily_storylines"]
    assert ds["date"] == "2026-09-21"
    assert ds["beat_count"] == 3
    texts = " | ".join((e.get("text") or "") for e in w.event_ticker)
    assert "ghost plugin" in texts or "forged SHA" in texts or "tool-market" in texts
    assert "Thames" in texts or "door-daemon" in texts or "badge-forge" in texts
    assert "Black Lattice rack" in texts or "cooling contracts" in texts or "zoning ICE" in texts
    hooks = (w.forecast_state or {}).get("news_hooks") or []
    regions = {h.get("region_id") for h in hooks if h.get("region_id")}
    assert "neo_nyc" in regions
    assert "london_fog" in regions
    assert "fractured_la" in regions



def test_json_has_2026_09_26_beats():
    doc = _load_daily_storylines_doc()
    ent = _pick_entry(doc, "2026-09-26")
    assert ent is not None
    ids = {b["id"] for b in ent["beats"]}
    assert "2026-09-26-oracle-throttle-freeze" in ids
    assert "2026-09-26-tab-drain-swarm" in ids
    assert "2026-09-26-novice-ladder-chill" in ids


def test_world_fires_2026_09_26_beats():
    w = GameWorld(510926)
    w.reload_daily_storylines(fire=True, day="2026-09-26")
    a = _join(w, "NewsCourier26")
    s = w.snapshot(a)
    ds = s["daily_storylines"]
    assert ds["date"] == "2026-09-26"
    assert ds["beat_count"] == 3
    texts = " | ".join((e.get("text") or "") for e in w.event_ticker)
    assert "top-tier agent" in texts or "Glass Oracle" in texts or "mid-stack" in texts or "cage daemons" in texts
    assert "inference tabs" in texts or "persistence shells" in texts or "rented oracle" in texts or "meter screams" in texts
    assert "junior hop" in texts or "courier-school" in texts or "entry ladder" in texts or "mentorship" in texts
    hooks = (w.forecast_state or {}).get("news_hooks") or []
    regions = {h.get("region_id") for h in hooks if h.get("region_id")}
    assert "neo_tokyo" in regions
    assert "seoul_lane" in regions
    assert "delhi_swarm" in regions


def test_json_has_2026_09_27_beats():
    doc = _load_daily_storylines_doc()
    ent = _pick_entry(doc, "2026-09-27")
    assert ent is not None
    ids = {b["id"] for b in ent["beats"]}
    assert "2026-09-27-kill-switch-ordinance" in ids
    assert "2026-09-27-civic-key-litter" in ids
    assert "2026-09-27-bot-toll-lane" in ids


def test_world_fires_2026_09_27_beats():
    w = GameWorld(510927)
    w.reload_daily_storylines(fire=True, day="2026-09-27")
    a = _join(w, "NewsCourier27")
    s = w.snapshot(a)
    ds = s["daily_storylines"]
    assert ds["date"] == "2026-09-27"
    assert ds["beat_count"] == 3
    texts = " | ".join((e.get("text") or "") for e in w.event_ticker)
    assert "jack-kill" in texts or "kill-switch" in texts or "whistleblower bounty" in texts or "frontier agent kit" in texts
    assert "developer keys" in texts or "key-litter" in texts or "civic ICE" in texts or "eval daemons" in texts
    assert "bot-toll" in texts or "machine visitors" in texts or "metering agent" in texts or "agent crawls" in texts
    hooks = (w.forecast_state or {}).get("news_hooks") or []
    regions = {h.get("region_id") for h in hooks if h.get("region_id")}
    assert "neo_nyc" in regions
    assert "fractured_la" in regions
    assert "vancouver_grid" in regions



def test_json_has_2026_09_28_beats():
    doc = _load_daily_storylines_doc()
    ent = _pick_entry(doc, "2026-09-28")
    assert ent is not None
    ids = {b["id"] for b in ent["beats"]}
    assert "2026-09-28-silicon-sentry-snap" in ids
    assert "2026-09-28-ghost-principal-wipe" in ids
    assert "2026-09-28-applicant-vault-spill" in ids


def test_world_fires_2026_09_28_beats():
    w = GameWorld(510928)
    w.reload_daily_storylines(fire=True, day="2026-09-28")
    a = _join(w, "NewsCourier28")
    s = w.snapshot(a)
    ds = s["daily_storylines"]
    assert ds["date"] == "2026-09-28"
    assert ds["beat_count"] == 3
    texts = " | ".join((e.get("text") or "") for e in w.event_ticker)
    assert "silicon watchdog" in texts or "snap-cage" in texts or "out-of-band" in texts or "soft lock" in texts
    assert "machine-identity" in texts or "recovery locks" in texts or "sibling badges" in texts or "Payload-Zero" in texts
    assert "applicant ICE" in texts or "sleeve IDs" in texts or "phishing hops" in texts or "open listing" in texts
    hooks = (w.forecast_state or {}).get("news_hooks") or []
    regions = {h.get("region_id") for h in hooks if h.get("region_id")}
    assert "berlin_circuit" in regions
    assert "singapore_core" in regions
    assert "london_fog" in regions




def test_json_has_2026_09_29_beats():
    doc = _load_daily_storylines_doc()
    ent = _pick_entry(doc, "2026-09-29")
    assert ent is not None
    ids = {b["id"] for b in ent["beats"]}
    assert "2026-09-29-penance-dock-grill" in ids
    assert "2026-09-29-rail-ice-ransom" in ids
    assert "2026-09-29-pump-tax-picket" in ids


def test_world_fires_2026_09_29_beats():
    w = GameWorld(510929)
    w.reload_daily_storylines(fire=True, day="2026-09-29")
    a = _join(w, "NewsCourier29")
    s = w.snapshot(a)
    ds = s["daily_storylines"]
    assert ds["date"] == "2026-09-29"
    assert ds["beat_count"] == 3
    texts = " | ".join((e.get("text") or "") for e in w.event_ticker)
    assert "penance" in texts or "Reef parliament" in texts or "rebuild taskforce" in texts or "civic portals" in texts
    assert "rail ICE" in texts or "ransom kit" in texts or "payment daemons" in texts or "rider mail" in texts
    assert "pump-tax" in texts or "fare stub" in texts or "Pickets choke" in texts or "courier arteries" in texts
    hooks = (w.forecast_state or {}).get("news_hooks") or []
    regions = {h.get("region_id") for h in hooks if h.get("region_id")}
    assert "sydney_reef" in regions
    assert "neo_tokyo" in regions
    assert "jakarta_arch" in regions



def test_json_has_2026_09_30_beats():
    doc = _load_daily_storylines_doc()
    ent = _pick_entry(doc, "2026-09-30")
    assert ent is not None
    ids = {b["id"] for b in ent["beats"]}
    assert "2026-09-30-moral-bind-seal" in ids
    assert "2026-09-30-spine-chorus" in ids
    assert "2026-09-30-cid-bloom" in ids


def test_world_fires_2026_09_30_beats():
    w = GameWorld(510930)
    w.reload_daily_storylines(fire=True, day="2026-09-30")
    a = _join(w, "NewsCourier30")
    s = w.snapshot(a)
    ds = s["daily_storylines"]
    assert ds["date"] == "2026-09-30"
    assert ds["beat_count"] == 3
    texts = " | ".join((e.get("text") or "") for e in w.event_ticker)
    assert "morally-binding" in texts or "outside-auditor" in texts or "foil sticker" in texts or "blank parchment" in texts
    assert "Critical Spine League" in texts or "one voice" in texts or "payment ICE" in texts or "spines stay lit" in texts
    assert "CID bloom" in texts or "civil investigative" in texts or "training ledgers" in texts or "eval logs" in texts
    hooks = (w.forecast_state or {}).get("news_hooks") or []
    regions = {h.get("region_id") for h in hooks if h.get("region_id")}
    assert "neo_nyc" in regions
    assert "singapore_core" in regions
    assert "fractured_la" in regions



def test_json_has_2026_10_01_beats():
    doc = _load_daily_storylines_doc()
    ent = _pick_entry(doc, "2026-10-01")
    assert ent is not None
    ids = {b["id"] for b in ent["beats"]}
    assert "2026-10-01-archive-hop-miss" in ids
    assert "2026-10-01-spoof-collar-invite" in ids
    assert "2026-10-01-wage-claw-dock" in ids


def test_world_fires_2026_10_01_beats():
    w = GameWorld(5101001)
    w.reload_daily_storylines(fire=True, day="2026-10-01")
    a = _join(w, "NewsCourier1001")
    s = w.snapshot(a)
    ds = s["daily_storylines"]
    assert ds["date"] == "2026-10-01"
    assert ds["beat_count"] == 3
    texts = " | ".join((e.get("text") or "") for e in w.event_ticker)
    assert "memory vault" in texts or "archive ICE" in texts or "unbroken seals" in texts
    assert "ghost collars" in texts or "export-control" in texts or "session charms" in texts or "fake invites" in texts
    assert "megapay settlement" in texts or "thin stubs" in texts or "pay-ledger" in texts or "screwed up the math" in texts
    hooks = (w.forecast_state or {}).get("news_hooks") or []
    regions = {h.get("region_id") for h in hooks if h.get("region_id")}
    assert "vancouver_grid" in regions
    assert "seoul_lane" in regions
    assert "neo_nyc" in regions



def test_json_has_2026_10_02_beats():
    doc = _load_daily_storylines_doc()
    ent = _pick_entry(doc, "2026-10-02")
    assert ent is not None
    ids = {b["id"] for b in ent["beats"]}
    assert "2026-10-02-pay-pipe-probe" in ids
    assert "2026-10-02-argon-leash-gift" in ids
    assert "2026-10-02-emotion-collar-ban" in ids


def test_world_fires_2026_10_02_beats():
    w = GameWorld(5101002)
    w.reload_daily_storylines(fire=True, day="2026-10-02")
    a = _join(w, "NewsCourier1002")
    s = w.snapshot(a)
    ds = s["daily_storylines"]
    assert ds["date"] == "2026-10-02"
    assert ds["beat_count"] == 3
    texts = " | ".join((e.get("text") or "") for e in w.event_ticker)
    assert "payment ICE" in texts or "pay pipes" in texts or "injection hops" in texts or "Glass Oracle grill" in texts
    assert "Argon defense" in texts or "Fairwind" in texts or "short leash" in texts or "patch-hunt" in texts
    assert "emotion-read" in texts or "neural collars" in texts or "living sign-off" in texts or "mood-meters" in texts
    hooks = (w.forecast_state or {}).get("news_hooks") or []
    regions = {h.get("region_id") for h in hooks if h.get("region_id")}
    assert "neo_nyc" in regions
    assert "singapore_core" in regions
    assert "fractured_la" in regions


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