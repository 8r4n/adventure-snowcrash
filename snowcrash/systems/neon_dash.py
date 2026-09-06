"""Neon Dash timed street race event (#48).

Periodic StreetNet broadcast starts a timed checkpoint dash through a district.
Finishers earn cosmetics/credits only (no P2W combat power). Original Metaverse prose.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from .. import constants as C

# Timing (world ticks)
NEON_DASH_FIRST_DELAY = 25
NEON_DASH_INTERVAL_MIN = 90
NEON_DASH_INTERVAL_MAX = 160
NEON_DASH_DURATION = 100  # ticks to clear all checkpoints
NEON_DASH_CHECKPOINT_COUNT = 4
NEON_DASH_HIT_RADIUS = 1  # Manhattan

# Rewards — cosmetics / credits / season XP only (no attack/defense/hp)
NEON_DASH_REWARD_CREDITS = 35
NEON_DASH_REWARD_SEASON_XP = 10
NEON_DASH_COSMETIC = {
    "id": "trail_neon_dash",
    "name": "Neon Dash Afterimage",
    "slot": "trail",
}

NEON_DASH_DISTRICTS = ("burbclave", "club", "uplink_rim")

START_LINES = (
    "StreetNet FLASH: Neon Dash live in {district} — hit every checkpoint before the clock dies.",
    "Courier channel opens: Neon Dash through {district}. Ghost the gates. Timer is law.",
    "Neon Dash broadcast — {district} route hot. Sleeve the checkpoints or eat static.",
)

END_LINES = (
    "Neon Dash closed in {district}. StreetNet wipes the route glyphs.",
    "Timer zero — Neon Dash ends. Finishers keep their afterimage; stragglers get fog.",
)

FINISH_LINES = (
    "You ghost the last gate — Neon Dash complete. +{credits} credits · cosmetic unlocked.",
    "Checkpoint lattice seals. StreetNet stamps your courier trail. +{credits} credits.",
)


class NeonDashMixin:
    """Mixed into YearFeaturesMixin / GameWorld."""

    def _neon_dash_init(self) -> None:
        self.neon_dash: Dict[str, Any] = {
            "active": False,
            "event_id": 0,
            "district_id": None,
            "district_name": None,
            "checkpoints": [],  # [{id,x,y,label}]
            "started_tick": 0,
            "ends_tick": 0,
            "started_at": 0.0,
            "finishers": [],  # agent ids
            "next_start_tick": NEON_DASH_FIRST_DELAY,
        }

    def _neon_dash_bootstrap_agent(self, agent) -> None:
        nd = getattr(agent, "neon_dash", None)
        if not isinstance(nd, dict):
            agent.neon_dash = {
                "event_id": 0,
                "joined": False,
                "hit": [],  # checkpoint ids hit this event
                "finished": False,
                "finish_tick": None,
                "rewards_claimed": False,
            }
            return
        nd.setdefault("event_id", 0)
        nd.setdefault("joined", False)
        nd.setdefault("hit", [])
        nd.setdefault("finished", False)
        nd.setdefault("finish_tick", None)
        nd.setdefault("rewards_claimed", False)

    def _neon_dash_reset_agent_for_event(self, agent, event_id: int) -> None:
        self._neon_dash_bootstrap_agent(agent)
        agent.neon_dash = {
            "event_id": event_id,
            "joined": False,
            "hit": [],
            "finished": False,
            "finish_tick": None,
            "rewards_claimed": False,
        }

    def _neon_dash_pick_district(self) -> Optional[Dict[str, Any]]:
        defs = getattr(self, "district_defs", {}) or {}
        choices = [
            d
            for d in defs.get("districts", [])
            if d.get("id") in NEON_DASH_DISTRICTS and d.get("plane") != -1
        ]
        if not choices:
            return None
        rng = getattr(self, "rng", None)
        if rng is not None:
            return rng.choice(choices)
        return choices[0]

    def _neon_dash_seed_checkpoints(self, district_id: str) -> List[Dict[str, Any]]:
        """Spread ordered checkpoints across a district AABB."""
        find = getattr(self, "_find_walkable_in_district", None)
        if not callable(find):
            return []
        pts: List[Tuple[int, int]] = []
        used = set()
        for _ in range(NEON_DASH_CHECKPOINT_COUNT * 12):
            pos = find(district_id)
            if pos is None:
                break
            if pos in used:
                continue
            # Keep spread — reject too-close to existing
            too_close = False
            for ox, oy in pts:
                if abs(pos[0] - ox) + abs(pos[1] - oy) < 6:
                    too_close = True
                    break
            if too_close and pts:
                continue
            used.add(pos)
            pts.append(pos)
            if len(pts) >= NEON_DASH_CHECKPOINT_COUNT:
                break
        # Fallback: allow closer if district is cramped
        while len(pts) < NEON_DASH_CHECKPOINT_COUNT:
            pos = find(district_id)
            if pos is None:
                break
            if pos in used:
                # nudge search by accepting duplicates attempt limit
                if len(used) > NEON_DASH_CHECKPOINT_COUNT * 20:
                    break
                used.add(pos)  # burn attempt
                continue
            used.add(pos)
            pts.append(pos)
        if len(pts) < 2:
            return []
        # Order roughly NW→SE for a readable route
        pts.sort(key=lambda p: (p[0] + p[1], p[0]))
        labels = ("Start gate", "Mid neon", "Bass cut", "Finish line")
        out: List[Dict[str, Any]] = []
        for i, (x, y) in enumerate(pts[:NEON_DASH_CHECKPOINT_COUNT]):
            label = labels[i] if i < len(labels) else ("Gate %d" % (i + 1))
            out.append({"id": "cp_%d" % i, "x": x, "y": y, "label": label, "index": i})
        return out

    def _neon_dash_start(self) -> bool:
        state = self.neon_dash
        if state.get("active"):
            return False
        district = self._neon_dash_pick_district()
        if not district:
            state["next_start_tick"] = self.tick + NEON_DASH_INTERVAL_MIN
            return False
        cps = self._neon_dash_seed_checkpoints(district["id"])
        if len(cps) < 2:
            state["next_start_tick"] = self.tick + 40
            return False
        eid = int(state.get("event_id", 0) or 0) + 1
        state.update(
            {
                "active": True,
                "event_id": eid,
                "district_id": district["id"],
                "district_name": district.get("name") or district["id"],
                "checkpoints": cps,
                "started_tick": self.tick,
                "ends_tick": self.tick + NEON_DASH_DURATION,
                "started_at": time.time(),
                "finishers": [],
            }
        )
        dname = state["district_name"]
        rng = getattr(self, "rng", None)
        line_tpl = START_LINES[0]
        if rng is not None:
            line_tpl = rng.choice(START_LINES)
        msg = line_tpl.format(district=dname)
        self._push_event(
            "neon_dash",
            msg,
            phase="start",
            district=state["district_id"],
            event_id=eid,
            ends_tick=state["ends_tick"],
        )
        if hasattr(self, "system_chat"):
            self.system_chat(msg)
        for p in list(getattr(self, "players", {}).values()):
            if not getattr(p, "connected", False):
                continue
            self._neon_dash_reset_agent_for_event(p, eid)
            p.log(msg)
            p.log(
                "Neon Dash: reach %d checkpoints in %s before tick clock dies. Status: neon_dash"
                % (len(cps), dname)
            )
        return True

    def _neon_dash_end(self, reason: str = "timer") -> None:
        state = self.neon_dash
        if not state.get("active"):
            return
        dname = state.get("district_name") or state.get("district_id") or "district"
        rng = getattr(self, "rng", None)
        line_tpl = END_LINES[0]
        if rng is not None:
            line_tpl = rng.choice(END_LINES)
        msg = line_tpl.format(district=dname)
        finishers = list(state.get("finishers") or [])
        self._push_event(
            "neon_dash",
            msg,
            phase="end",
            district=state.get("district_id"),
            event_id=state.get("event_id"),
            finishers=len(finishers),
            reason=reason,
        )
        if hasattr(self, "system_chat"):
            self.system_chat(msg)
        for p in list(getattr(self, "players", {}).values()):
            if getattr(p, "connected", False):
                p.log(msg)
        # Schedule next
        gap = NEON_DASH_INTERVAL_MIN
        if rng is not None:
            gap = rng.randint(NEON_DASH_INTERVAL_MIN, NEON_DASH_INTERVAL_MAX)
        state.update(
            {
                "active": False,
                "checkpoints": [],
                "district_id": None,
                "district_name": None,
                "ends_tick": 0,
                "next_start_tick": self.tick + gap,
            }
        )

    def _neon_dash_timer_remaining(self) -> int:
        state = self.neon_dash
        if not state.get("active"):
            return 0
        return max(0, int(state.get("ends_tick", 0) - self.tick))

    def _tick_neon_dash(self) -> None:
        state = getattr(self, "neon_dash", None)
        if not isinstance(state, dict):
            self._neon_dash_init()
            state = self.neon_dash
        if state.get("active"):
            if self.tick >= int(state.get("ends_tick", 0)):
                self._neon_dash_end("timer")
            return
        if self.tick >= int(state.get("next_start_tick", NEON_DASH_FIRST_DELAY)):
            self._neon_dash_start()

    def _neon_dash_on_move(self, agent) -> None:
        """Call after a successful street-plane step."""
        state = getattr(self, "neon_dash", None)
        if not isinstance(state, dict) or not state.get("active"):
            return
        if int(getattr(agent.actor, "z", 0) or 0) != C.PLANE_STREET:
            return
        if not getattr(agent.actor, "alive", True):
            return
        self._neon_dash_bootstrap_agent(agent)
        nd = agent.neon_dash
        eid = int(state.get("event_id", 0) or 0)
        if int(nd.get("event_id", 0) or 0) != eid:
            self._neon_dash_reset_agent_for_event(agent, eid)
            nd = agent.neon_dash
        if nd.get("finished"):
            return
        ax, ay = agent.actor.x, agent.actor.y
        hit = list(nd.get("hit") or [])
        cps = list(state.get("checkpoints") or [])
        # Must hit in order
        next_idx = len(hit)
        if next_idx >= len(cps):
            return
        cp = cps[next_idx]
        if abs(ax - int(cp["x"])) + abs(ay - int(cp["y"])) > NEON_DASH_HIT_RADIUS:
            return
        cid = cp["id"]
        if cid in hit:
            return
        hit.append(cid)
        nd["hit"] = hit
        nd["joined"] = True
        agent.log(
            "Neon Dash checkpoint %d/%d — %s."
            % (len(hit), len(cps), cp.get("label", cid))
        )
        if len(hit) >= len(cps):
            self._neon_dash_finish(agent)

    def _neon_dash_finish(self, agent) -> None:
        state = self.neon_dash
        self._neon_dash_bootstrap_agent(agent)
        nd = agent.neon_dash
        if nd.get("finished") or nd.get("rewards_claimed"):
            return
        if not state.get("active"):
            return
        nd["finished"] = True
        nd["finish_tick"] = self.tick
        nd["rewards_claimed"] = True
        aid = getattr(agent, "id", None)
        finishers = list(state.get("finishers") or [])
        if aid and aid not in finishers:
            finishers.append(aid)
            state["finishers"] = finishers

        # Credits
        credits = NEON_DASH_REWARD_CREDITS
        agent.credits = int(getattr(agent, "credits", 0) or 0) + credits

        # Cosmetic unlock (season.unlocked) — no combat stats
        season = getattr(agent, "season", None)
        if not isinstance(season, dict):
            season = {
                "id": None,
                "xp": 0,
                "tier": 0,
                "unlocked": [],
                "equipped": None,
            }
            agent.season = season
        unlocked = list(season.get("unlocked") or [])
        cos_id = NEON_DASH_COSMETIC["id"]
        newly = False
        if cos_id not in unlocked:
            unlocked.append(cos_id)
            season["unlocked"] = unlocked
            newly = True
        # Optional equip hint
        if newly and not season.get("equipped"):
            season["equipped"] = cos_id

        # Season XP only (tier cosmetics remain cosmetic)
        grant = getattr(self, "_grant_season_xp", None)
        if callable(grant):
            grant(agent, NEON_DASH_REWARD_SEASON_XP)

        rng = getattr(self, "rng", None)
        line_tpl = FINISH_LINES[0]
        if rng is not None:
            line_tpl = rng.choice(FINISH_LINES)
        agent.log(line_tpl.format(credits=credits))
        if newly:
            agent.log(
                "Cosmetic unlocked: %s (season_equip %s)."
                % (NEON_DASH_COSMETIC["name"], cos_id)
            )
        else:
            agent.log("Cosmetic already owned: %s — credits still paid." % NEON_DASH_COSMETIC["name"])

        place = len(finishers)
        self._push_event(
            "neon_dash",
            "%s finished Neon Dash (#%d)." % (getattr(agent, "name", "Courier"), place),
            phase="finish",
            event_id=state.get("event_id"),
            courier=getattr(agent, "name", None),
            place=place,
        )

    def _neon_dash_snapshot(self, agent) -> Dict[str, Any]:
        self._neon_dash_bootstrap_agent(agent)
        state = getattr(self, "neon_dash", None) or {}
        nd = agent.neon_dash
        active = bool(state.get("active"))
        eid = int(state.get("event_id", 0) or 0)
        # Sync agent event if stale while inactive
        agent_eid = int(nd.get("event_id", 0) or 0)
        hit = list(nd.get("hit") or []) if agent_eid == eid else []
        cps = list(state.get("checkpoints") or []) if active else []
        next_cp = None
        if active and not nd.get("finished") and agent_eid == eid:
            idx = len(hit)
            if idx < len(cps):
                next_cp = dict(cps[idx])
        timer = self._neon_dash_timer_remaining() if active else 0
        return {
            "active": active,
            "event_id": eid if active else 0,
            "district_id": state.get("district_id") if active else None,
            "district_name": state.get("district_name") if active else None,
            "timer_remaining": timer,
            "duration": NEON_DASH_DURATION,
            "ends_tick": int(state.get("ends_tick", 0) or 0) if active else 0,
            "checkpoints": cps,
            "hit": hit,
            "hit_count": len(hit),
            "checkpoint_count": len(cps) if active else NEON_DASH_CHECKPOINT_COUNT,
            "next_checkpoint": next_cp,
            "joined": bool(nd.get("joined")) and agent_eid == eid,
            "finished": bool(nd.get("finished")) and agent_eid == eid,
            "finishers": len(list(state.get("finishers") or [])) if active else 0,
            "reward": {
                "credits": NEON_DASH_REWARD_CREDITS,
                "cosmetic": dict(NEON_DASH_COSMETIC),
                "season_xp": NEON_DASH_REWARD_SEASON_XP,
                "p2w": False,
            },
            "next_start_tick": int(state.get("next_start_tick", 0) or 0) if not active else None,
        }

    def _neon_dash_landmarks(self) -> List[Dict[str, Any]]:
        state = getattr(self, "neon_dash", None) or {}
        if not state.get("active"):
            return []
        marks = []
        for cp in state.get("checkpoints") or []:
            marks.append(
                {
                    "id": "neon_dash_%s" % cp["id"],
                    "name": "Neon Dash · %s" % cp.get("label", cp["id"]),
                    "glyph": "+",
                    "x": int(cp["x"]),
                    "y": int(cp["y"]),
                    "z": 0,
                }
            )
        return marks

    def _neon_dash_action(self, agent, action: str, arg: str = "") -> bool:
        self._neon_dash_bootstrap_agent(agent)
        a = (action or "").strip().lower()
        if a in ("neon_dash", "dash_status", "neon_status", "dash"):
            snap = self._neon_dash_snapshot(agent)
            if snap["active"]:
                nxt = snap.get("next_checkpoint")
                nxt_s = (
                    "%s @ (%d,%d)" % (nxt["label"], nxt["x"], nxt["y"])
                    if nxt
                    else ("DONE" if snap["finished"] else "—")
                )
                agent.log(
                    "Neon Dash LIVE · %s · timer %d · checkpoints %d/%d · next %s"
                    % (
                        snap.get("district_name") or "?",
                        snap["timer_remaining"],
                        snap["hit_count"],
                        snap["checkpoint_count"],
                        nxt_s,
                    )
                )
            else:
                agent.log(
                    "Neon Dash idle — next StreetNet start around tick %s. Reward: %d cr + %s (cosmetic only)."
                    % (
                        snap.get("next_start_tick"),
                        NEON_DASH_REWARD_CREDITS,
                        NEON_DASH_COSMETIC["name"],
                    )
                )
            return True
        if a in ("neon_dash_force", "force_neon_dash") and arg == "dev":
            # Dev/test helper — only when explicitly arg=dev
            if self.neon_dash.get("active"):
                self._neon_dash_end("forced")
            self.neon_dash["next_start_tick"] = self.tick
            self._neon_dash_start()
            agent.log("Dev: Neon Dash forced start.")
            return True
        return False
