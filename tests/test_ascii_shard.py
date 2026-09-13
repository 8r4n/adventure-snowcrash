"""ASCII shard load path for globe teleport (#54)."""

from __future__ import annotations

from pathlib import Path

import pytest

from snowcrash.systems.ascii_shard import (
    load_shard_json,
    resolve_chunk_path,
    try_load_region_shard,
    world_from_ascii_shard,
)

ROOT = Path(__file__).resolve().parents[1]
NEO = ROOT / "snowcrash" / "systems" / "data" / "shards" / "neo_tokyo.json"


@pytest.mark.skipif(not NEO.is_file(), reason="pilot shard missing")
def test_load_and_hydrate_neo_tokyo_pilot():
    chunk = load_shard_json("shards/neo_tokyo.json")
    assert chunk["format"] == "snowcrash_ascii_shard_v1"
    assert chunk.get("region_id") == "neo_tokyo"
    world = world_from_ascii_shard(chunk, region_id="neo_tokyo")
    assert world.gmap.width >= chunk["width"]
    assert world.jackpoint_pos
    assert world.uplink_pos
    jx, jy = world.jackpoint_pos
    assert world.gmap.tiles[jy][jx] == "J"
    assert any(not a.is_player() for a in world.actors)


def test_try_load_missing_returns_none():
    assert try_load_region_shard(None) is None
    assert try_load_region_shard("shards/does_not_exist_54.json") is None


def test_resolve_chunk_path():
    p = resolve_chunk_path("shards/neo_tokyo.json")
    assert p.is_file()
