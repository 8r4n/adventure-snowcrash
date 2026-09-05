"""Tiles, colors, and shared constants."""

from __future__ import annotations

# Map tiles
WALL = "#"
FLOOR = "."
DOOR = "+"
WATER = "~"
STREET = "="
GRASS = ","
EMPTY = " "

# Entities (display glyphs)
PLAYER = "@"
NPC = "&"
ITEM = "*"

# Enemy glyphs
ENEMY_INFECTED = "i"
ENEMY_THUG = "t"
ENEMY_DRONE = "d"

# FOV / fog
VISIBLE = True
EXPLORED = True

MAP_WIDTH = 60
MAP_HEIGHT = 30

VIEW_RADIUS = 8

# Starting stats
START_HP = 30
START_FOCUS = 20
START_ATTACK = 4
START_DEFENSE = 2
START_HACK = 3

# Keys that move (dx, dy)
MOVE_KEYS = {
    "w": (0, -1),
    "s": (0, 1),
    "a": (-1, 0),
    "d": (1, 0),
    "k": (0, -1),
    "j": (0, 1),
    "h": (-1, 0),
    "l": (1, 0),
    "ArrowUp": (0, -1),
    "ArrowDown": (0, 1),
    "ArrowLeft": (-1, 0),
    "ArrowRight": (1, 0),
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}

HELP_TEXT = """\
CONTROLS
  WASD / arrows / hjkl  — move
  g                     — get / pick up item
  i                     — inventory
  u                     — use selected inventory item (TUI: number after)
  f                     — ranged / hack attack (adjacent or in FOV)
  . / space             — wait a turn
  ?                     — this help
  q                     — quit

GOAL
  Recover or neutralize the rogue Payload-Zero from the jackpoint,
  then reach the Metaverse uplink node. Talk to NPCs, loot terminals,
  survive the streets of fractured LA.
"""
