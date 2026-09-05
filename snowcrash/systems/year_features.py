"""Year backend feature mixin for GameWorld (issues #12–#39).

Playable stubs with complete action + snapshot surface. Original prose only.
"""

from __future__ import annotations

import csv
import io
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .. import constants as C
from ..entities import Actor, make_infected, make_thug
from ..items import Item

DATA_DIR = Path(__file__).resolve().parent / "data"

SKILL_CATALOG = {
    "streetwise": {"name": "Streetwise", "desc": "+1 defense on streets"},
    "jacker": {"name": "Jacker", "desc": "+1 hack"},
    "courier_legs": {"name": "Courier Legs", "desc": "+1 max focus"},
    "mono_form": {"name": "Mono Form", "desc": "+1 attack"},
    "faraday_mind": {"name": "Faraday Mind", "desc": "Resist signal storm focus drain"},
    "burb_charm": {"name": "Burb Charm", "desc": "Vendor prices -10%"},
}

LOADOUT_SLOTS = ("weapon", "armor", "trinket")

VENDOR_CATALOG = {
    "burb_kiosk": {
        "name": "Burbclave Kiosk",
        "stock": [
            {"id": "stimpack", "name": "Street Stimpack", "price": 12, "sell": 4},
            {"id": "focus_tab", "name": "Focus Tab", "price": 10, "sell": 3},
            {"id": "leather_jacket", "name": "Reinforced Jacket", "price": 40, "sell": 12},
        ],
    },
    "black_neon_bar": {
        "name": "Black Neon Bar",
        "stock": [
            {"id": "stimpack", "name": "Street Stimpack", "price": 14, "sell": 5},
            {"id": "pulse_shim", "name": "Pulse Shim", "price": 28, "sell": 9},
            {"id": "mono_knife", "name": "Monofilament Knife", "price": 35, "sell": 11},
        ],
    },
    "rim_parts": {
        "name": "Rim Parts Stall",
        "stock": [
            {"id": "pulse_shim", "name": "Pulse Shim", "price": 24, "sell": 8},
            {"id": "kevlar_vest", "name": "Kevlar Vest", "price": 45, "sell": 14},
            {"id": "focus_tab", "name": "Focus Tab", "price": 9, "sell": 3},
        ],
    },
    "tunnel_fence": {
        "name": "Tunnel Fence",
        "stock": [
            {"id": "stimpack", "name": "Street Stimpack", "price": 11, "sell": 4},
            {"id": "stun_baton", "name": "Stun Baton", "price": 22, "sell": 7},
        ],
    },
}

CONTRACT_DEFS = [
    {"id": "clear_thugs", "name": "Sweep Thugs", "desc": "Flatline 3 street thugs", "goal": 3, "kind": "kills_thug", "reward_credits": 30, "reward_rep": 5},
    {"id": "payload_run", "name": "Sleeve Run", "desc": "Pick up Payload-Zero once", "goal": 1, "kind": "got_payload", "reward_credits": 40, "reward_rep": 8},
    {"id": "uplink_clear", "name": "Scrub Contract", "desc": "Clear Payload-Zero at uplink", "goal": 1, "kind": "payload_cleared", "reward_credits": 60, "reward_rep": 12},
    {"id": "craft_once", "name": "Bench Duty", "desc": "Craft any Faraday recipe", "goal": 1, "kind": "craft", "reward_credits": 25, "reward_rep": 4},
]

JOURNAL_STEPS = [
    {"id": "brief", "text": "Talk to a street contact (or spawn) — accept Payload-Zero arc"},
    {"id": "jackpoint", "text": "Reach jackpoint (J) and sleeve Payload-Zero"},
    {"id": "survive", "text": "Survive the streets with the sleeve intact"},
    {"id": "uplink", "text": "Deliver to uplink (U) and scrub the payload"},
    {"id": "done", "text": "Arc complete — patrol or take contracts"},
]


def _load_json(name: str) -> Dict[str, Any]:
    path = DATA_DIR / name
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _item_from_shop_id(item_id: str) -> Optional[Item]:
    from ..items import (
        make_stimpack,
        make_focus_tab,
        make_leather_jacket,
        make_pulse_shim,
        make_mono_knife,
        make_kevlar_vest,
        make_stun_baton,
    )
    makers = {
        "stimpack": make_stimpack,
        "focus_tab": make_focus_tab,
        "leather_jacket": make_leather_jacket,
        "pulse_shim": make_pulse_shim,
        "mono_knife": make_mono_knife,
        "kevlar_vest": make_kevlar_vest,
        "stun_baton": make_stun_baton,
    }
    fn = makers.get(item_id)
    return fn() if fn else None


