"""Load snowcrash_ascii_shard_v1 JSON into a playable WorldBundle (#54 / #83).

Prebuilt OSM→ASCII packs (fixture or script output) live under
systems/data/shards/. Globe teleport prefers chunk_path when set; otherwise
falls back to generate_world(shard_seed).
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .. import constants as C
from ..entities import make_drone, make_infected, make_npc, make_player, make_thug
from ..items import make_payload_zero, make_pulse_pistol, make_stimpack, random_loot
from ..mapgen import FloorItem, GameMap, WorldBundle, _carve_rect, _fill

DATA_DIR = Path(__file__).resolve().parent / "data"
SHARDS_DIR = DATA_DIR / "shards"


def resolve_chunk_path(chunk_path: str) -> Path:
    """Resolve regions.json chunk_path relative to systems/data or cwd."""
    p = Path(str(chunk_path))
    if p.is_file():
        return p
    cand = DATA_DIR / p
    if cand.is_file():
        return cand
    cand = SHARDS_DIR / p.name
    if cand.is_file():
        return cand
    # Also allow repo-relative scripts/fixtures outputs
    repo = Path(__file__).resolve().parents[2]
    cand = repo / p
    if cand.is_file():
        return cand
    raise FileNotFoundError("ASCII shard not found: %s" % chunk_path)


def load_shard_json(path: str | Path) -> Dict[str, Any]:
    p = resolve_chunk_path(str(path)) if not Path(str(path)).is_file() else Path(str(path))
    with p.open("r", encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("format") != "snowcrash_ascii_shard_v1":
        raise ValueError("unsupported shard format: %s" % doc.get("format"))
    tiles = doc.get("tiles") or []
    if not tiles or not isinstance(tiles, list):
        raise ValueError("shard missing tiles")
    return doc


def _scale_stamp(
    dest: List[List[str]],
    src_lines: List[str],
    ox: int,
    oy: int,
    scale: int,
) -> None:
    h = len(src_lines)
    w = len(src_lines[0]) if src_lines else 0
    for y in range(h):
        row = src_lines[y]
        for x in range(min(w, len(row))):
            ch = row[x]
            for dy in range(scale):
                for dx in range(scale):
                    yy = oy + y * scale + dy
                    xx = ox + x * scale + dx
                    if 0 <= yy < len(dest) and 0 <= xx < len(dest[0]):
                        dest[yy][xx] = ch


def world_from_ascii_shard(
    chunk: Dict[str, Any],
    *,
    seed: Optional[int] = None,
    region_id: Optional[str] = None,
) -> WorldBundle:
    """Hydrate a WorldBundle from snowcrash_ascii_shard_v1 (scaled into MAP_*)."""
    if seed is None:
        seed = int(chunk.get("shard_seed") or 0)
    seed = int(seed)
    rng = random.Random(seed)
    w, h = C.MAP_WIDTH, C.MAP_HEIGHT
    tiles = _fill(w, h, C.WALL)
    _carve_rect(tiles, 1, 1, w - 2, h - 2, C.GRASS)

    src = [str(line) for line in chunk["tiles"]]
    sw = int(chunk.get("width") or (len(src[0]) if src else 0))
    sh = int(chunk.get("height") or len(src))
    if sw < 8 or sh < 8:
        raise ValueError("shard too small")

    # Nearest-neighbor scale so downtown fills most of the playable map
    scale = max(1, min((w - 8) // sw, (h - 8) // sh))
    dw, dh = sw * scale, sh * scale
    ox = (w - dw) // 2
    oy = (h - dh) // 2
    _scale_stamp(tiles, src, ox, oy, scale)

    # Arterial spokes from downtown to rim so the grass belt stays traversable
    cx, cy = w // 2, h // 2
    for x in range(2, w - 2):
        tiles[cy][x] = C.STREET if tiles[cy][x] in (C.GRASS, C.FLOOR) else tiles[cy][x]
        if cy + 1 < h - 1 and tiles[cy + 1][x] == C.GRASS:
            tiles[cy + 1][x] = C.STREET
    for y in range(2, h - 2):
        tiles[y][cx] = C.STREET if tiles[y][cx] in (C.GRASS, C.FLOOR) else tiles[y][cx]
        if cx + 1 < w - 1 and tiles[y][cx + 1] == C.GRASS:
            tiles[y][cx + 1] = C.STREET

    landmarks = dict(chunk.get("landmarks") or {})

    def lm_xy(key: str, default: Tuple[int, int]) -> Tuple[int, int]:
        raw = landmarks.get(key)
        if isinstance(raw, dict) and "x" in raw and "y" in raw:
            return (ox + int(raw["x"]) * scale + scale // 2, oy + int(raw["y"]) * scale + scale // 2)
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            return (ox + int(raw[0]) * scale + scale // 2, oy + int(raw[1]) * scale + scale // 2)
        return default

    jack_pos = lm_xy("jackpoint", (ox + dw // 4, oy + dh // 2))
    uplink_pos = lm_xy("uplink", (ox + 3 * dw // 4, oy + dh // 2))
    club_pos = lm_xy("club", (ox + dw // 2, oy + dh // 3))

    def _clamp_walk(x: int, y: int) -> Tuple[int, int]:
        x = max(2, min(w - 3, x))
        y = max(2, min(h - 3, y))
        if tiles[y][x] == C.WALL:
            for r in range(1, 12):
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        xx, yy = x + dx, y + dy
                        if 0 <= yy < h and 0 <= xx < w and tiles[yy][xx] != C.WALL and tiles[yy][xx] != C.WATER:
                            return xx, yy
        return x, y

    jack_pos = _clamp_walk(*jack_pos)
    uplink_pos = _clamp_walk(*uplink_pos)
    club_pos = _clamp_walk(*club_pos)
    tiles[jack_pos[1]][jack_pos[0]] = C.JACKPOINT
    tiles[uplink_pos[1]][uplink_pos[0]] = C.UPLINK

    explored = [[False] * w for _ in range(h)]
    visible = [[False] * w for _ in range(h)]
    gmap = GameMap(w, h, tiles, explored, visible, rooms=[])
    gmap.labels = {
        "jackpoint": jack_pos,
        "uplink": uplink_pos,
        "club": club_pos,
        "safehouse": (cx - 4, cy - 4),
    }

    # Spawn pads: street/floor cells away from jack swarm
    spawn_points: List[Tuple[int, int]] = []
    seen = set()
    for y in range(2, h - 2, 5):
        for x in range(2, w - 2, 7):
            if not gmap.walkable(x, y):
                continue
            if abs(x - jack_pos[0]) + abs(y - jack_pos[1]) <= 8:
                continue
            if tiles[y][x] not in (C.FLOOR, C.STREET, C.GRASS, C.DOOR):
                continue
            if (x, y) in seen:
                continue
            seen.add((x, y))
            spawn_points.append((x, y))
    rng.shuffle(spawn_points)
    spawn_points = spawn_points[: max(16, min(32, len(spawn_points)))]
    if not spawn_points:
        spawn_points = [_clamp_walk(cx, cy)]

    px, py = spawn_points[0]
    player = make_player(px, py)
    player.inventory.append(make_stimpack())
    actors = [player]
    occupied = {(px, py), jack_pos, uplink_pos}

    rid_label = region_id or chunk.get("region_id") or "remote shard"
    nx, ny = _clamp_walk(px + 2, py)
    if (nx, ny) in occupied:
        nx, ny = _clamp_walk(px - 2, py + 1)
    actors.append(
        make_npc(
            nx,
            ny,
            "Shard Cartographer",
            (
                "ASCII shard uplink for %s — topology from OSM→glyph pipeline (#83). "
                "Jackpoint and Metaverse uplink are painted from landmark POIs."
            )
            % rid_label,
            quest_flag="shard_briefing",
        )
    )
    occupied.add((nx, ny))

    cx2, cy2 = club_pos
    if (cx2, cy2) not in occupied and gmap.walkable(cx2, cy2):
        actors.append(
            make_npc(
                cx2,
                cy2,
                "Neon Relay",
                "Local mesh chatter. Payload-Zero still routes through the jack if you need a job.",
                quest_flag="club_tip",
            )
        )
        occupied.add((cx2, cy2))

    ux, uy = uplink_pos
    actors.append(
        make_npc(
            _clamp_walk(ux + 2, uy)[0],
            _clamp_walk(ux + 2, uy)[1],
            "Node Custodian",
            "Remote shard uplink. Bring clean packets — or Payload-Zero for a Babel scrub.",
            quest_flag="uplink_guard",
        )
    )
    occupied.add((actors[-1].x, actors[-1].y))

    # Sparse hostiles on streets
    enemy_spots: List[Tuple[int, int]] = []
    attempts = 0
    while len(enemy_spots) < 36 and attempts < 600:
        attempts += 1
        ex = rng.randint(2, w - 3)
        ey = rng.randint(2, h - 3)
        if not gmap.walkable(ex, ey):
            continue
        if (ex, ey) in occupied or (ex, ey) in seen:
            continue
        if abs(ex - px) + abs(ey - py) < 10:
            continue
        if abs(ex - jack_pos[0]) + abs(ey - jack_pos[1]) <= 3:
            continue
        if any(abs(ex - sx) + abs(ey - sy) <= C.SAFE_SPAWN_RADIUS for sx, sy in spawn_points):
            continue
        enemy_spots.append((ex, ey))
        occupied.add((ex, ey))
    for i, (ex, ey) in enumerate(enemy_spots):
        roll = rng.random()
        if roll < 0.45:
            actors.append(make_infected(ex, ey))
        elif roll < 0.8:
            actors.append(make_thug(ex, ey))
        else:
            actors.append(make_drone(ex, ey))

    floor_items: List[FloorItem] = [
        FloorItem(jack_pos[0], jack_pos[1], make_payload_zero()),
        FloorItem(*_clamp_walk(club_pos[0] + 1, club_pos[1]), make_pulse_pistol()),
    ]
    for _ in range(18):
        ix = rng.randint(2, w - 3)
        iy = rng.randint(2, h - 3)
        if gmap.walkable(ix, iy) and (ix, iy) not in occupied:
            loot = random_loot(rng)
            if loot:
                floor_items.append(FloorItem(ix, iy, loot))

    # Light multiplane: sew under/air along streets only
    under_tiles = _fill(w, h, C.WALL)
    air_tiles = _fill(w, h, C.WALL)
    shafts: List[Tuple[int, int]] = []
    for y in range(h):
        for x in range(w):
            st = tiles[y][x]
            if st in (C.STREET, C.MANHOLE, C.STAIRS_DOWN, C.STAIRS_UP):
                under_tiles[y][x] = C.FLOOR
                air_tiles[y][x] = C.STREET
            elif st in (C.FLOOR, C.DOOR, C.GRASS, C.JACKPOINT, C.UPLINK):
                if st in (C.FLOOR, C.DOOR, C.JACKPOINT, C.UPLINK):
                    air_tiles[y][x] = C.FLOOR
                else:
                    air_tiles[y][x] = C.GRASS
    # A few manholes
    for sx, sy in spawn_points[::4][:6]:
        if gmap.walkable(sx, sy) and tiles[sy][sx] == C.STREET:
            tiles[sy][sx] = C.MANHOLE
            under_tiles[sy][sx] = C.STAIRS_UP
            air_tiles[sy][sx] = C.STAIRS_DOWN
            shafts.append((sx, sy))

    under_map = GameMap(w, h, under_tiles, [[False] * w for _ in range(h)], [[False] * w for _ in range(h)], [])
    air_map = GameMap(w, h, air_tiles, [[False] * w for _ in range(h)], [[False] * w for _ in range(h)], [])
    planes = {
        C.PLANE_UNDER: under_map,
        C.PLANE_STREET: gmap,
        C.PLANE_AIR: air_map,
    }

    club_rects = []
    if club_pos:
        club_rects.append((club_pos[0] - 2, club_pos[1] - 2, 5, 5))

    return WorldBundle(
        gmap=gmap,
        player=player,
        actors=actors,
        floor_items=floor_items,
        uplink_pos=uplink_pos,
        jackpoint_pos=jack_pos,
        story_beats=[
            "ASCII shard hop: OSM-derived downtown stamped into Metaverse grid.",
            "Recover Payload-Zero near the painted jackpoint; uplink still takes the core.",
        ],
        spawn_points=spawn_points,
        planes=planes,
        shafts=shafts,
        club_rects=club_rects,
    )


def try_load_region_shard(
    chunk_path: Optional[str],
    *,
    seed: Optional[int] = None,
    region_id: Optional[str] = None,
) -> Optional[WorldBundle]:
    """Return WorldBundle if chunk_path resolves; else None (caller falls back to mapgen)."""
    if not chunk_path:
        return None
    try:
        chunk = load_shard_json(chunk_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    return world_from_ascii_shard(chunk, seed=seed, region_id=region_id)
