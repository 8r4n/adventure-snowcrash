"""Modder plugin framework loader (#72)."""

from __future__ import annotations

import json
from pathlib import Path

from snowcrash.mmorpg import GameWorld
from snowcrash.systems.modding import (
    PLUGIN_API_VERSION,
    _safe_child,
    api_compatible,
    api_incompatibility_reason,
    discover_mod_dirs,
    host_capability_flags,
    load_all_mods,
    load_mod,
    mod_has_permission,
    permission_status,
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
    assert api_compatible("1.0.0", "1.4.0")
    assert api_compatible("1.3.0", "1.4.0")
    assert not api_compatible("2.0.0", "1.0.0")
    assert not api_compatible("1.9.0", "1.0.0")
    assert not api_compatible("nope", "1.0.0")
    assert not api_compatible("", "1.4.0")
    r = api_incompatibility_reason("2.0.0", "1.4.0")
    assert r and "major mismatch" in r
    r = api_incompatibility_reason("1.9.0", "1.4.0")
    assert r and "requires newer host" in r
    r = api_incompatibility_reason("nope", "1.4.0")
    assert r and "unparseable" in r
    assert api_incompatibility_reason("1.1.0", "1.4.0") is None
    assert PLUGIN_API_VERSION.startswith("1.4")


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


def test_fail_closed_incompatible_api_reasons(tmp_path):
    def _mod(name, api):
        mod = tmp_path / name
        mod.mkdir()
        (mod / "mod.json").write_text(
            json.dumps(
                {
                    "id": name,
                    "version": "1.0.0",
                    "api_version": api,
                    "permissions": ["items"],
                    "entry": {"items": "items.json"},
                }
            ),
            encoding="utf-8",
        )
        (mod / "items.json").write_text('{"items": []}', encoding="utf-8")
        return mod

    reg = ModRegistry()
    assert load_mod(_mod("future_minor", "1.9.0"), reg) is None
    assert any("requires newer host" in e.message for e in reg.errors)
    assert load_mod(_mod("other_major", "2.0.0"), reg) is None
    assert any("major mismatch" in e.message for e in reg.errors)
    assert load_mod(_mod("junk_api", "banana"), reg) is None
    assert any("unparseable" in e.message for e in reg.errors)


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
    assert any("major mismatch" in e.message or "incompatible" in e.message for e in reg.errors)


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


def test_plugin_api_is_1_3():
    parts = PLUGIN_API_VERSION.split(".")
    assert int(parts[0]) == 1
    assert int(parts[1]) >= 3


def test_hello_courier_ui_panel():
    reg = ModRegistry()
    loaded = load_mod(EXAMPLE, reg)
    assert loaded is not None
    assert "ui_panel" in loaded.permissions
    assert any(p["id"] == "hello_courier.desk" for p in reg.ui_panels)
    panel = next(p for p in reg.ui_panels if p["id"] == "hello_courier.desk")
    assert panel["title"]
    assert panel["body_format"] == "markdown"
    assert panel["dock_label"]
    assert any(a["action"] == "mod_item" and a.get("arg") == "hello_courier.badge" for a in panel["actions"])
    snap = reg.snapshot()
    assert snap["ui_panel_count"] >= 1
    assert any(p["id"] == "hello_courier.desk" for p in snap["panels"])


def test_world_snapshot_includes_mod_panels(monkeypatch):
    monkeypatch.delenv("SNOWCRASH_DISABLE_MODS", raising=False)
    monkeypatch.setenv("SNOWCRASH_EXAMPLE_PLUGINS", "1")
    w = GameWorld(72021)
    a = _join(w)
    s = w.snapshot(a)
    panels = (s.get("mods") or {}).get("panels") or []
    assert any(p.get("id") == "hello_courier.desk" for p in panels)


def test_fail_closed_ui_panel_bad_action(tmp_path):
    mod = tmp_path / "bad_ui"
    mod.mkdir()
    (mod / "mod.json").write_text(
        json.dumps(
            {
                "id": "bad_ui",
                "version": "1.0.0",
                "api_version": PLUGIN_API_VERSION,
                "permissions": ["ui_panel"],
                "entry": {"ui_panel": "ui_panel.json"},
            }
        ),
        encoding="utf-8",
    )
    (mod / "ui_panel.json").write_text(
        json.dumps(
            {
                "panels": [
                    {
                        "id": "bad_ui.panel",
                        "title": "Nope",
                        "body": "x",
                        "actions": [{"label": "Boom", "action": "eval"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    reg = ModRegistry()
    assert load_mod(mod, reg) is None
    assert any("allowlisted" in e.message or "invalid" in e.message for e in reg.errors)


def test_fail_closed_ui_panel_html_not_required_but_body_ok(tmp_path):
    """Body may contain angle brackets; validator accepts text (host escapes)."""
    mod = tmp_path / "angle_ui"
    mod.mkdir()
    (mod / "mod.json").write_text(
        json.dumps(
            {
                "id": "angle_ui",
                "version": "1.0.0",
                "api_version": PLUGIN_API_VERSION,
                "permissions": ["ui_panel"],
                "entry": {"ui_panel": "ui_panel.json"},
            }
        ),
        encoding="utf-8",
    )
    (mod / "ui_panel.json").write_text(
        json.dumps(
            {
                "panels": [
                    {
                        "id": "angle_ui.panel",
                        "title": "Angles",
                        "dock_label": "Ang",
                        "body_format": "text",
                        "body": "See <script>alert(1)</script> — host must escape.",
                        "actions": [{"label": "Mods", "action": "mods"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    reg = ModRegistry()
    loaded = load_mod(mod, reg)
    assert loaded is not None
    assert "<script>" in reg.ui_panels[0]["body"]


def test_hello_courier_streetnet_command():
    reg = ModRegistry()
    loaded = load_mod(EXAMPLE, reg)
    assert loaded is not None
    slashes = [c["slash"] for c in reg.streetnet_commands]
    assert "hello" in slashes
    snap = reg.snapshot()
    assert snap["streetnet_command_count"] >= 1
    assert any(c.get("slash") == "hello" for c in snap["streetnet_commands"])


def test_world_streetnet_slash_hello(monkeypatch):
    monkeypatch.delenv("SNOWCRASH_DISABLE_MODS", raising=False)
    monkeypatch.setenv("SNOWCRASH_EXAMPLE_PLUGINS", "1")
    w = GameWorld(72031)
    a = _join(w)
    a.last_chat_ts = 0
    assert w.say(a, "/hello") is None
    notices = [ln.text for ln in a.private_chat]
    assert any("Hello Courier" in t or "HELLO_COURIER" in t or "Faraday" in t for t in notices)
    assert any("pinged Hello Courier" in m for m in a.messages)
    a.last_chat_ts = 0
    assert w.say(a, "/help") is None
    help_txt = " ".join(ln.text for ln in a.private_chat)
    assert "/hello" in help_txt


def test_fail_closed_reserved_streetnet_slash(tmp_path):
    mod = tmp_path / "reserved_slash"
    mod.mkdir()
    (mod / "mod.json").write_text(
        json.dumps(
            {
                "id": "reserved_slash",
                "version": "1.0.0",
                "api_version": PLUGIN_API_VERSION,
                "permissions": ["streetnet"],
                "entry": {"streetnet": "streetnet.json"},
            }
        ),
        encoding="utf-8",
    )
    (mod / "streetnet.json").write_text(
        json.dumps(
            {
                "commands": [
                    {
                        "id": "reserved_slash.help",
                        "slash": "help",
                        "replies": ["nope"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    reg = ModRegistry()
    assert load_mod(mod, reg) is None
    assert any("reserved" in e.message for e in reg.errors)
    assert "reserved_slash" not in reg.mods


def test_fail_closed_no_partial_apply(tmp_path):
    """A later bad def must not leave earlier items in the registry."""
    mod = tmp_path / "partial"
    mod.mkdir()
    (mod / "mod.json").write_text(
        json.dumps(
            {
                "id": "partial",
                "version": "1.0.0",
                "api_version": PLUGIN_API_VERSION,
                "permissions": ["items", "street_events"],
                "entry": {"items": "items.json", "street_events": "street_events.json"},
            }
        ),
        encoding="utf-8",
    )
    (mod / "items.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "partial.ok_item",
                        "name": "Should Not Land",
                        "kind": "trinket",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (mod / "street_events.json").write_text(
        json.dumps({"events": [{"id": "not a valid id!!!", "messages": ["x"]}]}),
        encoding="utf-8",
    )
    reg = ModRegistry()
    assert load_mod(mod, reg) is None
    assert "partial.ok_item" not in reg.items
    assert "partial" not in reg.mods


def test_api_reload_defs_includes_mods(monkeypatch):
    from fastapi.testclient import TestClient
    from snowcrash.web.app import create_app

    monkeypatch.delenv("SNOWCRASH_DISABLE_MODS", raising=False)
    monkeypatch.setenv("SNOWCRASH_EXAMPLE_PLUGINS", "1")
    monkeypatch.delenv("ADVENTURE_QA", raising=False)
    app = create_app(default_seed=72040, deploy_env="dev")
    with TestClient(app) as client:
        r = client.post("/api/reload_defs")
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        assert body.get("reload", {}).get("mods") is True
        assert body.get("reload", {}).get("fail_closed") is True
        mods = body.get("mods") or {}
        assert mods.get("mod_count", 0) >= 1
        assert str(mods.get("api_version") or "").startswith("1.")
        assert any(
            (m.get("id") == "hello_courier") for m in (mods.get("mods") or [])
        )


def test_reload_clears_stale_globe_overlay(monkeypatch, tmp_path):
    monkeypatch.delenv("SNOWCRASH_DISABLE_MODS", raising=False)
    monkeypatch.setenv("SNOWCRASH_EXAMPLE_PLUGINS", "0")
    extra = tmp_path / "packs"
    extra.mkdir()
    pack = extra / "temp_pin"
    pack.mkdir()
    (pack / "mod.json").write_text(
        json.dumps(
            {
                "id": "temp_pin",
                "version": "1.0.0",
                "api_version": PLUGIN_API_VERSION,
                "permissions": ["globe_regions"],
                "entry": {"globe_regions": "globe_regions.json"},
            }
        ),
        encoding="utf-8",
    )
    (pack / "globe_regions.json").write_text(
        json.dumps(
            {
                "pins": [
                    {
                        "id": "temp_pin.here",
                        "name": "Temp",
                        "lat": 10.0,
                        "lon": 10.0,
                    }
                ],
                "regions": [
                    {
                        "id": "temp_pin.rim",
                        "name": "Temp Rim",
                        "kind": "poi",
                        "lat": 11.0,
                        "lon": 11.0,
                        "metadata_only": True
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SNOWCRASH_MODS_PATH", str(extra))
    w = GameWorld(72041)
    assert any(p["id"] == "temp_pin.here" for p in w.mod_globe_pins)
    assert "temp_pin.rim" in (getattr(w, "globe_regions", {}) or {})
    # Remove the pack and reload — overlay must not linger.
    (pack / "mod.json").unlink()
    (pack / "globe_regions.json").unlink()
    pack.rmdir()
    w.reload_mods()
    assert not any(p.get("id") == "temp_pin.here" for p in w.mod_globe_pins)
    assert "temp_pin.rim" not in (getattr(w, "globe_regions", {}) or {})
    assert not any(
        isinstance(r, dict) and r.get("id") == "temp_pin.here"
        for r in (getattr(w, "globe_regions", {}) or {}).values()
    )


def test_host_capability_flags_safe_by_default():
    caps = host_capability_flags()
    assert caps["api_version"] == PLUGIN_API_VERSION
    perms = caps["permissions"]
    assert perms.get("items") == "implemented"
    assert perms.get("ui_panel") == "implemented"
    assert perms.get("streetnet") == "implemented"
    assert perms.get("network") == "denied"
    assert perms.get("fs_read") == "denied"
    assert perms.get("fs_write") == "denied"
    assert perms.get("wasm") == "denied"
    assert perms.get("exec") == "denied"
    sandbox = caps["sandbox"]
    assert sandbox["network"] == "denied"
    assert sandbox["fs"] == "mod_dir_jail"
    assert sandbox["symlinks"] == "denied"
    assert sandbox["partial_apply"] is False
    assert sandbox["unsigned_auto_download"] is False
    assert caps["clients"]["web_ui_panel"] is True
    assert caps["clients"]["godot_ui_panel"] is True
    assert permission_status("network") == "denied"
    assert permission_status("items") == "implemented"
    assert permission_status("nope_perm") == "unknown"


def test_snapshot_includes_capabilities(monkeypatch):
    monkeypatch.delenv("SNOWCRASH_DISABLE_MODS", raising=False)
    monkeypatch.setenv("SNOWCRASH_EXAMPLE_PLUGINS", "1")
    w = GameWorld(72042)
    snap = w._modding_snapshot()
    assert snap.get("api_version", "").startswith("1.4")
    caps = snap.get("capabilities") or {}
    assert caps.get("permissions", {}).get("network") == "denied"
    assert caps.get("sandbox", {}).get("fs") == "mod_dir_jail"
    assert "denied_permissions" in snap
    assert "network" in snap["denied_permissions"]
    assert any(m.get("id") == "hello_courier" for m in snap.get("mods") or [])
    assert any(m.get("id") == "street_tag" for m in snap.get("mods") or [])
    loaded = load_mod(EXAMPLE, ModRegistry())
    assert loaded is not None
    assert mod_has_permission(loaded, "items")
    assert not mod_has_permission(loaded, "network")


def test_safe_child_rejects_url_and_traversal(tmp_path):
    base = tmp_path / "mod"
    base.mkdir()
    (base / "items.json").write_text("{}", encoding="utf-8")
    assert _safe_child(base, "items.json") is not None
    assert _safe_child(base, "../items.json") is None
    assert _safe_child(base, "/etc/passwd") is None
    assert _safe_child(base, "https://evil.example/pack.json") is None
    assert _safe_child(base, "http://evil.example/x") is None
    assert _safe_child(base, "file:///etc/passwd") is None
    assert _safe_child(base, "C:/Windows/system.ini") is None


def test_fail_closed_symlink_entry(tmp_path):
    """Symlinked entry files are rejected (host FS sandbox)."""
    mod = tmp_path / "sym_mod"
    mod.mkdir()
    outside = tmp_path / "outside_items.json"
    outside.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "sym_mod.badge",
                        "name": "Should Not Load",
                        "kind": "trinket",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    link = mod / "items.json"
    try:
        link.symlink_to(outside)
    except OSError:
        return
    (mod / "mod.json").write_text(
        json.dumps(
            {
                "id": "sym_mod",
                "version": "1.0.0",
                "api_version": PLUGIN_API_VERSION,
                "permissions": ["items"],
                "entry": {"items": "items.json"},
            }
        ),
        encoding="utf-8",
    )
    reg = ModRegistry()
    assert load_mod(mod, reg) is None
    assert "sym_mod.badge" not in reg.items
    assert any("missing/unsafe" in e.message or "items" in e.message for e in reg.errors)


def test_fail_closed_url_entry_path(tmp_path):
    mod = tmp_path / "url_mod"
    mod.mkdir()
    (mod / "mod.json").write_text(
        json.dumps(
            {
                "id": "url_mod",
                "version": "1.0.0",
                "api_version": PLUGIN_API_VERSION,
                "permissions": ["items"],
                "entry": {"items": "https://evil.example/items.json"},
            }
        ),
        encoding="utf-8",
    )
    reg = ModRegistry()
    assert load_mod(mod, reg) is None
    assert "url_mod" not in reg.mods
    assert any("missing/unsafe" in e.message for e in reg.errors)


def test_fail_closed_fs_read_permission(tmp_path):
    mod = tmp_path / "fs_mod"
    mod.mkdir()
    (mod / "mod.json").write_text(
        json.dumps(
            {
                "id": "fs_mod",
                "version": "1.0.0",
                "api_version": PLUGIN_API_VERSION,
                "permissions": ["fs_read"],
                "entry": {},
            }
        ),
        encoding="utf-8",
    )
    reg = ModRegistry()
    assert load_mod(mod, reg) is None
    assert any("denied permission" in e.message and "fs_read" in e.message for e in reg.errors)


def test_godot_mod_panel_snapshot_parity():
    """Godot YearDocks must read mods.panels with mod:<id> dock keys (parity with web)."""
    src = (ROOT / "godot_client" / "scripts" / "year_docks.gd").read_text(encoding="utf-8")
    assert 'mods.get("panels"' in src
    assert "_paint_mod_panel" in src
    assert "_ensure_mod_dock_buttons" in src
    assert "mod:%s" in src
    assert 'begins_with("mod:")' in src
    assert "_mod_panel_ids" in src
    assert 'key = "mod:%s" % key' in src


def test_street_tag_minimal_example():
    tag = ROOT / "examples" / "plugins" / "street_tag"
    reg = ModRegistry()
    loaded = load_mod(tag, reg)
    assert loaded is not None
    assert "street_tag.sticker" in reg.items
    assert loaded.permissions == ["items"]
