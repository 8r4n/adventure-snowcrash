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
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "Closes #141" not in text
        assert "closes #141" not in text
