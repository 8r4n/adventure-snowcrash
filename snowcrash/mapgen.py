"""Procedural-ish map: streets, safehouse, club, jackpoint."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

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
    # Outer walls stay as WALL; interior floor
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


@dataclass
class WorldBundle:
    gmap: GameMap
    player: Actor
    actors: List[Actor]
    floor_items: List[FloorItem]
    uplink_pos: Tuple[int, int]
    jackpoint_pos: Tuple[int, int]
    story_beats: List[str]


def generate_world(seed: Optional[int] = None) -> WorldBundle:
    rng = random.Random(seed)
    w, h = C.MAP_WIDTH, C.MAP_HEIGHT
    tiles = _fill(w, h, C.WALL)

    # Outdoor plaza / streets
    _carve_rect(tiles, 1, 1, w - 2, h - 2, C.GRASS)
    _horizontal_street(tiles, 8, 1, w - 2)
    _horizontal_street(tiles, 20, 1, w - 2)
    _vertical_street(tiles, 15, 1, h - 2)
    _vertical_street(tiles, 40, 1, h - 2)

    rooms: List[Tuple[int, int, int, int, str]] = []

    # Safehouse (NW)
    sx, sy, sw, sh = 3, 2, 10, 6
    _carve_room(tiles, sx, sy, sw, sh)
    _door(tiles, sx + sw // 2, sy + sh - 1)
    rooms.append((sx, sy, sw, sh, "safehouse"))

    # Neon Club (NE)
    cx, cy, cw, ch = 45, 2, 12, 7
    _carve_room(tiles, cx, cy, cw, ch)
    _door(tiles, cx, cy + ch // 2)
    rooms.append((cx, cy, cw, ch, "club"))

    # Jackpoint / server room (SW)
    jx, jy, jw, jh = 3, 22, 11, 7
    _carve_room(tiles, jx, jy, jw, jh)
    _door(tiles, jx + jw // 2, jy)
    rooms.append((jx, jy, jw, jh, "jackpoint"))

    # Metaverse uplink node (SE)
    ux, uy, uw, uh = 44, 22, 13, 7
    _carve_room(tiles, ux, uy, uw, uh)
    _door(tiles, ux, uy + uh // 2)
    rooms.append((ux, uy, uw, uh, "uplink"))

    # Extra alley rooms
    for _ in range(3):
        rx = rng.randint(18, 35)
        ry = rng.randint(11, 16)
        rw, rh = rng.randint(5, 8), rng.randint(4, 5)
        if rx + rw >= w - 1 or ry + rh >= h - 1:
            continue
        _carve_room(tiles, rx, ry, rw, rh)
        _door(tiles, rx + rw // 2, ry + rh - 1)
        rooms.append((rx, ry, rw, rh, "alley"))

    explored = [[False] * w for _ in range(h)]
    visible = [[False] * w for _ in range(h)]
    gmap = GameMap(w, h, tiles, explored, visible, rooms)
    gmap.labels = {
        "safehouse": (sx + sw // 2, sy + sh // 2),
        "club": (cx + cw // 2, cy + ch // 2),
        "jackpoint": (jx + jw // 2, jy + jh // 2),
        "uplink": (ux + uw // 2, uy + uh // 2),
    }

    # Player starts in safehouse
    px, py = sx + 2, sy + 2
    player = make_player(px, py)
    player.inventory.append(make_stimpack())
    player.inventory.append(make_mono_knife())
    player.inventory[-1].equipped = True

    actors: List[Actor] = [player]

    # NPCs
    actors.append(
        make_npc(
            sx + 4,
            sy + 2,
            "Ngoc 'Relay' Tran",
            (
                "Courier job's simple, Rin: someone dumped Payload-Zero in the old "
                "jackpoint south of here. Scrub it or sleeve it, then punch it through "
                "the Metaverse uplink east of the neon strip. Don't recite anything "
                "that feels like a prayer."
            ),
            quest_flag="briefing",
        )
    )
    actors.append(
        make_npc(
            cx + 3,
            cy + 3,
            "DJ Glassline",
            (
                "Club's loud so the drones don't hear the deals. Infected avatars "
                "are glitching hard tonight — eyes full of leftover linguistic virus. "
                "If you need a pulse pistol, check the alley lockers. Uplink's locked "
                "until you've got the core."
            ),
            quest_flag="club_tip",
        )
    )
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

    # Enemies
    enemy_spots = []
    for _ in range(14):
        ex = rng.randint(2, w - 3)
        ey = rng.randint(2, h - 3)
        if not gmap.walkable(ex, ey):
            continue
        if abs(ex - px) + abs(ey - py) < 6:
            continue
        enemy_spots.append((ex, ey))

    for i, (ex, ey) in enumerate(enemy_spots[:12]):
        roll = rng.random()
        if roll < 0.45:
            actors.append(make_infected(ex, ey))
        elif roll < 0.8:
            actors.append(make_thug(ex, ey))
        else:
            actors.append(make_drone(ex, ey))

    # Guaranteed enemies near jackpoint
    actors.append(make_drone(jx + 2, jy + 2))
    actors.append(make_infected(jx + 5, jy + 3))
    actors.append(make_thug(jx + 7, jy + 4))

    # Floor items
    floor_items: List[FloorItem] = []
    # Quest item in jackpoint
    floor_items.append(FloorItem(jx + 4, jy + 3, make_payload_zero()))
    floor_items.append(FloorItem(cx + 5, cy + 2, make_pulse_pistol()))
    floor_items.append(FloorItem(cx + 6, cy + 4, make_focus_tab()))
    floor_items.append(FloorItem(sx + 6, sy + 3, make_leather_jacket()))
    floor_items.append(
        FloorItem(
            25,
            12,
            make_datachip(
                "Burbclave Rumor Chip",
                "Notes on Payload-Zero: a speech-act weapon. Neutralize at uplink.",
            ),
        )
    )

    for _ in range(8):
        ix = rng.randint(2, w - 3)
        iy = rng.randint(2, h - 3)
        if gmap.walkable(ix, iy):
            loot = random_loot(rng)
            if loot:
                floor_items.append(FloorItem(ix, iy, loot))

    # Permanent walkable landmark tiles so quest rooms are obvious
    jack_pos = (jx + jw // 2, jy + 1)
    uplink_pos = (ux + uw // 2, uy + uh // 2)
    tiles[jack_pos[1]][jack_pos[0]] = C.JACKPOINT
    tiles[uplink_pos[1]][uplink_pos[0]] = C.UPLINK

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
    )
