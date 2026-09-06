"""Corp patrol pressure vs courier crews (#50).

Heat rises with kills and Signal Keys. Named franchise patrols hunt hot
couriers; crews can contest. Safehouse sheds heat; crew members shed faster.
Original Metaverse prose only.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .. import constants as C
from ..entities import Actor

HEAT_MAX = 100
HEAT_PER_KILL = 8
HEAT_PER_KEY = 15
HEAT_PER_PATROL_KILL = -12  # shed when flatlining a patrol unit
HEAT_CONTEST_BONUS_SHED = -8  # extra shed for hunted courier when crew contests kill
HEAT_NATURAL_DECAY = 0.12  # per year_tick while alive on street
HEAT_SAFEHOUSE_SHED = 1.2  # per tick at_home
HEAT_CREW_SAFEHOUSE_BONUS = 1.3  # extra per tick at_home + in crew
HEAT_SPAWN_THRESHOLD = 55
HEAT_DESPAWN_THRESHOLD = 22
HEAT_COOLDOWN_TICKS = 80  # after patrol clears, wait before re-hunt

PATROL_UNIT_COUNT = 3
PATROL_SPAWN_RADIUS = 8

CORP_ROSTER = (
    {
        "id": "franchise_theta",
        "name": "Franchise Enforcement · Theta",
        "short": "Theta",
        "line": "Franchise Enforcement Theta locks your courier sigil — compliance vans ghost the block.",
    },
    {
        "id": "burb_compliance",
        "name": "Burbclave Compliance Patrol",
        "short": "Burbclave",
        "line": "Burbclave Compliance rolls out — branded batons and soft-serve warrants.",
    },
    {
        "id": "rim_wardens",
        "name": "Rim Wardens · Cable Baron",
        "short": "Rim Wardens",
        "line": "Cable Baron Rim Wardens ping your heat — Faraday cages hitch to street drones.",
    },
    {
        "id": "neon_recovery",
        "name": "Neon Grid Asset Recovery",
        "short": "Asset Recovery",
        "line": "Neon Grid Asset Recovery paints your trail — sleeve-snatchers in chrome jackets.",
    },
    {
        "id": "streetnet_audit",
        "name": "StreetNet Audit Squad",
        "short": "Audit Squad",
        "line": "StreetNet Audit Squad opens a heat case — your kill/key ledger is exhibit A.",
    },
)


def _heat_tier(value: float) -> str:
    v = float(value)
    if v >= 80:
        return "burning"
    if v >= HEAT_SPAWN_THRESHOLD:
        return "hot"
    if v >= 30:
        return "warm"
    return "cool"


class CorpPatrolMixin:
    """Mixed into YearFeaturesMixin / GameWorld."""

    def _corp_patrol_init(self) -> None:
        self.corp_patrols: Dict[str, Dict[str, Any]] = {}
        # agent_id -> tick when another patrol may spawn
        self._corp_patrol_cooldown_until: Dict[str, int] = {}

    def _corp_patrol_bootstrap_agent(self, agent) -> None:
        if not isinstance(getattr(agent, "heat", None), (int, float)):
            agent.heat = 0.0
        else:
            agent.heat = float(agent.heat)
        if not isinstance(getattr(agent, "corp_patrol_id", None), str):
            agent.corp_patrol_id = None

    def _clamp_heat(self, agent) -> float:
        self._corp_patrol_bootstrap_agent(agent)
        agent.heat = max(0.0, min(float(HEAT_MAX), float(agent.heat)))
        return agent.heat

    def _add_heat(self, agent, amount: float, reason: str = "") -> float:
        self._corp_patrol_bootstrap_agent(agent)
        before = float(agent.heat)
        agent.heat = before + float(amount)
        self._clamp_heat(agent)
        delta = agent.heat - before
        if abs(delta) >= 0.5 and reason:
            if delta > 0:
                agent.log(
                    "Heat %s → %d/%d (%s)."
                    % (reason, int(round(agent.heat)), HEAT_MAX, _heat_tier(agent.heat))
                )
            else:
                agent.log(
                    "Heat sheds %s → %d/%d (%s)."
                    % (reason, int(round(agent.heat)), HEAT_MAX, _heat_tier(agent.heat))
                )
        # Opportunistic spawn check after heat rises
        if delta > 0:
            self._corp_patrol_maybe_spawn(agent)
        return agent.heat

    def _heat_on_kill(self, agent, victim: Actor) -> None:
        """Called from year_on_kill — patrol unit kills shed; other kills raise heat."""
        if getattr(victim, "corp_patrol", False):
            self._corp_patrol_on_unit_killed(agent, victim)
            return
        self._add_heat(agent, HEAT_PER_KILL, "from street kill")

    def _heat_on_signal_key(self, agent) -> None:
        self._add_heat(agent, HEAT_PER_KEY, "from Signal Key sleeve")

    def _shed_rate_for(self, agent) -> float:
        """Positive = heat lost per tick."""
        self._corp_patrol_bootstrap_agent(agent)
        rate = float(HEAT_NATURAL_DECAY)
        at_home = bool((getattr(agent, "housing", None) or {}).get("at_home"))
        in_crew = bool(getattr(agent, "crew_id", None))
        if at_home:
            rate += float(HEAT_SAFEHOUSE_SHED)
            if in_crew:
                rate += float(HEAT_CREW_SAFEHOUSE_BONUS)
        return rate

    def _tick_corp_patrol(self) -> None:
        """Decay heat, shed in safehouse, spawn/despawn patrols, prune dead units."""
        # Per-courier heat shed
        for p in list(getattr(self, "players", {}).values()):
            if not getattr(p, "connected", False):
                continue
            if not getattr(getattr(p, "actor", None), "alive", False):
                continue
            self._corp_patrol_bootstrap_agent(p)
            rate = self._shed_rate_for(p)
            if rate > 0 and float(p.heat) > 0:
                p.heat = max(0.0, float(p.heat) - rate)
            # Spawn if still hot
            self._corp_patrol_maybe_spawn(p)
            # Despawn if cooled
            self._corp_patrol_maybe_despawn(p)

        # Prune patrol records whose units are all dead
        dead_ids = []
        for pid, patrol in list(self.corp_patrols.items()):
            alive = 0
            for a in list(getattr(self, "npcs_enemies", []) or []):
                if getattr(a, "corp_patrol_id", None) == pid and a.alive:
                    alive += 1
            patrol["units_alive"] = alive
            if alive <= 0:
                dead_ids.append(pid)
        for pid in dead_ids:
            self._corp_patrol_clear(pid, reason="wiped")

    def _corp_patrol_maybe_spawn(self, agent) -> bool:
        self._corp_patrol_bootstrap_agent(agent)
        if float(agent.heat) < HEAT_SPAWN_THRESHOLD:
            return False
        if getattr(agent, "corp_patrol_id", None):
            return False
        # Already hunted?
        for patrol in self.corp_patrols.values():
            if patrol.get("target_id") == agent.id and int(patrol.get("units_alive", 0)) > 0:
                agent.corp_patrol_id = patrol["id"]
                return False
        cool_until = int(self._corp_patrol_cooldown_until.get(agent.id, 0) or 0)
        if self.tick < cool_until:
            return False
        if not getattr(agent, "actor", None) or not agent.actor.alive:
            return False
        if int(getattr(agent.actor, "z", 0) or 0) != C.PLANE_STREET:
            return False
        return self._corp_patrol_spawn(agent)

    def _pick_corp(self) -> Dict[str, str]:
        rng = getattr(self, "rng", None)
        if rng is not None:
            return dict(rng.choice(CORP_ROSTER))
        return dict(CORP_ROSTER[0])

    def _corp_patrol_spawn(self, agent) -> bool:
        ax, ay = agent.actor.x, agent.actor.y
        positions: List[Tuple[int, int]] = []
        gmap = self.gmap
        rng = getattr(self, "rng", None)
        r = PATROL_SPAWN_RADIUS
        occupied = {
            (e.x, e.y)
            for e in getattr(self, "npcs_enemies", [])
            if getattr(e, "alive", False)
        }
        for _ in range(100):
            if rng is not None:
                x = rng.randint(max(1, ax - r), min(gmap.width - 2, ax + r))
                y = rng.randint(max(1, ay - r), min(gmap.height - 2, ay + r))
            else:
                x = ax + 4 + len(positions)
                y = ay + 3
            if abs(x - ax) + abs(y - ay) < 3:
                continue
            if (x, y) in occupied:
                continue
            if not gmap.in_bounds(x, y) or not gmap.walkable(x, y):
                continue
            if hasattr(self, "_near_any_spawn") and self._near_any_spawn(x, y):
                continue
            can = getattr(self, "_can_stand", None)
            if callable(can) and not can(x, y, z=C.PLANE_STREET):
                continue
            occupied.add((x, y))
            positions.append((x, y))
            if len(positions) >= PATROL_UNIT_COUNT:
                break
        if len(positions) < 1:
            return False

        corp = self._pick_corp()
        pid = uuid.uuid4().hex[:8]
        units = []
        for i, (x, y) in enumerate(positions):
            unit = Actor(
                x=x,
                y=y,
                name="%s · Unit %d" % (corp["short"], i + 1),
                glyph="C",
                hp=14,
                max_hp=14,
                attack=5,
                defense=2,
                ai="chase",
                faction="enemy",
                xp_value=12,
                color="red",
            )
            unit.z = C.PLANE_STREET
            setattr(unit, "corp_patrol", True)
            setattr(unit, "corp_patrol_id", pid)
            setattr(unit, "hunt_agent_id", agent.id)
            setattr(unit, "corp_name", corp["name"])
            self.npcs_enemies.append(unit)
            units.append({"name": unit.name, "x": x, "y": y})

        patrol = {
            "id": pid,
            "corp_id": corp["id"],
            "corp_name": corp["name"],
            "corp_short": corp["short"],
            "target_id": agent.id,
            "target_name": getattr(agent, "name", "Courier"),
            "units_alive": len(units),
            "unit_count": len(units),
            "spawned_tick": self.tick,
            "spawned_at": time.time(),
            "contested": False,
            "contest_crew_id": None,
            "contest_crew_name": None,
            "units": units,
        }
        self.corp_patrols[pid] = patrol
        agent.corp_patrol_id = pid

        msg = corp["line"]
        self._push_event(
            "corp_patrol",
            "%s hunts %s (heat %d)."
            % (corp["name"], getattr(agent, "name", "courier"), int(round(agent.heat))),
            phase="spawn",
            corp=corp["name"],
            target=getattr(agent, "name", None),
            patrol_id=pid,
            heat=int(round(agent.heat)),
        )
        if hasattr(self, "system_chat"):
            self.system_chat(
                "Corp patrol: %s hunting %s."
                % (corp["short"], getattr(agent, "name", "courier"))
            )
        agent.log(msg)
        agent.log(
            "Heat %d — %s on your six. Flatline them or cool in a safehouse. contest_patrol with crew."
            % (int(round(agent.heat)), corp["name"])
        )
        agent.sfx("pulse")
        return True

    def _corp_patrol_maybe_despawn(self, agent) -> None:
        self._corp_patrol_bootstrap_agent(agent)
        pid = getattr(agent, "corp_patrol_id", None)
        if not pid or pid not in self.corp_patrols:
            return
        if float(agent.heat) > HEAT_DESPAWN_THRESHOLD:
            return
        # Only despawn if heat cooled — units peel off
        patrol = self.corp_patrols[pid]
        if patrol.get("target_id") != agent.id:
            return
        self._corp_patrol_clear(pid, reason="cooled")
        agent.log(
            "%s peels off — heat cooled to %d. StreetNet drops the warrant for now."
            % (patrol.get("corp_short") or "Patrol", int(round(agent.heat)))
        )

    def _corp_patrol_clear(self, pid: str, reason: str = "clear") -> None:
        patrol = self.corp_patrols.pop(pid, None)
        if not patrol:
            return
        # Remove living units from world
        survivors = []
        for a in list(getattr(self, "npcs_enemies", []) or []):
            if getattr(a, "corp_patrol_id", None) == pid:
                a.alive = False
                a.hp = 0
            else:
                survivors.append(a)
        # Keep other enemies; dead patrol corpses can stay as dead actors like normal kills
        # (don't remove from list — combat already marks dead; filter optional)
        tid = patrol.get("target_id")
        if tid and tid in getattr(self, "players", {}):
            p = self.players[tid]
            if getattr(p, "corp_patrol_id", None) == pid:
                p.corp_patrol_id = None
            self._corp_patrol_cooldown_until[tid] = self.tick + HEAT_COOLDOWN_TICKS
        self._push_event(
            "corp_patrol",
            "%s patrol %s (%s)."
            % (patrol.get("corp_name") or "Corp", reason, patrol.get("target_name") or "?"),
            phase="end",
            reason=reason,
            corp=patrol.get("corp_name"),
            patrol_id=pid,
        )

    def _corp_patrol_on_unit_killed(self, agent, victim: Actor) -> None:
        pid = getattr(victim, "corp_patrol_id", None)
        if not pid or pid not in self.corp_patrols:
            self._add_heat(agent, HEAT_PER_PATROL_KILL, "corp unit down")
            return
        patrol = self.corp_patrols[pid]
        # Count remaining
        alive = sum(
            1
            for a in getattr(self, "npcs_enemies", [])
            if getattr(a, "corp_patrol_id", None) == pid and a.alive
        )
        patrol["units_alive"] = alive

        shed = float(HEAT_PER_PATROL_KILL)
        contested = bool(patrol.get("contested"))
        crew_id = getattr(agent, "crew_id", None)
        if contested and crew_id and crew_id == patrol.get("contest_crew_id"):
            shed += float(HEAT_CONTEST_BONUS_SHED)
            agent.log("Crew contest bonus — extra heat shed.")

        # Apply shed to hunted courier (and killer if different)
        target_id = patrol.get("target_id")
        hunted = self.players.get(target_id) if target_id else None
        if hunted is not None:
            self._add_heat(hunted, shed, "corp unit flatlined")
        if agent is not hunted:
            self._add_heat(agent, max(-6.0, shed * 0.5), "helped drop corp unit")

        agent.log(
            "Corp unit down — %s (%d/%d left)."
            % (patrol.get("corp_short") or "patrol", alive, int(patrol.get("unit_count") or PATROL_UNIT_COUNT))
        )
        if alive <= 0:
            if hunted is not None:
                hunted.log(
                    "You broke %s — warrant shreds. Heat %d."
                    % (patrol.get("corp_name") or "the patrol", int(round(float(hunted.heat))))
                )
                if contested and hunted.crew_id:
                    hunted.credits = int(getattr(hunted, "credits", 0) or 0) + 15
                    hunted.log("Crew contest payout +15 credits.")
            self._corp_patrol_clear(pid, reason="wiped")

    def _corp_patrol_prefer_target(self, enemy: Actor, vulnerable: list):
        """If this is a corp hunter, prefer the heat target when still aggro-ok."""
        hunt_id = getattr(enemy, "hunt_agent_id", None)
        if not hunt_id:
            return None
        for p in vulnerable:
            if getattr(p, "id", None) == hunt_id:
                return p
        return None

    def _contest_patrol(self, agent) -> bool:
        """Crew marks an active nearby/hunted patrol as contested."""
        self._corp_patrol_bootstrap_agent(agent)
        crew_id = getattr(agent, "crew_id", None)
        if not crew_id or crew_id not in getattr(self, "crews", {}):
            agent.log("Contest needs a crew — crew_create / crew_join first.")
            return True
        crew = self.crews[crew_id]
        patrol = None
        # Prefer own hunt, else nearest active patrol
        pid = getattr(agent, "corp_patrol_id", None)
        if pid and pid in self.corp_patrols:
            patrol = self.corp_patrols[pid]
        if patrol is None:
            # Find patrol hunting a crewmate, or any nearby
            for p in self.corp_patrols.values():
                if int(p.get("units_alive", 0) or 0) <= 0:
                    continue
                tid = p.get("target_id")
                if tid in (crew.get("members") or []):
                    patrol = p
                    break
            if patrol is None and self.corp_patrols:
                # nearest by target position
                best = None
                best_d = 9999
                for p in self.corp_patrols.values():
                    if int(p.get("units_alive", 0) or 0) <= 0:
                        continue
                    t = self.players.get(p.get("target_id"))
                    if not t or not getattr(t, "actor", None):
                        continue
                    d = abs(t.actor.x - agent.actor.x) + abs(t.actor.y - agent.actor.y)
                    if d < best_d:
                        best_d = d
                        best = p
                if best is not None and best_d <= 20:
                    patrol = best
        if patrol is None:
            agent.log("No corp patrol to contest — raise heat or find a hunted crewmate.")
            return True
        if patrol.get("contested") and patrol.get("contest_crew_id") == crew_id:
            agent.log("Crew already contesting %s." % patrol.get("corp_name"))
            return True
        patrol["contested"] = True
        patrol["contest_crew_id"] = crew_id
        patrol["contest_crew_name"] = crew.get("name")
        msg = (
            "Crew %s contests %s — flatline their units to shred the warrant."
            % (crew.get("name"), patrol.get("corp_name"))
        )
        agent.log(msg)
        self._push_event(
            "corp_patrol",
            msg,
            phase="contest",
            corp=patrol.get("corp_name"),
            crew=crew.get("name"),
            patrol_id=patrol.get("id"),
        )
        # Notify crew
        for mid in crew.get("members") or []:
            m = self.players.get(mid)
            if m and m is not agent and getattr(m, "connected", False):
                m.log(msg)
        ch = crew.get("channel")
        if ch and hasattr(self, "channel_chat"):
            # soft notice via system if available
            if hasattr(self, "system_chat"):
                self.system_chat("Crew contest: %s vs %s" % (crew.get("name"), patrol.get("corp_short")))
        return True

    def _corp_patrol_snapshot(self, agent) -> Dict[str, Any]:
        self._corp_patrol_bootstrap_agent(agent)
        heat = self._clamp_heat(agent)
        at_home = bool((getattr(agent, "housing", None) or {}).get("at_home"))
        in_crew = bool(getattr(agent, "crew_id", None))
        shed = self._shed_rate_for(agent)
        pid = getattr(agent, "corp_patrol_id", None)
        patrol = self.corp_patrols.get(pid) if pid else None
        # Also surface if agent is contesting / near another hunt
        if patrol is None:
            for p in self.corp_patrols.values():
                if int(p.get("units_alive", 0) or 0) <= 0:
                    continue
                if p.get("contest_crew_id") and p.get("contest_crew_id") == getattr(agent, "crew_id", None):
                    patrol = p
                    break
        patrol_snap = None
        if patrol and int(patrol.get("units_alive", 0) or 0) > 0:
            # Live unit positions
            units = []
            for a in getattr(self, "npcs_enemies", []) or []:
                if getattr(a, "corp_patrol_id", None) == patrol["id"] and a.alive:
                    units.append({"name": a.name, "x": a.x, "y": a.y, "hp": a.hp, "max_hp": a.max_hp})
            patrol_snap = {
                "id": patrol["id"],
                "corp_name": patrol.get("corp_name"),
                "corp_short": patrol.get("corp_short"),
                "target_id": patrol.get("target_id"),
                "target_name": patrol.get("target_name"),
                "hunting_you": patrol.get("target_id") == agent.id,
                "units_alive": len(units),
                "unit_count": int(patrol.get("unit_count") or len(units)),
                "units": units,
                "contested": bool(patrol.get("contested")),
                "contest_crew_name": patrol.get("contest_crew_name"),
            }
        return {
            "value": int(round(heat)),
            "max": HEAT_MAX,
            "tier": _heat_tier(heat),
            "spawn_threshold": HEAT_SPAWN_THRESHOLD,
            "despawn_threshold": HEAT_DESPAWN_THRESHOLD,
            "in_safehouse": at_home,
            "crew_shed_bonus": bool(at_home and in_crew),
            "shed_per_tick": round(shed, 2),
            "patrol": patrol_snap,
            "active_patrols": len(
                [p for p in self.corp_patrols.values() if int(p.get("units_alive", 0) or 0) > 0]
            ),
        }

    def _corp_patrol_landmarks(self) -> List[Dict[str, Any]]:
        marks = []
        for a in getattr(self, "npcs_enemies", []) or []:
            if not a.alive or not getattr(a, "corp_patrol", False):
                continue
            marks.append(
                {
                    "id": "corp_%s" % getattr(a, "corp_patrol_id", "x"),
                    "name": getattr(a, "corp_name", None) or a.name,
                    "glyph": "C",
                    "x": a.x,
                    "y": a.y,
                    "z": int(getattr(a, "z", 0) or 0),
                }
            )
        return marks

    def _corp_patrol_action(self, agent, action: str, arg: str = "") -> bool:
        self._corp_patrol_bootstrap_agent(agent)
        a = (action or "").strip().lower()
        if a in ("heat", "heat_status", "corp_heat"):
            snap = self._corp_patrol_snapshot(agent)
            pat = snap.get("patrol")
            if pat:
                agent.log(
                    "Heat %d/%d (%s) · shed %.2f/tick%s · patrol %s (%d alive)%s"
                    % (
                        snap["value"],
                        snap["max"],
                        snap["tier"],
                        snap["shed_per_tick"],
                        " · crew safehouse bonus" if snap["crew_shed_bonus"] else (
                            " · safehouse" if snap["in_safehouse"] else ""
                        ),
                        pat.get("corp_short") or "?",
                        pat.get("units_alive") or 0,
                        " · CONTESTED" if pat.get("contested") else "",
                    )
                )
            else:
                agent.log(
                    "Heat %d/%d (%s) · shed %.2f/tick%s · no corp patrol"
                    % (
                        snap["value"],
                        snap["max"],
                        snap["tier"],
                        snap["shed_per_tick"],
                        " · crew safehouse bonus" if snap["crew_shed_bonus"] else (
                            " · safehouse" if snap["in_safehouse"] else ""
                        ),
                    )
                )
            return True
        if a in ("contest_patrol", "patrol_contest", "crew_contest"):
            return self._contest_patrol(agent)
        if a in ("corp_patrol", "patrol_status"):
            snap = self._corp_patrol_snapshot(agent)
            pat = snap.get("patrol")
            if not pat:
                agent.log(
                    "No active corp patrol on you. Heat %d — patrols spawn at %d+."
                    % (snap["value"], HEAT_SPAWN_THRESHOLD)
                )
            else:
                agent.log(
                    "%s hunting %s · %d/%d units · contested=%s"
                    % (
                        pat.get("corp_name"),
                        pat.get("target_name"),
                        pat.get("units_alive"),
                        pat.get("unit_count"),
                        "yes" if pat.get("contested") else "no",
                    )
                )
            return True
        if a in ("corp_patrol_force", "force_corp_patrol") and arg == "dev":
            # Dev: spike heat and force spawn
            agent.heat = float(HEAT_SPAWN_THRESHOLD + 10)
            self._corp_patrol_cooldown_until[agent.id] = 0
            if getattr(agent, "corp_patrol_id", None):
                self._corp_patrol_clear(agent.corp_patrol_id, reason="forced")
            ok = self._corp_patrol_spawn(agent)
            agent.log("Dev: corp patrol force %s (heat %d)." % ("ok" if ok else "fail", int(agent.heat)))
            return True
        return False
