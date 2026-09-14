"""Snowcrash Blender kit — original hard-surface pieces for Godot (#179).

Headless: blender --background --python tools/blender/export_kit.py -- --out godot_client/models

Units: metric meters. Origin at tile-center floor contact. Apply scale. Smart UV.
Materials named Mat_*. Catppuccin neon language — not Abandoned Spaceship IP.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy


def _argv_after_double_dash() -> list[str]:
    if "--" in sys.argv:
        return sys.argv[sys.argv.index("--") + 1 :]
    return []


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0


def apply_scale(obj) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.select_set(False)


def bevel(obj, width: float = 0.012, segments: int = 2) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_add(type="BEVEL")
    obj.modifiers["Bevel"].width = width
    obj.modifiers["Bevel"].segments = segments
    obj.modifiers["Bevel"].limit_method = "ANGLE"
    bpy.ops.object.modifier_apply(modifier="Bevel")
    obj.select_set(False)


def unwrap(obj) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.select_set(False)


def make_mat(name: str, color, roughness: float = 0.7, emission=None, emission_strength: float = 0.0):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        if emission is not None:
            bsdf.inputs["Emission Color"].default_value = (
                emission[0],
                emission[1],
                emission[2],
                1.0,
            )
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = emission_strength
    return mat


def add_box(name: str, loc, scale, material, do_bevel: bool = True, bevel_w: float = 0.012):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    apply_scale(obj)
    if do_bevel:
        bevel(obj, width=bevel_w, segments=2)
    obj.data.materials.clear()
    obj.data.materials.append(material)
    return obj


def join_named(keep_name: str, objects: list) -> object:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    joined = bpy.context.active_object
    joined.name = keep_name
    joined.location = (0.0, 0.0, 0.0)
    return joined


def build_wall_panel() -> object:
    """1 m × 1 m tile, 2.55 m tall, origin at floor center. Inset plates + neon."""
    mat_wall = make_mat("Mat_WallConcrete", (0.12, 0.14, 0.18), roughness=0.74)
    mat_rail = make_mat("Mat_WallRail", (0.18, 0.20, 0.24), roughness=0.45)
    mat_neon = make_mat(
        "Mat_NeonSky",
        (0.50, 0.85, 1.00),
        roughness=0.25,
        emission=(0.40, 0.85, 1.00),
        emission_strength=4.0,
    )
    core = add_box("wall_core", (0.0, 0.0, 1.275), (0.98, 0.98, 2.55), mat_wall, bevel_w=0.018)
    plates = [
        add_box("plate_n", (0.0, 0.485, 1.45), (0.70, 0.04, 1.05), mat_wall, bevel_w=0.008),
        add_box("plate_s", (0.0, -0.485, 1.45), (0.70, 0.04, 1.05), mat_wall, bevel_w=0.008),
        add_box("plate_e", (0.485, 0.0, 1.45), (0.04, 0.70, 1.05), mat_wall, bevel_w=0.008),
        add_box("plate_w", (-0.485, 0.0, 1.45), (0.04, 0.70, 1.05), mat_wall, bevel_w=0.008),
    ]
    rail = add_box("mid_rail", (0.0, 0.0, 1.22), (1.00, 1.00, 0.07), mat_rail, bevel_w=0.006)
    base = add_box("baseboard", (0.0, 0.0, 0.10), (1.00, 1.00, 0.20), mat_rail, bevel_w=0.008)
    cap = add_box("cornice", (0.0, 0.0, 2.48), (1.00, 1.00, 0.10), mat_rail, bevel_w=0.006)
    neons = [
        add_box("neon_n", (0.0, 0.502, 1.58), (0.78, 0.018, 0.045), mat_neon, do_bevel=False),
        add_box("neon_s", (0.0, -0.502, 1.58), (0.78, 0.018, 0.045), mat_neon, do_bevel=False),
        add_box("neon_e", (0.502, 0.0, 1.58), (0.018, 0.78, 0.045), mat_neon, do_bevel=False),
        add_box("neon_w", (-0.502, 0.0, 1.58), (0.018, 0.78, 0.045), mat_neon, do_bevel=False),
    ]
    parts = [core] + plates + [rail, base, cap] + neons
    joined = join_named("wall_panel", parts)
    unwrap(joined)
    return joined


def build_door_frame() -> object:
    """1 m tile door: jambs / lintel / threshold. Origin at floor center. ~2.2 m opening."""
    mat_frame = make_mat("Mat_DoorFrame", (0.18, 0.16, 0.12), roughness=0.42)
    mat_neon = make_mat(
        "Mat_NeonYellow",
        (0.98, 0.80, 0.35),
        roughness=0.22,
        emission=(0.98, 0.82, 0.30),
        emission_strength=3.5,
    )
    left = add_box("jamb_l", (-0.42, 0.0, 1.10), (0.16, 0.22, 2.20), mat_frame, bevel_w=0.012)
    right = add_box("jamb_r", (0.42, 0.0, 1.10), (0.16, 0.22, 2.20), mat_frame, bevel_w=0.012)
    lintel = add_box("lintel", (0.0, 0.0, 2.22), (1.00, 0.24, 0.18), mat_frame, bevel_w=0.010)
    thresh = add_box("threshold", (0.0, 0.0, 0.05), (1.00, 0.28, 0.10), mat_frame, bevel_w=0.008)
    lip_l = add_box("lip_l", (-0.32, 0.0, 1.10), (0.04, 0.16, 2.12), mat_frame, bevel_w=0.004)
    lip_r = add_box("lip_r", (0.32, 0.0, 1.10), (0.04, 0.16, 2.12), mat_frame, bevel_w=0.004)
    neon = add_box("neon_lintel", (0.0, 0.0, 2.33), (0.72, 0.05, 0.035), mat_neon, do_bevel=False)
    parts = [left, right, lintel, thresh, lip_l, lip_r, neon]
    joined = join_named("door_frame", parts)
    unwrap(joined)
    return joined


def export_glb(obj, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(
        filepath=str(dest),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
    )
    print("WROTE_GLB", dest, dest.stat().st_size)


def save_blend(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(dest))
    print("WROTE_BLEND", dest, dest.stat().st_size)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export Snowcrash Blender kit (#179)")
    here = Path(__file__).resolve()
    repo = here.parents[2]
    p.add_argument("--out", type=Path, default=repo / "godot_client" / "models")
    p.add_argument("--blend-out", type=Path, default=here.parent / "src")
    p.add_argument(
        "--pieces",
        default="wall_panel,door_frame",
        help="Comma list: wall_panel,door_frame",
    )
    return p.parse_args(_argv_after_double_dash())


def main() -> None:
    args = parse_args()
    builders = {
        "wall_panel": build_wall_panel,
        "door_frame": build_door_frame,
    }
    wanted = [s.strip() for s in args.pieces.split(",") if s.strip()]
    for name in wanted:
        if name not in builders:
            raise SystemExit(f"unknown piece {name!r}; choose from {sorted(builders)}")
        reset_scene()
        obj = builders[name]()
        export_glb(obj, Path(args.out) / f"{name}.glb")
        save_blend(Path(args.blend_out) / f"{name}.blend")
    print("KIT_EXPORT_OK", ",".join(wanted))


if __name__ == "__main__":
    main()
