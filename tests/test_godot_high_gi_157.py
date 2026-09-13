"""Static checks: High-preset SSAO/SSIL/TAA/volumetric + probes (#157).

Refs #163 / #141 / #148 — never close those epics.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GODOT = ROOT / "godot_client"
DOCS = ROOT / "docs"


def test_graphics_settings_high_stack_knobs():
    gs = (GODOT / "scripts" / "graphics_settings.gd").read_text(encoding="utf-8")
    for name in (
        "ssao_enabled",
        "ssil_enabled",
        "taa_enabled",
        "volumetric_fog_enabled",
        "volumetric_fog_density_street",
        "volumetric_fog_density_ice",
        "volumetric_fog_density_globe",
        "reflection_probes_enabled",
    ):
        assert f"func {name}" in gs, name
    assert "return is_high()" in gs
    assert "#157" in gs
    assert "Closes #141" not in gs
    assert "Closes #163" not in gs


def test_street_applies_env_and_hotspot_probes():
    src = (GODOT / "scripts" / "street_3d.gd").read_text(encoding="utf-8")
    assert "env.ssao_enabled" in src
    assert "env.ssil_enabled" in src
    assert "env.volumetric_fog_enabled" in src
    assert "_add_hotspot_probe" in src
    assert "ReflectionProbe" in src
    assert "_add_hotspot_probe(holder" in src
    assert "core_holder" in src and "exit_holder" in src
    assert "not every tile" in src.lower() or "Hotspots only" in src or "hotspot" in src.lower()
    assert "courier + J + U" in src or "Omni budget" in src
    assert "Closes #141" not in src
    assert "Closes #163" not in src


def test_main_taa_and_globe_stack():
    main = (GODOT / "scripts" / "main.gd").read_text(encoding="utf-8")
    assert "use_taa" in main
    assert "taa_enabled" in main
    assert "prefer Low on Deck" in main or "High can be expensive" in main
    globe = (GODOT / "scripts" / "globe_3d.gd").read_text(encoding="utf-8")
    assert "ssao_enabled" in globe
    assert "volumetric_fog_enabled" in globe
    assert "Fill" in globe or "Omni" in globe


def test_docs_157_matrix():
    d3d = (DOCS / "godot-3d.md").read_text(encoding="utf-8")
    assert "High-preset GI / atmosphere (#157)" in d3d
    assert "SSAO" in d3d and "SSIL" in d3d and "TAA" in d3d
    assert "ReflectionProbe" in d3d or "ReflectionProbe" in d3d
    assert "jackpoint" in d3d.lower() or "**J**" in d3d
    assert "[x] [#157]" in d3d
    assert "Closes #141" not in d3d
    assert "Closes #163" not in d3d
    # Quality matrix Low off
    assert "SSAO (#157)" in d3d
    assert "Volumetric fog (#157)" in d3d
    bar = (DOCS / "steam-quality-bar.md").read_text(encoding="utf-8")
    assert "[x] [#157]" in bar
    sd = (DOCS / "steam-deck.md").read_text(encoding="utf-8")
    assert "SSAO" in sd or "#157" in sd


def test_omni_budget_unchanged():
    street = (GODOT / "scripts" / "street_3d.gd").read_text(encoding="utf-8")
    # Probes must not add OmniLight3D
    probe_fn = street.split("func _add_hotspot_probe")[1].split("\nfunc ")[0]
    assert "OmniLight3D" not in probe_fn
    assert "ReflectionProbe" in probe_fn
