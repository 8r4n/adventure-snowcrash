"""Offline spike tests for OSM → ASCII shard (#83)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "osm_to_ascii_shard.py"
FIXTURE = ROOT / "scripts" / "fixtures" / "tiny_downtown.osm.xml"


@pytest.mark.skipif(not SCRIPT.is_file(), reason="spike script missing")
def test_fixture_emits_shard_json(tmp_path: Path) -> None:
    out = tmp_path / "shard.json"
    txt = tmp_path / "shard.txt"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(FIXTURE),
            "--width",
            "32",
            "--height",
            "20",
            "--out",
            str(out),
            "--txt",
            str(txt),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert out.is_file()
    chunk = json.loads(out.read_text(encoding="utf-8"))
    assert chunk["format"] == "snowcrash_ascii_shard_v1"
    assert chunk["width"] == 32
    assert chunk["height"] == 20
    assert len(chunk["tiles"]) == 20
    assert all(len(row) == 32 for row in chunk["tiles"])
    assert "jackpoint" in chunk["landmarks"]
    assert "uplink" in chunk["landmarks"]
    glyphs = set("".join(chunk["tiles"]))
    # Expect street / building / landmark language from constants
    assert "=" in glyphs
    assert "#" in glyphs
    assert "J" in glyphs
    assert "U" in glyphs
    assert isinstance(chunk["shard_seed"], int)
    assert txt.is_file()
    assert "J" in txt.read_text(encoding="utf-8")
    assert "attribution" in chunk
    # Preview header should mention seed
    assert "seed=" in proc.stdout


def test_parse_fixture_directly() -> None:
    # Import without installing package: load module by path
    import importlib.util

    spec = importlib.util.spec_from_file_location("osm_to_ascii_shard", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    raw = FIXTURE.read_bytes()
    nodes, ways, pois, bounds = mod.parse_osm_xml(raw)
    assert bounds is not None
    assert len(nodes) >= 16
    assert any(w["tags"].get("highway") for w in ways)
    assert any(w["tags"].get("building") for w in ways)
    grid, landmarks = mod.rasterize(nodes, ways, pois, bounds, 24, 16)
    assert landmarks.get("jackpoint")
    assert landmarks.get("uplink")
    assert len(grid) == 16 and len(grid[0]) == 24
