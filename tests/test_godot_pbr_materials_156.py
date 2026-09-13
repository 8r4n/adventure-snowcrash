"""Static checks: Godot trim / PBR + Catppuccin recolor library (#156).

No Godot binary required. Refs #163 / #141 — never close those epics.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GODOT = ROOT / "godot_client"
MATS = GODOT / "materials"
DOCS = ROOT / "docs"


def test_materials_library_files_exist():
    assert (MATS / "recolor_trim.gdshader").is_file()
    assert (MATS / "library.gd").is_file()
    for name in ("wall_teal.tres", "street_mantle.tres", "door_yellow.tres", "ice_glass.tres"):
        assert (MATS / name).is_file(), name
    tex = MATS / "textures"
    for name in (
        "trim_albedo.png",
        "trim_normal.png",
        "trim_orm.png",
        "concrete_albedo.png",
        "ice_grid.png",
    ):
        p = tex / name
        assert p.is_file(), name
        assert p.stat().st_size > 200, name


def test_shader_is_original_recolor_with_quality_hooks():
    src = (MATS / "recolor_trim.gdshader").read_text(encoding="utf-8")
    assert "shader_type spatial" in src
    assert "albedo_tint" in src
    assert "emission_energy" in src
    assert "use_normal" in src
    assert "use_orm" in src
    assert "trim_mix" in src
    assert "#156" in src
    assert "Catppuccin" in src
    # Must not ship / cite the demo shader as ours
    assert "RecoloredBase" not in src
    assert "third-party demo IP" in src or "Original shader" in src


def test_library_factory_maps_catppuccin_roles():
    src = (MATS / "library.gd").read_text(encoding="utf-8")
    assert "class_name MaterialLibrary" in src
    assert "func make(" in src
    assert "func make_alpha(" in src
    assert "func apply_quality(" in src
    assert "func set_emission(" in src
    assert "recolor_trim.gdshader" in src
    assert "trim_albedo.png" in src
    assert "materials_use_orm" in src
    for role in ("wall", "floor", "street", "door", "jack", "uplink", "vendor", "ice_wall", "ice_barrier"):
        assert f'"{role}"' in src
    assert "Omni" in src
    assert "Closes #141" not in src
    assert "Closes #163" not in src


def test_street_rebuild_uses_material_library():
    src = (GODOT / "scripts" / "street_3d.gd").read_text(encoding="utf-8")
    assert "MaterialLibrary.make" in src
    assert 'MaterialLibrary.make("wall"' in src
    # #159 routes floor/street/grass/water through make_ground (still MaterialLibrary).
    assert 'MaterialLibrary.make_ground("floor"' in src or 'MaterialLibrary.make("floor"' in src
    assert 'MaterialLibrary.make_ground("street"' in src or 'MaterialLibrary.make("street"' in src
    assert 'MaterialLibrary.make("door"' in src
    assert 'MaterialLibrary.make("jack"' in src
    assert 'MaterialLibrary.make("uplink"' in src
    assert 'MaterialLibrary.make("vendor"' in src
    assert "MaterialLibrary.make_alpha" in src or "MaterialLibrary.make_ground_alpha" in src
    assert "ice_wall" in src and "ice_barrier" in src
    assert "_apply_material_quality" in src
    assert "MaterialLibrary.set_emission" in src
    # #150 silhouettes kept
    assert "jack_shaft" in src and "uplink_shaft" in src and "vendor_shaft" in src
    assert 'glyph.text = "$"' in src
    # Omni budget language retained
    assert "Omni budget" in src or "courier + J + U" in src
    assert "Closes #141" not in src
    assert "Closes #163" not in src


def test_graphics_settings_high_low_orm_hook():
    gs = (GODOT / "scripts" / "graphics_settings.gd").read_text(encoding="utf-8")
    assert "func materials_use_orm" in gs
    assert "func materials_use_normal" in gs
    assert "return is_high()" in gs
    # Still no extra lights
    assert "never adds lights" in gs or "Omni" in gs


def test_tres_reference_shared_shader_not_demo():
    for name in ("wall_teal.tres", "street_mantle.tres", "door_yellow.tres", "ice_glass.tres"):
        body = (MATS / name).read_text(encoding="utf-8")
        assert "recolor_trim.gdshader" in body
        assert "albedo_tint" in body
        assert "RecoloredBase" not in body
        assert "perfoon" not in body.lower()


def test_docs_156_and_no_ip_copy():
    d3d = (DOCS / "godot-3d.md").read_text(encoding="utf-8")
    assert "Materials library (#156)" in d3d
    assert "MaterialLibrary" in d3d
    assert "recolor_trim.gdshader" in d3d
    assert "materials_use_orm" in d3d
    assert "courier + J + U" in d3d
    assert "third-party demo shaders" in d3d or "Not shipped" in d3d
    assert "Closes #141" not in d3d
    assert "Closes #163" not in d3d
    assert "Refs #163" in d3d
    assert "Refs #141" in d3d
    bar = (DOCS / "steam-quality-bar.md").read_text(encoding="utf-8")
    assert "#156" in bar
    assert "[x] [#156]" in bar or "[x] [#156]" in d3d


def test_no_abandoned_spaceship_assets_vendored():
    banned = (
        "RecoloredBase.gdshader",
        "Hangar.glb",
        "AbandonedSpaceship",
        "perfoon/Abandoned",
    )
    for path in MATS.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in {".png"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for tok in banned:
            if tok == "perfoon/Abandoned":
                continue  # cite-only would be in docs, not materials
            assert tok not in text, f"{path}: {tok}"
    # materials dir must not contain glb/gltf from anyone else
    for ext in (".glb", ".gltf", ".fbx"):
        assert not list(MATS.rglob(f"*{ext}"))
