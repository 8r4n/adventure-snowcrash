# Blender → Godot authored assets

Issue **[#179](https://github.com/8r4n/adventure-snowcrash/issues/179)** (parent **#141** · interim procedural kit **#158** · visual bar **#163**).

Procedural / primitive OBJ under `godot_client/models/*.obj` (#158) is the stopgap. Authored hard-surface pieces ship as **glTF 2.0 / GLB** from Blender 4.3+, rebuilt headless, and preferred by `MeshKit` when present.

**No Abandoned Spaceship IP.** Original Snowcrash / Catppuccin neon language only.

`Refs #141` — epic stays OPEN.

---

## Units, origin, axes

| Convention | Value |
|------------|--------|
| Blender units | **Metric**, `scale_length = 1.0` → **1.0 = 1 meter** |
| Tile | 1 m × 1 m footprint (matches `Street3D` `TILE`) |
| Wall height | **2.55 m** (`WALL_H`) |
| Door opening | ~2.2 m to lintel, origin still on the floor |
| Origin | **Tile-center floor contact** (Godot snap point). Do not leave origin at mesh centroid. |
| Apply scale | Always (`transform_apply` / Ctrl-A) before export |
| Up / forward | Blender Z-up → glTF/Godot Y-up, −Z forward. Verify the panel faces after import. |

World-scale GLB means `street_3d.gd` instances with **identity scale** at the tile origin (`MeshKit.is_authored`). The #158 unit OBJ kit still uses the historical `Vector3(1, WALL_H, 1)` offset.

---

## Naming

| Kind | Pattern | Examples |
|------|---------|----------|
| File / object | `role_variant` snake | `wall_panel`, `door_frame`, `deliverator_car` |
| Material slots | `Mat_*` | `Mat_WallConcrete`, `Mat_NeonSky`, `Mat_DoorFrame`, `Mat_NeonYellow`, `Mat_DeliveratorBody` |
| One mesh per file | Join parts (core + plates + neon) before export | Godot AOI instances a single `Mesh`, not a full scene per tile |

Future wave (not required this slice): `floor_tile`, `jackpoint`, `uplink`, `vendor_kiosk`, `neon_strip`, `crate`.

---

## Modeling bar

- Small **bevel** (1–2 segments, ~1–2 cm) on hard edges; apply the modifier.
- **UVs:** Smart Project or manual unwrap; island margin ≥ 0.02 so #156 trim/recolor still works.
- **Principled BSDF** only. Emission on neon slots. Street still applies Catppuccin `material_override` for role tint — authored slots are the PBR language and survive if override is lifted later.
- Read as modular corridor kit, not AAA organics.

---

## Export (glTF / GLB)

Preferred format: **GLB** (binary glTF 2.0). Draco optional; uncompressed is fine.

Headless (Blender 4.3+; numpy must be installed on *Blender’s* Python):

```bash
./scripts/blender_export_kit.sh
# equivalent:
blender --background --python tools/blender/export_kit.py --   --out godot_client/models --blend-out tools/blender/src
```

Exporter settings (see `tools/blender/export_kit.py`):

```python
bpy.ops.export_scene.gltf(
    filepath="out.glb",
    export_format="GLB",
    use_selection=True,
    export_apply=True,
    export_texcoords=True,
    export_normals=True,
    export_materials="EXPORT",
)
```

Also save `.blend` sources under `tools/blender/src/` (regenerate anytime; do not hand-edit the GLB).

**Fallback:** if glTF fails, OBJ with Y-up / −Z forward + UVs. `MeshKit` still loads `#158` OBJ.

numpy: `blender --background --python-expr "import sys; print(sys.executable)"` then `pip install numpy` into that interpreter.

---

## Godot import

1. Drop `.glb` in `godot_client/models/` next to the #158 `.obj` files.
2. Import dock: materials on; mesh scale ≈ 1 (already meters).
3. **`MeshKit` prefers GLB** via `ResourceLoader` / `GLTFDocument.append_from_file` (no editor import required for headless). Then OBJ, then a 1 m `BoxMesh`.
4. `street_3d.gd` `_kit_place`: authored → identity xform at tile origin; OBJ kit → legacy unit scale.
5. Pack as shared `Mesh` (AOI-friendly). Do **not** instance a full PackedScene per wall tile.
6. **Lights stay separate.** Emissive mats ≠ Omni. Budget remains courier + J + U. `MeshKit` never creates lights.
7. Low / High: `BUILD_RADIUS` 18, `MAX_POOLED_ENTITIES` 48, `kit_scatter()` High-only — unchanged.

---

## First wave shipped

| Piece | Path | Notes |
|-------|------|--------|
| `wall_panel` | `godot_client/models/wall_panel.glb` | 1×1×2.55 m, inset plates, mid rail, Sky neon trims |
| `door_frame` | `godot_client/models/door_frame.glb` | Jambs / lintel / threshold / Yellow neon |
| `deliverator_car` | `godot_client/models/deliverator_car.glb` | Courier ride prop, low poly hard-surface body + neon side stripes |

Sources: `tools/blender/export_kit.py` + `tools/blender/src/*.blend`. Rebuild with `./scripts/blender_export_kit.sh`.

`#158` OBJ files stay as fallback for pieces without a GLB yet (`floor_tile`, scatter props).

---

## Files

| Path | Role |
|------|------|
| `docs/godot-blender-assets.md` | This convention sheet |
| `scripts/blender_export_kit.sh` | Headless rebuild entry |
| `tools/blender/export_kit.py` | bpy builders + glTF export |
| `tools/blender/src/*.blend` | Regenerable Blender sources |
| `godot_client/models/*.glb` | Runtime meshes (`MeshKit`) |
| `godot_client/scripts/mesh_kit.gd` | GLB → Mesh, then OBJ |
| `godot_client/scripts/street_3d.gd` | `_kit_place` / `is_authored` |

`Refs #179` · `Refs #141` — #141 stays OPEN.
