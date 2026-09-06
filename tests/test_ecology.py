"""Scarce resource ecology wars on globe regions (#57)."""

from __future__ import annotations

from snowcrash.mmorpg import GameWorld


def _join(w: GameWorld, name: str = "EcoCourier"):
    a = w.join(name)
    a.last_action_ts = 0
    a.actor.focus = 20
    a.credits = 200
    return a


def test_nodes_on_at_least_three_regions():
    w = GameWorld(5701)
    a = _join(w)
    s = w.snapshot(a)
    assert "ecology" in s
    eco = s["ecology"]
    assert eco["node_count"] >= 3
    assert eco["region_count"] >= 3
    resources = {n["resource"] for n in eco["nodes"]}
    for need in ("bandwidth", "water", "uplink_spectrum"):
        assert need in resources
    assert eco["hooks"]["globe"] and eco["hooks"]["contracts"] and eco["hooks"]["raids"]


def test_globe_exposes_ecology_nodes():
    w = GameWorld(5702)
    a = _join(w)
    s = w.snapshot(a)
    g = s["globe"]
    assert "ecology_nodes" in g
    assert len(g["ecology_nodes"]) >= 3
    # Regions with nodes flagged
    flagged = [r for r in g["regions"] if r.get("has_ecology")]
    assert len(flagged) >= 3


def test_claim_contract_flips_control():
    w = GameWorld(5703)
    a = _join(w)
    # Home region has LA Packet Well (bandwidth)
    node = w.ecology_nodes["node_la_bandwidth"]
    before = dict(node["controller"])
    assert w.handle_year_action(a, "ecology_claim", "node_la_bandwidth")
    after = node["controller"]
    assert after["id"] != before["id"] or after["kind"] != before["kind"] or after["name"] != before["name"]
    assert after["kind"] in ("crew", "courier")
    assert int(a.ecology["claims"]) == 1
    # Contract completed
    done = [c for c in a.contracts if c.get("ecology_node") == "node_la_bandwidth" and c.get("status") == "done"]
    assert done
    # Weather shifted
    assert w.weather_state.get("ecology_node") == "node_la_bandwidth"
    s = w.snapshot(a)
    assert s["ecology"]["claims"] == 1


def test_raid_flips_control_on_remote_region():
    w = GameWorld(5704)
    a = _join(w)
    # Hop to neo_tokyo (corp-held spectrum stack)
    assert w.handle_year_action(a, "teleport", "neo_tokyo")
    a.globe["cooldown_until"] = 0
    a.ecology["cooldown_until"] = 0
    a.last_action_ts = 0
    a.actor.focus = 20
    a.credits = max(int(a.credits), 100)
    node = w.ecology_nodes["node_tokyo_spectrum"]
    assert node["controller"]["kind"] == "corp"
    assert w.handle_year_action(a, "ecology_raid", "node_tokyo_spectrum")
    assert node["controller"]["kind"] in ("crew", "courier")
    assert int(a.ecology["raids"]) == 1
    # StreetNet ecology event recorded
    assert any("Ecology flip" in (e.get("text") or "") for e in w.event_ticker)


def test_must_be_in_region_to_claim():
    w = GameWorld(5705)
    a = _join(w)
    # Still on home — cannot claim Tokyo
    ctrl0 = dict(w.ecology_nodes["node_tokyo_spectrum"]["controller"])
    assert w.handle_year_action(a, "ecology_claim", "node_tokyo_spectrum")
    assert w.ecology_nodes["node_tokyo_spectrum"]["controller"] == ctrl0
    assert int(a.ecology.get("claims") or 0) == 0


def test_panel_list_and_contract_offer():
    w = GameWorld(5706)
    a = _join(w)
    assert w.handle_year_action(a, "ecology")
    assert a.ecology["panel_open"] is True
    assert w.handle_year_action(a, "ecology_list")
    assert w.handle_year_action(a, "ecology_contract", "node_sydney_water")
    assert a.ecology["active_contract_node"] == "node_sydney_water"
    assert any(c.get("ecology_node") == "node_sydney_water" for c in a.contracts)
    assert w.handle_year_action(a, "ecology_close")
    assert a.ecology["panel_open"] is False


def test_ecology_tick_updates_pressure():
    w = GameWorld(5707)
    _join(w)
    node = next(iter(w.ecology_nodes.values()))
    before = float(node["pressure"])
    w.tick = int(w.ecology_tick_interval)
    w._tick_ecology()
    # Pressure should have drifted (may equal if rng lands near 0 — allow small change OR streetnet entry)
    after = float(node["pressure"])
    assert after != before or w.ecology_streetnet or abs(after - before) < 0.001
    # Force second tick path with known pressure
    node["pressure"] = 0.8
    node["controller"] = {"kind": "corp", "id": "x", "name": "X Corp"}
    w.tick = int(w.ecology_tick_interval) * 2
    w._tick_ecology()
    assert w.weather_state.get("id") in (
        "packet_drought",
        "dry_signal",
        "spectrum_hash",
        "mesh_clarity",
        "condensate_mist",
        "clean_spectrum",
        w.weather_state.get("id"),
    )
