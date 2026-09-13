"""Static checks: Godot ground blend materials (#159). Refs #163 / #141 — never close those epics."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GODOT = ROOT / "godot_client"
MATS = GODOT / "materials"
DOCS = ROOT / "docs"


def test_ground_blend_shader_and_textures_exist():
    assert (MATS / "ground_blend.gdshader").is_file()
    tex = MATS / "textures"
    for name in (
        "ground_floor.png",
        "ground_street.png",
        "ground_grass.png",
        "ground_water.png",
        "ground_rubble.png",
    ):
        p = tex / name
        assert p.is_file(), name
        assert p.stat().st_size > 200, name
        assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_ground_shader_is_original_world_space_blend():
    src = (MATS / "ground_blend.gdshader").read_text(encoding="utf-8")
    assert "shader_type spatial" in src
    assert "#159" in src
    assert "world_pos" in src
    assert "blend_strength" in src
    assert "rubble_mix" in src
    assert "use_blend" in src
    assert "albedo_tint" in src
    assert "GroundBase" not in src
    assert "Abandoned" not in src
    assert "perfoon" not in src.lower()
    assert "third-party demo IP" in src or "Original shader" in src


def test_library_make_ground_factory():
    src = (MATS / "library.gd").read_text(encoding="utf-8")
    assert "GROUND_SHADER_PATH" in src
    assert "func make_ground(" in src
    assert "func make_ground_alpha(" in src
    assert "func apply_ground_quality(" in src
    assert "func is_ground_role(" in src
    assert "ground_blend.gdshader" in src
    assert "ground_blend_full" in src
    for role in ("floor", "street", "grass", "water", "rubble"):
        assert f'"{role}"' in src
    assert "Closes #141" not in src
    assert "Closes #163" not in src


def test_street_uses_ground_blend_mats():
    src = (GODOT / "scripts" / "street_3d.gd").read_text(encoding="utf-8")
    assert "MaterialLibrary.make_ground" in src
    assert 'MaterialLibrary.make_ground("floor"' in src
    assert 'MaterialLibrary.make_ground("street"' in src
    assert 'MaterialLibrary.make_ground("grass"' in src
    assert "MaterialLibrary.make_ground_alpha" in src
    assert 'make_ground("rubble"' in src or '_mats["rubble"]' in src
    assert "_maybe_rubble_overlay" in src
    assert "#159" in src
    assert "Omni budget" in src or "courier + J + U" in src
    assert "Closes #141" not in src
    assert "Closes #163" not in src


def test_graphics_settings_ground_low_high():
    gs = (GODOT / "scripts" / "graphics_settings.gd").read_text(encoding="utf-8")
    assert "func ground_blend_full" in gs
    assert "func ground_rubble_overlay" in gs
    assert "return is_high()" in gs
    assert "#159" in gs


def test_docs_159_ground_blend():
    d3d = (DOCS / "godot-3d.md").read_text(encoding="utf-8")
    assert "Ground blend (#159)" in d3d
    assert "ground_blend.gdshader" in d3d
    assert "make_ground" in d3d
    assert "ground_blend_full" in d3d
    assert "world-space" in d3d or "world XZ" in d3d
    assert "no per-tile bake" in d3d.lower() or "no per-tile bake" in d3d
    assert "[x] [#159]" in d3d
    assert "Closes #141" not in d3d
    assert "Closes #163" not in d3d
    assert "Refs #163" in d3d
    assert "Refs #141" in d3d
    bar = (DOCS / "steam-quality-bar.md").read_text(encoding="utf-8")
    assert "[x] [#159]" in bar


def test_no_abandoned_spaceship_ground_ip():
    banned = ("GroundBase.gdshader", "Hangar.glb", "AbandonedSpaceship")
    for path in MATS.rglob("*"):
        if not path.is_file() or path.suffix.lower() == ".png":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for tok in banned:
            assert tok not in text, f"{path}: {tok}"
