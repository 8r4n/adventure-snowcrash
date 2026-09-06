"""Deep ICE heist runs + hostile AI presence (#56).

Multi-step jack-in heists: penetrate layered ICE, risk flatline (Focus/HP),
optional AI antagonist as StreetNet omen + cyberspace boss stub.
Synergizes with ICE probes (#46) and cyberspace jack-in (#47).
Neuromancer-inspired fantasy; original Metaverse naming and prose only.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from .. import constants as C
from ..items import Item, make_datachip
from .cyberspace import (
    CYBER_CORE,
    CYBER_EXIT,
    CYBER_FLOOR,
    CYBER_ICE,
    CYBER_START,
    CYBER_WALL,
    JACK_IN_RADIUS,
    _cyber_relative_delta,
    _find_glyph,
    _lines_to_grid,
    _replace_glyph,
    render_node_map,
    walkable_cyber,
)

# ---------------------------------------------------------------------------
# Template: Black Lattice Vault (3 ICE layers)
# ---------------------------------------------------------------------------

HEIST_TEMPLATE_ID = "black_lattice_vault"
HEIST_TEMPLATE_NAME = "Black Lattice Vault"
HEIST_LAYER_COUNT = 3

# Failure costs — recoverable, never soft-lock the street loop
HEIST_FAIL_STUN_SEC = 8.0
HEIST_FAIL_DEBT = 8  # bandwidth_debt (pay_bandwidth / credits clear)
HEIST_FAIL_HEAT = 12.0
HEIST_COOLDOWN_SEC = 20.0  # before another heist start after fail/success
HEIST_ICE_BUMP_FOCUS = 1
HEIST_ICE_BUMP_HP = 1
HEIST_FLATLINE_FOCUS = 0  # Focus at/below this + backlash can abort
HEIST_AI_PULSE_HP = 2
HEIST_AI_PULSE_FOCUS = 1

# StreetNet omen cadence (world ticks)
HEIST_OMEN_FIRST_TICK = 18
HEIST_OMEN_INTERVAL_MIN = 70
HEIST_OMEN_INTERVAL_MAX = 110

OMEN_LINES = (
    "StreetNet omen: something older than Babel skims the jack lattice — a name without a face.",
    "Courier channel hush — rumor of a hostile intelligence pacing the deep ICE. Jackpoints itch.",
    "StreetNet flicker: BLACK LATTICE watchers. If you jack deep, bring Focus — or bring a spare sleeve.",
)

AI_NAME = "Null Choir"
AI_TITLE = "hostile lattice intelligence"

LAYER_HINTS = (
    "Layer 1/3 · Perimeter Scrub — melt I with stun/reveal, take % core, exit X.",
    "Layer 2/3 · Honeycomb Lattice — denser ICE; bumps tax Focus/HP. Core then X.",
    "Layer 3/3 · Core Sanctum — %s presence (%s). Melt ICE, seize core, escape before the pulse."
    % (AI_NAME, AI_TITLE),
)

# Layer maps — @ start, I ICE, % core, X exit
_LAYER_1 = [
    "#########",
    "#@......#",
    "#.###I..#",
    "#...#I..#",
    "#.%.#I..#",
    "#.###...#",
    "#.......#",
    "#......X#",
    "#########",
]

_LAYER_2 = [
    "###########",
    "#@..I.....#",
    "###.I.###.#",
    "#...I...#.#",
    "#.#####I#.#",
    "#.%...I...#",
    "#.#####I###",
    "#.....I...#",
    "#####.I.###",
    "#.....I..X#",
    "###########",
]

_LAYER_3 = [
    "#############",
    "#@....I.....#",
    "#.###.I.###.#",
    "#...#.I.#...#",
    "###.#.I.#.###",
    "#...#.I.#.%A#",  # A = AI boss stub tile (treated as floor + presence)
    "#.###.I.#####",
    "#.....I.....#",
    "#####.I.#####",
    "#.....I....X#",
    "#############",
]

_LAYERS = (_LAYER_1, _LAYER_2, _LAYER_3)


def make_heist_shard() -> Item:
    return Item(
        id="heist_shard",
        name="Black Lattice Shard",
        glyph="*",
        kind="datachip",
        description=(
            "A cold splinter cut from a deep ICE vault. "
            "StreetNet treats it like a rumor you can hold."
        ),
        hack_bonus=1,
        consumable=False,
        extra={"heist": True, "cyber": True},
    )


def make_heist_dump(layer: int) -> Item:
    return make_datachip(
        name="Vault Dump · L%d" % layer,
        desc=(
            "Packet dump from Black Lattice Vault layer %d. "
            "Scrubbed of Choir residue — mostly."
        )
        % layer,
    )


def build_heist_layer(layer_index: int) -> Dict[str, Any]:
    """Build one heist layer session (0-based index)."""
    idx = max(0, min(HEIST_LAYER_COUNT - 1, int(layer_index)))
    tmpl = _LAYERS[idx]
    grid = _lines_to_grid(tmpl)
    start = _find_glyph(grid, CYBER_START) or (1, 1)
    _replace_glyph(grid, CYBER_START, CYBER_FLOOR)
    # AI stub glyph A → floor; presence tracked separately on layer 3
    ai_pos = _find_glyph(grid, "A")
    if ai_pos:
        grid[ai_pos[1]][ai_pos[0]] = CYBER_FLOOR
    ice_cells: List[List[int]] = []
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch == CYBER_ICE:
                ice_cells.append([x, y])
    return {
        "layer": idx + 1,
        "layer_index": idx,
        "node_type": "heist_layer",
        "grid": grid,
        "width": len(grid[0]) if grid else 0,
        "height": len(grid),
        "px": start[0],
        "py": start[1],
        "ice_cells": ice_cells,
        "loot_taken": False,
        "cleared": False,
        "hint": LAYER_HINTS[idx],
        "ai": (
            {
                "id": "null_choir",
                "name": AI_NAME,
                "title": AI_TITLE,
                "x": ai_pos[0] if ai_pos else None,
                "y": ai_pos[1] if ai_pos else None,
                "hp": 24,
                "max_hp": 24,
                "pulse_every": 4,  # actions between pulses
                "pulse_counter": 0,
                "stub": True,
            }
            if idx == HEIST_LAYER_COUNT - 1
            else None
        ),
    }


class IceHeistMixin:
    """Mixed into YearFeaturesMixin / GameWorld."""

    def _ice_heist_init(self) -> None:
        self.ice_heist_world: Dict[str, Any] = {
            "omen_next_tick": HEIST_OMEN_FIRST_TICK,
            "omen_count": 0,
            "last_omen_text": None,
            "template_id": HEIST_TEMPLATE_ID,
            "template_name": HEIST_TEMPLATE_NAME,
        }

    def _ice_heist_bootstrap_agent(self, agent) -> None:
        h = getattr(agent, "heist", None)
        if not isinstance(h, dict):
            agent.heist = {
                "active": False,
                "template_id": None,
                "layer": 0,
                "layers_cleared": 0,
                "runs": 0,
                "fails": 0,
                "wins": 0,
                "cooldown_until": 0.0,
                "stun_until": 0.0,
                "last_result": None,
            }
            return
        h.setdefault("active", False)
        h.setdefault("template_id", None)
        h.setdefault("layer", 0)
        h.setdefault("layers_cleared", 0)
        h.setdefault("runs", 0)
        h.setdefault("fails", 0)
        h.setdefault("wins", 0)
        h.setdefault("cooldown_until", 0.0)
        h.setdefault("stun_until", 0.0)
        h.setdefault("last_result", None)

    def _ice_heist_at_jackpoint(self, agent) -> bool:
        jx, jy = self.jackpoint_pos
        ax, ay = agent.actor.x, agent.actor.y
        az = int(getattr(agent.actor, "z", 0) or 0)
        if az != C.PLANE_STREET:
            return False
        return abs(ax - jx) + abs(ay - jy) <= JACK_IN_RADIUS

    def _ice_heist_stunned(self, agent) -> bool:
        self._ice_heist_bootstrap_agent(agent)
        return float(agent.heist.get("stun_until") or 0) > time.time()

    def _ice_heist_on_cooldown(self, agent) -> bool:
        self._ice_heist_bootstrap_agent(agent)
        return float(agent.heist.get("cooldown_until") or 0) > time.time()

    def _tick_ice_heist(self) -> None:
        """StreetNet omen broadcasts — AI presence as myth/corporate force."""
        world = getattr(self, "ice_heist_world", None)
        if not isinstance(world, dict):
            self._ice_heist_init()
            world = self.ice_heist_world
        if self.tick < int(world.get("omen_next_tick") or 0):
            return
        rng = getattr(self, "rng", None)
        import random as _random

        r = rng if rng is not None else _random
        line = r.choice(list(OMEN_LINES))
        world["omen_count"] = int(world.get("omen_count") or 0) + 1
        world["last_omen_text"] = line
        gap = r.randint(HEIST_OMEN_INTERVAL_MIN, HEIST_OMEN_INTERVAL_MAX)
        world["omen_next_tick"] = self.tick + gap
        if hasattr(self, "_push_event"):
            self._push_event(
                "ice_heist_omen",
                line,
                ai=AI_NAME,
                template=HEIST_TEMPLATE_ID,
                phase="omen",
            )
        # Soft system chat to connected couriers
        for p in list(getattr(self, "players", {}).values()):
            if getattr(p, "connected", False):
                p.log(line)

    def _ice_heist_start(self, agent, arg: str = "") -> bool:
        self._ice_heist_bootstrap_agent(agent)
        if agent.mode == "heist" and (agent.heist or {}).get("active"):
            agent.log("Already deep in a Black Lattice run. Esc / heist_abort to jack out.")
            return True
        if agent.mode == "cyberspace":
            agent.log("Jack out of the current node before starting a deep heist.")
            return True
        if not self._ice_heist_at_jackpoint(agent):
            agent.log(
                "Deep heist needs a jackpoint handshake. Stand on or next to J, then heist_start."
            )
            return True
        if self._ice_heist_stunned(agent):
            left = float(agent.heist["stun_until"]) - time.time()
            agent.log(
                "Neural stun still fading (%.1fs) — StreetNet won't open the vault yet."
                % max(0.0, left)
            )
            return True
        if self._ice_heist_on_cooldown(agent):
            left = float(agent.heist["cooldown_until"]) - time.time()
            agent.log(
                "Vault handshake cooling (%.1fs). Walk the street; try again soon."
                % max(0.0, left)
            )
            return True

        street = {
            "x": agent.actor.x,
            "y": agent.actor.y,
            "z": int(getattr(agent.actor, "z", 0) or 0),
            "facing": int(getattr(agent.actor, "facing", 0) or 0) % 4,
        }
        layer = build_heist_layer(0)
        agent.heist.update(
            {
                "active": True,
                "template_id": HEIST_TEMPLATE_ID,
                "template_name": HEIST_TEMPLATE_NAME,
                "layer": 1,
                "layers_cleared": 0,
                "street": street,
                "session": layer,
                "last_result": None,
            }
        )
        agent.heist["runs"] = int(agent.heist.get("runs") or 0) + 1
        agent.mode = "heist"
        # Parked sleeve shield (same idea as cyberspace)
        agent.invuln_until = max(
            float(getattr(agent, "invuln_until", 0) or 0),
            time.time() + 600.0,
        )
        agent.cutscene("terminal")
        agent.sfx("pulse")
        agent.log(
            "Deep heist — %s opens. Layer 1/%d. Street body parked at (%d,%d). %s"
            % (
                HEIST_TEMPLATE_NAME,
                HEIST_LAYER_COUNT,
                street["x"],
                street["y"],
                layer["hint"],
            )
        )
        j = getattr(agent, "journal", None) or {}
        notes = list(j.get("notes", []) or [])
        note = "Started Black Lattice Vault deep heist from jackpoint."
        if note not in notes:
            notes.append(note)
            j["notes"] = notes[-8:]
            agent.journal = j
        if hasattr(self, "_push_event"):
            self._push_event(
                "ice_heist",
                "%s jacked into %s." % (getattr(agent, "name", "Courier"), HEIST_TEMPLATE_NAME),
                phase="start",
                agent=getattr(agent, "name", None),
            )
        if hasattr(self, "_analytics"):
            self._analytics("heist_start", agent, template=HEIST_TEMPLATE_ID)
        return True

    def _ice_heist_apply_failure(self, agent, reason: str) -> None:
        """Stun + debt + heat — recoverable; never soft-locks play."""
        self._ice_heist_bootstrap_agent(agent)
        now = time.time()
        agent.heist["stun_until"] = now + HEIST_FAIL_STUN_SEC
        agent.heist["cooldown_until"] = now + HEIST_COOLDOWN_SEC
        agent.heist["fails"] = int(agent.heist.get("fails") or 0) + 1
        agent.heist["last_result"] = "fail:%s" % reason
        # Debt — bandwidth ledger (pay_bandwidth clears)
        agent.bandwidth_debt = int(getattr(agent, "bandwidth_debt", 0) or 0) + HEIST_FAIL_DEBT
        # Heat — corp interest without trapping the courier
        if hasattr(self, "_add_heat"):
            self._add_heat(agent, HEIST_FAIL_HEAT, "deep ICE backlash")
        else:
            agent.heat = float(getattr(agent, "heat", 0) or 0) + HEIST_FAIL_HEAT
        # Keep HP/Focus at least 1 so street play continues (no soft-lock death from heist abort)
        if agent.actor.hp < 1:
            agent.actor.hp = 1
        if agent.actor.focus < 0:
            agent.actor.focus = 0
        agent.log(
            "Heist abort — neural stun %.0fs, +%d bandwidth debt, heat spike. "
            "Street loop still open: walk, pay_bandwidth, shed heat in a safehouse."
            % (HEIST_FAIL_STUN_SEC, HEIST_FAIL_DEBT)
        )

    def _ice_heist_jack_out(self, agent, *, reason: str = "manual") -> bool:
        self._ice_heist_bootstrap_agent(agent)
        session_meta = agent.heist or {}
        if not session_meta.get("active") and agent.mode != "heist":
            agent.log("Not in a deep heist.")
            return True
        street = session_meta.get("street") or {}
        sx = int(street.get("x", agent.actor.x))
        sy = int(street.get("y", agent.actor.y))
        sz = int(street.get("z", C.PLANE_STREET))
        facing = int(street.get("facing", getattr(agent.actor, "facing", 0)) or 0) % 4
        if hasattr(self, "_force_set_pos"):
            self._force_set_pos(agent, sx, sy, sz, "heist jack-out")
        else:
            agent.actor.x, agent.actor.y = sx, sy
            agent.actor.z = sz
        agent.actor.facing = facing
        agent.last_good_x, agent.last_good_y, agent.last_good_z = sx, sy, sz
        agent.mode = "play"
        layers_cleared = int(session_meta.get("layers_cleared") or 0)
        agent.heist["active"] = False
        agent.heist["session"] = None
        agent.heist["layer"] = 0
        agent.invuln_until = time.time() + 3.0

        if reason == "cleared":
            agent.heist["cooldown_until"] = time.time() + HEIST_COOLDOWN_SEC
            agent.heist["wins"] = int(agent.heist.get("wins") or 0) + 1
            agent.heist["last_result"] = "win"
            agent.log(
                "Heist clear — vault sealed behind you. Re-sleeved at (%d,%d,z=%d). Choir echo fades."
                % (sx, sy, sz)
            )
        elif reason in ("flatline", "ai_pulse", "abort_fail"):
            self._ice_heist_apply_failure(agent, reason)
            agent.log(
                "Jack-out under fire — re-sleeved at (%d,%d). Layers held: %d/%d."
                % (sx, sy, layers_cleared, HEIST_LAYER_COUNT)
            )
        else:
            # Manual abort mid-run counts as soft fail (costs) so quitting isn't free cheese
            if layers_cleared < HEIST_LAYER_COUNT:
                self._ice_heist_apply_failure(agent, "manual")
            agent.log(
                "Heist jack-out — connection dropped at (%d,%d). Grid echo fades."
                % (sx, sy)
            )
        agent.sfx("click")
        if hasattr(self, "update_fov"):
            self.update_fov(agent)
        return True

    def _ice_heist_grant_layer_rewards(self, agent, layer_num: int) -> None:
        agent.actor.inventory.append(make_heist_dump(layer_num))
        agent.credits = int(getattr(agent, "credits", 0) or 0) + (8 + layer_num * 4)
        agent.actor.focus = min(
            agent.actor.max_focus,
            int(agent.actor.focus) + 2,
        )
        agent.log(
            "Layer %d dump sleeved (+credits, +Focus). Vault still deeper."
            % layer_num
        )

    def _ice_heist_grant_finale_rewards(self, agent) -> None:
        agent.actor.inventory.append(make_heist_shard())
        agent.credits = int(getattr(agent, "credits", 0) or 0) + 40
        agent.actor.focus = min(
            agent.actor.max_focus,
            int(agent.actor.focus) + 5,
        )
        flags = getattr(agent, "quest_flags", None)
        if not isinstance(flags, dict):
            flags = {}
            agent.quest_flags = flags
        flags["ice_heist_cleared"] = True
        flags["ice_heists_cleared"] = int(flags.get("ice_heists_cleared", 0) or 0) + 1
        j = getattr(agent, "journal", None) or {}
        notes = list(j.get("notes", []) or [])
        notes.append(
            "Black Lattice Vault cleared — shard sleeved; %s watched and lost interest… for now."
            % AI_NAME
        )
        j["notes"] = notes[-8:]
        side = list(j.get("side", []) or [])
        if "ice_heist" not in [s.get("id") for s in side if isinstance(s, dict)]:
            side.append(
                {
                    "id": "ice_heist",
                    "text": "Deep heist: clear Black Lattice Vault (3 ICE layers) at J",
                    "done": True,
                }
            )
        else:
            for s in side:
                if isinstance(s, dict) and s.get("id") == "ice_heist":
                    s["done"] = True
        j["side"] = side
        agent.journal = j
        agent.log(
            "Vault payload sleeved: Black Lattice Shard. +40 credits. "
            "%s retreats into rumor. Same courier, colder sleeve."
            % AI_NAME
        )
        if hasattr(self, "_grant_season_xp"):
            self._grant_season_xp(agent, 14)
        if hasattr(self, "_analytics"):
            self._analytics("heist_clear", agent, template=HEIST_TEMPLATE_ID)
        if hasattr(self, "_push_event"):
            self._push_event(
                "ice_heist",
                "%s scrubbed the Black Lattice Vault." % getattr(agent, "name", "Courier"),
                phase="clear",
                agent=getattr(agent, "name", None),
            )

    def _ice_heist_advance_or_finish(self, agent) -> None:
        h = agent.heist
        session = h.get("session") or {}
        layer_num = int(h.get("layer") or 1)
        h["layers_cleared"] = layer_num
        self._ice_heist_grant_layer_rewards(agent, layer_num)
        if layer_num >= HEIST_LAYER_COUNT:
            self._ice_heist_grant_finale_rewards(agent)
            self._ice_heist_jack_out(agent, reason="cleared")
            return
        # Next layer
        nxt = build_heist_layer(layer_num)  # layer_num is 1-based cleared → next index
        h["layer"] = layer_num + 1
        h["session"] = nxt
        agent.log(
            "Lattice shifts — descending to layer %d/%d. %s"
            % (h["layer"], HEIST_LAYER_COUNT, nxt["hint"])
        )
        agent.sfx("pulse")
        if nxt.get("ai"):
            agent.log(
                "%s stirs in the sanctum — a boss stub of attention, not a full fight. "
                "Grab the core and exit before the pulse flatlines your Focus."
                % AI_NAME
            )

    def _ice_heist_try_pickup(self, agent) -> None:
        session = (agent.heist or {}).get("session") or {}
        grid = session.get("grid") or []
        px, py = int(session.get("px", 0)), int(session.get("py", 0))
        if py < 0 or px < 0 or py >= len(grid) or px >= len(grid[0]):
            return
        ch = grid[py][px]
        if ch == CYBER_CORE and not session.get("loot_taken"):
            session["loot_taken"] = True
            grid[py][px] = CYBER_FLOOR
            agent.log("Vault core dissolves into your sleeve buffer — find the exit (X).")
            agent.sfx("pulse")
            # Damaging the AI stub if standing near / on its tile when taking core
            ai = session.get("ai")
            if ai and ai.get("stub"):
                ai["hp"] = max(0, int(ai.get("hp") or 0) - 8)
                agent.log(
                    "%s recoils (stub HP %d/%d) — attention thins."
                    % (ai.get("name") or AI_NAME, ai["hp"], ai.get("max_hp") or 24)
                )
        if ch == CYBER_EXIT and session.get("loot_taken"):
            session["cleared"] = True
            self._ice_heist_advance_or_finish(agent)
        elif ch == CYBER_EXIT and not session.get("loot_taken"):
            agent.log("Exit port locked — seize the vault core (%) first.")

    def _ice_heist_ai_pulse(self, agent) -> None:
        session = (agent.heist or {}).get("session") or {}
        ai = session.get("ai")
        if not ai or not ai.get("stub"):
            return
        if int(ai.get("hp") or 0) <= 0:
            return
        ai["pulse_counter"] = int(ai.get("pulse_counter") or 0) + 1
        every = max(1, int(ai.get("pulse_every") or 4))
        if ai["pulse_counter"] % every != 0:
            return
        # Hostile attention pulse — Focus/HP tax; can force abort without soft-lock
        agent.actor.focus = max(0, int(agent.actor.focus) - HEIST_AI_PULSE_FOCUS)
        agent.actor.hp = max(0, int(agent.actor.hp) - HEIST_AI_PULSE_HP)
        agent.log(
            "%s pulses the sanctum (−%d Focus, −%d HP). Stub presence; melt ICE and run."
            % (ai.get("name") or AI_NAME, HEIST_AI_PULSE_FOCUS, HEIST_AI_PULSE_HP)
        )
        agent.sfx("hurt")
        if agent.actor.hp <= 0 or agent.actor.focus <= 0:
            agent.actor.hp = max(1, agent.actor.hp)  # prevent street soft-lock death
            agent.log("Flatline risk — forcing jack-out before the Choir writes your name.")
            self._ice_heist_jack_out(agent, reason="ai_pulse")

    def _ice_heist_move(self, agent, dx: int, dy: int) -> bool:
        session = (agent.heist or {}).get("session") or {}
        if not (agent.heist or {}).get("active"):
            return False
        nx = int(session.get("px", 0)) + dx
        ny = int(session.get("py", 0)) + dy
        grid = session.get("grid") or []
        if not walkable_cyber(session, nx, ny):
            if 0 <= ny < len(grid) and 0 <= nx < len(grid[0]) and grid[ny][nx] == CYBER_ICE:
                # Bump tax — failure pressure without soft-lock
                agent.actor.focus = max(0, int(agent.actor.focus) - HEIST_ICE_BUMP_FOCUS)
                if int(session.get("layer") or 1) >= 2:
                    agent.actor.hp = max(1, int(agent.actor.hp) - HEIST_ICE_BUMP_HP)
                agent.log(
                    "ICE wall bites (−Focus%s). ice_probe stun|reveal to melt."
                    % ("/−HP" if int(session.get("layer") or 1) >= 2 else "")
                )
                if agent.actor.focus <= 0:
                    agent.log("Focus flatlined on ICE — aborting heist.")
                    self._ice_heist_jack_out(agent, reason="flatline")
                    return True
            agent.sfx("bump")
            self._ice_heist_ai_pulse(agent)
            return True
        session["px"], session["py"] = nx, ny
        self._ice_heist_try_pickup(agent)
        if (agent.heist or {}).get("active"):
            self._ice_heist_ai_pulse(agent)
        return True

    def _ice_heist_clear_ice_near(self, agent, radius: int = 1) -> int:
        session = (agent.heist or {}).get("session") or {}
        if not (agent.heist or {}).get("active"):
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
                "Probe melts %d ICE cell%s in the vault lattice."
                % (cleared, "" if cleared == 1 else "s")
            )
            agent.sfx("pulse")
            # Probing near AI stub chips its attention
            ai = session.get("ai")
            if ai and ai.get("stub") and int(ai.get("hp") or 0) > 0:
                ai["hp"] = max(0, int(ai["hp"]) - cleared)
        return cleared

    def _ice_heist_handle_action(self, agent, action: str, arg: Optional[str] = None) -> bool:
        """Handle actions while mode==heist. Return True if consumed."""
        self._ice_heist_bootstrap_agent(agent)
        a = (action or "").strip()
        al = a.lower()

        if al in (
            "heist_abort", "heist_out", "jack_out", "jackout", "unjack",
            "leave_heist", "cyber_out", "escape", "esc", "q",
        ):
            return self._ice_heist_jack_out(agent, reason="manual")
        if al in ("?", "help"):
            session = (agent.heist or {}).get("session") or {}
            agent.log(session.get("hint") or "Deep heist — melt ICE, take core, exit X.")
            agent.log(
                "Controls: move as street · ice_probe stun|reveal melts I · Esc / heist_abort jack out "
                "(abort costs stun/debt/heat, no soft-lock)."
            )
            return True

        # ICE probes inside heist — same Focus economy as #46 / #47
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
                agent.log("In-heist ICE: stun or reveal melts adjacent I cells (Focus cost).")
                return True
            if pid not in ("stun", "reveal"):
                if pid == "scramble":
                    agent.log("Aggro Scramble has no street hostiles in the vault — try stun or reveal.")
                    return True
                agent.log("Unknown probe in-heist. Try: stun, reveal.")
                return True
            defn = C.ICE_PROBES[pid]
            now = time.time()
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
                agent.log("Need %d Focus for %s — abort or wait if you're empty." % (cost, defn["name"]))
                if agent.actor.focus <= 0:
                    self._ice_heist_jack_out(agent, reason="flatline")
                return True
            agent.actor.focus -= cost
            cds[pid] = now + float(defn["cooldown"])
            n = self._ice_heist_clear_ice_near(agent, radius=2 if pid == "reveal" else 1)
            if not n:
                agent.log(
                    "%s pulses the vault (−%d Focus) — no ICE in reach. Step closer to an I."
                    % (defn["name"], cost)
                )
            self._ice_heist_ai_pulse(agent)
            return True

        if a in getattr(C, "REL_MOVE_ACTIONS", ()):
            dx, dy = _cyber_relative_delta(int(getattr(agent.actor, "facing", 0) or 0), a)
            return self._ice_heist_move(agent, dx, dy)
        if a in getattr(C, "MOVE_8", {}):
            dx, dy = C.MOVE_8[a]
            return self._ice_heist_move(agent, dx, dy)
        if a in getattr(C, "MOVE_KEYS", {}):
            dx, dy = C.MOVE_KEYS[a]
            return self._ice_heist_move(agent, dx, dy)
        if al in ("turn_left", "tl", ","):
            agent.actor.facing = (agent.actor.facing - 1) % 4
            agent.sfx("click")
            return True
        if al in ("turn_right", "tr"):
            agent.actor.facing = (agent.actor.facing + 1) % 4
            agent.sfx("click")
            return True
        if al in (".", " ", "wait", "look", "noop"):
            self._ice_heist_ai_pulse(agent)
            return True
        if al in ("g", "get", "pickup"):
            self._ice_heist_try_pickup(agent)
            return True
        if al in ("i", "inventory", "f", "fire", "hack", "plane_up", "plane_down"):
            agent.log("Street controls muted in deep heist — move, probe ICE, or heist_abort.")
            return True
        return True

    def _ice_heist_action(self, agent, action: str, arg: str = "") -> bool:
        """Street-side heist commands."""
        self._ice_heist_bootstrap_agent(agent)
        a = (action or "").strip().lower()
        if a in (
            "heist_start", "deep_heist", "ice_heist", "start_heist",
            "heist_begin", "vault_heist",
        ):
            return self._ice_heist_start(agent, arg)
        if a in ("heist_abort", "heist_out", "leave_heist"):
            return self._ice_heist_jack_out(agent, reason="manual")
        if a in ("heist", "heist_status", "heist_info", "vault_status"):
            return self._ice_heist_status(agent)
        return False

    def _ice_heist_status(self, agent) -> bool:
        self._ice_heist_bootstrap_agent(agent)
        h = agent.heist
        world = getattr(self, "ice_heist_world", {}) or {}
        if h.get("active"):
            session = h.get("session") or {}
            ai = session.get("ai")
            agent.log(
                "%s — layer %d/%d · ICE left %d · core %s%s"
                % (
                    HEIST_TEMPLATE_NAME,
                    int(h.get("layer") or 1),
                    HEIST_LAYER_COUNT,
                    sum(1 for row in (session.get("grid") or []) for ch in row if ch == CYBER_ICE),
                    "taken" if session.get("loot_taken") else "secure",
                    (
                        " · %s stub HP %d/%d"
                        % (
                            ai.get("name") or AI_NAME,
                            int(ai.get("hp") or 0),
                            int(ai.get("max_hp") or 0),
                        )
                        if ai
                        else ""
                    ),
                )
            )
            return True
        now = time.time()
        stun_left = max(0.0, float(h.get("stun_until") or 0) - now)
        cd_left = max(0.0, float(h.get("cooldown_until") or 0) - now)
        can = self._ice_heist_at_jackpoint(agent) and stun_left <= 0 and cd_left <= 0
        agent.log(
            "Deep heist idle — template %s (%d layers). Wins %d · fails %d. "
            "At J: %s. Stun %.1fs · cooldown %.1fs. "
            "Start: heist_start (or jack_in heist). Last omen: %s"
            % (
                HEIST_TEMPLATE_NAME,
                HEIST_LAYER_COUNT,
                int(h.get("wins") or 0),
                int(h.get("fails") or 0),
                "yes" if can else "no",
                stun_left,
                cd_left,
                (world.get("last_omen_text") or "none yet")[:80],
            )
        )
        return True

    def _ice_heist_snapshot(self, agent) -> Dict[str, Any]:
        self._ice_heist_bootstrap_agent(agent)
        h = agent.heist
        world = getattr(self, "ice_heist_world", None)
        if not isinstance(world, dict):
            world = {}
        now = time.time()
        stun_left = max(0.0, float(h.get("stun_until") or 0) - now)
        cd_left = max(0.0, float(h.get("cooldown_until") or 0) - now)
        active = bool(h.get("active") and agent.mode == "heist")
        base = {
            "active": active,
            "template_id": HEIST_TEMPLATE_ID,
            "template_name": HEIST_TEMPLATE_NAME,
            "layers": HEIST_LAYER_COUNT,
            "can_start": (
                (not active)
                and self._ice_heist_at_jackpoint(agent)
                and stun_left <= 0
                and cd_left <= 0
            ),
            "stun_remaining": round(stun_left, 1),
            "cooldown_remaining": round(cd_left, 1),
            "wins": int(h.get("wins") or 0),
            "fails": int(h.get("fails") or 0),
            "runs": int(h.get("runs") or 0),
            "last_result": h.get("last_result"),
            "omen": {
                "count": int(world.get("omen_count") or 0),
                "last": world.get("last_omen_text"),
                "next_tick": world.get("omen_next_tick"),
                "ai": AI_NAME,
            },
            "hint": (
                "Deep heist live — melt I, take %, exit X. Esc aborts (stun/debt/heat)."
                if active
                else (
                    "At jackpoint — heist_start or jack_in heist for Black Lattice Vault (3 layers)."
                    if self._ice_heist_at_jackpoint(agent)
                    else "Reach jackpoint (J) to start a deep ICE heist."
                )
            ),
            "failure_costs": {
                "stun_sec": HEIST_FAIL_STUN_SEC,
                "debt": HEIST_FAIL_DEBT,
                "heat": HEIST_FAIL_HEAT,
                "soft_lock": False,
            },
        }
        if not active:
            return base
        session = h.get("session") or {}
        rows = render_node_map(session)
        ai = session.get("ai")
        base.update(
            {
                "layer": int(h.get("layer") or 1),
                "layers_cleared": int(h.get("layers_cleared") or 0),
                "map": rows,
                "width": session.get("width"),
                "height": session.get("height"),
                "px": session.get("px"),
                "py": session.get("py"),
                "loot_taken": bool(session.get("loot_taken")),
                "ice_remaining": sum(
                    1 for row in (session.get("grid") or []) for ch in row if ch == CYBER_ICE
                ),
                "layer_hint": session.get("hint"),
                "street": dict(h.get("street") or {}),
                "ai": (
                    {
                        "name": ai.get("name"),
                        "title": ai.get("title"),
                        "hp": ai.get("hp"),
                        "max_hp": ai.get("max_hp"),
                        "stub": True,
                        "x": ai.get("x"),
                        "y": ai.get("y"),
                    }
                    if ai
                    else None
                ),
                "legend": "# wall  . floor  I ICE  % core  X exit  @ you  · AI stub on L3",
            }
        )
        return base
