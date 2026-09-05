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
JACKPOINT = "J"
UPLINK = "U"

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

# MMORPG-scale city (local FOV / minimap / FPV keep perf reasonable)
MAP_WIDTH = 200
MAP_HEIGHT = 120

VIEW_RADIUS = 8

# Spawn protection (seconds) — AI cannot one-shot new joins
SPAWN_INVULN_SEC = 2.5

# MVP: players cannot damage other players
PVP_ENABLED = False

# Player facing: 0=N, 1=E, 2=S, 3=W
FACING_DIRS = ((0, -1), (1, 0), (0, 1), (-1, 0))
FACING_NAMES = ("N", "E", "S", "W")

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
  W / Up                — move forward (relative to facing)
  S / Down              — move backward
  A / D                 — strafe left / right
  Q / E / Left / Right  — turn left / right (web; no step)
  hjkl (TUI)            — absolute move (N/S/W/E on map)
  g                     — get / pick up item
  i                     — inventory
  u                     — use selected inventory item (TUI: number after)
  f                     — ranged / hack attack (adjacent or in FOV)
  . / space             — wait a turn
  ?                     — this help
  q (TUI)               — quit
  m (web)               — mute / unmute SFX
  Space/Esc (web)       — skip intensive cutscene

GOAL
  Recover or neutralize the rogue Payload-Zero from the jackpoint (J),
  then reach the Metaverse uplink node (U). Talk to NPCs, loot terminals,
  survive the streets of fractured LA.

MAP
  # wall  . floor  + door  = street  , grass  ~ water
  J jackpoint  U uplink  @ you  & NPC  i infected  t thug  d drone
  ! med  / weapon  [ armor  } pistol  % Payload-Zero  * loot
"""
