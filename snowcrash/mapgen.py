"""Procedural-ish map: massive fractured-LA street grid for MMORPG."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

from . import constants as C
from .entities import (
    Actor,
    make_drone,
    make_infected,
    make_npc,
    make_player,
    make_thug,
)
from .items import (
    Item,
    make_datachip,
    make_focus_tab,
    make_leather_jacket,
    make_mono_knife,
    make_payload_zero,
    make_pulse_pistol,
    make_stimpack,
    random_loot,
)


@dataclass
class FloorItem:
    x: int
    y: int
    item: Item


@dataclass
class GameMap:
    width: int
    height: int
    tiles: List[List[str]]
    explored: List[List[bool]]
    visible: List[List[bool]]
    rooms: List[Tuple[int, int, int, int, str]] = field(default_factory=list)
    labels: dict = field(default_factory=dict)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def walkable(self, x: int, y: int) -> bool:
        if not self.in_bounds(x, y):
            return False
        t = self.tiles[y][x]
        return t in (C.FLOOR, C.DOOR, C.STREET, C.GRASS, C.JACKPOINT, C.UPLINK)

    def blocks_sight(self, x: int, y: int) -> bool:
        if not self.in_bounds(x, y):
            return True
        return self.tiles[y][x] == C.WALL

    def opaque_glyph(self, x: int, y: int) -> str:
        return self.tiles[y][x]


def _fill(w: int, h: int, ch: str) -> List[List[str]]:
    return [[ch for _ in range(w)] for _ in range(h)]


def _carve_rect(tiles: List[List[str]], x: int, y: int, w: int, h: int, ch: str = C.FLOOR) -> None:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            if 0 <= yy < len(tiles) and 0 <= xx < len(tiles[0]):
                tiles[yy][xx] = ch


def _carve_room(
    tiles: List[List[str]], x: int, y: int, w: int, h: int
) -> Tuple[int, int, int, int]:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            if not (0 <= yy < len(tiles) and 0 <= xx < len(tiles[0])):
                continue
            if yy in (y, y + h - 1) or xx in (x, x + w - 1):
                tiles[yy][xx] = C.WALL
            else:
                tiles[yy][xx] = C.FLOOR
    return (x, y, w, h)


def _door(tiles: List[List[str]], x: int, y: int) -> None:
    if 0 <= y < len(tiles) and 0 <= x < len(tiles[0]):
        tiles[y][x] = C.DOOR


def _horizontal_street(tiles: List[List[str]], y: int, x0: int, x1: int) -> None:
    for x in range(x0, x1 + 1):
        if 0 <= y < len(tiles) and 0 <= x < len(tiles[0]):
            tiles[y][x] = C.STREET
            if y + 1 < len(tiles):
                tiles[y + 1][x] = C.STREET


def _vertical_street(tiles: List[List[str]], x: int, y0: int, y1: int) -> None:
    for y in range(y0, y1 + 1):
        if 0 <= y < len(tiles) and 0 <= x < len(tiles[0]):
            tiles[y][x] = C.STREET
            if x + 1 < len(tiles[0]):
                tiles[y][x + 1] = C.STREET


def _room_interior_spawns(x: int, y: int, w: int, h: int) -> List[Tuple[int, int]]:
    """Safe floor cells inside a carved room (not on walls/door ring)."""
    out: List[Tuple[int, int]] = []
    for yy in range(y + 1, y + h - 1):
        for xx in range(x + 1, x + w - 1):
            out.append((xx, yy))
    return out


def _plaza_spawns(cx: int, cy: int, radius: int = 2) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            out.append((cx + dx, cy + dy))
    return out


@dataclass
class WorldBundle:
    gmap: GameMap
    player: Actor
    actors: List[Actor]
    floor_items: List[FloorItem]
    uplink_pos: Tuple[int, int]
    jackpoint_pos: Tuple[int, int]
    story_beats: List[str]
    spawn_points: List[Tuple[int, int]] = field(default_factory=list)


def generate_world(seed: Optional[int] = None) -> WorldBundle:
    rng = random.Random(seed)
    w, h = C.MAP_WIDTH, C.MAP_HEIGHT
    tiles = _fill(w, h, C.WALL)

    # Outdoor base
    _carve_rect(tiles, 1, 1, w - 2, h - 2, C.GRASS)

    # Dense street grid
    h_streets = list(range(8, h - 6, 14))
    v_streets = list(range(10, w - 8, 18))
    for sy in h_streets:
        _horizontal_street(tiles, sy, 1, w - 2)
    for sx in v_streets:
        _vertical_street(tiles, sx, 1, h - 2)

    # A few diagonal-feel alleys (extra horizontal mid-block)
    for sy in range(15, h - 10, 28):
        _horizontal_street(tiles, sy + 5, 1, w - 2)

    rooms: List[Tuple[int, int, int, int, str]] = []
    spawn_candidates: List[Tuple[int, int]] = []
    occupied: Set[Tuple[int, int]] = set()

    def place_room(
        rx: int,
        ry: int,
        rw: int,
        rh: int,
        kind: str,
        door_side: str = "s",
        force: bool = False,
    ) -> Optional[Tuple[int, int, int, int]]:
        if rx < 2 or ry < 2 or rx + rw >= w - 1 or ry + rh >= h - 1:
            return None
        if not force:
            for ox, oy, ow, oh, _ in rooms:
                if not (rx + rw <= ox or ox + ow <= rx or ry + rh <= oy or oy + oh <= ry):
                    return None
        _carve_room(tiles, rx, ry, rw, rh)
        if door_side == "s":
            _door(tiles, rx + rw // 2, ry + rh - 1)
        elif door_side == "n":
            _door(tiles, rx + rw // 2, ry)
        elif door_side == "w":
            _door(tiles, rx, ry + rh // 2)
        else:
            _door(tiles, rx + rw - 1, ry + rh // 2)
        rooms.append((rx, ry, rw, rh, kind))
        return (rx, ry, rw, rh)

    # --- Landmark rooms ---
    # Safehouses (multiple districts)
    safehouse_specs = [
        (4, 2, 12, 7, "safehouse"),
        (w // 2 - 6, 2, 12, 7, "safehouse"),
        (w - 18, 2, 14, 7, "safehouse"),
        (4, h // 2 - 4, 11, 7, "safehouse"),
        (w - 16, h // 2 - 3, 12, 7, "safehouse"),
        (4, h - 12, 12, 8, "safehouse"),
        (w // 2 - 5, h - 11, 11, 7, "safehouse"),
        (w - 18, h - 12, 14, 8, "safehouse"),
    ]
    safehouses: List[Tuple[int, int, int, int]] = []
    for sx, sy, sw, sh, kind in safehouse_specs:
        placed = place_room(
            sx, sy, sw, sh, kind,
            door_side="s" if sy < h // 2 else "n",
            force=True,
        )
        if placed:
            safehouses.append(placed)
            for cell in _room_interior_spawns(*placed):
                spawn_candidates.append(cell)

    # Clubs
    club_specs = [
        (v_streets[1] + 4 if len(v_streets) > 1 else 40, 2, 14, 8, "club"),
        (v_streets[-2] + 4 if len(v_streets) > 2 else w - 40, h // 3, 13, 8, "club"),
        (w // 3, h // 2 + 2, 12, 7, "club"),
        (2 * w // 3, 2 * h // 3, 14, 8, "club"),
    ]
    clubs: List[Tuple[int, int, int, int]] = []
    for cx, cy, cw, ch, kind in club_specs:
        placed = place_room(cx, cy, cw, ch, kind, door_side="w", force=True)
        if placed:
            clubs.append(placed)
            # Fewer club spawns (party floors still ok)
            cells = _room_interior_spawns(*placed)
            spawn_candidates.extend(cells[::3])

    # Main jackpoint (SW-ish, away from NW safehouse) — enemy swarm lives here
    jx, jy, jw, jh = 6, h - 18, 14, 10
    jack_room = place_room(jx, jy, jw, jh, "jackpoint", door_side="n", force=True)
    if not jack_room:
        jx, jy, jw, jh = 8, h - 16, 12, 9
        jack_room = place_room(jx, jy, jw, jh, "jackpoint", door_side="n", force=True)
    if not jack_room:
        raise RuntimeError("failed to place jackpoint room")
    jx, jy, jw, jh = jack_room

    # Metaverse uplink (SE)
    ux, uy, uw, uh = w - 22, h - 18, 16, 10
    uplink_room = place_room(ux, uy, uw, uh, "uplink", door_side="w", force=True)
    if not uplink_room:
        ux, uy, uw, uh = w - 20, h - 16, 14, 9
        uplink_room = place_room(ux, uy, uw, uh, "uplink", door_side="w", force=True)
    if not uplink_room:
        raise RuntimeError("failed to place uplink room")
    ux, uy, uw, uh = uplink_room

    # Extra alley / shop / loft rooms scattered in blocks
    for _ in range(55):
        rx = rng.randint(3, w - 14)
        ry = rng.randint(3, h - 12)
        rw, rh = rng.randint(6, 11), rng.randint(5, 8)
        kind = rng.choice(["alley", "shop", "loft", "garage", "clinic"])
        door = rng.choice(["s", "n", "e", "w"])
        placed = place_room(rx, ry, rw, rh, kind, door_side=door)
        if placed and kind in ("clinic", "garage", "loft"):
            cells = _room_interior_spawns(*placed)
            if cells:
                spawn_candidates.append(cells[len(cells) // 2])

    # Street-corner / plaza spawns at intersections (safe outdoor)
    for sx in v_streets:
        for sy in h_streets:
            # Corners offset from the dual-width street
            for ox, oy in ((-2, -2), (3, -2), (-2, 3), (3, 3), (1, -3), (1, 4)):
                spawn_candidates.append((sx + ox, sy + oy))
            spawn_candidates.extend(_plaza_spawns(sx + 1, sy + 1, 1))

    # Mid-block plaza pockets
    for _ in range(12):
        px = rng.choice(v_streets) + rng.randint(-4, 6)
        py = rng.choice(h_streets) + rng.randint(-4, 6)
        spawn_candidates.extend(_plaza_spawns(px, py, 2))

    explored = [[False] * w for _ in range(h)]
    visible = [[False] * w for _ in range(h)]
    gmap = GameMap(w, h, tiles, explored, visible, rooms)

    # Permanent landmarks
    jack_pos = (jx + jw // 2, jy + 2)
    uplink_pos = (ux + uw // 2, uy + uh // 2)
    tiles[jack_pos[1]][jack_pos[0]] = C.JACKPOINT
    tiles[uplink_pos[1]][uplink_pos[0]] = C.UPLINK

    gmap.labels = {
        "safehouse": (safehouses[0][0] + 2, safehouses[0][1] + 2) if safehouses else (4, 3),
        "club": (clubs[0][0] + 3, clubs[0][1] + 3) if clubs else (40, 4),
        "jackpoint": jack_pos,
        "uplink": uplink_pos,
    }

    # Deduplicate / validate spawn points — never on jackpoint swarm or uplink core
    def _near_danger(x: int, y: int) -> bool:
        if abs(x - jack_pos[0]) + abs(y - jack_pos[1]) <= 8:
            return True
        if abs(x - uplink_pos[0]) + abs(y - uplink_pos[1]) <= 3:
            return True
        return False

    spawn_points: List[Tuple[int, int]] = []
    seen: Set[Tuple[int, int]] = set()
    for x, y in spawn_candidates:
        if (x, y) in seen:
            continue
        if not gmap.walkable(x, y):
            continue
        if _near_danger(x, y):
            continue
        # Prefer floor/street/grass
        t = tiles[y][x]
        if t not in (C.FLOOR, C.STREET, C.GRASS, C.DOOR):
            continue
        seen.add((x, y))
        spawn_points.append((x, y))

    # Ensure plenty of spread-out spawns: thin to max ~1 per local cell cluster
    # Keep all if <= 40; else diversify by grid buckets
    if len(spawn_points) > 48:
        buckets: dict = {}
        diversified: List[Tuple[int, int]] = []
        for x, y in spawn_points:
            key = (x // 12, y // 10)
            if key not in buckets or buckets[key] < 2:
                buckets[key] = buckets.get(key, 0) + 1
                diversified.append((x, y))
        spawn_points = diversified

    # Guarantee minimum count by adding more street corners if needed
    if len(spawn_points) < 16:
        for sx in v_streets:
            for sy in h_streets:
                for ox, oy in ((-3, -3), (4, -3), (-3, 4), (4, 4)):
                    x, y = sx + ox, sy + oy
                    if gmap.walkable(x, y) and not _near_danger(x, y) and (x, y) not in seen:
                        seen.add((x, y))
                        spawn_points.append((x, y))
                if len(spawn_points) >= 24:
                    break
            if len(spawn_points) >= 24:
                break

    # Player starts at first safehouse spawn
    if safehouses:
        px, py = safehouses[0][0] + 2, safehouses[0][1] + 2
    elif spawn_points:
        px, py = spawn_points[0]
    else:
        px, py = 5, 5
    player = make_player(px, py)
    player.inventory.append(make_stimpack())
    player.inventory.append(make_mono_knife())
    player.inventory[-1].equipped = True
    occupied.add((px, py))

    actors: List[Actor] = [player]

    # NPCs at landmarks
    if safehouses:
        sx0, sy0, sw0, sh0 = safehouses[0]
        actors.append(
            make_npc(
                sx0 + 4,
                sy0 + 2,
                "Ngoc 'Relay' Tran",
                (
                    "Courier job's simple, Rin: someone dumped Payload-Zero in the old "
                    "jackpoint. Scrub it or sleeve it, then punch it through "
                    "the Metaverse uplink. Don't recite anything that feels like a prayer. "
                    "Streets are huge — safehouses are marked on your HUD when you find them."
                ),
                quest_flag="briefing",
            )
        )
        occupied.add((sx0 + 4, sy0 + 2))
    if clubs:
        cx0, cy0, cw0, ch0 = clubs[0]
        actors.append(
            make_npc(
                cx0 + 3,
                cy0 + 3,
                "DJ Glassline",
                (
                    "Club's loud so the drones don't hear the deals. Infected avatars "
                    "are glitching hard tonight. Pulse pistols in alley lockers. "
                    "Uplink's locked until you've got the core."
                ),
                quest_flag="club_tip",
            )
        )
        occupied.add((cx0 + 3, cy0 + 3))
    actors.append(
        make_npc(
            ux + 3,
            uy + 3,
            "Node Custodian",
            (
                "This uplink speaks only in clean packets. Bring Payload-Zero here "
                "and I'll help you neutralize or ship it into the Metaverse proper. "
                "Arrive empty-handed and you're just another tourist."
            ),
            quest_flag="uplink_guard",
        )
    )
    occupied.add((ux + 3, uy + 3))

    # Secondary NPCs
    if len(safehouses) > 1:
        s1 = safehouses[1]
        actors.append(
            make_npc(
                s1[0] + 3,
                s1[1] + 2,
                "Patch Medtech",
                "Stim packs restock here when the streets chew you up. Stay off the jackpoint swarm.",
                quest_flag="med_tip",
            )
        )
        occupied.add((s1[0] + 3, s1[1] + 2))

    # Enemies — spread across city, never on spawn points / near player start
    spawn_set = set(spawn_points)
    enemy_spots: List[Tuple[int, int]] = []
    attempts = 0
    target_enemies = 70
    while len(enemy_spots) < target_enemies and attempts < 800:
        attempts += 1
        ex = rng.randint(2, w - 3)
        ey = rng.randint(2, h - 3)
        if not gmap.walkable(ex, ey):
            continue
        if (ex, ey) in occupied or (ex, ey) in spawn_set:
            continue
        if abs(ex - px) + abs(ey - py) < 10:
            continue
        if any(abs(ex - sx) + abs(ey - sy) < 4 for sx, sy in spawn_points):
            continue
        # Don't pack too near other enemies
        if any(abs(ex - ox) + abs(ey - oy) < 2 for ox, oy in enemy_spots[-15:]):
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

    # Guaranteed jackpoint swarm (NOT spawn points)
    for ox, oy in ((2, 3), (5, 4), (8, 5), (4, 6), (7, 3)):
        ex, ey = jx + ox, jy + oy
        if gmap.walkable(ex, ey) and (ex, ey) not in occupied:
            if len(actors) % 3 == 0:
                actors.append(make_drone(ex, ey))
            elif len(actors) % 3 == 1:
                actors.append(make_infected(ex, ey))
            else:
                actors.append(make_thug(ex, ey))
            occupied.add((ex, ey))

    # Floor items
    floor_items: List[FloorItem] = []
    floor_items.append(FloorItem(jx + 4, jy + 4, make_payload_zero()))
    if clubs:
        cx0, cy0, cw0, ch0 = clubs[0]
        floor_items.append(FloorItem(cx0 + 5, cy0 + 2, make_pulse_pistol()))
        floor_items.append(FloorItem(cx0 + 6, cy0 + 4, make_focus_tab()))
    if safehouses:
        sx0, sy0, sw0, sh0 = safehouses[0]
        floor_items.append(FloorItem(sx0 + 6, sy0 + 3, make_leather_jacket()))
    floor_items.append(
        FloorItem(
            w // 2,
            h // 3,
            make_datachip(
                "Burbclave Rumor Chip",
                "Notes on Payload-Zero: a speech-act weapon. Neutralize at uplink.",
            ),
        )
    )

    for _ in range(40):
        ix = rng.randint(2, w - 3)
        iy = rng.randint(2, h - 3)
        if gmap.walkable(ix, iy) and (ix, iy) not in spawn_set:
            loot = random_loot(rng)
            if loot:
                floor_items.append(FloorItem(ix, iy, loot))

    story = [
        "Briefing: Relay Tran wants Payload-Zero recovered from the jackpoint.",
        "Rumor: Club Glassline knows about street weapons and infected avatars.",
        "Discovery: Payload-Zero sits in a Faraday sleeve in the south jackpoint.",
        "Choice: Bring the core to the Metaverse uplink to scrub or transmit.",
        "Victory: Payload neutralized / couriered — fractured LA breathes easier.",
    ]

    return WorldBundle(
        gmap=gmap,
        player=player,
        actors=actors,
        floor_items=floor_items,
        uplink_pos=uplink_pos,
        jackpoint_pos=jack_pos,
        story_beats=story,
        spawn_points=spawn_points,
    )
