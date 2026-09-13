"""Static checks: Godot 4.3 := type-inference fixes for headless export (#154)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "godot_client" / "scripts"


def test_audio_manager_chat_size_is_explicit_int():
    src = (SCRIPTS / "audio_manager.gd").read_text(encoding="utf-8")
    assert "var n: int = chat.size()" in src
    assert "var n := chat.size()" not in src


def test_year_docks_active_is_explicit_bool():
    src = (SCRIPTS / "year_docks.gd").read_text(encoding="utf-8")
    assert "var active: bool = (id == _open_id)" in src
    assert "var active := (id == _open_id)" not in src


def test_main_chord_keys_use_explicit_bool_not_variant_infer():
    src = (SCRIPTS / "main.gd").read_text(encoding="utf-8")
    for key in ("w", "a", "s", "d"):
        assert f"var {key}: bool = (" in src
        assert f'bool(_move_keys.get("{key}", false))' in src
    # Bad forms that broke Godot 4.3.stable headless export
    assert "var w := (" not in src
    assert "var a := (" not in src
    assert "var s := (" not in src
    assert "var d := (" not in src


def test_desktop_export_docs_note_linux_43_verification():
    doc = (ROOT / "docs" / "godot-desktop-export.md").read_text(encoding="utf-8")
    assert "godot-linux-2026-09-13" in doc
    assert "4.3.stable" in doc
