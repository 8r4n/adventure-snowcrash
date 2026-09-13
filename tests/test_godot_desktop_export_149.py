"""Static checks for Godot desktop export (#149) — no Godot binary required."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GODOT = ROOT / "godot_client"
DOCS = ROOT / "docs"
SCRIPT = ROOT / "scripts" / "export_godot_client.sh"


def test_export_presets_tracked_linux_and_windows():
    presets = (GODOT / "export_presets.cfg").read_text(encoding="utf-8")
    assert 'name="Linux/X11 (Steam Deck / desktop)"' in presets
    assert 'platform="Linux/X11"' in presets
    assert 'binary_format/architecture="x86_64"' in presets
    assert "build/linux/Snowcrash.x86_64" in presets
    assert 'name="Windows Desktop"' in presets
    assert 'platform="Windows Desktop"' in presets
    assert "build/windows/Snowcrash.exe" in presets
    example = (GODOT / "export_presets.cfg.example").read_text(encoding="utf-8")
    assert 'name="Linux/X11 (Steam Deck / desktop)"' in example
    assert 'name="Windows Desktop"' in example
    gitignore = (GODOT / ".gitignore").read_text(encoding="utf-8")
    assert "export_presets.cfg" not in [
        line.strip().split("#")[0].strip()
        for line in gitignore.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_export_script_exists_and_fails_without_godot():
    assert SCRIPT.is_file()
    assert os.access(SCRIPT, os.X_OK)
    # Clear PATH so godot cannot be found accidentally
    env = {**os.environ, "PATH": "/usr/bin:/bin", "GODOT": "", "GODOT_BIN": ""}
    env.pop("GODOT", None)
    env.pop("GODOT_BIN", None)
    # Use env -u style by deleting keys
    for k in ("GODOT", "GODOT_BIN"):
        env.pop(k, None)
    proc = subprocess.run(
        [str(SCRIPT), "linux"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 127
    assert "Godot 4 binary not found" in proc.stderr
    assert "godot-desktop-export.md" in proc.stderr


def test_desktop_export_docs_cover_ws_and_depots():
    doc = (DOCS / "godot-desktop-export.md").read_text(encoding="utf-8")
    assert "SNOWCRASH_WS_URL" in doc
    assert "export templates" in doc.lower() or "Export Templates" in doc
    assert "--export-release" in doc
    assert "build/linux/Snowcrash.x86_64" in doc
    assert "build/windows/Snowcrash.exe" in doc
    assert "steam-packaging.md" in doc
    assert "steam-deck.md" in doc
    assert "#67" in doc or "67" in doc
    client = (DOCS / "godot-client.md").read_text(encoding="utf-8")
    assert "godot-desktop-export.md" in client
    three_d = (DOCS / "godot-3d.md").read_text(encoding="utf-8")
    assert "godot-desktop-export.md" in three_d


def test_main_resolves_ws_url_from_env_and_config():
    main = (GODOT / "scripts" / "main.gd").read_text(encoding="utf-8")
    assert "func _apply_ws_url_defaults" in main
    assert "SNOWCRASH_WS_URL" in main
    assert 'NET_CONFIG_SECTION := "net"' in main
    assert 'cfg.set_value(NET_CONFIG_SECTION, "ws_url"' in main
