"""Jack-in cyberspace puzzle layer (#47).

Same courier identity: enter a short ASCII node from a jackpoint, solve a
maze or ICE-gate puzzle, return loot/keys to the street layer without
scrambling street position. Synergizes with ICE probes (#46) on ICE-gate nodes.
Original Metaverse prose only.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

from .. import constants as C
from ..items import Item, make_datachip


# Glyphs inside cyberspace nodes
CYBER_WALL = "#"
CYBER_FLOOR = "."
CYBER_ICE = "I"  # clearable with stun/reveal probes
CYBER_LOOT = "*"
CYBER_EXIT = "X"
CYBER_CORE = "%"
CYBER_START = "@"

JACK_IN_RADIUS = 1  # manhattan from jackpoint tile


def make_cyber_key() -> Item:
    return Item(
        id="cyber_key",
        name="Cyberspace Node Key",
        glyph="*",
        kind="datachip",
        description=(
            "A hardlight shard cut from a StreetNet node. "
            "Opens soft locks on the street layer and whispers grid topology."
        ),
        hack_bonus=1,
        consumable=False,
        extra={"cyber": True, "key": True},
    )


def make_node_chip(node_type: str) -> Item:
    label = "Maze Trace" if node_type == "maze" else "ICE Gate Dump"
    return make_datachip(
        name="Node Chip · %s" % label,
        desc=(
            "Packet dump from a jacked Metaverse node (%s). "
            "Scrubbed of Babel residue — safe to sleeve."
        )
        % node_type,
    )


# Fixed small templates — rotation / mirror via generation helpers
_MAZE_A = [
    "###########",
    "#@........#",
    "#.###.###.#",
    "#...#...#.#",
    "###.#.#.#.#",
    "#.....#...#",
    "#.#####.#.#",
    "#.......#*#",
    "#######.#.#",
    "#.......X.#",
    "###########",
]

_MAZE_B = [
    "###########",
    "#@#.....#X#",
    "#.#.###.#.#",
    "#.#.#...#.#",
    "#...#.###.#",
    "###.#.....#",
    "#...###.#.#",
    "#.#.....#*#",
    "#.#######.#",
    "#.........#",
    "###########",
]

_ICE_GATE_A = [
    "###########",
    "#@........#",
    "#.#######.#",
    "#.#.....#.#",
    "#.#.I.I.#.#",
    "#.#..%..#.#",
    "#.#.I.I.#.#",
    "#.#.....#.#",
    "#.#######.#",
    "#........X#",
    "###########",
]

_ICE_GATE_B = [
    "###########",
    "#@..I.....#",
    "###.I.###.#",
    "#...I...#.#",
    "#.#####.#.#",
    "#.%...I...#",
    "#.#####.###",
    "#.....I...#",
    "#####.I.###",
    "#.....I..X#",
    "###########",
]


def _lines_to_grid(lines: List[str]) -> List[List[str]]:
    return [list(row) for row in lines]


def _find_glyph(grid: List[List[str]], glyph: str) -> Optional[Tuple[int, int]]:
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch == glyph:
                return x, y
    return None


def _replace_glyph(grid: List[List[str]], glyph: str, with_ch: str) -> None:
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch == glyph:
                grid[y][x] = with_ch


def build_node(node_type: str, rng: random.Random) -> Dict[str, Any]:
    """Build a cyberspace node session dict."""
    if node_type == "ice_gate":
        tmpl = rng.choice([_ICE_GATE_A, _ICE_GATE_B])
    else:
        node_type = "maze"
        tmpl = rng.choice([_MAZE_A, _MAZE_B])
    grid = _lines_to_grid(tmpl)
    start = _find_glyph(grid, CYBER_START)
    if not start:
        start = (1, 1)
    _replace_glyph(grid, CYBER_START, CYBER_FLOOR)
    ice_cells = []
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch == CYBER_ICE:
                ice_cells.append([x, y])
    loot_pos = _find_glyph(grid, CYBER_LOOT) or _find_glyph(grid, CYBER_CORE)
    exit_pos = _find_glyph(grid, CYBER_EXIT)
    return {
        "node_type": node_type,
        "grid": grid,
        "width": len(grid[0]) if grid else 0,
        "height": len(grid),
        "px": start[0],
        "py": start[1],
        "ice_cells": ice_cells,
        "loot_taken": False,
        "cleared": False,
        "rewarded": False,
        "hint": (
            "Maze node — reach * loot then X exit. Esc or jack_out to street."
            if node_type == "maze"
            else "ICE gate — stun/reveal probes clear I cells; reach % core then X. Esc to jack out."
        ),
    }


def render_node_map(session: Dict[str, Any]) -> List[str]:
    grid = session.get("grid") or []
    px, py = int(session.get("px", 0)), int(session.get("py", 0))
    rows = []
    for y, row in enumerate(grid):
        chars = []
        for x, ch in enumerate(row):
            if x == px and y == py:
                chars.append(C.PLAYER if hasattr(C, "PLAYER") else "@")
            else:
                chars.append(ch)
        rows.append("".join(chars))
    return rows


def walkable_cyber(session: Dict[str, Any], x: int, y: int) -> bool:
    grid = session.get("grid") or []
    if y < 0 or x < 0 or y >= len(grid) or x >= len(grid[0]):
        return False
    ch = grid[y][x]
    if ch == CYBER_WALL:
        return False
    if ch == CYBER_ICE:
        return False
    return True



def _cyber_relative_delta(facing: int, action: str) -> Tuple[int, int]:
    """8-way deltas relative to facing (0=N,1=E,2=S,3=W). Local copy to avoid import cycles."""
    fx, fy = C.FACING_DIRS[facing % 4]
    lx, ly = fy, -fx
    rx, ry = -fy, fx
    table = {
        "forward": (fx, fy),
        "back": (-fx, -fy),
        "strafe_left": (lx, ly),
        "strafe_right": (rx, ry),
        "forward_left": (fx + lx, fy + ly),
        "forward_right": (fx + rx, fy + ry),
        "back_left": (-fx + lx, -fy + ly),
        "back_right": (-fx + rx, -fy + ry),
    }
    dx, dy = table.get(action, (0, 0))
    if dx != 0:
        dx = 1 if dx > 0 else -1
    if dy != 0:
        dy = 1 if dy > 0 else -1
    return dx, dy


class CyberspaceMixin:
    """Mixin methods for GameWorld / YearFeaturesMixin."""

    def _cyber_bootstrap(self, agent) -> None:
        if not isinstance(getattr(agent, "cyber", None), dict):
            agent.cyber = {"active": False}

    def _cyber_at_jackpoint(self, agent) -> bool:
        jx, jy = self.jackpoint_pos
        ax, ay = agent.actor.x, agent.actor.y
        az = int(getattr(agent.actor, "z", 0) or 0)
        if az != C.PLANE_STREET:
            return False
        return abs(ax - jx) + abs(ay - jy) <= JACK_IN_RADIUS

    def _cyber_pick_node_type(self, agent) -> str:
        """Alternate maze / ice_gate across clears (even=maze, odd=ice_gate)."""
        flags = getattr(agent, "quest_flags", {}) or {}
        cleared = int(flags.get("cyber_nodes_cleared", 0) or 0)
        return "maze" if cleared % 2 == 0 else "ice_gate"

    def _cyber_jack_in(self, agent, arg: str = "") -> bool:
        self._cyber_bootstrap(agent)
        if agent.mode == "cyberspace" and (agent.cyber or {}).get("active"):
            agent.log("Already jacked into a StreetNet node. Esc or jack_out to leave.")
            return True
        if not self._cyber_at_jackpoint(agent):
            agent.log(
                "No jackport handshake here. Stand on or next to the jackpoint (J) to jack in."
            )
            return True
        arg_l = (arg or "").strip().lower()
        if arg_l in ("maze", "ice_gate", "ice", "gate"):
            node_type = "ice_gate" if arg_l in ("ice_gate", "ice", "gate") else "maze"
        else:
            node_type = self._cyber_pick_node_type(agent)

        street = {
            "x": agent.actor.x,
            "y": agent.actor.y,
            "z": int(getattr(agent.actor, "z", 0) or 0),
            "facing": int(getattr(agent.actor, "facing", 0) or 0) % 4,
        }
        rng = getattr(self, "rng", None) or random.Random(
            (getattr(self, "seed", 0) or 0) ^ hash(agent.id) ^ self.tick
        )
        session = build_node(node_type, rng)
        session["active"] = True
        session["street"] = street
        # Soft shield while jacked so street swarm doesn't flatline the parked body
        agent.invuln_until = max(
            float(getattr(agent, "invuln_until", 0) or 0),
            __import__("time").time() + 600.0,
        )
        agent.cyber = session
        agent.mode = "cyberspace"
        agent.cutscene("terminal")
        agent.sfx("pulse")
        label = "maze lattice" if node_type == "maze" else "ICE gate lattice"
        agent.log(
            "Jack-in — avatar dissolves into the %s. Street body parked at (%d,%d). "
            "Same courier. %s"
            % (label, street["x"], street["y"], session["hint"])
        )
        # Journal side-note
        j = getattr(agent, "journal", None) or {}
        notes = list(j.get("notes", []) or [])
        note = "Jacked a %s node from the street jackpoint." % node_type
        if note not in notes:
            notes.append(note)
            j["notes"] = notes[-8:]
            agent.journal = j
        return True

    def _cyber_jack_out(self, agent, *, reason: str = "manual") -> bool:
        self._cyber_bootstrap(agent)
        session = agent.cyber or {}
        if not session.get("active") and agent.mode != "cyberspace":
            agent.log("Not jacked in.")
            return True
        street = session.get("street") or {}
        sx = int(street.get("x", agent.actor.x))
        sy = int(street.get("y", agent.actor.y))
        sz = int(street.get("z", C.PLANE_STREET))
        facing = int(street.get("facing", getattr(agent.actor, "facing", 0)) or 0) % 4
        # Restore exact street pad — never random teleport
        if hasattr(self, "_force_set_pos"):
            self._force_set_pos(agent, sx, sy, sz, "cyber jack-out")
        else:
            agent.actor.x, agent.actor.y = sx, sy
            agent.actor.z = sz
        agent.actor.facing = facing
        agent.last_good_x, agent.last_good_y, agent.last_good_z = sx, sy, sz
        agent.mode = "play"
        agent.cyber = {"active": False, "last_node": session.get("node_type"), "last_cleared": bool(session.get("cleared"))}
        # Drop long jack shield; brief exit grace
        import time as _time
        agent.invuln_until = _time.time() + 3.0
        if reason == "cleared":
            agent.log(
                "Jack-out — node scrubbed. You re-sleeve at (%d,%d,z=%d) facing %s. Streets wait."
                % (sx, sy, sz, C.FACING_NAMES[facing] if hasattr(C, "FACING_NAMES") else facing)
            )
        else:
            agent.log(
                "Jack-out — connection dropped. Re-sleeved at (%d,%d,z=%d). Grid echo fades."
                % (sx, sy, sz)
            )
        agent.sfx("click")
        if hasattr(self, "update_fov"):
            self.update_fov(agent)
        return True

    def _cyber_grant_rewards(self, agent, session: Dict[str, Any]) -> None:
        if session.get("rewarded"):
            return
        session["rewarded"] = True
        node_type = session.get("node_type", "maze")
        agent.actor.inventory.append(make_cyber_key())
        agent.actor.inventory.append(make_node_chip(node_type))
        agent.credits = int(getattr(agent, "credits", 0) or 0) + 15
        agent.actor.focus = min(
            agent.actor.max_focus,
            int(agent.actor.focus) + 3,
        )
        flags = getattr(agent, "quest_flags", None)
        if not isinstance(flags, dict):
            flags = {}
            agent.quest_flags = flags
        flags["cyber_node_cleared"] = True
        flags["cyber_nodes_cleared"] = int(flags.get("cyber_nodes_cleared", 0) or 0) + 1
        if node_type == "ice_gate":
            flags["cyber_ice_gate_cleared"] = True
        else:
            flags["cyber_maze_cleared"] = True
        j = getattr(agent, "journal", None) or {}
        notes = list(j.get("notes", []) or [])
        notes.append(
            "Cyberspace %s cleared — node key + chip sleeved; +15 credits."
            % node_type
        )
        j["notes"] = notes[-8:]
        # Optional side quest line
        side = list(j.get("side", []) or [])
        if "cyber_jack" not in [s.get("id") for s in side if isinstance(s, dict)]:
            side.append({
                "id": "cyber_jack",
                "text": "Jack cyberspace nodes at J — loot keys for the street run",
                "done": True,
            })
        else:
            for s in side:
                if isinstance(s, dict) and s.get("id") == "cyber_jack":
                    s["done"] = True
        j["side"] = side
        agent.journal = j
        agent.log(
            "Node payload sleeved: Cyberspace Node Key + Node Chip. "
            "+15 credits, Focus topped a little. Same courier, richer sleeve."
        )
        if hasattr(self, "_grant_season_xp"):
            self._grant_season_xp(agent, 8)
        if hasattr(self, "_analytics"):
            self._analytics("cyber_clear", agent, node_type=node_type)

    def _cyber_try_pickup(self, agent) -> None:
        session = agent.cyber or {}
        grid = session.get("grid") or []
        px, py = int(session.get("px", 0)), int(session.get("py", 0))
        if py < 0 or px < 0 or py >= len(grid) or px >= len(grid[0]):
            return
        ch = grid[py][px]
        if ch in (CYBER_LOOT, CYBER_CORE) and not session.get("loot_taken"):
            session["loot_taken"] = True
            grid[py][px] = CYBER_FLOOR
            agent.log(
                "Hardlight %s dissolves into your sleeve buffer — find the exit (X)."
                % ("core" if ch == CYBER_CORE else "loot packet")
            )
            agent.sfx("pulse")
        if ch == CYBER_EXIT and session.get("loot_taken"):
            session["cleared"] = True
            self._cyber_grant_rewards(agent, session)
            self._cyber_jack_out(agent, reason="cleared")
        elif ch == CYBER_EXIT and not session.get("loot_taken"):
            need = "core (%)" if session.get("node_type") == "ice_gate" else "loot (*)"
            agent.log("Exit port locked — grab the %s first." % need)

    def _cyber_move(self, agent, dx: int, dy: int) -> bool:
        session = agent.cyber or {}
        if not session.get("active"):
            return False
        nx = int(session.get("px", 0)) + dx
        ny = int(session.get("py", 0)) + dy
        if not walkable_cyber(session, nx, ny):
            grid = session.get("grid") or []
            if 0 <= ny < len(grid) and 0 <= nx < len(grid[0]) and grid[ny][nx] == CYBER_ICE:
                agent.log(
                    "ICE wall — spend Focus: ice_probe stun or reveal to melt this cell."
                )
            agent.sfx("bump")
            return True
        session["px"], session["py"] = nx, ny
        self._cyber_try_pickup(agent)
        return True

    def _cyber_clear_ice_near(self, agent, radius: int = 1) -> int:
        """Clear ICE cells adjacent/under courier — called from probe synergy."""
        session = agent.cyber or {}
        if not session.get("active"):
            return 0
        grid = session.get("grid") or []
        px, py = int(session.get("px", 0)), int(session.get("py", 0))
        cleared = 0
        for y in range(max(0, py - radius), min(len(grid), py + radius + 1)):
            for x in range(max(0, px - radius), min(len(grid[0]), px + radius + 1)):
                if grid[y][x] == CYBER_ICE:
                    grid[y][x] = CYBER_FLOOR
                    cleared += 1
        if cleared:
            ice_cells = session.get("ice_cells") or []
            session["ice_cells"] = [
                c for c in ice_cells if grid[int(c[1])][int(c[0])] == CYBER_ICE
            ]
            agent.log(
                "Probe melts %d ICE cell%s in the node lattice."
                % (cleared, "" if cleared == 1 else "s")
            )
            agent.sfx("pulse")
        return cleared

    def _cyber_handle_action(self, agent, action: str, arg: Optional[str] = None) -> bool:
        """Handle actions while mode==cyberspace. Return True if consumed."""
        self._cyber_bootstrap(agent)
        a = (action or "").strip()
        al = a.lower()

        if al in ("jack_out", "jackout", "unjack", "leave_cyber", "cyber_out"):
            return self._cyber_jack_out(agent)
        if al in ("escape", "esc", "q") and agent.mode == "cyberspace":
            return self._cyber_jack_out(agent)
        if al in ("?", "help"):
            session = agent.cyber or {}
            agent.log(session.get("hint") or "Cyberspace node — move, grab loot, exit X.")
            agent.log("Controls: move as street · ice_probe stun|reveal melts I · Esc jack_out.")
            return True

        # ICE probes inside node — synergize with #46
        if al in ("ice_probe", "probe", "ice") or (
            al.startswith("ice_") and al[4:] in getattr(C, "ICE_PROBES", {})
        ) or (
            al.startswith("probe_") and al[6:] in getattr(C, "ICE_PROBES", {})
        ):
            pid = (arg or "").strip().lower()
            if al.startswith("ice_") and al[4:] in C.ICE_PROBES:
                pid = al[4:]
            elif al.startswith("probe_") and al[6:] in C.ICE_PROBES:
                pid = al[6:]
            if pid in ("", "list", "help", "?"):
                agent.log("In-node ICE: stun or reveal melts adjacent I cells (Focus cost).")
                return True
            if pid not in ("stun", "reveal"):
                if pid == "scramble":
                    agent.log("Aggro Scramble has no street hostiles here — try stun or reveal.")
                    return True
                agent.log("Unknown probe in-node. Try: stun, reveal.")
                return True
            defn = C.ICE_PROBES[pid]
            import time as _time
            now = _time.time()
            cds = getattr(agent, "ice_cooldowns", None)
            if not isinstance(cds, dict):
                cds = {}
                agent.ice_cooldowns = cds
            ready_at = float(cds.get(pid, 0) or 0)
            if ready_at > now + 0.05:
                agent.log("%s cooling down — %.1fs left." % (defn["name"], ready_at - now))
                return True
            cost = int(defn["focus_cost"])
            if agent.actor.focus < cost:
                agent.log("Need %d Focus for %s." % (cost, defn["name"]))
                return True
            agent.actor.focus -= cost
            cds[pid] = now + float(defn["cooldown"])
            n = self._cyber_clear_ice_near(agent, radius=2 if pid == "reveal" else 1)
            if not n:
                agent.log(
                    "%s pulses the lattice (−%d Focus) — no ICE in reach. Step closer to an I."
                    % (defn["name"], cost)
                )
            return True

        # Movement — relative and absolute
        if a in getattr(C, "REL_MOVE_ACTIONS", ()):
            dx, dy = _cyber_relative_delta(int(getattr(agent.actor, "facing", 0) or 0), a)
            return self._cyber_move(agent, dx, dy)
        if a in getattr(C, "MOVE_8", {}):
            dx, dy = C.MOVE_8[a]
            return self._cyber_move(agent, dx, dy)
        if a in getattr(C, "MOVE_KEYS", {}):
            dx, dy = C.MOVE_KEYS[a]
            return self._cyber_move(agent, dx, dy)
        if al in ("turn_left", "tl", ","):
            agent.actor.facing = (agent.actor.facing - 1) % 4
            agent.sfx("click")
            return True
        if al in ("turn_right", "tr"):
            agent.actor.facing = (agent.actor.facing + 1) % 4
            agent.sfx("click")
            return True
        if al in (".", " ", "wait", "look", "noop"):
            return True
        if al in ("g", "get", "pickup"):
            self._cyber_try_pickup(agent)
            return True
        # Ignore street-only actions quietly
        if al in ("i", "inventory", "f", "fire", "hack", "plane_up", "plane_down", "g"):
            agent.log("Street controls muted in cyberspace — move, probe ICE, or jack_out.")
            return True
        return True  # consume unknown while jacked so street logic doesn't fire

    def _cyber_snapshot(self, agent) -> Dict[str, Any]:
        self._cyber_bootstrap(agent)
        session = agent.cyber or {}
        active = bool(session.get("active") and agent.mode == "cyberspace")
        if not active:
            return {
                "active": False,
                "can_jack_in": self._cyber_at_jackpoint(agent),
                "hint": (
                    "At jackpoint (J) — press j or jack_in to enter a cyberspace node."
                    if self._cyber_at_jackpoint(agent)
                    else "Reach jackpoint (J) to jack into a cyberspace puzzle node."
                ),
            }
        rows = render_node_map(session)
        return {
            "active": True,
            "node_type": session.get("node_type"),
            "map": rows,
            "width": session.get("width"),
            "height": session.get("height"),
            "px": session.get("px"),
            "py": session.get("py"),
            "loot_taken": bool(session.get("loot_taken")),
            "ice_remaining": sum(
                1 for row in (session.get("grid") or []) for ch in row if ch == CYBER_ICE
            ),
            "hint": session.get("hint"),
            "street": dict(session.get("street") or {}),
            "legend": "# wall  . floor  I ICE  * loot  % core  X exit  @ you",
        }
