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
