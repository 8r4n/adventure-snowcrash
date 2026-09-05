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
# Vertical transitions (walkable)
STAIRS_DOWN = ">"  # descend to lower plane
STAIRS_UP = "<"  # ascend to higher plane
SHAFT = "*"  # open shaft (fly/climb) — note: item glyph also *; shafts marked in shaft list
MANHOLE = "o"

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
SPAWN_INVULN_SEC = 12.0
# Manhattan radius: no enemies may stand/spawn within this of any spawn pad
SAFE_SPAWN_RADIUS = 8
# On join/respawn, clear threats within this smaller radius of the pad
CLEAR_SPAWN_THREAT_RADIUS = 6
# Cap enemy melee damage vs players (MVP anti-brutal)
ENEMY_MELEE_CAP_VS_PLAYER = 2
# Mapgen: keep a modest spread of pads so SAFE_SPAWN_RADIUS is bubbles, not a city-wide ban
SPAWN_PAD_TARGET = 24
SPAWN_PAD_MIN = 16
SPAWN_PAD_MAX = 32
SPAWN_PAD_MIN_SEP = 14  # Manhattan min distance between kept pads
# Contested scoring radius when picking a join/respawn pad
CONTESTED_SPAWN_RADIUS = 14

# MVP: players cannot damage other players
PVP_ENABLED = False

# Multiplanar stack
PLANE_UNDER = -1
PLANE_STREET = 0
PLANE_AIR = 1
PLANE_NAMES = {
    PLANE_UNDER: "UNDER",
    PLANE_STREET: "STREET",
    PLANE_AIR: "AIR",
}
PLANE_LABELS = {
    PLANE_UNDER: "sewers / tunnels",
    PLANE_STREET: "street level",
    PLANE_AIR: "air / rooftops",
}
# Focus cost to free-fly street ↔ air (shafts are free)
FLY_FOCUS_COST = 1

# Player facing: 0=N, 1=E, 2=S, 3=W
FACING_DIRS = ((0, -1), (1, 0), (0, 1), (-1, 0))
FACING_NAMES = ("N", "E", "S", "W")

# Starting stats
START_HP = 30
START_FOCUS = 20
START_ATTACK = 4
START_DEFENSE = 2
START_HACK = 3

# Absolute 8-way (octile) deltas
MOVE_8 = {
    "n": (0, -1),
    "ne": (1, -1),
    "e": (1, 0),
    "se": (1, 1),
    "s": (0, 1),
    "sw": (-1, 1),
    "w": (-1, 0),
    "nw": (-1, -1),
}

# Absolute keys (avoid letters used for plane/use/fire on web)
MOVE_KEYS = {
    "h": (-1, 0),
    "j": (0, 1),
    "k": (0, -1),
    "l": (1, 0),
    "y": (-1, -1),  # NW (vi)
    "n": (1, 1),  # SE (vi) — only when not chatting
    # Named absolute octile actions (preferred from web client)
    "n_abs": (0, -1),
    "ne": (1, -1),
    "e_abs": (1, 0),
    "se": (1, 1),
    "s_abs": (0, 1),
    "sw": (-1, 1),
    "w_abs": (-1, 0),
    "nw": (-1, -1),
}

# Relative 8-way action names
REL_MOVE_ACTIONS = (
    "forward",
    "back",
    "strafe_left",
    "strafe_right",
    "forward_left",
    "forward_right",
    "back_left",
    "back_right",
)

HELP_TEXT = """\
CONTROLS — 8-WAY + MULTIPLANE
  W/A/S/D           — move relative to facing (chord WA/WD/SA/SD = diagonals)
  Q / E             — turn left / right
  Arrows            — turn (Left/Right) or step (Up/Down) relative
  y u h j k l b n   — absolute octile (TUI / fallback)
  Numpad 1-9        — absolute octile
  t / [ / PgUp      — ascend plane (street→air, under→street)
  b / ] / PgDn      — descend plane (street→under, air→street)
  g                 — get / pick up item
  i                 — inventory
  f                 — ranged / hack attack
  r                 — respawn (when dead)
  . / space         — wait
  ?                 — this help
  m (web)           — mute SFX
  Enter             — chat

PLANES
  UNDER (-1)  sewers / tunnels — enter via manholes (o) or descend
  STREET (0)  fractured LA streets — spawn here
  AIR (+1)    rooftops / Metaverse sky — fly up (costs focus off-shaft)
  Shafts/stairs (< > o) are free vertical transitions.

GOAL
  Recover Payload-Zero from the jackpoint (J), then reach the uplink (U).

MAP
  # wall  . floor  + door  = street  , grass  ~ water
  o manhole  < stairs up  > stairs down
  J jackpoint  U uplink  @ you  & NPC  i infected  t thug  d drone
"""


# Progression / combat density (MMORPG street loop)
XP_PER_KILL = 12
XP_PER_LEVEL = 40
MAX_COURIER_LEVEL = 12
ENCOUNTER_EXTRA_STREET = 18  # additional hostiles seeded away from spawns
CREDIT_DROP_CHANCE = 0.45
LOOT_DROP_CHANCE = 0.28
