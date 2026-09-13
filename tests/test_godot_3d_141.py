"""Static checks for Godot 3D street slice (#141) — no Godot binary required."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GODOT = ROOT / "godot_client"
DOCS = ROOT / "docs"


def test_street_scene_is_node3d():
    tscn = (GODOT / "scenes" / "street.tscn").read_text(encoding="utf-8")
    assert 'type="Node3D"' in tscn
    assert "street_3d.gd" in tscn
    assert "WorldEnvironment" in tscn
    assert "Camera3D" in tscn
    assert "Courier" in tscn
    main = (GODOT / "scenes" / "main.tscn").read_text(encoding="utf-8")
    assert "scenes/street.tscn" in main
    assert "StreetHost" in main
    assert "SubViewport" in main
    assert "Street3D" in main


def test_street_glyph_catalog_and_landmarks():
    src = (GODOT / "scripts" / "street_3d.gd").read_text(encoding="utf-8")
    assert "class_name Street3D" in src
    assert "GLYPH_ROLE" in src
    for glyph in ('"#": "wall"', '"J": "jackpoint"', '"U": "uplink"', '"~": "water"', '"+": "door"'):
        assert glyph in src
    assert "func apply_snapshot" in src
    assert "func toggle_camera" in src
    assert "jackpoint" in src and "uplink" in src
    assert "Label3D" in src
    assert "BUILD_RADIUS" in src


def test_main_keeps_ascii_and_defaults_to_3d():
    main = (GODOT / "scripts" / "main.gd").read_text(encoding="utf-8")
    assert '_view_mode: String = "3d"' in main
    assert "FpvAscii.render" in main
    assert "FpvAscii.map_crop" in main
    assert "_on_cam_toggle" in main
    assert "look_left" in main
    assert "street.apply_snapshot" in main
    # ASCII path must not be deleted
    assert (GODOT / "scripts" / "fpv_ascii.gd").is_file()


def test_renderer_is_forward_plus_mobile():
    proj = (GODOT / "project.godot").read_text(encoding="utf-8")
    assert "forward_plus" in proj
    assert 'rendering_method.mobile="mobile"' in proj
    assert "look_left" in proj
    assert "toggle_camera" in proj
    assert "Forward Plus" in proj


def test_docs_state_3d_is_steam_presentation_goal():
    d3d = (DOCS / "godot-3d.md").read_text(encoding="utf-8")
    assert "#141" in d3d
    assert "Steam presentation goal" in d3d
    assert "BUILD_RADIUS" in d3d
    assert "30 fps" in d3d
    assert "stays OPEN" in d3d
    client = (DOCS / "godot-client.md").read_text(encoding="utf-8")
    assert "godot-3d.md" in client
    assert "3D Metaverse" in client or "3D street" in client
    bar = (DOCS / "steam-quality-bar.md").read_text(encoding="utf-8")
    assert "godot-3d.md" in bar
    assert "3D" in bar
    assert "presentation goal" in bar.lower() or "Presentation goal" in bar


def test_issue_141_must_not_be_closed_by_docs():
    """Slice PRs use Refs #141 — never Closes #141 in tracked copy."""
    for rel in (
        "docs/godot-3d.md",
        "docs/godot-client.md",
        "docs/steam-quality-bar.md",
        "godot_client/README.md",
        "godot_client/scripts/street_3d.gd",
        "godot_client/scripts/main.gd",
        "godot_client/scripts/year_docks.gd",
        "godot_client/README.md",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "Closes #141" not in text
        assert "closes #141" not in text


def test_slice2_entity_polish_meshes_and_landmarks():
    """Slice 2: distinct silhouettes, facing, vendors, pickups — Refs #141."""
    src = (GODOT / "scripts" / "street_3d.gd").read_text(encoding="utf-8")
    assert '"$": "vendor"' in src
    assert '"B": "boss"' in src
    assert "MAX_POOLED_ENTITIES" in src
    assert "_spawn_vendor" in src
    assert "_spawn_jack_uplink" in src
    assert "_spawn_pickup_beacon" in src
    assert "_ensure_courier_parts" in src
    assert 'name = "Facing"' in src or 'Facing"' in src
    assert "_mats[\"vendor\"]" in src or '_mats["vendor"]' in src
    assert "landmarks" in src
    assert "facing_other" in src or "facing" in src
    # Must not claim to close the epic
    assert "Closes #141" not in src


def test_docs_slice2_progress():
    d3d = (DOCS / "godot-3d.md").read_text(encoding="utf-8")
    assert "Entities polish" in d3d
    assert "vendor" in d3d.lower()
    assert "Facing" in d3d or "facing" in d3d
    assert "pooled" in d3d.lower() or "MAX_POOLED" in d3d or "pool" in d3d.lower()
    assert "Refs #141" in d3d and "stays OPEN" in d3d


def test_slice3_ice_visual_language():
    """Slice 3: cyberspace / ICE 3D lattice — Refs #141, never Closes."""
    src = (GODOT / "scripts" / "street_3d.gd").read_text(encoding="utf-8")
    assert "func ice_active" in src
    assert "func ice_avatar_xy" in src
    assert "func ice_banner_text" in src
    assert "_place_ice_lattice_wall" in src
    assert "_place_ice_floor" in src
    assert "_apply_ice_environment" in src
    assert "_begin_ice_transition" in src
    assert "ice_barrier" in src
    assert "ice_frame" in src
    assert "HEIST_LAYER_NAMES" in src
    assert "Perimeter Scrub" in src
    assert "Honeycomb Lattice" in src
    assert "Core Sanctum" in src
    assert "cyberspace" in src and "ice_heist" in src
    assert "Closes #141" not in src
    main = (GODOT / "scripts" / "main.gd").read_text(encoding="utf-8")
    assert "IceBanner" in main or "ice_banner" in main
    assert "ice_flash" in main or "IceFlash" in main
    assert "jack_in" in main and "jack_out" in main
    assert "ice_probe" in main
    tscn = (GODOT / "scenes" / "main.tscn").read_text(encoding="utf-8")
    assert "IceBanner" in tscn
    assert "IceFlash" in tscn


def test_docs_slice3_progress():
    d3d = (DOCS / "godot-3d.md").read_text(encoding="utf-8")
    assert "Cyberspace / ICE" in d3d
    assert "This PR" in d3d
    assert "ice_avatar_xy" in d3d or "px/py" in d3d
    assert "lattice" in d3d.lower()
    assert "Perimeter Scrub" in d3d
    assert "ice_jackin" in d3d or "ice bed" in d3d.lower() or "#134" in d3d
    assert "Refs #141" in d3d and "stays OPEN" in d3d
    assert "Closes #141" not in d3d
    client = (DOCS / "godot-client.md").read_text(encoding="utf-8")
    assert "ICE 3D" in client or "ICE lattice" in client or "cyberspace / ICE" in client.lower()


def test_snapshot_fields_godot_ice_reads():
    """Godot ICE 3D keys the same /ws fields as web — no server rewrite."""
    from snowcrash import constants as C
    from snowcrash.mmorpg import GameWorld

    w = GameWorld(1413)
    a = w.join("Ice3D")
    a.last_action_ts = 0
    a.actor.focus = a.actor.max_focus
    jx, jy = w.jackpoint_pos
    w._force_set_pos(a, jx, jy, C.PLANE_STREET, "test ice 3d")
    a.last_action_ts = 0
    street = w.snapshot(a)
    assert street.get("mode") not in ("cyberspace", "heist")
    assert street["cyberspace"]["can_jack_in"] is True
    assert street["cyberspace"]["active"] is False
    assert street["ice_heist"]["active"] is False

    a.last_action_ts = 0
    w.handle_action(a, "jack_in", "ice_gate")
    jacked = w.snapshot(a)
    assert jacked["mode"] == "cyberspace"
    cyber = jacked["cyberspace"]
    assert cyber["active"] is True
    assert "px" in cyber and "py" in cyber
    assert cyber.get("map")
    assert jacked.get("map") == cyber["map"]
    # Street body parked — player x/y is NOT the lattice avatar
    assert (a.actor.x, a.actor.y) == (jx, jy)
    assert (cyber["px"], cyber["py"]) != (None, None)
    assert "I" in "".join(cyber["map"]) or cyber.get("ice_remaining", 0) >= 0

    a.last_action_ts = 0
    w.handle_action(a, "jack_out")
    out = w.snapshot(a)
    assert out["mode"] != "cyberspace"
    assert out["cyberspace"]["active"] is False

    a.last_action_ts = 0
    w.handle_action(a, "heist_start")
    heist_snap = w.snapshot(a)
    assert heist_snap["mode"] == "heist"
    h = heist_snap["ice_heist"]
    assert h["active"] is True
    assert h.get("layer") == 1
    assert h.get("layers") == 3
    assert "px" in h and "py" in h
    assert heist_snap.get("map") == h["map"]
