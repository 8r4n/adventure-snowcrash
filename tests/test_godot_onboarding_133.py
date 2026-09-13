"""Static checks for Godot first-10 onboarding (#133) — no Godot binary required."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GODOT = ROOT / "godot_client"
DOCS = ROOT / "docs"


def test_onboarding_script_and_scene_present():
    assert (GODOT / "scripts" / "onboarding.gd").is_file()
    main = (GODOT / "scripts" / "main.gd").read_text(encoding="utf-8")
    assert "OnboardingBeat" in main
    assert "_wire_onboarding" in main
    assert "_format_objective" in main
    tscn = (GODOT / "scenes" / "main.tscn").read_text(encoding="utf-8")
    assert "OnboardingBeat" in tscn
    assert "onboarding.gd" in tscn


def test_dock_gate_api():
    docks = (GODOT / "scripts" / "year_docks.gd").read_text(encoding="utf-8")
    assert "func set_secondary_gated" in docks
    assert "_secondary_gated" in docks
    assert "OnboardingGateBanner" in docks or "onboarding beat" in docks.lower()


def test_onboarding_chapters_are_original_metaverse():
    src = (GODOT / "scripts" / "onboarding.gd").read_text(encoding="utf-8")
    assert "PAYLOAD-ZERO" in src
    assert "INTRO_CHAPTERS" in src
    assert "snowcrash_client.cfg" in src
    # Must not ship Diamond Age / other novel verbatim tells
    banned = ["Nell", "Hackworth", "John Percival", "Diamond Age"]
    for b in banned:
        assert b not in src


def test_docs_linked_from_quality_bar():
    onboarding = (DOCS / "godot-onboarding.md").read_text(encoding="utf-8")
    assert "#133" in onboarding or "**#133**" in onboarding
    assert "Playtest" in onboarding
    assert "Payload-Zero" in onboarding
    bar = (DOCS / "steam-quality-bar.md").read_text(encoding="utf-8")
    assert "godot-onboarding.md" in bar
