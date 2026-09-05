#!/usr/bin/env python3
"""One-shot 32x32 cyberpunk tile generator for Snowcrash.

Writes PNGs + tiles.json into snowcrash/static/tiles/.
Requires Pillow (dev-only; not a runtime dependency).
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

SIZE = 32
OUT = Path(__file__).resolve().parent.parent / "snowcrash" / "static" / "tiles"

# Palette matches static/style.css
BG = (10, 14, 20, 255)
PANEL = (17, 24, 34, 255)
FG = (201, 209, 217, 255)
DIM = (110, 118, 129, 255)
CYAN = (57, 197, 207, 255)
CYAN_D = (24, 90, 98, 255)
CYAN_G = (120, 230, 236, 255)
NEON = (255, 42, 109, 255)
NEON_D = (120, 18, 52, 255)
NEON_G = (255, 130, 170, 255)
OK = (61, 214, 140, 255)
OK_D = (18, 72, 48, 255)
WARN = (240, 180, 41, 255)
WARN_D = (90, 64, 12, 255)
PURPLE = (210, 168, 255, 255)
PURPLE_D = (72, 40, 110, 255)
BLUE = (88, 166, 255, 255)
BLUE_D = (20, 48, 92, 255)
WALL_C = (42, 48, 62, 255)
WALL_H = (68, 78, 96, 255)
WALL_S = (22, 26, 34, 255)
FLOOR_C = (22, 28, 38, 255)
FLOOR_H = (32, 40, 54, 255)
STREET_C = (28, 30, 36, 255)
GRASS_C = (18, 36, 28, 255)
GRASS_H = (40, 92, 58, 255)
WATER_C = (12, 32, 52, 255)
WATER_H = (36, 110, 140, 255)
FOG_C = (8, 10, 14, 255)
SKIN = (230, 196, 168, 255)
HAIR = (28, 24, 32, 255)
BLACK = (0, 0, 0, 255)
WHITE = (236, 240, 244, 255)
ORANGE = (255, 120, 48, 255)


class Canvas:
    def __init__(self, bg=BG):
        self.img = Image.new("RGBA", (SIZE, SIZE), bg)
        self.px = self.img.load()

    def p(self, x, y, c):
        if 0 <= x < SIZE and 0 <= y < SIZE:
            self.px[x, y] = c

    def fill(self, x, y, w, h, c):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.p(xx, yy, c)

    def hline(self, x, y, w, c):
        self.fill(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        self.fill(x, y, 1, h, c)

    def outline(self, x, y, w, h, c):
        self.hline(x, y, w, c)
        self.hline(x, y + h - 1, w, c)
        self.vline(x, y, h, c)
        self.vline(x + w - 1, y, h, c)

    def rect(self, x, y, w, h, fill=None, border=None):
        if fill is not None:
            self.fill(x, y, w, h, fill)
        if border is not None:
            self.outline(x, y, w, h, border)

    def diamond(self, cx, cy, r, c):
        for yy in range(-r, r + 1):
            for xx in range(-r, r + 1):
                if abs(xx) + abs(yy) <= r:
                    self.p(cx + xx, cy + yy, c)

    def save(self, name: str) -> Path:
        path = OUT / name
        self.img.save(path, "PNG")
        return path


def floor_base(c: Canvas, speckle=True):
    c.fill(0, 0, 32, 32, FLOOR_C)
    for i in range(0, 32, 8):
        c.hline(0, i, 32, FLOOR_H)
        c.vline(i, 0, 32, FLOOR_H)
    if speckle:
        for x, y in ((3, 5), (14, 11), (21, 19), (27, 7), (9, 24), (18, 28)):
            c.p(x, y, CYAN_D)


def wall() -> Canvas:
    c = Canvas(WALL_S)
    # brick courses
    for row in range(0, 32, 8):
        c.fill(0, row, 32, 7, WALL_C)
        c.hline(0, row + 7, 32, WALL_S)
        offset = 0 if (row // 8) % 2 == 0 else 8
        for col in range(offset, 32, 16):
            c.vline(col, row, 7, WALL_S)
            c.hline(col + 1, row, 6, WALL_H)
    # neon seam
    c.vline(0, 0, 32, CYAN_D)
    c.vline(31, 0, 32, NEON_D)
    c.hline(0, 0, 32, CYAN)
    c.p(4, 3, CYAN)
    c.p(20, 11, NEON)
    return c


def floor() -> Canvas:
    c = Canvas()
    floor_base(c)
    return c


def door() -> Canvas:
    c = wall()
    # doorway cut
    c.rect(8, 4, 16, 28, fill=PANEL, border=NEON)
    c.rect(10, 6, 12, 24, fill=(28, 16, 28, 255))
    c.rect(14, 16, 3, 6, fill=WARN, border=WARN_D)  # keypad
    c.hline(10, 18, 12, NEON_D)
    c.p(22, 20, CYAN_G)
    return c


def water() -> Canvas:
    c = Canvas(WATER_C)
    for y in range(32):
        shade = 8 if (y // 4) % 2 == 0 else 0
        c.hline(0, y, 32, (12 + shade, 32 + shade, 56 + shade, 255))
    for y, x0 in ((4, 2), (10, 8), (16, 1), (22, 10), (28, 4)):
        c.hline(x0, y, 12, WATER_H)
        c.hline(x0 + 2, y + 1, 8, CYAN_D)
    c.p(20, 7, CYAN)
    c.p(6, 19, CYAN_G)
    return c


def street() -> Canvas:
    c = Canvas(STREET_C)
    c.fill(0, 0, 32, 32, (24, 26, 32, 255))
    # lane dashes
    for x in range(2, 30, 8):
        c.fill(x, 14, 5, 4, WARN)
        c.fill(x + 1, 15, 3, 2, (255, 220, 90, 255))
    # curb glow
    c.hline(0, 0, 32, CYAN_D)
    c.hline(0, 31, 32, CYAN_D)
    for x in (5, 17, 28):
        c.p(x, 6, DIM)
        c.p(x, 25, DIM)
    return c


def grass() -> Canvas:
    c = Canvas(GRASS_C)
    c.fill(0, 0, 32, 32, GRASS_C)
    blades = [
        (2, 20, 2, 10), (5, 16, 2, 14), (8, 22, 2, 8),
        (12, 14, 2, 16), (16, 18, 2, 12), (20, 12, 2, 18),
        (24, 19, 2, 11), (28, 15, 2, 15), (10, 24, 2, 6),
        (18, 26, 2, 5), (26, 24, 2, 7),
    ]
    for x, y, w, h in blades:
        c.fill(x, y, w, h, GRASS_H)
    c.p(7, 10, OK)
    c.p(21, 8, OK)
    c.p(14, 6, CYAN_D)
    return c


def fog() -> Canvas:
    c = Canvas(FOG_C)
    c.fill(0, 0, 32, 32, FOG_C)
    for x, y in (
        (4, 6), (11, 3), (19, 8), (27, 4),
        (6, 14), (15, 17), (23, 12), (2, 22),
        (12, 26), (20, 21), (28, 27), (8, 30),
    ):
        c.p(x, y, (22, 26, 32, 255))
    c.outline(0, 0, 32, 32, (16, 18, 24, 255))
    return c


def empty() -> Canvas:
    c = Canvas((6, 8, 12, 255))
    return c


def _humanoid(c: Canvas, body, accent, visor, hair=HAIR, wide=False):
    """Standing courier-scale figure on a floor plate."""
    floor_base(c, speckle=False)
    # ground blob
    c.fill(9, 29, 14, 2, (8, 10, 14, 180) if False else PANEL)
    # legs
    c.fill(12, 22, 3, 8, body)
    c.fill(17, 22, 3, 8, body)
    c.fill(12, 28, 3, 2, DIM)
    c.fill(17, 28, 3, 2, DIM)
    # torso
    tw = 10 if wide else 8
    tx = 11 if wide else 12
    c.fill(tx, 13, tw, 10, body)
    c.hline(tx, 13, tw, accent)
    # arms
    c.fill(tx - 2, 14, 2, 8, body)
    c.fill(tx + tw, 14, 2, 8, body)
    # head
    c.fill(13, 6, 6, 7, SKIN)
    c.fill(13, 5, 6, 3, hair)
    c.fill(13, 8, 6, 2, visor)
    c.p(14, 8, WHITE)
    c.p(17, 8, accent)
    return c


def player() -> Canvas:
    c = Canvas()
    _humanoid(c, CYAN_D, CYAN, CYAN_G)
    # jacket stripe
    c.vline(15, 14, 8, CYAN)
    c.p(16, 16, NEON)
    # visor glow
    c.hline(12, 8, 8, CYAN)
    return c


def npc() -> Canvas:
    c = Canvas()
    _humanoid(c, BLUE_D, BLUE, BLUE)
    # coat flare
    c.fill(10, 20, 3, 6, BLUE_D)
    c.fill(19, 20, 3, 6, BLUE_D)
    c.p(15, 16, WARN)
    return c


def infected() -> Canvas:
    c = Canvas()
    _humanoid(c, OK_D, OK, OK)
    # glitch pixels
    for x, y in ((10, 10), (21, 12), (9, 18), (22, 20), (16, 7), (11, 25)):
        c.p(x, y, OK)
    c.fill(13, 8, 6, 2, NEON_D)
    c.p(14, 8, OK)
    c.p(18, 9, NEON)
    return c


def thug() -> Canvas:
    c = Canvas()
    _humanoid(c, WARN_D, WARN, ORANGE, wide=True)
    # baton
    c.fill(22, 10, 2, 12, DIM)
    c.fill(22, 8, 2, 3, WARN)
    c.fill(11, 15, 10, 3, (50, 36, 16, 255))
    return c


def drone() -> Canvas:
    c = Canvas()
    floor_base(c, speckle=False)
    # body
    c.diamond(16, 16, 8, PURPLE_D)
    c.diamond(16, 16, 5, PURPLE)
    c.diamond(16, 16, 2, WHITE)
    # rotors
    c.hline(4, 10, 8, DIM)
    c.hline(20, 10, 8, DIM)
    c.hline(4, 22, 8, DIM)
    c.hline(20, 22, 8, DIM)
    c.fill(6, 9, 3, 3, NEON)
    c.fill(23, 9, 3, 3, NEON)
    c.fill(6, 21, 3, 3, CYAN)
    c.fill(23, 21, 3, 3, CYAN)
    # lens
    c.fill(15, 15, 3, 3, NEON)
    return c


def misc() -> Canvas:
    c = Canvas()
    floor_base(c, speckle=False)
    # datachip / loot gem
    c.rect(10, 8, 12, 16, fill=NEON_D, border=NEON)
    c.rect(12, 10, 8, 12, fill=(40, 12, 28, 255))
    c.hline(13, 14, 6, NEON_G)
    c.hline(13, 16, 6, CYAN)
    c.p(16, 12, WHITE)
    c.fill(14, 20, 4, 2, NEON)
    return c


def med() -> Canvas:
    c = Canvas()
    floor_base(c, speckle=False)
    # stim vial
    c.rect(12, 6, 8, 20, fill=(40, 16, 24, 255), border=NEON_G)
    c.fill(13, 14, 6, 10, NEON)
    c.fill(14, 16, 4, 6, NEON_G)
    c.rect(11, 5, 10, 4, fill=DIM, border=FG)
    # cross
    c.fill(15, 8, 2, 6, WHITE)
    c.fill(13, 10, 6, 2, WHITE)
    return c


def weapon() -> Canvas:
    c = Canvas()
    floor_base(c, speckle=False)
    # monofilament knife
    c.fill(7, 22, 6, 4, DIM)
    c.fill(8, 21, 4, 2, FG)
    c.fill(11, 8, 4, 16, CYAN_D)
    c.fill(12, 6, 2, 18, CYAN)
    c.p(12, 5, WHITE)
    c.p(13, 5, CYAN_G)
    c.hline(10, 20, 6, NEON_D)
    return c


def armor() -> Canvas:
    c = Canvas()
    floor_base(c, speckle=False)
    # jacket
    c.rect(8, 8, 16, 18, fill=(36, 20, 28, 255), border=NEON)
    c.fill(10, 10, 12, 14, NEON_D)
    c.vline(16, 10, 14, NEON)
    c.fill(8, 8, 5, 6, (50, 28, 36, 255))
    c.fill(19, 8, 5, 6, (50, 28, 36, 255))
    c.p(12, 14, CYAN)
    c.p(20, 14, CYAN)
    return c


def payload() -> Canvas:
    c = Canvas()
    floor_base(c, speckle=False)
    # Faraday cube
    c.rect(8, 8, 16, 16, fill=(28, 12, 40, 255), border=NEON)
    c.rect(10, 10, 12, 12, fill=PURPLE_D, border=PURPLE)
    # % mark
    c.fill(12, 12, 3, 3, NEON)
    c.fill(17, 17, 3, 3, NEON)
    c.fill(13, 18, 6, 2, CYAN_G)
    c.p(16, 14, WHITE)
    c.p(15, 15, WHITE)
    c.p(14, 16, WHITE)
    # glow corners
    c.p(8, 8, WHITE)
    c.p(23, 8, CYAN)
    c.p(8, 23, NEON)
    c.p(23, 23, WHITE)
    return c


def pistol() -> Canvas:
    c = Canvas()
    floor_base(c, speckle=False)
    # side-view pulse pistol
    c.fill(6, 12, 18, 6, DIM)
    c.fill(7, 13, 16, 4, CYAN_D)
    c.fill(20, 11, 6, 4, CYAN)
    c.fill(22, 12, 3, 2, CYAN_G)
    c.fill(10, 18, 4, 7, (40, 40, 48, 255))
    c.fill(11, 18, 2, 6, FG)
    c.p(8, 14, NEON)
    c.p(16, 14, WARN)
    return c


def jackpoint() -> Canvas:
    c = Canvas()
    floor_base(c, speckle=False)
    # street jack terminal
    c.rect(6, 10, 20, 16, fill=PANEL, border=CYAN)
    c.rect(8, 12, 16, 10, fill=(8, 20, 24, 255), border=CYAN_D)
    # screen glyph
    c.fill(10, 14, 12, 6, CYAN_D)
    c.hline(11, 15, 10, CYAN)
    c.hline(11, 17, 7, CYAN_G)
    # cable
    c.fill(14, 26, 4, 4, DIM)
    c.hline(4, 28, 12, CYAN_D)
    c.p(4, 27, CYAN)
    # J-ish ports
    c.fill(9, 23, 3, 2, NEON)
    c.fill(20, 23, 3, 2, NEON)
    return c


def uplink() -> Canvas:
    c = Canvas()
    floor_base(c, speckle=False)
    # dish / node
    c.diamond(16, 14, 9, PURPLE_D)
    c.diamond(16, 14, 6, BLUE_D)
    c.diamond(16, 14, 3, CYAN)
    c.fill(15, 20, 3, 8, DIM)
    c.fill(10, 27, 13, 3, PANEL)
    c.outline(10, 27, 13, 3, PURPLE)
    # signal rings
    c.p(16, 4, WHITE)
    c.p(12, 6, PURPLE)
    c.p(20, 6, PURPLE)
    c.p(16, 14, WHITE)
    return c


TILES = [
    # glyph, filename, label, builder
    ("#", "wall.png", "Wall", wall),
    (".", "floor.png", "Floor", floor),
    ("+", "door.png", "Door", door),
    ("~", "water.png", "Water", water),
    ("=", "street.png", "Street", street),
    (",", "grass.png", "Grass", grass),
    (" ", "fog.png", "Fog / unknown", fog),
    ("@", "player.png", "You (Rin Vale)", player),
    ("&", "npc.png", "NPC", npc),
    ("i", "infected.png", "Infected avatar", infected),
    ("t", "thug.png", "Street thug", thug),
    ("d", "drone.png", "Security drone", drone),
    ("*", "misc.png", "Datachip / loot", misc),
    ("!", "med.png", "Med / stim", med),
    ("/", "weapon.png", "Weapon", weapon),
    ("[", "armor.png", "Armor", armor),
    ("%", "payload.png", "Payload-Zero", payload),
    ("}", "pistol.png", "Pulse pistol", pistol),
    ("J", "jackpoint.png", "Jackpoint", jackpoint),
    ("U", "uplink.png", "Metaverse uplink", uplink),
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # extra empty tile (same as near-black)
    empty().save("empty.png")

    glyphs = {}
    legend = []
    for glyph, filename, label, builder in TILES:
        builder().save(filename)
        glyphs[glyph] = {"file": filename, "label": label}
        legend.append({"glyph": glyph, "file": filename, "label": label})

    meta = {
        "tile_size": SIZE,
        "path": "/static/tiles/",
        "empty": "empty.png",
        "fog": "fog.png",
        "glyphs": glyphs,
        "legend": legend,
    }
    (OUT / "tiles.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"wrote {len(legend)} tiles + tiles.json → {OUT}")


if __name__ == "__main__":
    main()
