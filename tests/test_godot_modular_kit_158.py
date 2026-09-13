"""Static checks: original modular corridor / prop kit (#158). Refs #163 / #141."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GODOT = ROOT / "godot_client"
MODELS = GODOT / "models"
DOCS = ROOT / "docs"

KIT = (
    "wall_panel",
    "floor_tile",
    "door_frame",
    "crate",
    "pipe",
    "neon_strip",
    "foliage",
    "vent",
)


def test_kit_obj_files_are_original():
    for name in KIT:
        p = MODELS / f"{name}.obj"
        assert p.is_file(), name
        body = p.read_text(encoding="utf-8")
        assert body.startswith("# adventure-snowcrash original kit #158")
        assert "Abandoned" not in body
        assert "perfoon" not in body.lower()
        assert body.count("\nf ") >= 8
        assert "\nv " in body
        assert "\nvn " in body


def test_mesh_kit_loader_and_role_catalog():
    src = (GODOT / "scripts" / "mesh_kit.gd").read_text(encoding="utf-8")
    assert "class_name MeshKit" in src
    assert "func get_mesh" in src
    assert "func mesh_for_role" in src
    assert "ROLE_MESH" in src
    assert '"wall": "wall_panel"' in src
    assert '"door": "door_frame"' in src
    assert "res://models/" in src
    assert "_parse_obj" in src
    assert "Closes #141" not in src
    assert "Closes #163" not in src
    for name in KIT:
        assert name in src


def test_street_instances_kit_by_role():
    src = (GODOT / "scripts" / "street_3d.gd").read_text(encoding="utf-8")
    assert "MeshKit.ensure" in src
    assert "_kit(" in src
    assert "_maybe_scatter_prop" in src
    assert "wall_panel" in src
    assert "floor_tile" in src
    assert "door_frame" in src
    assert "kit_scatter" in src
    # #150 silhouettes retained
    assert "jack_shaft" in src and "uplink_shaft" in src and "vendor_shaft" in src
    assert "MAX_POOLED_ENTITIES" in src
    assert "BUILD_RADIUS" in src
    assert "Closes #141" not in src
    assert "Closes #163" not in src


def test_graphics_settings_kit_scatter_high_only():
    gs = (GODOT / "scripts" / "graphics_settings.gd").read_text(encoding="utf-8")
    assert "func kit_scatter" in gs
    assert "return is_high()" in gs


def test_docs_158_catalog_and_comparison():
    d3d = (DOCS / "godot-3d.md").read_text(encoding="utf-8")
    assert "Modular corridor + prop kit (#158)" in d3d
    assert "Screenshot comparison" in d3d
    assert "kit-158-catalog.png" in d3d
    assert "wall_panel" in d3d
    assert "door_frame" in d3d
    assert "kit_scatter" in d3d
    assert "#150" in d3d
    assert "Closes #141" not in d3d
    assert "Closes #163" not in d3d
    shot = DOCS / "screenshots" / "kit-158-catalog.png"
    assert shot.is_file()
    assert shot.stat().st_size > 500
    bar = (DOCS / "steam-quality-bar.md").read_text(encoding="utf-8")
    assert "[x] [#158]" in bar or "[x] [#158]" in d3d


def test_no_abandoned_spaceship_meshes():
    for p in MODELS.rglob("*"):
        if not p.is_file():
            continue
        assert p.suffix.lower() in {".obj"}
        text = p.read_text(encoding="utf-8")
        assert "Hangar" not in text
        assert ".glb" not in text
    assert not list(MODELS.rglob("*.glb"))
    assert not list(MODELS.rglob("*.gltf"))
