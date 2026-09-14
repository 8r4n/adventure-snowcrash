"""Static checks for Godot death/recap + inventory juice (Refs #118)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GODOT = ROOT / "godot_client"
DOCS = ROOT / "docs"


def test_death_recap_script_and_scene():
    script = GODOT / "scripts" / "death_recap.gd"
    assert script.is_file()
    src = script.read_text(encoding="utf-8")
    assert "class_name DeathRecapOverlay" in src
    assert "SIGNAL LOST" in src
    assert "respawn_options" in src
    assert "soft_hardcore" in src
    assert "respawn_requested" in src
    tscn = (GODOT / "scenes" / "main.tscn").read_text(encoding="utf-8")
    assert "DeathRecapOverlay" in tscn
    assert "death_recap.gd" in tscn


def test_main_wires_death_and_inventory_juice():
    main = (GODOT / "scripts" / "main.gd").read_text(encoding="utf-8")
    assert "_wire_death_recap" in main
    assert "death_recap.apply_snapshot" in main
    assert "_inv_juice_t" in main
    assert 'play_sfx("pickup")' in main
    assert "set_item_tooltip" in main
    net = (GODOT / "scripts" / "net_client.gd").read_text(encoding="utf-8")
    assert "func send_respawn(option_id" in net
    assert 'send_action("r"' in net


def test_docs_first_hour_and_client_progress():
    first = (DOCS / "godot-first-hour.md").read_text(encoding="utf-8")
    assert "SIGNAL LOST" in first
    assert "Refs #118" in first
    assert "Abandoned Spaceship" in first
    client = (DOCS / "godot-client.md").read_text(encoding="utf-8")
    assert "death_recap.gd" in client
    assert "godot-first-hour.md" in client
    assert "Death / respawn UX polish" in client
