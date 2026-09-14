#!/usr/bin/env python3
"""Generate sparse absolute-map fixtures for Godot 3D demo capture (#166)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from snowcrash.mmorpg import GameWorld  # noqa: E402

OUT_STREET = ROOT / "docs/fixtures/demo-godot3d-seed42.json"
OUT_ICE = ROOT / "docs/fixtures/demo-godot3d-ice-seed42.json"


def sparsify(snap: dict, radius: int = 18) -> dict:
    rows = snap.get("map") or []
    p = snap["player"]
    px, py = int(p["x"]), int(p["y"])
    cyber = snap.get("cyberspace") or {}
    if cyber.get("active"):
        px = int(cyber.get("px", px))
        py = int(cyber.get("py", py))
    h = len(rows)
    out = [""] * h
    y0, y1 = max(0, py - radius), min(h, py + radius + 1)
    for y in range(y0, y1):
        out[y] = rows[y]
    snap["map"] = out

    def near(e: dict, r: int = radius + 4) -> bool:
        return abs(int(e.get("x", 9999)) - px) + abs(int(e.get("y", 9999)) - py) <= r

    if isinstance(snap.get("entities"), list):
        snap["entities"] = [e for e in snap["entities"] if isinstance(e, dict) and near(e)][:40]
    if isinstance(snap.get("players"), list):
        snap["players"] = [e for e in snap["players"] if isinstance(e, dict) and near(e)][:12]
    return snap


def main() -> None:
    world = GameWorld(42)
    agent = world.join("Fixture3D")
    jx, jy = world.jackpoint_pos
    world._force_set_pos(agent, jx, jy + 2, 0, "fixture-166")
    agent.actor.facing = 0
    street = sparsify(world.snapshot(agent))
    lms = list(street.get("landmarks") or [])
    if not any(isinstance(l, dict) and l.get("id") == "jackpoint" for l in lms):
        lms.append({"id": "jackpoint", "name": "Jackpoint", "glyph": "J", "x": jx, "y": jy, "z": 0})
    street["landmarks"] = lms
    street.setdefault("jackpoint", [jx, jy])
    street.setdefault("mode", "street")
    OUT_STREET.parent.mkdir(parents=True, exist_ok=True)
    OUT_STREET.write_text(
        json.dumps(
            {
                "meta": {
                    "seed": 42,
                    "capture": "stills-fallback",
                    "note": "Sparse absolute-map fixture near jackpoint (#166). Original kit/materials only — no Abandoned Spaceship IP.",
                    "player": {"x": street["player"]["x"], "y": street["player"]["y"]},
                    "jackpoint": street.get("jackpoint"),
                },
                "state": street,
            },
            separators=(",", ":"),
        )
    )
    print("wrote", OUT_STREET, OUT_STREET.stat().st_size)

    world._force_set_pos(agent, jx, jy, 0, "on-j")
    world.handle_action(agent, "jack_in")
    ice = sparsify(world.snapshot(agent), radius=12)
    OUT_ICE.write_text(
        json.dumps(
            {
                "meta": {
                    "seed": 42,
                    "capture": "stills-fallback-ice",
                    "note": "ICE lattice sparse fixture (#166).",
                    "mode": ice.get("mode"),
                },
                "state": ice,
            },
            separators=(",", ":"),
        )
    )
    print("wrote", OUT_ICE, OUT_ICE.stat().st_size, "mode", ice.get("mode"))


if __name__ == "__main__":
    main()
