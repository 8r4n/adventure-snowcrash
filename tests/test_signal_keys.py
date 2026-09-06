"""Signal Keys scavenger hunt (#45)."""

from __future__ import annotations

from snowcrash.mmorpg import GameWorld
from snowcrash.systems.signal_keys import SIGNAL_KEY_DEFS, SIGNAL_KEY_IDS, SIGNAL_SIDE_ID


def _join(w: GameWorld, name: str = "KeyHunter"):
    a = w.join(name)
    a.last_action_ts = 0
    return a


def test_signal_keys_seeded_in_districts():
    w = GameWorld(245)
    assert len(w.signal_key_positions) == 3
    assert w.flotilla_pad is not None
    for meta in SIGNAL_KEY_DEFS:
        kid = meta["id"]
        assert kid in w.signal_key_positions
        x, y = w.signal_key_positions[kid]
        d = w._district_at(x, y, 0)
        # Prefer matching district; allow overlap fallback but item must exist
        found = any(
            fi.item.id == kid and fi.x == x and fi.y == y
            for fi in w.floor_items
        )
        assert found, kid
        assert d.get("id") in ("burbclave", "club", "uplink_rim", "undercity")


def test_snapshot_has_signal_keys():
    w = GameWorld(246)
    a = _join(w)
    s = w.snapshot(a)
    assert "signal_keys" in s
    assert s["signal_keys"]["total"] == 3
    assert s["signal_keys"]["held_count"] == 0
    assert s["signal_keys"]["flotilla_pad"]
    side_ids = [q.get("id") for q in (s["journal"].get("side") or [])]
    assert SIGNAL_SIDE_ID in side_ids


def test_pickup_updates_journal_and_compass():
    w = GameWorld(247)
    a = _join(w, "SleeveOne")
    # Skip payload compass — mark payload cleared so Signal Keys own objective
    a.quest_flags["payload_cleared"] = True
    a.won = True
    kid = SIGNAL_KEY_IDS[0]
    x, y = w.signal_key_positions[kid]
    w._force_set_pos(a, x, y, 0, "key tile")
    a.last_action_ts = 0
    w.handle_action(a, "g")
    assert any(i.id == kid for i in a.actor.inventory)
    assert kid in a.signal_keys["collected"]
    assert a.quest_flags.get(kid)
    s = w.snapshot(a)
    assert s["signal_keys"]["held_count"] == 1
    obj = s["objective"]
    assert obj["id"] in SIGNAL_KEY_IDS or obj["id"] == "flotilla_finale"
    assert "Signal Key" in obj["text"] or "Flotilla" in obj["text"] or "Find" in obj["text"]


def test_district_clue_once():
    w = GameWorld(248)
    a = _join(w, "ClueWalker")
    # Move into burbclave key tile district
    kid = "signal_key_burbclave"
    x, y = w.signal_key_positions[kid]
    w._force_set_pos(a, x, y, 0, "clue")
    a.log_lines = [] if not hasattr(a, "log_lines") else a.log_lines
    before = list(a.logs) if hasattr(a, "logs") else None
    # Trigger clue via year_tick path
    w._maybe_district_signal_clue(a)
    assert kid in a.signal_keys["clues_seen"]
    # Second call should not re-append clue id
    w._maybe_district_signal_clue(a)
    assert a.signal_keys["clues_seen"].count(kid) == 1


def test_finale_broadcast_with_all_keys():
    w = GameWorld(249)
    a = _join(w, "Finale")
    a.quest_flags["payload_cleared"] = True
    a.won = True
    # Grant all keys directly
    from snowcrash.systems.signal_keys import make_signal_key

    for kid in SIGNAL_KEY_IDS:
        a.actor.inventory.append(make_signal_key(kid))
        w._on_signal_key_pickup(a, a.actor.inventory[-1])
    assert a.signal_keys["finale_unlocked"]
    assert len(a.signal_keys["collected"]) == 3
    pad = w.flotilla_pad
    w._force_set_pos(a, pad[0], pad[1], 0, "finale pad")
    a.last_action_ts = 0
    w.handle_action(a, "enter_flotilla")
    assert a.mode == "flotilla"
    assert a.signal_keys["broadcast_done"]
    assert a.quest_flags.get("signal_broadcast")
    s = w.snapshot(a)
    assert s["signal_keys"]["broadcast_done"] is True
    side = [q for q in (s["journal"].get("side") or []) if q.get("id") == SIGNAL_SIDE_ID][0]
    assert side.get("done") or side.get("status") == "done"
    a.last_action_ts = 0
    w.handle_action(a, "leave_flotilla")
    assert a.mode == "play"


def test_finale_sealed_without_keys():
    w = GameWorld(250)
    a = _join(w, "NoKeys")
    pad = w.flotilla_pad
    w._force_set_pos(a, pad[0], pad[1], 0, "pad")
    a.last_action_ts = 0
    w.handle_action(a, "enter_flotilla")
    assert a.mode != "flotilla"
    assert not a.signal_keys.get("broadcast_done")
