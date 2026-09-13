"""Static checks for Godot FPS measurement harness (#148) — no Godot binary required."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GODOT = ROOT / "godot_client"
DOCS = ROOT / "docs"


def test_fps_meter_script_exists_and_covers_overlay_log():
    src = (GODOT / "scripts" / "fps_meter.gd").read_text(encoding="utf-8")
    assert "user://fps_samples.log" in src
    assert "KEY_F3" in src
    assert "Engine.get_frames_per_second" in src
    assert "--fps-log" in src
    assert "JSON.stringify" in src or "JSON." in src
    assert "MOUSE_FILTER_IGNORE" in src
    assert "quality_name" in src
    assert "build_radius" in src
    assert "max_pooled" in src or "max_pooled_entities" in src


def test_fps_meter_autoload_registered():
    proj = (GODOT / "project.godot").read_text(encoding="utf-8")
    assert 'FpsMeter="*res://scripts/fps_meter.gd"' in proj
    assert "GraphicsSettings=" in proj


def test_main_documents_f3_and_scene_mode():
    main = (GODOT / "scripts" / "main.gd").read_text(encoding="utf-8")
    assert "F3 fps" in main
    assert "fps_scene_mode" in main
    assert "_sync_fps_scene_mode" in main
    assert "FpsMeter" in main
    assert "KEY_F8" in main  # quality toggle stays


def test_low_preset_tightened_for_deck_headroom():
    gs = (GODOT / "scripts" / "graphics_settings.gd").read_text(encoding="utf-8")
    # Low values after #148
    assert "return 12 if is_low() else 18" in gs
    assert "return 10 if is_low() else 16" in gs
    assert "return 24 if is_low() else 48" in gs
    # High unchanged / Omni budget not expanded in this file
    assert "Omni" in gs


def test_docs_mention_148_protocol_and_tbd_table():
    d3d = (DOCS / "godot-3d.md").read_text(encoding="utf-8")
    assert "#148" in d3d
    assert "FPS measurement" in d3d
    assert "F3" in d3d
    assert "fps_samples.log" in d3d
    assert "TBD" in d3d
    assert "street combat" in d3d.lower() or "street combat" in d3d
    deck = (DOCS / "steam-deck.md").read_text(encoding="utf-8")
    assert "#148" in deck
    assert "fps-measurement-148" in deck or "FPS measurement" in deck
    assert "F3" in deck


def test_no_closes_141_in_fps_docs():
    """Keep epic open — harness PRs must not auto-close #141."""
    for rel in ("docs/godot-3d.md", "docs/steam-deck.md"):
        body = (ROOT / rel).read_text(encoding="utf-8")
        assert "Closes #141" not in body
