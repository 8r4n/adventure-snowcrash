"""Static checks: GodotSteam integration stub (#173). Refs #141 — never close that epic."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GODOT = ROOT / "godot_client"
DOCS = ROOT / "docs"
SCRIPTS = GODOT / "scripts"


def test_steam_bridge_autoload_and_noop_design():
    bridge = (SCRIPTS / "steam_bridge.gd").read_text(encoding="utf-8")
    assert "#173" in bridge
    assert "Refs #141" in bridge
    assert "Closes #141" not in bridge
    assert 'Engine.has_singleton("Steam")' in bridge
    assert "Engine.get_singleton" in bridge
    assert "ClassDB.class_call_static" not in bridge  # Godot 4.3-safe
    assert "func suggest_low_quality" in bridge
    assert "func set_achievement" in bridge
    assert "func is_deck" in bridge
    assert "func is_big_picture" in bridge
    assert "SNOWCRASH_DISABLE_STEAM" in bridge
    assert "headless" in bridge.lower()
    assert "PLACEHOLDER_APP_ID" in bridge
    assert "SteamDeck" in bridge
    assert "isSteamRunningOnSteamDeck" in bridge
    assert "isSteamInBigPictureMode" in bridge
    # Must not hard-reference the Steam identifier at parse time
    assert "\nSteam." not in bridge
    assert " Steam." not in bridge
    assert "extends Steam" not in bridge


def test_project_autoload_order_steam_before_graphics():
    proj = (GODOT / "project.godot").read_text(encoding="utf-8")
    assert 'SteamBridge="*res://scripts/steam_bridge.gd"' in proj
    assert 'GraphicsSettings="*res://scripts/graphics_settings.gd"' in proj
    steam_i = proj.index("SteamBridge=")
    gfx_i = proj.index("GraphicsSettings=")
    assert steam_i < gfx_i


def test_graphics_settings_low_hint_from_steam():
    gs = (SCRIPTS / "graphics_settings.gd").read_text(encoding="utf-8")
    assert "prefer_low_from_steam_hint" in gs
    assert "suggest_low_quality" in gs
    assert "SteamBridge" in gs
    assert "#173" in gs
    assert "Closes #141" not in gs


def test_install_path_and_appid_example():
    readme = GODOT / "addons" / "godotsteam" / "README.md"
    assert readme.is_file()
    body = readme.read_text(encoding="utf-8")
    assert "GodotSteam" in body
    assert "4.4.1" in body or "4.4+" in body
    assert "steam_appid.txt" in body
    example = GODOT / "steam_appid.txt.example"
    assert example.is_file()
    assert example.read_text(encoding="utf-8").strip() == "480"
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "steam_appid.txt" in gitignore
    assert "addons/godotsteam" in gitignore or "godotsteam" in gitignore


def test_docs_173_install_and_acceptance():
    gc = (DOCS / "godot-client.md").read_text(encoding="utf-8")
    assert "GodotSteam integration stub (#173)" in gc
    assert "SteamBridge" in gc
    assert "addons/godotsteam" in gc
    assert "suggest_low_quality" in gc
    assert "Closes #141" not in gc

    sp = (DOCS / "steam-packaging.md").read_text(encoding="utf-8")
    assert "GodotSteam stub (#173)" in sp
    assert "steam_appid.txt" in sp
    assert "[x] `steam_appid.txt` dev workflow documented" in sp

    sd = (DOCS / "steam-deck.md").read_text(encoding="utf-8")
    assert "#173" in sd
    assert "SteamBridge" in sd or "suggest_low_quality" in sd

    d3 = (DOCS / "godot-3d.md").read_text(encoding="utf-8")
    assert "GodotSteam (#173)" in d3 or "GodotSteam stub (#173)" in d3
    assert "SteamBridge" in d3
    assert "Closes #141" not in d3
    assert "Refs #141" in d3 or "#141" in d3


def test_no_vendored_steam_binaries():
    addon = GODOT / "addons" / "godotsteam"
    assert addon.is_dir()
    banned_suffixes = {".dll", ".so", ".dylib"}
    for path in addon.rglob("*"):
        if path.is_file():
            assert path.suffix.lower() not in banned_suffixes, path
            assert path.name != "steam_api.dll"
            assert path.name != "libsteam_api.so"
