"""Uplink Hop / Street Jaunt — learned short→district→globe hops (#62).

Skill ranks gate range. Underleveled attempts risk misfire + Focus burn.
Mechanics inspired by trained-teleport progression tropes; prose is
**original Metaverse fiction only** (no copyrighted names/quotes).
Ties to globe region teleports (#54) at rank 3.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from .. import constants as C

# Rank ladder (0 = untrained)
RANK_NAMES = {
    0: "Untrained",
    1: "Street Jaunt",
    2: "District Hop",
    3: "Globe Hop",
}

# XP thresholds to reach each rank (from previous)
RANK_XP = {1: 3, 2: 10, 3: 22}

# Max Manhattan range for short hops by rank (0 can attempt but misfires often)
SHORT_RANGE = {0: 4, 1: 6, 2: 8, 3: 10}

FOCUS_COST = {"short": 3, "district": 6, "globe": 8}
COOLDOWN_SEC = {"short": 4.0, "district": 12.0, "globe": 20.0}

# Base misfire when hop kind requires higher rank than owned
MISFIRE_UNDERLEVEL = {"short": 0.55, "district": 0.72, "globe": 0.85}
# Spice misfire even when ranked
MISFIRE_RANKED = {"short": 0.04, "district": 0.07, "globe": 0.10}

XP_GAIN = {"short": 1, "district": 3, "globe": 5}

SKILL_ID = "uplink_jaunte"
SKILL_NAME = "Uplink Jaunte"

# Minimum rank to attempt without counting as underleveled
MIN_RANK = {"short": 1, "district": 2, "globe": 3}


class JaunteMixin:
    """Mixed into YearFeaturesMixin / GameWorld."""

    def _jaunte_init(self) -> None:
        self._jaunte_ready = True
        self._push_event(
            "broadcast",
            "StreetNet uplink lattice online — train Street Jaunt hops (#62).",
        )

    def _jaunte_bootstrap_agent(self, agent) -> None:
        if not isinstance(getattr(agent, "jaunte", None), dict):
            agent.jaunte = {
                "rank": 0,
                "xp": 0,
                "hops": 0,
                "misfires": 0,
                "cooldown_until": 0.0,
                "panel_open": False,
                "last_feedback": None,
                "last_result": None,
            }
        else:
            j = agent.jaunte
            j.setdefault("rank", 0)
            j.setdefault("xp", 0)
            j.setdefault("hops", 0)
            j.setdefault("misfires", 0)
            j.setdefault("cooldown_until", 0.0)
            j.setdefault("panel_open", False)
            j.setdefault("last_feedback", None)
            j.setdefault("last_result", None)
        # Skill pick floor: owning uplink_jaunte grants at least rank 1
        skills = getattr(agent, "skills", None) or {}
        if SKILL_ID in skills:
            agent.jaunte["rank"] = max(int(agent.jaunte.get("rank") or 0), 1)
        agent.jaunte["rank"] = max(0, min(3, int(agent.jaunte.get("rank") or 0)))

    def _jaunte_on_skill_pick(self, agent) -> None:
        """Called after skill_pick learns uplink_jaunte."""
        self._jaunte_bootstrap_agent(agent)
        before = int(agent.jaunte.get("rank") or 0)
        agent.jaunte["rank"] = min(3, max(before + 1, 1))
        self._jaunte_feedback(
            agent,
            "success",
            "Uplink Jaunte etched — Street Jaunt rank %d (%s)."
            % (agent.jaunte["rank"], RANK_NAMES[agent.jaunte["rank"]]),
        )

    def _jaunte_feedback(self, agent, kind: str, text: str) -> None:
        agent.jaunte["last_feedback"] = {
            "kind": kind,
            "text": text,
            "t": time.time(),
        }
        agent.jaunte["last_result"] = kind
        agent.log(text)

    def _jaunte_rank(self, agent) -> int:
        self._jaunte_bootstrap_agent(agent)
        return int(agent.jaunte.get("rank") or 0)

    def _jaunte_gain_xp(self, agent, amount: int) -> None:
        j = agent.jaunte
        j["xp"] = int(j.get("xp") or 0) + max(0, int(amount))
        # Rank up while thresholds met
        while True:
            rank = int(j.get("rank") or 0)
            if rank >= 3:
                break
            need = RANK_XP.get(rank + 1, 9999)
            if int(j.get("xp") or 0) < need:
                break
            j["rank"] = rank + 1
            self._jaunte_feedback(
                agent,
                "rankup",
                "Uplink Hop rank up — now %s (rank %d). Range unlocked."
                % (RANK_NAMES[j["rank"]], j["rank"]),
            )

    def _jaunte_blocked_mode(self, agent) -> Optional[str]:
        mode = getattr(agent, "mode", "play")
        if mode in ("cyberspace", "heist", "flotilla", "dead", "won") or getattr(
            agent, "dead", False
        ):
            return mode or "down"
        return None

    def _jaunte_cooldown_left(self, agent) -> float:
        return max(0.0, float(agent.jaunte.get("cooldown_until") or 0) - time.time())

    def _jaunte_check_ready(self, agent, kind: str) -> bool:
        """Focus + cooldown gate. Logs + feedback on fail."""
        blocked = self._jaunte_blocked_mode(agent)
        if blocked:
            self._jaunte_feedback(
                agent,
                "blocked",
                "Cannot Street Jaunt while %s — jack out / finish first." % blocked,
            )
            return False
        left = self._jaunte_cooldown_left(agent)
        if left > 0.05:
            self._jaunte_feedback(
                agent,
                "cooldown",
                "Uplink cooldown — %.0fs before next hop." % (left + 0.5),
            )
            return False
        cost = int(FOCUS_COST.get(kind, 3))
        focus = int(getattr(agent.actor, "focus", 0) or 0)
        if focus < cost:
            self._jaunte_feedback(
                agent,
                "focus",
                "Need %d Focus for %s hop (have %d)." % (cost, kind, focus),
            )
            return False
        return True

    def _jaunte_spend(self, agent, kind: str) -> None:
        cost = int(FOCUS_COST.get(kind, 3))
        agent.actor.focus = max(0, int(agent.actor.focus) - cost)
        cd = float(COOLDOWN_SEC.get(kind, 4.0))
        # Underleveled attempts still burn a longer cooldown fragment
        rank = self._jaunte_rank(agent)
        need = MIN_RANK.get(kind, 1)
        if rank < need:
            cd = max(cd, cd * 1.25)
        agent.jaunte["cooldown_until"] = time.time() + cd

    def _jaunte_misfire_chance(self, agent, kind: str) -> float:
        rank = self._jaunte_rank(agent)
        need = MIN_RANK.get(kind, 1)
        if rank < need:
            base = float(MISFIRE_UNDERLEVEL.get(kind, 0.7))
            # Each missing rank worsens odds
            return min(0.95, base + 0.08 * (need - rank - 1))
        return float(MISFIRE_RANKED.get(kind, 0.05))

    def _jaunte_find_standable_near(
        self, x: int, y: int, z: int, agent, radius: int = 6
    ) -> Tuple[int, int]:
        if self._can_stand(x, y, ignore=agent.actor, z=z):
            return x, y
        for r in range(1, max(1, radius) + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if abs(dx) + abs(dy) != r:
                        continue
                    nx, ny = x + dx, y + dy
                    if self._can_stand(nx, ny, ignore=agent.actor, z=z):
                        return nx, ny
        # Fallback spawn
        if hasattr(self, "_find_spawn"):
            return self._find_spawn()
        return int(agent.actor.x), int(agent.actor.y)

    def _jaunte_do_misfire(self, agent, kind: str) -> bool:
        """Scatter nearby, burn focus/cooldown, toast feedback."""
        self._jaunte_spend(agent, kind)
        agent.jaunte["misfires"] = int(agent.jaunte.get("misfires") or 0) + 1
        z = int(getattr(agent.actor, "z", 0) or 0)
        ox, oy = int(agent.actor.x), int(agent.actor.y)
        # Scatter 2–7 tiles
        rng = getattr(self, "rng", None)
        import random as _random

        r = rng if rng is not None else _random
        best = (ox, oy)
        for _ in range(24):
            dx = r.randint(-7, 7)
            dy = r.randint(-7, 7)
            if abs(dx) + abs(dy) < 2:
                continue
            nx, ny = ox + dx, oy + dy
            if self._can_stand(nx, ny, ignore=agent.actor, z=z):
                best = (nx, ny)
                break
        else:
            best = self._jaunte_find_standable_near(ox + 3, oy + 2, z, agent)
        self._force_set_pos(agent, best[0], best[1], z, "jaunte misfire")
        if hasattr(self, "update_fov"):
            self.update_fov(agent)
        # Light slap — never lethal from misfire alone
        if hasattr(agent.actor, "take_damage") and r.random() < 0.35:
            try:
                agent.actor.take_damage(1)
            except Exception:
                agent.actor.hp = max(1, int(agent.actor.hp) - 1)
        self._jaunte_feedback(
            agent,
            "misfire",
            "Uplink misfire — lattice rejected the %s hop. Scattered (%d,%d)."
            % (kind, best[0], best[1]),
        )
        try:
            agent.sfx("hit")
        except Exception:
            pass
        return True

    def _jaunte_short(self, agent, arg: str = "") -> bool:
        self._jaunte_bootstrap_agent(agent)
        if not self._jaunte_check_ready(agent, "short"):
            return True
        chance = self._jaunte_misfire_chance(agent, "short")
        rng = getattr(self, "rng", None)
        roll = rng.random() if rng is not None else __import__("random").random()
        if roll < chance:
            return self._jaunte_do_misfire(agent, "short")

        rank = self._jaunte_rank(agent)
        max_r = int(SHORT_RANGE.get(rank, 4))
        # Direction: arg cardinal / relative, else facing forward
        dx, dy = self._jaunte_parse_dir(agent, arg)
        z = int(getattr(agent.actor, "z", 0) or 0)
        ox, oy = int(agent.actor.x), int(agent.actor.y)
        dest = (ox, oy)
        for step in range(1, max_r + 1):
            nx, ny = ox + dx * step, oy + dy * step
            if self._can_stand(nx, ny, ignore=agent.actor, z=z):
                dest = (nx, ny)
            else:
                # Soft stop: try one tile slide
                break
        if dest == (ox, oy):
            # No clear corridor — treat as soft misfire without full scatter
            self._jaunte_spend(agent, "short")
            self._jaunte_feedback(
                agent,
                "blocked",
                "Street Jaunt failed — no clear uplink corridor that way.",
            )
            return True

        self._jaunte_spend(agent, "short")
        self._force_set_pos(agent, dest[0], dest[1], z, "jaunte short")
        if hasattr(self, "update_fov"):
            self.update_fov(agent)
        agent.jaunte["hops"] = int(agent.jaunte.get("hops") or 0) + 1
        self._jaunte_gain_xp(agent, XP_GAIN["short"])
        dist = abs(dest[0] - ox) + abs(dest[1] - oy)
        self._jaunte_feedback(
            agent,
            "success",
            "Street Jaunt locked — hopped %d tiles (rank %d · −%d Focus)."
            % (dist, rank, FOCUS_COST["short"]),
        )
        try:
            agent.sfx("uplink")
        except Exception:
            pass
        return True

    def _jaunte_parse_dir(self, agent, arg: str) -> Tuple[int, int]:
        a = (arg or "").strip().lower()
        # Strip leading "short"
        if a.startswith("short"):
            a = a[5:].strip()
        dirs = {
            "n": (0, -1), "north": (0, -1), "up": (0, -1),
            "s": (0, 1), "south": (0, 1), "down": (0, 1),
            "e": (1, 0), "east": (1, 0), "right": (1, 0),
            "w": (-1, 0), "west": (-1, 0), "left": (-1, 0),
            "ne": (1, -1), "nw": (-1, -1), "se": (1, 1), "sw": (-1, 1),
            "f": None, "fwd": None, "forward": None,
        }
        if a in dirs and dirs[a] is not None:
            return dirs[a]  # type: ignore[return-value]
        facing = int(getattr(agent.actor, "facing", 0) or 0) % 4
        return C.FACING_DIRS[facing]

    def _jaunte_district_center(self, district: Dict[str, Any]) -> Tuple[int, int]:
        w, h = max(1, self.gmap.width), max(1, self.gmap.height)
        cx = int(((float(district.get("x0", 0)) + float(district.get("x1", 1))) / 2.0) * w)
        cy = int(((float(district.get("y0", 0)) + float(district.get("y1", 1))) / 2.0) * h)
        return cx, cy

    def _jaunte_district(self, agent, arg: str = "") -> bool:
        self._jaunte_bootstrap_agent(agent)
        if not self._jaunte_check_ready(agent, "district"):
            return True
        chance = self._jaunte_misfire_chance(agent, "district")
        rng = getattr(self, "rng", None)
        roll = rng.random() if rng is not None else __import__("random").random()
        if roll < chance:
            return self._jaunte_do_misfire(agent, "district")

        # Resolve target district
        raw = (arg or "").strip().lower()
        if raw.startswith("district"):
            raw = raw[8:].strip()
        districts = list(getattr(self, "district_defs", {}).get("districts", []) or [])
        target = None
        if raw:
            for d in districts:
                if d.get("id") == raw or (d.get("name") or "").lower() == raw:
                    target = d
                    break
        if target is None:
            # Hop to a different district than current
            cur = self._district_at(
                agent.actor.x, agent.actor.y, int(getattr(agent.actor, "z", 0) or 0)
            )
            cur_id = cur.get("id")
            others = [d for d in districts if d.get("id") != cur_id]
            if not others:
                others = districts
            rng2 = rng if rng is not None else __import__("random")
            target = others[int(rng2.random() * len(others)) % len(others)]

        z = C.PLANE_STREET
        if target.get("plane") == -1 or target.get("id") == "undercity":
            z = C.PLANE_UNDER
        cx, cy = self._jaunte_district_center(target)
        dest = self._jaunte_find_standable_near(cx, cy, z, agent, radius=10)

        self._jaunte_spend(agent, "district")
        self._force_set_pos(agent, dest[0], dest[1], z, "jaunte district")
        if hasattr(self, "update_fov"):
            self.update_fov(agent)
        if hasattr(self, "_grant_spawn_invuln"):
            self._grant_spawn_invuln(agent)
        agent.jaunte["hops"] = int(agent.jaunte.get("hops") or 0) + 1
        self._jaunte_gain_xp(agent, XP_GAIN["district"])
        name = target.get("name") or target.get("id") or "district"
        self._jaunte_feedback(
            agent,
            "success",
            "District Hop complete — sleeved into %s (−%d Focus)."
            % (name, FOCUS_COST["district"]),
        )
        try:
            agent.sfx("uplink")
        except Exception:
            pass
        return True

    def _jaunte_globe(self, agent, arg: str = "") -> bool:
        """Rank-3 globe hop via existing globe teleport; underleveled = misfire risk."""
        self._jaunte_bootstrap_agent(agent)
        raw = (arg or "").strip().lower()
        if raw.startswith("globe"):
            raw = raw[5:].strip()
        if not raw:
            agent.jaunte["panel_open"] = True
            self._jaunte_feedback(
                agent,
                "hint",
                "Usage: jaunte globe <region_id> (needs rank 3 · e.g. neo_tokyo).",
            )
            return True
        if not self._jaunte_check_ready(agent, "globe"):
            return True
        chance = self._jaunte_misfire_chance(agent, "globe")
        rng = getattr(self, "rng", None)
        roll = rng.random() if rng is not None else __import__("random").random()
        if roll < chance:
            return self._jaunte_do_misfire(agent, "globe")

        # Spend Focus; globe teleport handles credits + its own cooldown
        self._jaunte_spend(agent, "globe")
        if not hasattr(self, "_globe_teleport"):
            self._jaunte_feedback(
                agent, "blocked", "Globe layer offline — cannot complete globe hop."
            )
            return True
        # force=False so credits/cooldown still apply on globe side
        ok = self._globe_teleport(agent, raw, force=False)
        # If globe rejected (unknown region / credits), refund is too late — leave feedback
        agent.jaunte["hops"] = int(agent.jaunte.get("hops") or 0) + 1
        self._jaunte_gain_xp(agent, XP_GAIN["globe"])
        # Prefer globe's own log; add jaunte toast
        rank = self._jaunte_rank(agent)
        self._jaunte_feedback(
            agent,
            "success",
            "Globe Hop channel opened (rank %d) — see uplink log for region pad."
            % rank,
        )
        return bool(ok) if ok is not None else True

    def _jaunte_train(self, agent) -> bool:
        """Spend a skill pick to raise jaunte rank by 1."""
        self._jaunte_bootstrap_agent(agent)
        picks = int(getattr(agent, "skill_picks_available", 0) or 0)
        if picks <= 0:
            self._jaunte_feedback(
                agent,
                "blocked",
                "No skill picks — level up or use skill_pick uplink_jaunte.",
            )
            return True
        rank = self._jaunte_rank(agent)
        if rank >= 3:
            self._jaunte_feedback(agent, "blocked", "Uplink Hop already max rank (3).")
            return True
        agent.skill_picks_available = picks - 1
        skills = getattr(agent, "skills", None)
        if not isinstance(skills, dict):
            agent.skills = {}
            skills = agent.skills
        if SKILL_ID not in skills:
            skills[SKILL_ID] = SKILL_NAME
        agent.jaunte["rank"] = rank + 1
        self._jaunte_feedback(
            agent,
            "rankup",
            "Trained Uplink Hop — now %s (rank %d)."
            % (RANK_NAMES[agent.jaunte["rank"]], agent.jaunte["rank"]),
        )
        return True

    def _jaunte_open(self, agent) -> bool:
        self._jaunte_bootstrap_agent(agent)
        agent.jaunte["panel_open"] = True
        rank = self._jaunte_rank(agent)
        left = self._jaunte_cooldown_left(agent)
        agent.log(
            "Uplink Hop panel — rank %d (%s) · xp %d · cooldown %.0fs. "
            "Commands: jaunte short | jaunte district [id] | jaunte globe <region> | jaunte_train"
            % (rank, RANK_NAMES.get(rank, "?"), int(agent.jaunte.get("xp") or 0), left)
        )
        return True

    def _jaunte_snapshot(self, agent) -> Dict[str, Any]:
        self._jaunte_bootstrap_agent(agent)
        j = agent.jaunte
        rank = int(j.get("rank") or 0)
        left = self._jaunte_cooldown_left(agent)
        next_need = RANK_XP.get(rank + 1) if rank < 3 else None
        ranks_out: List[Dict[str, Any]] = []
        for r in range(0, 4):
            ranks_out.append({
                "rank": r,
                "name": RANK_NAMES[r],
                "unlocked": rank >= r,
                "range_short": SHORT_RANGE[r],
                "unlocks": (
                    "short hops" if r == 1
                    else "district hops" if r == 2
                    else "globe hops (#54)" if r == 3
                    else "untrained (high misfire)"
                ),
            })
        return {
            "rank": rank,
            "rank_name": RANK_NAMES.get(rank, "Untrained"),
            "xp": int(j.get("xp") or 0),
            "xp_next": next_need,
            "hops": int(j.get("hops") or 0),
            "misfires": int(j.get("misfires") or 0),
            "cooldown": left,
            "cooldown_until": float(j.get("cooldown_until") or 0),
            "ready": left <= 0.05,
            "focus_costs": dict(FOCUS_COST),
            "short_range": SHORT_RANGE.get(rank, 4),
            "can_short": True,
            "can_district": rank >= 2,
            "can_globe": rank >= 3,
            "ranks": ranks_out,
            "panel_open": bool(j.get("panel_open")),
            "last_feedback": j.get("last_feedback"),
            "last_result": j.get("last_result"),
            "skill_id": SKILL_ID,
            "hint": (
                "Train via successful hops or skill_pick uplink_jaunte / jaunte_train. "
                "Underleveled hops risk misfire."
            ),
        }

    def _jaunte_action(self, agent, action: str, arg: str = "") -> bool:
        self._jaunte_bootstrap_agent(agent)
        a = (action or "").strip().lower()
        arg = (arg or "").strip()
        arg_l = arg.lower()

        if a in (
            "jaunte", "street_jaunt", "street_jaunte", "jaunt",
            "open_jaunte", "jaunte_panel", "uplink_jaunte",
        ):
            # Bare open, or route by arg
            if not arg_l:
                return self._jaunte_open(agent)
            if arg_l in ("status", "info"):
                snap = self._jaunte_snapshot(agent)
                agent.log(
                    "Uplink Hop rank %d (%s) · xp %d/%s · hops %d · misfires %d · cd %.0fs"
                    % (
                        snap["rank"], snap["rank_name"], snap["xp"],
                        snap["xp_next"] if snap["xp_next"] is not None else "max",
                        snap["hops"], snap["misfires"], snap["cooldown"],
                    )
                )
                return True
            if arg_l in ("train", "learn"):
                return self._jaunte_train(agent)
            if arg_l in ("close",):
                agent.jaunte["panel_open"] = False
                agent.log("Uplink Hop panel closed.")
                return True
            if arg_l.startswith("short") or arg_l in (
                "n", "s", "e", "w", "north", "south", "east", "west",
                "ne", "nw", "se", "sw", "f", "fwd", "forward",
            ):
                return self._jaunte_short(agent, arg_l)
            if arg_l.startswith("district") or arg_l in (
                "burbclave", "club", "uplink_rim", "undercity",
            ):
                return self._jaunte_district(agent, arg_l)
            if arg_l.startswith("globe") or arg_l.startswith("region"):
                # jaunte globe neo_tokyo OR jaunte region neo_tokyo
                parts = arg_l.split(None, 1)
                region = parts[1] if len(parts) > 1 else ""
                if arg_l.startswith("region") and region:
                    return self._jaunte_globe(agent, region)
                return self._jaunte_globe(agent, arg_l)
            # Unknown arg — treat as short-dir attempt or open
            return self._jaunte_short(agent, arg_l)

        if a in ("jaunte_short", "jaunt_short", "street_hop", "short_jaunt"):
            return self._jaunte_short(agent, arg_l)
        if a in ("jaunte_district", "jaunt_district", "district_hop", "district_jaunt"):
            return self._jaunte_district(agent, arg_l)
        if a in ("jaunte_globe", "jaunt_globe", "globe_jaunt", "jaunte_tp"):
            return self._jaunte_globe(agent, arg_l)
        if a in ("jaunte_status", "jaunt_status", "uplink_status"):
            snap = self._jaunte_snapshot(agent)
            agent.log(
                "Uplink Hop rank %d (%s) · xp %d · ready=%s"
                % (snap["rank"], snap["rank_name"], snap["xp"], snap["ready"])
            )
            agent.jaunte["panel_open"] = True
            return True
        if a in ("jaunte_train", "train_jaunte", "jaunt_train"):
            return self._jaunte_train(agent)
        if a in ("jaunte_close", "close_jaunte"):
            agent.jaunte["panel_open"] = False
            agent.log("Uplink Hop panel closed.")
            return True

        return False
