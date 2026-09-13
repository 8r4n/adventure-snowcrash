"""Static checks: Abandoned Spaceship visual-bar docs (#162). Refs #163 / #141 — never Closes those epics."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def test_steam_quality_bar_cites_abandoned_spaceship_and_blastronaut():
    bar = (DOCS / "steam-quality-bar.md").read_text(encoding="utf-8")
    assert "Abandoned Spaceship" in bar
    assert "perfoon/Abandoned-Spaceship-Godot-Demo" in bar
    assert "BLASTRONAUT" in bar
    assert "store.steampowered.com/app/1392650" in bar
    assert "#163" in bar
    assert "look" in bar.lower()
    # Children of the visual-bar epic
    for n in ("#156", "#157", "#158", "#159", "#160", "#161", "#162"):
        assert n in bar
    assert "Closes #141" not in bar
    assert "Closes #163" not in bar
    assert "keep parent epics" in bar.lower() or "Refs" in bar


def test_godot_3d_visual_bar_section_will_and_wont_copy():
    d3d = (DOCS / "godot-3d.md").read_text(encoding="utf-8")
    assert "## Visual bar (#163)" in d3d
    assert "Abandoned Spaceship" in d3d
    assert "BLASTRONAUT" in d3d
    assert "What we will copy" in d3d
    assert "What we will not copy" in d3d
    assert "Catppuccin" in d3d
    assert "courier + J + U" in d3d
    assert "meshes, textures" in d3d.lower() or "Meshes, textures" in d3d
    assert "live `/ws`" in d3d or "live `/ws` snapshot" in d3d
    for n in ("#156", "#157", "#158", "#159", "#160", "#161", "#162"):
        assert n in d3d
    assert "Closes #141" not in d3d
    assert "Closes #163" not in d3d
    assert "Refs #141" in d3d and "stays OPEN" in d3d


def test_visual_bar_docs_do_not_ship_abandoned_spaceship_assets():
    """Docs cite the demo as a bar only — no vendored demo paths."""
    for rel in ("docs/steam-quality-bar.md", "docs/godot-3d.md"):
        body = (ROOT / rel).read_text(encoding="utf-8")
        assert "res://addons/abandoned" not in body.lower()
        assert "Hangar.glb" not in body
        assert "RecoloredBase.gdshader" not in body