class YearFeaturesMixin:
    """Mixed into GameWorld — call _year_init() at end of __init__."""

    def _year_init(self) -> None:
        self.district_defs = _load_json("districts.json")
        self.recipe_defs = _load_json("recipes.json")
        self.season_defs = _load_json("season.json")
        self.parties: Dict[str, Dict[str, Any]] = {}
        self.crews: Dict[str, Dict[str, Any]] = {}
        self.kill_feed: List[Dict[str, Any]] = []
        self.event_ticker: List[Dict[str, Any]] = []
        self.world_events: List[Dict[str, Any]] = []
        self.next_event_tick = 40
        self.weather_state = {"id": "clear", "label": "Clear neon night", "until_tick": 200}
        self.bosses: List[Dict[str, Any]] = []
        self.analytics_log: List[Dict[str, Any]] = []
        self.replay_buffer: List[Dict[str, Any]] = []
        self.raid_instances: Dict[str, Dict[str, Any]] = {}
        self.mutes: Dict[str, set] = {}  # agent_id -> set of muted names
        self.channel_kicks: Dict[str, set] = {}  # channel -> kicked names lower
        self.auth_nicks: Dict[str, str] = {}  # token -> nick
        self.vendor_positions: Dict[str, Tuple[int, int]] = {}
        self._seed_vendors()
        self._seed_boss()
        self._push_event("broadcast", "StreetNet year layer online — districts, crews, contracts live.")

    # ----- agent field bootstrap -----
    def _year_bootstrap_agent(self, agent) -> None:
        agent.skills = getattr(agent, "skills", {}) or {}
        agent.loadout = getattr(agent, "loadout", None) or {"weapon": None, "armor": None, "trinket": None}
        agent.skill_picks_available = int(getattr(agent, "skill_picks_available", 0) or 0)
        agent.party_id = getattr(agent, "party_id", None)
        agent.party_invites = list(getattr(agent, "party_invites", []) or [])
        agent.crew_id = getattr(agent, "crew_id", None)
        agent.housing = getattr(agent, "housing", None) or {
            "room_id": f"room_{agent.id}",
            "stash": [],
            "at_home": False,
        }
        agent.journal = getattr(agent, "journal", None) or {
            "arc": "payload_zero",
            "step": 0,
            "steps": [dict(s) for s in JOURNAL_STEPS],
            "completed": False,
        }
        agent.reputation = int(getattr(agent, "reputation", 0) or 0)
        agent.contracts = list(getattr(agent, "contracts", []) or [])
        agent.pvp = getattr(agent, "pvp", None) or {"opt_in": False, "arena": None, "streets_pvp": False}
        agent.season = getattr(agent, "season", None) or {
            "id": self.season_defs.get("season_id"),
            "xp": 0,
            "tier": 0,
            "unlocked": [],
            "equipped": None,
        }
        agent.dead = False
        agent.respawn_options = []
        agent.spectating = None
        agent.muted = set(getattr(agent, "muted", set()) or set())
        agent.reports_filed = int(getattr(agent, "reports_filed", 0) or 0)
        agent.auth_nick = getattr(agent, "auth_nick", None)
        agent.raid_id = getattr(agent, "raid_id", None)
        agent.raid_lockout_until = float(getattr(agent, "raid_lockout_until", 0) or 0)
        agent.bandwidth_debt = int(getattr(agent, "bandwidth_debt", 0) or 0)
        agent.repair_needed = int(getattr(agent, "repair_needed", 0) or 0)
        if not agent.contracts:
            # Offer first contract
            c = dict(CONTRACT_DEFS[0])
            c["progress"] = 0
            c["status"] = "available"
            agent.contracts = [c]

    def _seed_vendors(self) -> None:
        w, h = self.gmap.width, self.gmap.height
        sx, sy = self.spawn_xy
        # Place relative landmarks
        candidates = {
            "burb_kiosk": (max(2, sx - 8), max(2, sy - 2)),
            "black_neon_bar": None,
            "rim_parts": (min(w - 3, self.uplink_pos[0] + 3), max(2, self.uplink_pos[1] - 2)),
            "tunnel_fence": (max(2, self.jackpoint_pos[0] - 4), min(h - 3, self.jackpoint_pos[1] + 4)),
        }
        if self.club_rects:
            cx = self.club_rects[0][0] + 1
            cy = self.club_rects[0][1] + 1
            candidates["black_neon_bar"] = (cx, cy)
        else:
            candidates["black_neon_bar"] = (min(w - 3, sx + 12), min(h - 3, sy + 4))
        for vid, pos in candidates.items():
            if not pos:
                continue
            x, y = pos
            # snap to walkable
            if not self.gmap.walkable(x, y):
                found = False
                for r in range(1, 10):
                    for dx in range(-r, r + 1):
                        for dy in range(-r, r + 1):
                            nx, ny = x + dx, y + dy
                            if self.gmap.walkable(nx, ny):
                                x, y = nx, ny
                                found = True
                                break
                        if found:
                            break
                    if found:
                        break
            self.vendor_positions[vid] = (x, y)

    def _seed_boss(self) -> None:
        # Place one elite near undercity-ish coords
        g = self.gmap
        bx = min(g.width - 4, max(4, int(g.width * 0.7)))
        by = min(g.height - 4, max(4, int(g.height * 0.75)))
        for _ in range(80):
            x = self.rng.randint(max(2, bx - 15), min(g.width - 3, bx + 15))
            y = self.rng.randint(max(2, by - 15), min(g.height - 3, by + 15))
            if self.gmap.walkable(x, y) and not self._near_any_spawn(x, y):
                boss = Actor(
                    x=x, y=y, name="Signal Baron", glyph="B",
                    hp=48, max_hp=48, attack=6, defense=3,
                    ai="chase", faction="enemy", xp_value=40, color="red",
                )
                boss.z = C.PLANE_STREET
                setattr(boss, "boss", True)
                setattr(boss, "telegraph", "windup")
                setattr(boss, "unique_drop", "baron_core")
                self.npcs_enemies.append(boss)
                self.bosses.append({"id": "signal_baron", "name": "Signal Baron", "x": x, "y": y, "alive": True})
                break

    def reload_district_defs(self) -> None:
        self.district_defs = _load_json("districts.json")
        self.recipe_defs = _load_json("recipes.json")
        self.season_defs = _load_json("season.json")

    # ----- districts / weather / time of day -----
    def _district_at(self, x: int, y: int, z: int = 0) -> Dict[str, Any]:
        if z == C.PLANE_UNDER:
            for d in self.district_defs.get("districts", []):
                if d.get("id") == "undercity":
                    return d
        w, h = max(1, self.gmap.width), max(1, self.gmap.height)
        nx, ny = x / w, y / h
        best = self.district_defs["districts"][0]
        for d in self.district_defs.get("districts", []):
            if d.get("plane") == -1:
                continue
            if d["x0"] <= nx <= d["x1"] and d["y0"] <= ny <= d["y1"]:
                return d
        return best

    def _tod(self) -> str:
        # 4 phases cycling every ~120 ticks
        phase = (self.tick // 120) % 4
        return ("dawn", "day", "dusk", "night")[phase]

    def _npc_schedule_line(self, npc: Actor) -> str:
        tod = self._tod()
        base = npc.talk or "..."
        schedules = {
            "dawn": " (rubs eyes) Streets reboot — %s",
            "day": " (scanning) Day traffic — %s",
            "dusk": " (nervous) Neon rising — %s",
            "night": " (whisper) Night market open — %s",
        }
        return (schedules.get(tod, " %s") % base)[:160]

    def _tick_weather(self) -> None:
        if self.tick >= int(self.weather_state.get("until_tick", 0)):
            roll = self.rng.random()
            if roll < 0.35:
                wid, label = "neon_rain", "Neon rain — slick streets"
            elif roll < 0.55:
                wid, label = "signal_storm", "Signal storm — focus static"
            else:
                wid, label = "clear", "Clear neon night"
            self.weather_state = {"id": wid, "label": label, "until_tick": self.tick + self.rng.randint(80, 200)}
            self._push_event("weather", label)
        # Apply mild storm drain
        if self.weather_state.get("id") == "signal_storm" and self.tick % 8 == 0:
            for p in self.players.values():
                if not p.connected or not p.actor.alive:
                    continue
                if "faraday_mind" in getattr(p, "skills", {}):
                    continue
                if p.actor.focus > 0:
                    p.actor.focus = max(0, p.actor.focus - 1)

    def _tick_npc_schedules(self) -> None:
        if self.tick % 40 != 0:
            return
        tod = self._tod()
        for a in self.npcs_enemies:
            if a.faction != "npc" or not a.alive:
                continue
            # Mild wander on schedule change
            if self.rng.random() < 0.4:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = a.x + dx, a.y + dy
                    z = int(getattr(a, "z", 0) or 0)
                    if self._can_stand(nx, ny, ignore=a, z=z):
                        a.x, a.y = nx, ny
                        break
            setattr(a, "schedule_tod", tod)

    def _push_event(self, kind: str, text: str, **extra: Any) -> None:
        ev = {"t": time.time(), "tick": self.tick, "kind": kind, "text": text, **extra}
        self.event_ticker.append(ev)
        if len(self.event_ticker) > 40:
            self.event_ticker = self.event_ticker[-40:]
        self.world_events.append(ev)
        if len(self.world_events) > 80:
            self.world_events = self.world_events[-80:]

    def _tick_street_events(self) -> None:
        if self.tick < self.next_event_tick:
            return
        self.next_event_tick = self.tick + self.rng.randint(50, 120)
        roll = self.rng.random()
        living = [p for p in self.players.values() if p.connected and p.actor.alive]
        if roll < 0.34 and living:
            # Ambush near a random player — never fresh-spawn / shielded / on-pad
            candidates = [
                p for p in living
                if not p.is_invulnerable()
                and not (
                    int(getattr(p.actor, "z", 0) or 0) == C.PLANE_STREET
                    and self._near_any_spawn(p.actor.x, p.actor.y)
                )
            ]
            if not candidates:
                self.next_event_tick = self.tick + self.rng.randint(20, 40)
                return
            p = self.rng.choice(candidates)
            spawned = 0
            for _ in range(3):
                for _try in range(20):
                    nx = p.actor.x + self.rng.randint(-4, 4)
                    ny = p.actor.y + self.rng.randint(-4, 4)
                    z = int(getattr(p.actor, "z", 0) or 0)
                    if self._can_stand(nx, ny, z=z) and not self._near_any_spawn(nx, ny):
                        mon = make_infected(nx, ny) if self.rng.random() < 0.5 else make_thug(nx, ny)
                        mon.z = z
                        self.npcs_enemies.append(mon)
                        spawned += 1
                        break
            self._push_event("ambush", "Ambush near %s — %d hostiles." % (p.name, spawned), x=p.actor.x, y=p.actor.y)
            p.log("Street event: ambush! Hostiles closing in.")
        elif roll < 0.67:
            job = self.rng.choice(["escort rumor chip", "scrub graffiti uplink", "deliver stim crate"])
            self._push_event("job", "Job board ping: %s (+credits if you poke a vendor)." % job)
            for p in living:
                p.log("Street job broadcast: %s" % job)
        else:
            msg = self.rng.choice([
                "Flotilla propaganda washes the rim.",
                "Burbclave tax drones overhead.",
                "Club Glassline guest list glitches open.",
            ])
            self._push_event("broadcast", msg)
            self.system_chat(msg)

    def _tick_boss_telegraphs(self) -> None:
        for a in self.npcs_enemies:
            if not getattr(a, "boss", False) or not a.alive:
                continue
            # Cycle telegraph states
            phase = (self.tick // 6) % 3
            a.telegraph = ("windup", "slam", "recover")[phase]
            if a.telegraph == "slam":
                # Extra punch vs nearest player
                living = [
                    p for p in self.players.values()
                    if p.connected and p.actor.alive
                    and int(getattr(p.actor, "z", 0) or 0) == int(getattr(a, "z", 0) or 0)
                ]
                if not living:
                    continue
                tgt = min(living, key=lambda p: abs(p.actor.x - a.x) + abs(p.actor.y - a.y))
                if abs(tgt.actor.x - a.x) + abs(tgt.actor.y - a.y) <= 2 and not tgt.is_invulnerable():
                    dmg = tgt.actor.take_damage(4)
                    tgt.log("Signal Baron telegraphed SLAM hits you for %d!" % dmg)
                    if not tgt.actor.alive:
                        self._year_on_player_death(tgt, killer_name=a.name)

    # ----- progression -----
    def _year_on_level_up(self, agent) -> None:
        agent.skill_picks_available = int(getattr(agent, "skill_picks_available", 0)) + 1
        agent.log("Skill pick available — action: skill_pick <id> (%s)" % ", ".join(SKILL_CATALOG))
        # Season XP
        self._grant_season_xp(agent, 15)

    def _sync_loadout_from_inventory(self, agent) -> None:
        loadout = {"weapon": None, "armor": None, "trinket": None}
        for it in agent.actor.inventory:
            if not it.equipped:
                continue
            if it.kind == "weapon":
                loadout["weapon"] = it.id
            elif it.kind == "armor":
                loadout["armor"] = it.id
            else:
                loadout["trinket"] = it.id
        agent.loadout = loadout

    # ----- death -----
    def _year_on_player_death(self, agent, killer_name: str = "unknown") -> None:
        agent.dead = True
        agent.lost = True
        agent.mode = "dead"
        agent.respawn_options = [
            {"id": "safe_pad", "label": "Safe street pad (default)"},
            {"id": "district", "label": "District node (near current district)"},
            {"id": "housing", "label": "Personal safehouse"},
        ]
        feed = {
            "t": time.time(),
            "victim": agent.name,
            "killer": killer_name,
            "tick": self.tick,
        }
        self.kill_feed.append(feed)
        if len(self.kill_feed) > 30:
            self.kill_feed = self.kill_feed[-30:]
        self.system_chat("%s flatlined by %s." % (agent.name, killer_name))
        self._analytics("death", agent, killer=killer_name)
        agent.repair_needed = min(40, agent.repair_needed + 8)
        # Party ping
        if agent.party_id and agent.party_id in self.parties:
            self.parties[agent.party_id]["ping"] = {
                "x": agent.actor.x, "y": agent.actor.y, "z": int(getattr(agent.actor, "z", 0) or 0),
                "by": agent.name, "kind": "down",
            }

    def _year_respawn(self, agent, choice: Optional[str] = None) -> None:
        choice = choice or "safe_pad"
        agent.dead = False
        agent.respawn_options = []
        # Call existing respawn then maybe relocate
        self._respawn(agent)
        if choice == "housing":
            # Place near spawn but mark at_home
            agent.housing["at_home"] = True
            agent.log("Respawned into safehouse instance (stash available).")
            n = self.clear_spawn_threats(agent.actor.x, agent.actor.y, C.PLANE_STREET)
            if n:
                agent.log("Cleared %d hostiles near safehouse pad." % n)
            self._grant_spawn_invuln(agent)
        elif choice == "district":
            d = self._district_at(agent.last_good_x, agent.last_good_y)
            # nudge toward district center
            w, h = self.gmap.width, self.gmap.height
            cx = int(((d["x0"] + d["x1"]) / 2) * w)
            cy = int(((d["y0"] + d["y1"]) / 2) * h)
            for r in range(0, 12):
                for dx in range(-r, r + 1):
                    for dy in range(-r, r + 1):
                        nx, ny = cx + dx, cy + dy
                        if self._can_stand(nx, ny, z=C.PLANE_STREET):
                            self._force_set_pos(agent, nx, ny, C.PLANE_STREET, "district respawn")
                            agent.log("Respawned at %s node." % d.get("name", "district"))
                            n = self.clear_spawn_threats(nx, ny, C.PLANE_STREET)
                            if n:
                                agent.log("Cleared %d hostiles near district pad." % n)
                            self._grant_spawn_invuln(agent)
                            self.update_fov(agent)
                            return

    # ----- journal -----
    def _year_update_journal(self, agent) -> None:
        j = agent.journal
        if j.get("completed"):
            return
        step = int(j.get("step", 0))
        if step == 0:
            j["step"] = 1  # auto-accept on join
        if step <= 1 and agent.has_payload():
            j["step"] = 2
            agent.log("Journal: Payload sleeved — survive to uplink.")
        if step <= 2 and agent.has_payload() and agent.kills >= 1:
            j["step"] = 3
        if agent.quest_flags.get("payload_cleared") or agent.won:
            j["step"] = 4
            j["completed"] = True
            agent.log("Journal: Payload-Zero arc complete.")
            self._grant_season_xp(agent, 40)
            self._analytics("payload", agent)

    # ----- analytics -----
    def _analytics(self, kind: str, agent=None, **extra: Any) -> None:
        row = {"t": time.time(), "tick": self.tick, "kind": kind, **extra}
        if agent is not None:
            row["player"] = agent.name
            row["player_id"] = agent.id
        self.analytics_log.append(row)
        if len(self.analytics_log) > 500:
            self.analytics_log = self.analytics_log[-500:]
        # Replay breadcrumb
        if agent is not None and agent.actor.x >= 0:
            self.replay_buffer.append({
                "t": time.time(), "tick": self.tick, "id": agent.id, "name": agent.name,
                "x": agent.actor.x, "y": agent.actor.y, "z": int(getattr(agent.actor, "z", 0) or 0),
                "event": kind,
            })
            if len(self.replay_buffer) > 2000:
                self.replay_buffer = self.replay_buffer[-2000:]

    def analytics_export_csv(self) -> str:
        buf = io.StringIO()
        fields = ["t", "tick", "kind", "player", "player_id"]
        w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in self.analytics_log:
            w.writerow(row)
        return buf.getvalue()

    # ----- season -----
    def _grant_season_xp(self, agent, amount: int) -> None:
        s = agent.season
        s["xp"] = int(s.get("xp", 0)) + amount
        per = int(self.season_defs.get("xp_per_tier", 50))
        cosmetics = self.season_defs.get("cosmetics", [])
        while s["xp"] >= per and s["tier"] < int(self.season_defs.get("max_tier", 12)):
            s["xp"] -= per
            s["tier"] += 1
            for c in cosmetics:
                if int(c.get("tier", 0)) == s["tier"] and c["id"] not in s["unlocked"]:
                    s["unlocked"].append(c["id"])
                    agent.log("Season unlock: %s" % c.get("name", c["id"]))

    # ----- economy sinks -----
    def _apply_tax(self, agent, gross: int) -> int:
        d = self._district_at(agent.actor.x, agent.actor.y, int(getattr(agent.actor, "z", 0) or 0))
        rate = 0.08 if d.get("id") == "burbclave" else 0.04
        tax = max(0, int(gross * rate))
        if tax and agent.credits >= tax:
            agent.credits -= tax
            agent.log("District tax −%d credits." % tax)
        return tax

    # ----- year tick hook -----
    def year_tick(self) -> None:
        self._tick_weather()
        self._tick_street_events()
        self._tick_npc_schedules()
        self._tick_boss_telegraphs()
        # Bandwidth sink every ~60 ticks
        if self.tick % 60 == 0:
            for p in self.players.values():
                if p.connected and p.actor.alive:
                    cost = 1
                    if p.credits >= cost:
                        p.credits -= cost
                        p.bandwidth_debt = 0
                    else:
                        p.bandwidth_debt += 1
                        if p.bandwidth_debt >= 3:
                            p.log("Bandwidth unpaid — focus regen slowed.")

    # ----- action dispatch -----
    def handle_year_action(self, agent, action: str, arg: Optional[str] = None) -> bool:
        """Return True if action consumed."""
        self._year_bootstrap_agent(agent)
        a = (action or "").strip().lower()
        arg = arg if arg is not None else ""

        # Death respawn with choice
        if agent.mode == "dead" and a in ("r", "restart", "respawn"):
            self._year_respawn(agent, (arg or "safe_pad").strip() or "safe_pad")
            return True

        if a == "skill_pick":
            sid = (arg or "").strip()
            if agent.skill_picks_available <= 0:
                agent.log("No skill picks available.")
                return True
            if sid not in SKILL_CATALOG:
                agent.log("Unknown skill. Options: %s" % ", ".join(SKILL_CATALOG))
                return True
            if sid in agent.skills:
                agent.log("Already learned %s." % sid)
                return True
            agent.skills[sid] = SKILL_CATALOG[sid]["name"]
            agent.skill_picks_available -= 1
            if sid == "jacker":
                agent.actor.hack += 1
            elif sid == "mono_form":
                agent.actor.attack += 1
            elif sid == "streetwise":
                agent.actor.defense += 1
            elif sid == "courier_legs":
                agent.actor.max_focus += 1
                agent.actor.focus += 1
            agent.log("Learned skill: %s" % SKILL_CATALOG[sid]["name"])
            return True

        if a == "set_loadout":
            # arg: slot=item_id
            self._sync_loadout_from_inventory(agent)
            agent.log("Loadout synced from equipped gear: %s" % agent.loadout)
            return True

        if a in ("buy", "sell"):
            return self._shop_action(agent, a, arg)

        if a.startswith("party_") or a in ("party_invite", "party_accept", "party_leave", "party_ping"):
            return self._party_action(agent, a, arg)

        if a.startswith("crew_") or a in ("crew_create", "crew_join", "crew_leave", "crew_stash"):
            return self._crew_action(agent, a, arg)

        if a in ("craft", "craft_list"):
            return self._craft_action(agent, a, arg)

        if a in ("house", "housing", "stash_put", "stash_take"):
            return self._housing_action(agent, a, arg)

        if a in ("contract_accept", "contract_list", "contract_turnin"):
            return self._contract_action(agent, a, arg)

        if a in ("pvp_optin", "pvp_optout", "pvp_arena"):
            return self._pvp_action(agent, a, arg)

        if a in ("mute", "unmute", "report", "kick"):
            return self._mod_action(agent, a, arg)

        if a in ("spectate", "unspectate", "replay_dump"):
            return self._spectate_action(agent, a, arg)

        if a in ("season_equip",):
            cid = (arg or "").strip()
            if cid in agent.season.get("unlocked", []):
                agent.season["equipped"] = cid
                agent.log("Equipped season cosmetic %s." % cid)
            else:
                agent.log("Cosmetic not unlocked.")
            return True

        if a in ("repair",):
            cost = max(5, int(getattr(agent, "repair_needed", 0) or 5))
            if agent.credits < cost:
                agent.log("Need %d credits to repair kit." % cost)
                return True
            agent.credits -= cost
            agent.repair_needed = 0
            agent.actor.hp = min(agent.actor.max_hp, agent.actor.hp + 10)
            agent.log("Repaired gear (−%d credits). HP topped a bit." % cost)
            return True

        if a in ("pay_bandwidth", "bandwidth"):
            cost = 5
            if agent.credits < cost:
                agent.log("Need %d credits for bandwidth." % cost)
                return True
            agent.credits -= cost
            agent.bandwidth_debt = 0
            agent.log("Bandwidth prepaid (−%d)." % cost)
            return True

        if a in ("raid_start", "raid_leave"):
            return self._raid_action(agent, a, arg)

        if a == "auth_nick":
            # Stub: arg is desired authenticated nick
            nick = (arg or agent.name).strip()[:24]
            token = uuid.uuid4().hex[:12]
            self.auth_nicks[token] = nick
            agent.auth_nick = nick
            agent.log("Auth nick stub bound: %s (token %s — staging only)." % (nick, token))
            return True

        return False

    def _near_vendor(self, agent) -> Optional[str]:
        ax, ay = agent.actor.x, agent.actor.y
        for vid, (vx, vy) in self.vendor_positions.items():
            if abs(ax - vx) + abs(ay - vy) <= 2:
                return vid
        return None

    def _shop_snapshot(self, agent) -> Optional[Dict[str, Any]]:
        vid = self._near_vendor(agent)
        if not vid:
            return None
        cat = VENDOR_CATALOG.get(vid, {})
        discount = 0.9 if "burb_charm" in getattr(agent, "skills", {}) else 1.0
        stock = []
        for s in cat.get("stock", []):
            stock.append({**s, "price": max(1, int(s["price"] * discount))})
        return {
            "vendor_id": vid,
            "name": cat.get("name", vid),
            "stock": stock,
            "pos": list(self.vendor_positions[vid]),
        }

    def _shop_action(self, agent, action: str, arg: str) -> bool:
        vid = self._near_vendor(agent)
        if not vid:
            agent.log("No vendor nearby.")
            return True
        cat = VENDOR_CATALOG[vid]
        discount = 0.9 if "burb_charm" in agent.skills else 1.0
        if action == "buy":
            item_id = (arg or "").strip()
            row = next((s for s in cat["stock"] if s["id"] == item_id), None)
            if not row:
                agent.log("Vendor does not sell that. Stock: %s" % ", ".join(s["id"] for s in cat["stock"]))
                return True
            price = max(1, int(row["price"] * discount))
            if agent.credits < price:
                agent.log("Need %d credits." % price)
                return True
            item = _item_from_shop_id(item_id)
            if not item:
                agent.log("Stock glitch.")
                return True
            agent.credits -= price
            self._apply_tax(agent, price)
            agent.actor.inventory.append(item)
            agent.log("Bought %s for %d." % (item.name, price))
            agent.sfx("pickup")
            return True
        # sell
        try:
            idx = int((arg or "").strip())
        except ValueError:
            agent.log("Usage: sell <inventory_index>")
            return True
        inv = agent.actor.inventory
        if idx < 0 or idx >= len(inv):
            agent.log("Bad index.")
            return True
        it = inv[idx]
        if it.quest or it.id == "payload_zero":
            agent.log("Cannot sell quest gear.")
            return True
        row = next((s for s in cat["stock"] if s["id"] == it.id), None)
        price = int(row["sell"]) if row else 2
        inv.pop(idx)
        agent.credits += price
        agent.log("Sold %s for %d." % (it.name, price))
        return True

    def _party_action(self, agent, action: str, arg: str) -> bool:
        if action == "party_invite":
            name = (arg or "").strip()
            tid = self.name_index.get(name.lower())
            other = self.players.get(tid) if tid else None
            if not other or not other.connected:
                agent.log("No such courier online.")
                return True
            if not agent.party_id:
                pid = uuid.uuid4().hex[:8]
                self.parties[pid] = {"id": pid, "leader": agent.id, "members": [agent.id], "ping": None, "channel": "#party-" + pid}
                agent.party_id = pid
                self.channel_chat.setdefault(self.parties[pid]["channel"], [])
                self.channel_topics[self.parties[pid]["channel"]] = "Party channel"
            other.party_invites = list(getattr(other, "party_invites", []))
            if agent.party_id not in other.party_invites:
                other.party_invites.append(agent.party_id)
            other.log("%s invited you to party %s — party_accept %s" % (agent.name, agent.party_id, agent.party_id))
            agent.log("Invite sent to %s." % other.name)
            return True
        if action == "party_accept":
            pid = (arg or "").strip() or (agent.party_invites[0] if agent.party_invites else "")
            if pid not in self.parties:
                agent.log("No such party invite.")
                return True
            party = self.parties[pid]
            if agent.id not in party["members"]:
                party["members"].append(agent.id)
            agent.party_id = pid
            agent.party_invites = [x for x in agent.party_invites if x != pid]
            ch = party["channel"]
            if ch not in agent.irc_channels:
                agent.irc_channels.append(ch)
            agent.irc_channel = ch
            agent.log("Joined party %s — channel %s" % (pid, ch))
            return True
        if action == "party_leave":
            pid = agent.party_id
            if not pid or pid not in self.parties:
                agent.party_id = None
                agent.log("Not in a party.")
                return True
            party = self.parties[pid]
            party["members"] = [m for m in party["members"] if m != agent.id]
            ch = party["channel"]
            agent.irc_channels = [c for c in agent.irc_channels if c != ch]
            agent.party_id = None
            if agent.irc_channel == ch:
                agent.irc_channel = "#streets"
            if not party["members"]:
                self.parties.pop(pid, None)
            agent.log("Left party.")
            return True
        if action == "party_ping":
            if not agent.party_id or agent.party_id not in self.parties:
                agent.log("Join a party first.")
                return True
            self.parties[agent.party_id]["ping"] = {
                "x": agent.actor.x, "y": agent.actor.y,
                "z": int(getattr(agent.actor, "z", 0) or 0),
                "by": agent.name, "kind": "ping",
            }
            agent.log("Party ping dropped.")
            return True
        return False

    def _crew_action(self, agent, action: str, arg: str) -> bool:
        if action == "crew_create":
            name = (arg or "crew").strip()[:20] or "crew"
            cid = uuid.uuid4().hex[:8]
            ch = "#crew-" + cid
            self.crews[cid] = {
                "id": cid, "name": name, "leader": agent.id,
                "members": [agent.id], "stash": [], "channel": ch,
            }
            agent.crew_id = cid
            self.channel_chat.setdefault(ch, [])
            self.channel_topics[ch] = "Crew %s stash channel" % name
            if ch not in agent.irc_channels:
                agent.irc_channels.append(ch)
            agent.log("Crew '%s' created (%s)." % (name, cid))
            return True
        if action == "crew_join":
            cid = (arg or "").strip()
            if cid not in self.crews:
                agent.log("No such crew id.")
                return True
            crew = self.crews[cid]
            if agent.id not in crew["members"]:
                crew["members"].append(agent.id)
            agent.crew_id = cid
            ch = crew["channel"]
            if ch not in agent.irc_channels:
                agent.irc_channels.append(ch)
            agent.log("Joined crew %s." % crew["name"])
            return True
        if action == "crew_leave":
            cid = agent.crew_id
            if not cid or cid not in self.crews:
                agent.crew_id = None
                agent.log("Not in a crew.")
                return True
            crew = self.crews[cid]
            crew["members"] = [m for m in crew["members"] if m != agent.id]
            agent.irc_channels = [c for c in agent.irc_channels if c != crew["channel"]]
            agent.crew_id = None
            if not crew["members"]:
                self.crews.pop(cid, None)
            agent.log("Left crew.")
            return True
        if action == "crew_stash":
            # arg: put <idx> | take <stash_idx>
            if not agent.crew_id or agent.crew_id not in self.crews:
                agent.log("No crew.")
                return True
            crew = self.crews[agent.crew_id]
            parts = (arg or "").split()
            if len(parts) < 2:
                agent.log("Usage: crew_stash put <inv_idx> | crew_stash take <stash_idx>")
                return True
            op, idx_s = parts[0], parts[1]
            try:
                idx = int(idx_s)
            except ValueError:
                agent.log("Bad index.")
                return True
            if op == "put":
                inv = agent.actor.inventory
                if idx < 0 or idx >= len(inv) or inv[idx].quest:
                    agent.log("Cannot stash that.")
                    return True
                it = inv.pop(idx)
                crew["stash"].append({
                    "id": it.id, "name": it.name, "kind": it.kind, "glyph": it.glyph,
                    "description": it.description,
                })
                agent.log("Stashed %s in crew vault." % it.name)
            elif op == "take":
                if idx < 0 or idx >= len(crew["stash"]):
                    agent.log("Bad stash index.")
                    return True
                row = crew["stash"].pop(idx)
                item = _item_from_shop_id(row["id"])
                if not item:
                    item = Item(id=row["id"], name=row["name"], kind=row.get("kind", "misc"),
                                glyph=row.get("glyph", "*"), description=row.get("description", ""))
                agent.actor.inventory.append(item)
                agent.log("Took %s from crew vault." % item.name)
            return True
        return False

    def _craft_action(self, agent, action: str, arg: str) -> bool:
        if action == "craft_list":
            names = [r["id"] for r in self.recipe_defs.get("recipes", [])]
            agent.log("Faraday recipes: %s" % ", ".join(names))
            return True
        rid = (arg or "").strip()
        recipe = next((r for r in self.recipe_defs.get("recipes", []) if r["id"] == rid), None)
        if not recipe:
            agent.log("Unknown recipe. craft_list for ids.")
            return True
        # Check inputs
        inputs = recipe.get("inputs", {})
        credit_cost = int(inputs.get("credits", 0))
        if agent.credits < credit_cost:
            agent.log("Need %d credits." % credit_cost)
            return True
        for iid, qty in inputs.items():
            if iid == "credits":
                continue
            have = sum(1 for i in agent.actor.inventory if i.id == iid)
            if have < int(qty):
                agent.log("Need %s x%d." % (iid, qty))
                return True
        # Consume
        agent.credits -= credit_cost
        for iid, qty in inputs.items():
            if iid == "credits":
                continue
            left = int(qty)
            new_inv = []
            for it in agent.actor.inventory:
                if it.id == iid and left > 0 and not it.equipped:
                    left -= 1
                    continue
                new_inv.append(it)
            agent.actor.inventory = new_inv
        out = recipe["output"]
        item = Item(
            id=out["id"], name=out["name"], glyph=out.get("glyph", "*"),
            kind=out.get("kind", "misc"), description=out.get("description", ""),
            heal=int(out.get("heal", 0)), hack_bonus=int(out.get("hack_bonus", 0)),
            attack_bonus=int(out.get("attack_bonus", 0)), defense_bonus=int(out.get("defense_bonus", 0)),
            consumable=bool(out.get("consumable", False)),
            equippable=bool(out.get("equippable", False)),
            extra=dict(out.get("extra") or {}),
        )
        agent.actor.inventory.append(item)
        agent.log("Crafted %s at Faraday bench." % item.name)
        agent.sfx("use")
        self._contract_progress(agent, "craft", 1)
        if item.extra.get("wish_origin"):
            agent.log("Wish→item pipeline: wish-origin lens online.")
        return True

    def _housing_action(self, agent, action: str, arg: str) -> bool:
        if action in ("house", "housing"):
            agent.housing["at_home"] = not agent.housing.get("at_home")
            state = "entered" if agent.housing["at_home"] else "left"
            agent.log("Safehouse %s. Stash size %d." % (state, len(agent.housing.get("stash", []))))
            return True
        parts = (arg or "").split()
        if action == "stash_put":
            try:
                idx = int(parts[0]) if parts else -1
            except ValueError:
                agent.log("Usage: stash_put <inv_idx>")
                return True
            inv = agent.actor.inventory
            if idx < 0 or idx >= len(inv) or inv[idx].quest:
                agent.log("Cannot stash that.")
                return True
            it = inv.pop(idx)
            agent.housing.setdefault("stash", []).append({
                "id": it.id, "name": it.name, "kind": it.kind, "glyph": it.glyph,
                "description": it.description,
            })
            agent.log("Stored %s in safehouse." % it.name)
            return True
        if action == "stash_take":
            try:
                idx = int(parts[0]) if parts else -1
            except ValueError:
                agent.log("Usage: stash_take <stash_idx>")
                return True
            stash = agent.housing.setdefault("stash", [])
            if idx < 0 or idx >= len(stash):
                agent.log("Bad stash index.")
                return True
            row = stash.pop(idx)
            item = _item_from_shop_id(row["id"]) or Item(
                id=row["id"], name=row["name"], kind=row.get("kind", "misc"),
                glyph=row.get("glyph", "*"), description=row.get("description", ""),
            )
            agent.actor.inventory.append(item)
            agent.log("Took %s from safehouse." % item.name)
            return True
        return False

    def _contract_progress(self, agent, kind: str, amount: int = 1) -> None:
        for c in agent.contracts:
            if c.get("status") != "active":
                continue
            if c.get("kind") != kind:
                continue
            c["progress"] = int(c.get("progress", 0)) + amount
            if c["progress"] >= int(c.get("goal", 1)):
                c["status"] = "ready"
                agent.log("Contract ready to turn in: %s" % c.get("name"))

    def _contract_action(self, agent, action: str, arg: str) -> bool:
        if action == "contract_list":
            # Ensure board
            have = {c["id"] for c in agent.contracts}
            for d in CONTRACT_DEFS:
                if d["id"] not in have:
                    row = dict(d)
                    row["progress"] = 0
                    row["status"] = "available"
                    agent.contracts.append(row)
            agent.log("Contracts: " + "; ".join("%s[%s]" % (c["id"], c.get("status")) for c in agent.contracts))
            return True
        if action == "contract_accept":
            cid = (arg or "").strip()
            c = next((x for x in agent.contracts if x["id"] == cid), None)
            if not c:
                self._contract_action(agent, "contract_list", "")
                c = next((x for x in agent.contracts if x["id"] == cid), None)
            if not c:
                agent.log("Unknown contract.")
                return True
            c["status"] = "active"
            agent.log("Accepted contract: %s" % c["name"])
            return True
        if action == "contract_turnin":
            cid = (arg or "").strip()
            c = next((x for x in agent.contracts if x["id"] == cid), None)
            if not c or c.get("status") != "ready":
                agent.log("Nothing to turn in.")
                return True
            agent.credits += int(c.get("reward_credits", 0))
            agent.reputation += int(c.get("reward_rep", 0))
            c["status"] = "done"
            agent.log("Turned in %s (+%d cr, +%d rep)." % (c["name"], c.get("reward_credits", 0), c.get("reward_rep", 0)))
            self._grant_season_xp(agent, 10)
            return True
        return False

    def _pvp_action(self, agent, action: str, arg: str) -> bool:
        if action == "pvp_optin":
            agent.pvp["opt_in"] = True
            agent.pvp["streets_pvp"] = False
            agent.log("PvP opt-in — streets still PvP-off. Use pvp_arena enter.")
            return True
        if action == "pvp_optout":
            agent.pvp["opt_in"] = False
            agent.pvp["arena"] = None
            agent.log("PvP opted out.")
            return True
        if action == "pvp_arena":
            op = (arg or "enter").strip()
            if op == "leave":
                agent.pvp["arena"] = None
                agent.log("Left arena.")
                return True
            if not agent.pvp.get("opt_in"):
                agent.log("Opt in first (pvp_optin).")
                return True
            agent.pvp["arena"] = "arena_1"
            agent.log("Entered opt-in arena_1 (PvP on here only).")
            return True
        return False

    def _mod_action(self, agent, action: str, arg: str) -> bool:
        target = (arg or "").strip()
        if action == "mute":
            agent.muted.add(target.lower())
            agent.log("Muted %s." % target)
            return True
        if action == "unmute":
            agent.muted.discard(target.lower())
            agent.log("Unmuted %s." % target)
            return True
        if action == "report":
            agent.reports_filed += 1
            self._analytics("report", agent, target=target)
            agent.log("Report filed on %s (stub logged)." % (target or "unknown"))
            return True
        if action == "kick":
            # Channel kick from current channel (stub moderation)
            ch = agent.irc_channel or "#streets"
            if ch == "#streets":
                agent.log("Cannot kick from #streets in stub.")
                return True
            kicked = self.channel_kicks.setdefault(ch, set())
            kicked.add(target.lower())
            tid = self.name_index.get(target.lower())
            other = self.players.get(tid) if tid else None
            if other and ch in other.irc_channels:
                other.irc_channels = [c for c in other.irc_channels if c != ch]
                if other.irc_channel == ch:
                    other.irc_channel = "#streets"
                other.log("Kicked from %s by %s." % (ch, agent.name))
            agent.log("Kicked %s from %s." % (target, ch))
            return True
        return False

    def _spectate_action(self, agent, action: str, arg: str) -> bool:
        if action == "spectate":
            name = (arg or "").strip()
            tid = self.name_index.get(name.lower())
            other = self.players.get(tid) if tid else None
            if not other:
                agent.log("No such player.")
                return True
            agent.spectating = other.id
            agent.mode = "spectate"
            agent.log("Spectating %s." % other.name)
            return True
        if action == "unspectate":
            agent.spectating = None
            agent.mode = "play"
            agent.log("Left spectate.")
            return True
        if action == "replay_dump":
            agent.log("Replay buffer entries: %d (GET /api/replay)." % len(self.replay_buffer))
            return True
        return False

    def _raid_action(self, agent, action: str, arg: str) -> bool:
        if action == "raid_leave":
            if agent.raid_id and agent.raid_id in self.raid_instances:
                inst = self.raid_instances[agent.raid_id]
                inst["members"] = [m for m in inst["members"] if m != agent.id]
            agent.raid_id = None
            agent.log("Left raid instance.")
            return True
        # start
        if time.time() < float(agent.raid_lockout_until or 0):
            agent.log("Raid lockout active.")
            return True
        rid = uuid.uuid4().hex[:8]
        # Pull party members if any
        members = [agent.id]
        if agent.party_id and agent.party_id in self.parties:
            members = list(self.parties[agent.party_id]["members"])[:5]
        if len(members) < 1:
            members = [agent.id]
        self.raid_instances[rid] = {
            "id": rid, "members": members, "boss_hp": 100,
            "started": time.time(), "lockout_sec": 300,
        }
        for mid in members:
            m = self.players.get(mid)
            if m:
                m.raid_id = rid
                m.log("Raid instance %s started (3–5p stub). raid_leave to exit." % rid)
        agent.log("Raid lockout will apply on clear/fail.")
        return True

    def year_snapshot_fields(self, agent) -> Dict[str, Any]:
        self._year_bootstrap_agent(agent)
        self._sync_loadout_from_inventory(agent)
        self._year_update_journal(agent)
        z = int(getattr(agent.actor, "z", 0) or 0)
        district = self._district_at(agent.actor.x, agent.actor.y, z)
        shop = self._shop_snapshot(agent)
        party = None
        if agent.party_id and agent.party_id in self.parties:
            p = self.parties[agent.party_id]
            party = {
                "id": p["id"],
                "members": [
                    self.players[m].name for m in p["members"] if m in self.players
                ],
                "ping": p.get("ping"),
                "channel": p.get("channel"),
                "invites": list(agent.party_invites),
            }
        crew = None
        if agent.crew_id and agent.crew_id in self.crews:
            c = self.crews[agent.crew_id]
            crew = {
                "id": c["id"], "name": c["name"], "channel": c["channel"],
                "members": [self.players[m].name for m in c["members"] if m in self.players],
                "stash": list(c.get("stash", [])),
            }
        boss_snap = None
        for a in self.npcs_enemies:
            if getattr(a, "boss", False) and a.alive:
                if abs(a.x - agent.actor.x) + abs(a.y - agent.actor.y) <= 14:
                    boss_snap = {
                        "name": a.name, "x": a.x, "y": a.y, "hp": a.hp, "max_hp": a.max_hp,
                        "telegraph": getattr(a, "telegraph", "idle"),
                        "unique_drop": getattr(a, "unique_drop", None),
                    }
                    break
        craft = {
            "bench": "faraday",
            "recipes": [
                {"id": r["id"], "name": r["name"], "inputs": r.get("inputs", {})}
                for r in self.recipe_defs.get("recipes", [])
            ],
        }
        # Filter chat mute client-side hint
        return {
            "skills": dict(agent.skills),
            "loadout": dict(agent.loadout),
            "skill_picks_available": int(agent.skill_picks_available),
            "shop": shop,
            "events": self.event_ticker[-12:],
            "party": party,
            "dead": bool(agent.dead or agent.mode == "dead"),
            "respawn_options": list(agent.respawn_options),
            "kill_feed": self.kill_feed[-10:],
            "journal": dict(agent.journal),
            "district": {
                "id": district.get("id"),
                "name": district.get("name"),
                "label": district.get("label"),
            },
            "boss": boss_snap,
            "craft": craft,
            "housing": {
                "room_id": agent.housing.get("room_id"),
                "at_home": bool(agent.housing.get("at_home")),
                "stash": list(agent.housing.get("stash", [])),
            },
            "weather": dict(self.weather_state),
            "tod": self._tod(),
            "crew": crew,
            "contracts": list(agent.contracts),
            "reputation": int(agent.reputation),
            "pvp": dict(agent.pvp),
            "season": dict(agent.season),
            "spectating": agent.spectating,
            "auth_nick": agent.auth_nick,
            "raid": (
                {"id": agent.raid_id, **{k: v for k, v in self.raid_instances.get(agent.raid_id, {}).items() if k != "members"}}
                if agent.raid_id else None
            ),
            "economy": {
                "bandwidth_debt": agent.bandwidth_debt,
                "repair_needed": agent.repair_needed,
                "sinks": ["repair", "bandwidth", "district_tax"],
            },
            "aoi_radius": 28,
        }

    def year_on_kill(self, agent, victim: Actor) -> None:
        self._year_bootstrap_agent(agent)
        if "thug" in (victim.name or "").lower() or victim.glyph == C.ENEMY_THUG:
            self._contract_progress(agent, "kills_thug", 1)
        self._grant_season_xp(agent, 2)
        # Boss unique drop
        if getattr(victim, "boss", False):
            drop = Item(
                id=getattr(victim, "unique_drop", "baron_core") or "baron_core",
                name="Baron Signal Core",
                glyph="%",
                kind="misc",
                description="Unique boss drop — wish-adjacent artifact.",
                extra={"boss_drop": True, "wish_origin": False},
            )
            agent.actor.inventory.append(drop)
            agent.credits += 50
            agent.log("Unique drop: %s" % drop.name)
            for b in self.bosses:
                if b.get("name") == victim.name:
                    b["alive"] = False
            agent.raid_lockout_until = time.time() + 300

    def year_on_payload(self, agent) -> None:
        self._contract_progress(agent, "got_payload", 1)
        self._year_update_journal(agent)
        self._analytics("payload", agent)

    def year_on_uplink(self, agent) -> None:
        self._contract_progress(agent, "payload_cleared", 1)
        self._year_update_journal(agent)
        self._analytics("uplink", agent)
        if agent.raid_id and agent.raid_id in self.raid_instances:
            agent.raid_lockout_until = time.time() + 300
