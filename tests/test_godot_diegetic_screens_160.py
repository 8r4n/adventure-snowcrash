"""Static checks: diegetic in-world screens (#160). Refs #163 / #141 — never close those epics."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GODOT = ROOT / "godot_client"
DOCS = ROOT / "docs"


def test_diegetic_screens_script_prefabs():
    src = (GODOT / "scripts" / "diegetic_screens.gd").read_text(encoding="utf-8")
    assert "class_name DiegeticScreens" in src
    assert "func spawn_terminal" in src
    assert "func spawn_billboard" in src
    assert "func paint(" in src
    assert "Label3D" in src
    assert "KIND_TERMINAL" in src or "jack_terminal" in src
    assert "streetnet_board" in src or "KIND_BILLBOARD" in src
    assert "AD_LOOP" in src
    assert "#160" in src
    assert "#133" in src
    assert "never opens year docks" in src.lower() or "never unlocks" in src.lower() or "Display-only" in src
    assert "no browser" in src.lower() or "Label3D" in src
    assert "WebBrowser" not in src
    assert "Closes #141" not in src
    assert "Closes #163" not in src
    assert "Abandoned" not in src or "no third-party" in src


def test_street_wires_diegetic_screens():
    src = (GODOT / "scripts" / "street_3d.gd").read_text(encoding="utf-8")
    assert "_paint_diegetic_screens" in src
    assert "DiegeticScreens.spawn_terminal" in src
    assert "DiegeticScreens.spawn_billboard" in src
    assert "DiegeticScreens.paint" in src
    assert "ScreenRoot" in src or "_screen_root" in src
    assert "#160" in src
    assert "#133" in src
    assert "Closes #141" not in src
    assert "Closes #163" not in src
    tscn = (GODOT / "scenes" / "street.tscn").read_text(encoding="utf-8")
    assert "ScreenRoot" in tscn


def test_graphics_settings_diegetic_low_high():
    gs = (GODOT / "scripts" / "graphics_settings.gd").read_text(encoding="utf-8")
    assert "func diegetic_screens_detailed" in gs
    assert "return is_high()" in gs
    assert "#160" in gs


def test_screens_do_not_unlock_docks():
    """#133: diegetic screens must not gate-unlock year docks."""
    src = (GODOT / "scripts" / "diegetic_screens.gd").read_text(encoding="utf-8")
    street = (GODOT / "scripts" / "street_3d.gd").read_text(encoding="utf-8")
    for body in (src, street):
        assert "set_secondary_gated(false)" not in body
        assert "YearDocks" not in body
        assert "cycle_dock" not in body


def test_docs_160_diegetic():
    d3d = (DOCS / "godot-3d.md").read_text(encoding="utf-8")
    assert "Diegetic in-world screens (#160)" in d3d
    assert "diegetic_screens.gd" in d3d
    assert "Label3D" in d3d
    assert "#133" in d3d
    assert "[x] [#160]" in d3d
    assert "Closes #141" not in d3d
    assert "Closes #163" not in d3d
    bar = (DOCS / "steam-quality-bar.md").read_text(encoding="utf-8")
    assert "[x] [#160]" in bar
