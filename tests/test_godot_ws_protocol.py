"""Godot client WS envelope smoke (#118) — no Godot binary required."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_harness():
    path = ROOT / "scripts" / "godot_ws_harness.py"
    spec = importlib.util.spec_from_file_location("godot_ws_harness", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_godot_ws_message_shapes():
    harness = _load_harness()
    harness.run_with_starlette_client()
