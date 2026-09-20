"""Static checks: Blender→Godot authored asset pipeline (#179).

No Blender / Godot binary required at test time. Refs #141 — never close that epic.
"""

from __future__ import annotations

import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GODOT = ROOT / "godot_client"
MODELS = GODOT / "models"
DOCS = ROOT / "docs"
TOOLS = ROOT / "tools" / "blender"

AUTHORED = ("wall_panel", "door_frame")


def _glb_json(data: bytes) -> str:
    assert data[:4] == b"glTF", "GLB magic"
    chunk_len = struct.unpack_from("<I", data, 12)[0]
    chunk_type = data[16:20]
    assert chunk_type == b"JSON", chunk_type
    return data[20 : 20 + chunk_len].decode("utf-8")


def test_docs_godot_blender_assets_conventions():
    doc = (DOCS / "godot-blender-assets.md").read_text(encoding="utf-8")
    assert "meters" in doc.lower() or "1.0 = 1 meter" in doc
    assert "origin" in doc.lower()
    assert "naming" in doc.lower() or "Mat_*" in doc
    assert "export" in doc.lower()
    assert "Godot import" in doc or "import" in doc.lower()
    assert "Blender 4.3" in doc
    assert "wall_panel" in doc and "door_frame" in doc
    assert "deliverator_car" in doc
    assert "scripts/blender_export_kit.sh" in doc
    assert "MeshKit" in doc
    assert "Abandoned Spaceship" in doc
    assert "not" in doc.lower()
    assert "Catppuccin" in doc
    assert "Closes #141" not in doc
    assert "Refs #141" in doc
    assert "stays OPEN" in doc
    d3d = (DOCS / "godot-3d.md").read_text(encoding="utf-8")
    assert "Blender-authored kit (#179)" in d3d
    assert "godot-blender-assets.md" in d3d
    assert "BUILD_RADIUS" in d3d
    assert "MAX_POOLED_ENTITIES" in d3d
    assert "Closes #141" not in d3d
    bar = (DOCS / "steam-quality-bar.md").read_text(encoding="utf-8")
    assert "[#179]" in bar
    assert "Closes #141" not in bar


def test_export_script_headless_blender():
    sh = ROOT / "scripts" / "blender_export_kit.sh"
    assert sh.is_file()
    assert sh.stat().st_mode & 0o111, "executable bit"
    body = sh.read_text(encoding="utf-8")
    assert "blender --background --python" in body or '"$BLENDER" --background --python' in body
    assert "tools/blender/export_kit.py" in body
    py = TOOLS / "export_kit.py"
    assert py.is_file()
    src = py.read_text(encoding="utf-8")
    assert "export_scene.gltf" in src
    assert 'export_format="GLB"' in src or "export_format='GLB'" in src
    assert "build_wall_panel" in src
    assert "build_door_frame" in src
    assert "build_deliverator_car" in src
    assert "wall_panel,door_frame,deliverator_car" in src
    assert "Mat_" in src
    assert "smart_project" in src
    assert "BEVEL" in src
    assert "METRIC" in src
    assert "not abandoned" in src.lower()
    assert "perfoon" not in src.lower()


def test_authored_glb_files_are_original():
    for name in AUTHORED:
        p = MODELS / f"{name}.glb"
        assert p.is_file(), name
        data = p.read_bytes()
        assert len(data) > 800, name
        js = _glb_json(data)
        assert "TEXCOORD" in js, name
        assert "Mat_" in js, name
        low = data.lower()
        assert b"abandoned" not in low
        assert b"hangar" not in low
        assert b"perfoon" not in low
        blend = TOOLS / "src" / f"{name}.blend"
        assert blend.is_file(), f"regenerable source missing: {blend}"
        assert blend.stat().st_size > 1000


def test_mesh_kit_prefers_glb_and_flags_authored():
    src = (GODOT / "scripts" / "mesh_kit.gd").read_text(encoding="utf-8")
    assert "class_name MeshKit" in src
    assert ".glb" in src
    assert "func is_authored" in src
    assert "func _load_glb" in src
    assert "GLTFDocument" in src
    assert "append_from_file" in src
    assert "_load_obj" in src
    assert '"wall": "wall_panel"' in src
    assert '"door": "door_frame"' in src
    # Prefer GLB then OBJ
    assert src.find("_load_glb") < src.find("_load_obj")
    assert "OmniLight" not in src
    assert "Closes #141" not in src
    assert "Closes #163" not in src
    for name in AUTHORED:
        assert name in src


def test_street_prefers_authored_without_changing_aoi_or_omni():
    src = (GODOT / "scripts" / "street_3d.gd").read_text(encoding="utf-8")
    assert "MeshKit.is_authored" in src
    assert "func _kit_place" in src
    assert "_kit_place(map_root, \"wall_panel\"" in src or '_kit_place(map_root, "wall_panel"' in src
    assert "_kit_place(map_root, \"door_frame\"" in src or '_kit_place(map_root, "door_frame"' in src
    assert "const BUILD_RADIUS_DEFAULT := 18" in src
    assert "const MAX_POOLED_ENTITIES := 48" in src
    assert "kit_scatter" in src
    assert "courier + J + U" in src
    assert "Closes #141" not in src
    assert "Closes #163" not in src
