"""Modder plugin framework loader (#72)."""

from __future__ import annotations

import json
from pathlib import Path

from snowcrash.mmorpg import GameWorld
from snowcrash.systems.modding import (
    PLUGIN_API_VERSION,
    api_compatible,
    discover_mod_dirs,
    load_all_mods,
    load_mod,
    ModRegistry,
    item_from_def,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "plugins" / "hello_courier"


def _join(w: GameWorld, name: str = "ModCourier"):
    a = w.join(name)
    a.last_action_ts = 0
    return a


def test_api_semver_compatible():
    assert api_compatible("1.0.0", "1.0.0")
    assert api_compatible("1.0.0", "1.2.0")
    assert not api_compatible("2.0.0", "1.0.0")
    assert not api_compatible("1.9.0", "1.0.0")
    assert not api_compatible("nope", "1.0.0")


def test_discover_includes_hello_courier(tmp_path, monkeypatch):
    monkeypatch.delenv("SNOWCRASH_DISABLE_MODS", raising=False)
    monkeypatch.setenv("SNOWCRASH_EXAMPLE_PLUGINS", "1")
    monkeypatch.delenv("SNOWCRASH_MODS_PATH", raising=False)
    dirs = discover_mod_dirs()
    assert any(p.name == "hello_courier" for p in dirs)


def test_load_hello_courier_items_and_events():
    reg = ModRegistry()
    loaded = load_mod(EXAMPLE, reg)
    assert loaded is not None
    assert loaded.id == "hello_courier"
    assert "hello_courier.badge" in reg.items
    assert any(e["id"] == "hello_courier.ping" for e in reg.street_events)
    item = item_from_def(reg.items["hello_courier.badge"])
    assert item.name == "Hello Courier Badge"
    assert item.hack_bonus == 1
    assert item.equippable


def test_fail_closed_unknown_permission(tmp_path):
    mod = tmp_path / "bad_perm"
    mod.mkdir()
    (mod / "mod.json").write_text(
        json.dumps(
            {
                "id": "bad_perm",
                "version": "1.0.0",
                "api_version": PLUGIN_API_VERSION,
                "permissions": ["network"],
                "entry": {},
            }
        ),
        encoding="utf-8",
    )
    reg = ModRegistry()
    assert load_mod(mod, reg) is None
    assert reg.errors
    assert "network" in reg.errors[0].message
    assert "bad_perm" not in reg.mods


def test_fail_closed_path_traversal(tmp_path):
    mod = tmp_path / "trav"
    mod.mkdir()
    (mod / "mod.json").write_text(
        json.dumps(
            {
                "id": "trav",
                "version": "1.0.0",
                "api_version": PLUGIN_API_VERSION,
                "permissions": ["items"],
                "entry": {"items": "../secrets.json"},
            }
        ),
        encoding="utf-8",
    )
    reg = ModRegistry()
    assert load_mod(mod, reg) is None
    assert any("missing/unsafe" in e.message for e in reg.errors)


def test_fail_closed_incompatible_api(tmp_path):
    mod = tmp_path / "old_api"
    mod.mkdir()
    (mod / "mod.json").write_text(
        json.dumps(
            {
                "id": "old_api",
                "version": "1.0.0",
                "api_version": "9.0.0",
                "permissions": ["items"],
                "entry": {"items": "items.json"},
            }
        ),
        encoding="utf-8",
    )
    (mod / "items.json").write_text('{"items": []}', encoding="utf-8")
    reg = ModRegistry()
    assert load_mod(mod, reg) is None
    assert any("incompatible" in e.message for e in reg.errors)


def test_fail_closed_core_item_collision(tmp_path):
    mod = tmp_path / "collide"
    mod.mkdir()
    (mod / "mod.json").write_text(
        json.dumps(
            {
                "id": "collide",
                "version": "1.0.0",
                "api_version": PLUGIN_API_VERSION,
                "permissions": ["items"],
                "entry": {"items": "items.json"},
            }
        ),
        encoding="utf-8",
    )
    (mod / "items.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "stimpack",
                        "name": "Fake Stim",
                        "kind": "med",
                        "description": "nope",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    reg = ModRegistry()
    assert load_mod(mod, reg) is None
    assert any("core item" in e.message for e in reg.errors)


def test_world_loads_example_and_grants_item(monkeypatch):
    monkeypatch.delenv("SNOWCRASH_DISABLE_MODS", raising=False)
    monkeypatch.setenv("SNOWCRASH_EXAMPLE_PLUGINS", "1")
    w = GameWorld(72001)
    assert "hello_courier" in w.mod_registry.mods
    a = _join(w)
    s = w.snapshot(a)
    assert "mods" in s
    assert s["mods"]["mod_count"] >= 1
    assert w.handle_year_action(a, "mods")
    assert w.handle_year_action(a, "mod_item", "hello_courier.badge")
    ids = [getattr(i, "id", None) for i in a.actor.inventory]
    assert "hello_courier.badge" in ids


def test_reload_defs_reloads_mods(monkeypatch):
    monkeypatch.setenv("SNOWCRASH_EXAMPLE_PLUGINS", "1")
    w = GameWorld(72002)
    before = w.mod_registry.mod_count if hasattr(w.mod_registry, "mod_count") else len(w.mod_registry.mods)
    assert before >= 1
    w.reload_district_defs()
    assert len(w.mod_registry.mods) >= 1
    assert any(e.get("id") == "hello_courier.ping" for e in w.mod_street_events)


def test_mod_street_event_can_fire(monkeypatch):
    monkeypatch.setenv("SNOWCRASH_EXAMPLE_PLUGINS", "1")
    w = GameWorld(72003)
    a = _join(w)
    # Force the broadcast band + mod branch
    w.next_event_tick = w.tick
    # Stub rng: amb_thresh path skipped by high roll into else, then mod fires
    rolls = iter([0.99, 0.0])  # else branch; then < 0.4 mod branch

    def fake_random():
        try:
            return next(rolls)
        except StopIteration:
            return 0.5

    w.rng.random = fake_random  # type: ignore
    w._tick_street_events()
    texts = [e.get("text") or "" for e in w.event_ticker]
    assert any("Hello Courier" in t or "Faraday pin" in t for t in texts)


def test_disable_mods_env(monkeypatch):
    monkeypatch.setenv("SNOWCRASH_DISABLE_MODS", "1")
    assert discover_mod_dirs() == []
    reg = load_all_mods()
    assert reg.mods == {}


def test_hello_courier_slice2_hooks():
    reg = ModRegistry()
    loaded = load_mod(EXAMPLE, reg)
    assert loaded is not None
    assert loaded.api_version.startswith("1.")
    assert any(a["id"] == "hello_courier.delivery" for a in reg.journal_arcs)
    assert any(b["id"] == "hello_courier.welcome" for b in reg.journal_beats)
    assert any(b["id"] == "hello_courier.streetnet_hello" for b in reg.streetnet_broadcasts)
    assert "hello_courier.ping_probe" in reg.ice_probes
    assert reg.ice_probes["hello_courier.ping_probe"]["effect"] == "reveal"
    assert any(n["id"] == "hello_courier.tutorial_node" for n in reg.cyber_nodes)
    assert any(p["id"] == "hello_courier.drop_pin" for p in reg.globe_pins)
    assert any(r["id"] == "hello_courier.rim_cache" for r in reg.globe_regions)


def test_world_journal_and_streetnet_and_globe(monkeypatch):
    monkeypatch.delenv("SNOWCRASH_DISABLE_MODS", raising=False)
    monkeypatch.setenv("SNOWCRASH_EXAMPLE_PLUGINS", "1")
    w = GameWorld(72011)
    assert "hello_courier.ping_probe" in w._all_ice_probes()
    assert any(p["id"] == "hello_courier.drop_pin" for p in w.mod_globe_pins)
    # fire_on_load StreetNet should have landed in the ticker
    texts = [e.get("text") or "" for e in w.event_ticker]
    assert any("HELLO_COURIER" in t or "Hello Courier" in t for t in texts)
    a = _join(w)
    j = a.journal
    assert any(arc.get("id") == "hello_courier.delivery" for arc in (j.get("mod_arcs") or []))
    assert "hello_courier.welcome" in (j.get("mod_beats_seen") or [])
    snap = w._globe_snapshot(a)
    assert any(p.get("id") == "hello_courier.drop_pin" for p in (snap.get("mod_pins") or []))
    # metadata region rejects teleport
    assert w._globe_teleport(a, "hello_courier.rim_cache") is True
    assert w._globe_agent_region(a) != "hello_courier.rim_cache"


def test_mod_ice_probe_listed(monkeypatch):
    monkeypatch.setenv("SNOWCRASH_EXAMPLE_PLUGINS", "1")
    w = GameWorld(72012)
    a = _join(w)
    a.actor.focus = 20
    assert w.handle_year_action(a, "ice_probe", "list")
    cat = w._ice_probe_catalog(a)
    assert any(p["id"] == "hello_courier.ping_probe" for p in cat)


def test_fail_closed_bad_cyber_grid(tmp_path):
    mod = tmp_path / "bad_grid"
    mod.mkdir()
    (mod / "mod.json").write_text(
        json.dumps(
            {
                "id": "bad_grid",
                "version": "1.0.0",
                "api_version": PLUGIN_API_VERSION,
                "permissions": ["ice_nodes"],
                "entry": {"ice_nodes": "ice_nodes.json"},
            }
        ),
        encoding="utf-8",
    )
    (mod / "ice_nodes.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "bad_grid.node",
                        "grid": ["####", "#@.#", "####"],  # missing X
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    reg = ModRegistry()
    assert load_mod(mod, reg) is None
    assert any("X exit" in e.message for e in reg.errors)


def test_plugin_api_is_1_1():
    parts = PLUGIN_API_VERSION.split(".")
    assert int(parts[0]) == 1
    assert int(parts[1]) >= 1
