"""Static checks: Godot camera juice (#161) — cosmetic only; /ws authority.

Refs #163 / #141 — never close those epics.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GODOT = ROOT / "godot_client"
DOCS = ROOT / "docs"


def test_graphics_settings_camera_juice_knobs():
    gs = (GODOT / "scripts" / "graphics_settings.gd").read_text(encoding="utf-8")
    assert "func look_smoothing" in gs
    assert "func head_bob" in gs
    assert "func look_yaw_rate" in gs
    assert "func look_pos_rate" in gs
    assert "head_bob" in gs
    assert "look_smooth" in gs
    # Low forces bob off
    assert "if is_low():" in gs
    assert "return false" in gs
    assert "cosmetic" in gs.lower() or "authority" in gs.lower()
    assert "Closes #141" not in gs
    assert "Closes #163" not in gs


def test_street_cosmetic_lerp_and_bob_not_authority():
    src = (GODOT / "scripts" / "street_3d.gd").read_text(encoding="utf-8")
    assert "_update_camera_juice" in src
    assert "_apply_head_bob" in src
    assert "_lerp_entity_meshes" in src
    assert "look_pos_rate" in src
    assert "look_yaw_rate" in src
    assert 'set_meta("target_pos"' in src
    assert "LAND_FOV" in src or "land_fov" in src
    assert "cosmetic" in src.lower() or "#161" in src
    # Still uses server pose targets
    assert "_target_pos" in src
    assert "_target_yaw" in src
    assert "Closes #141" not in src
    assert "Closes #163" not in src


def test_main_bob_toggle_ui():
    main = (GODOT / "scripts" / "main.gd").read_text(encoding="utf-8")
    assert "_on_bob_toggle" in main
    assert "KEY_F7" in main
    assert "toggle_head_bob" in main
    assert "authority" in main.lower() or "cosmetic" in main.lower()
    tscn = (GODOT / "scenes" / "main.tscn").read_text(encoding="utf-8")
    assert "BobBtn" in tscn
    assert "Bob: Off" in tscn


def test_docs_cosmetic_vs_authority():
    d3d = (DOCS / "godot-3d.md").read_text(encoding="utf-8")
    assert "Camera juice (#161)" in d3d
    assert "cosmetic vs authority" in d3d.lower() or "Cosmetic vs authority" in d3d or "cosmetic vs authority" in d3d
    assert "source of truth" in d3d.lower() or "Truth" in d3d
    assert "turn_left" in d3d
    assert "[x] [#161]" in d3d
    assert "Closes #141" not in d3d
    assert "Closes #163" not in d3d
    assert "Refs #163" in d3d
    assert "Refs #141" in d3d
    gc = (DOCS / "godot-client.md").read_text(encoding="utf-8")
    assert "Camera juice (#161)" in gc
    assert "cosmetic" in gc.lower()
    assert "/ws" in gc
    bar = (DOCS / "steam-quality-bar.md").read_text(encoding="utf-8")
    assert "[x] [#161]" in bar


def test_no_client_position_cheating_language():
    """Ensure we document that intents stay the same and mesh lerp is render-only."""
    street = (GODOT / "scripts" / "street_3d.gd").read_text(encoding="utf-8")
    assert "Render-only" in street or "render-only" in street or "cosmetic" in street.lower()
    # Entity paint still driven by snapshot x/y
    assert 'float(spec["x"])' in street
    assert 'float(spec["y"])' in street
