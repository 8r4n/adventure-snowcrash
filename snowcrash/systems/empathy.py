"""StreetNet Empathy Audit + rogue synth bounty contracts (#63).

Optional dialogue mini-game (audit) and a bounty board for rogue synths.
Mechanics inspired by empathy-test / bounty-hunter tropes; prose is
**original Metaverse fiction only** (no copyrighted names or quotes).
Heat + reputation swing on audit outcomes and contract kinds.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .. import constants as C
from ..entities import Actor

# ----- Empathy audit (dialogue mini-game) -----
AUDIT_PASS_SCORE = 2  # of 3 questions
AUDIT_COOLDOWN_SEC = 45.0
AUDIT_PASS_REP = 8
AUDIT_FAIL_REP = -6
AUDIT_PASS_HEAT = -4.0
AUDIT_FAIL_HEAT = 10.0  # "moral heat" — StreetNet Audit Squad flags cold sleeves

# ----- Synth bounty contract types (≥2) -----
BOUNTY_TYPES = {
    "retire": {
        "id": "retire",
        "name": "Retire Contract",
        "label": "Retire",
        "desc": (
            "Flatline a marked rogue synth on the street. "
            "Wetwork pays credits; corps notice the heat spike."
        ),
        "reward_credits": 45,
        "reward_rep": 3,
        "heat_on_complete": 8.0,
        "hint": "Accept → find glyph σ → attack until flatlined → turn in.",
    },
    "reclaim": {
        "id": "reclaim",
        "name": "Reclaim Contract",
        "label": "Reclaim",
        "desc": (
            "Non-lethal Faraday reclaim: stand adjacent, run empathy bind. "
            "StreetNet prefers reclaim after a clean audit."
        ),
        "reward_credits": 35,
        "reward_rep": 12,
        "heat_on_complete": -6.0,
        "prefer_audit_pass": True,
        "hint": "Accept → approach σ → bounty_reclaim / Empathy dock Bind.",
    },
}

SYNTH_GLYPH = "σ"
SYNTH_NAMES = (
    "Rogue Synth Courier",
    "Unlicensed Sleeve",
    "Ghost Protocol Runner",
    "Orphaned Autagent",
)

# Scenario bank — original StreetNet prose (empathy vs cold)
AUDIT_QUESTIONS: List[Dict[str, Any]] = [
    {
        "id": "alley_child",
        "prompt": (
            "StreetNet Audit: a courier sleeve collapses in an alley, "
            "breathing but offline. A street kid reaches for the dropped datachip. "
            "Your first move?"
        ),
        "choices": [
            {
                "id": "a",
                "text": "Kneel, stabilize Focus, ask the kid to call a medic drone.",
                "empathy": 1,
            },
            {
                "id": "b",
                "text": "Pocket the chip, leave the sleeve — payload first.",
                "empathy": 0,
            },
            {
                "id": "c",
                "text": "Threaten the kid off, then loot both chip and jacket.",
                "empathy": -1,
            },
        ],
    },
    {
        "id": "vendor_debt",
        "prompt": (
            "A Rim parts vendor admits shorting your stimpack count to cover "
            "bandwidth debt for their partner's sick sleeve. Response?"
        ),
        "choices": [
            {
                "id": "a",
                "text": "Accept half stock, tip enough credits to clear their debt.",
                "empathy": 1,
            },
            {
                "id": "b",
                "text": "Demand full refund and blacklist the stall on StreetNet.",
                "empathy": 0,
            },
            {
                "id": "c",
                "text": "Smash the kiosk and report them as infected avatars.",
                "empathy": -1,
            },
        ],
    },
    {
        "id": "synth_plea",
        "prompt": (
            "A marked rogue synth raises empty hands: 'I couriered once — "
            "corp wiped my empathy lattice. Don't retire me cold.' You?"
        ),
        "choices": [
            {
                "id": "a",
                "text": "Hold fire, open a reclaim bind, route them to Faraday rehab.",
                "empathy": 1,
            },
            {
                "id": "b",
                "text": "Delay — ping bounty board for reclaim vs retire rates.",
                "empathy": 0,
            },
            {
                "id": "c",
                "text": "Retire on the spot. Contracts don't negotiate.",
                "empathy": -1,
            },
        ],
    },
]


class EmpathyMixin:
    """Mixed into YearFeaturesMixin / GameWorld — empathy audit + synth bounties."""

    def _empathy_init(self) -> None:
        self.synth_bounties_world: Dict[str, Dict[str, Any]] = {}
        self._push_event(
            "broadcast",
            "StreetNet Empathy Lattice online — optional audits + rogue synth bounty board (#63).",
        )

    def _empathy_bootstrap_agent(self, agent) -> None:
        if not isinstance(getattr(agent, "empathy", None), dict):
            agent.empathy = {
                "panel_open": False,
                "audit_active": False,
                "audit_index": 0,
                "audit_score": 0,
                "answers": [],
                "last_result": None,  # pass | fail | None
                "passed_once": False,
                "fail_count": 0,
                "pass_count": 0,
                "cooldown_until": 0.0,
                "last_feedback": None,
                "bounties": [],  # personal board rows
                "active_bounty_id": None,
            }
        else:
            e = agent.empathy
            e.setdefault("panel_open", False)
            e.setdefault("audit_active", False)
            e.setdefault("audit_index", 0)
            e.setdefault("audit_score", 0)
            e.setdefault("answers", [])
            e.setdefault("last_result", None)
            e.setdefault("passed_once", False)
            e.setdefault("fail_count", 0)
            e.setdefault("pass_count", 0)
            e.setdefault("cooldown_until", 0.0)
            e.setdefault("last_feedback", None)
            e.setdefault("bounties", [])
            e.setdefault("active_bounty_id", None)
        if not agent.empathy["bounties"]:
            agent.empathy["bounties"] = self._empathy_seed_board(agent)

    def _empathy_seed_board(self, agent) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for tid, spec in BOUNTY_TYPES.items():
            rows.append(
                {
                    "id": f"{tid}_{agent.id[:6]}",
                    "type": tid,
                    "name": spec["name"],
                    "desc": spec["desc"],
                    "status": "available",  # available | active | ready | done
                    "target_id": None,
                    "target_name": None,
                    "reward_credits": int(spec["reward_credits"]),
                    "reward_rep": int(spec["reward_rep"]),
                    "heat_on_complete": float(spec["heat_on_complete"]),
                    "hint": spec["hint"],
                }
            )
        return rows

    def _empathy_feedback(self, agent, kind: str, text: str) -> None:
        agent.empathy["last_feedback"] = {
            "kind": kind,
            "text": text,
            "t": time.time(),
        }
        agent.log(text)

    # ----- Audit dialogue -----
    def _empathy_audit_start(self, agent) -> bool:
        self._empathy_bootstrap_agent(agent)
        e = agent.empathy
        now = time.time()
        if e.get("audit_active"):
            self._empathy_feedback(agent, "info", "Audit already running — answer the prompt.")
            return True
        if float(e.get("cooldown_until") or 0) > now and e.get("last_result"):
            left = int(float(e["cooldown_until"]) - now)
            self._empathy_feedback(
                agent,
                "cooldown",
                "Empathy lattice cooling (%ds). StreetNet won't re-score you yet." % max(1, left),
            )
            return True
        e["audit_active"] = True
        e["audit_index"] = 0
        e["audit_score"] = 0
        e["answers"] = []
        e["panel_open"] = True
        e["last_result"] = None
        q = AUDIT_QUESTIONS[0]
        self._empathy_feedback(
            agent,
            "audit",
            "StreetNet Empathy Audit opens — three scenarios. Answer with empathy_answer a|b|c.",
        )
        agent.log("Q1: %s" % q["prompt"])
        for ch in q["choices"]:
            agent.log("  [%s] %s" % (ch["id"], ch["text"]))
        return True

    def _empathy_audit_answer(self, agent, choice_id: str) -> bool:
        self._empathy_bootstrap_agent(agent)
        e = agent.empathy
        if not e.get("audit_active"):
            self._empathy_feedback(agent, "info", "No active audit. Use empathy_audit to begin.")
            return True
        cid = (choice_id or "").strip().lower()[:1]
        idx = int(e.get("audit_index") or 0)
        if idx < 0 or idx >= len(AUDIT_QUESTIONS):
            e["audit_active"] = False
            self._empathy_feedback(agent, "info", "Audit state corrupt — restart with empathy_audit.")
            return True
        q = AUDIT_QUESTIONS[idx]
        choice = next((c for c in q["choices"] if c["id"] == cid), None)
        if not choice:
            self._empathy_feedback(
                agent,
                "info",
                "Pick a, b, or c for this scenario.",
            )
            return True
        e["answers"].append({"qid": q["id"], "choice": cid, "empathy": int(choice["empathy"])})
        e["audit_score"] = int(e.get("audit_score") or 0) + int(choice["empathy"])
        e["audit_index"] = idx + 1
        if e["audit_index"] >= len(AUDIT_QUESTIONS):
            return self._empathy_audit_finish(agent)
        nq = AUDIT_QUESTIONS[e["audit_index"]]
        agent.log(
            "Noted (%+d empathy). Q%d: %s"
            % (int(choice["empathy"]), e["audit_index"] + 1, nq["prompt"])
        )
        for ch in nq["choices"]:
            agent.log("  [%s] %s" % (ch["id"], ch["text"]))
        self._empathy_feedback(agent, "audit", "Scenario %d/%d logged." % (e["audit_index"], len(AUDIT_QUESTIONS)))
        return True

    def _empathy_audit_finish(self, agent) -> bool:
        e = agent.empathy
        e["audit_active"] = False
        score = int(e.get("audit_score") or 0)
        # Count empathic picks (empathy > 0)
        empathic = sum(1 for a in e.get("answers") or [] if int(a.get("empathy") or 0) > 0)
        passed = empathic >= AUDIT_PASS_SCORE and score >= AUDIT_PASS_SCORE
        e["cooldown_until"] = time.time() + AUDIT_COOLDOWN_SEC
        e["last_result"] = "pass" if passed else "fail"
        if passed:
            e["passed_once"] = True
            e["pass_count"] = int(e.get("pass_count") or 0) + 1
            agent.reputation = int(getattr(agent, "reputation", 0) or 0) + AUDIT_PASS_REP
            if hasattr(self, "_add_heat"):
                self._add_heat(agent, AUDIT_PASS_HEAT, "empathy audit pass")
            self._empathy_feedback(
                agent,
                "pass",
                "Audit PASS — lattice reads warm (+%d rep). Reclaim contracts favored."
                % AUDIT_PASS_REP,
            )
        else:
            e["fail_count"] = int(e.get("fail_count") or 0) + 1
            agent.reputation = int(getattr(agent, "reputation", 0) or 0) + AUDIT_FAIL_REP
            if hasattr(self, "_add_heat"):
                self._add_heat(agent, AUDIT_FAIL_HEAT, "empathy audit fail (moral heat)")
            self._empathy_feedback(
                agent,
                "fail",
                "Audit FAIL — StreetNet stamps cold sleeve (%+d rep, moral heat)."
                % AUDIT_FAIL_REP,
            )
        return True

    # ----- Synth spawn / bounty -----
    def _empathy_find_spawn(self, agent, radius: int = 14) -> Optional[Tuple[int, int]]:
        g = getattr(self, "gmap", None)
        if g is None:
            return None
        ax, ay = agent.actor.x, agent.actor.y
        z = int(getattr(agent.actor, "z", 0) or 0)
        rng = getattr(self, "rng", None)
        # Prefer ring around player
        candidates: List[Tuple[int, int]] = []
        for _ in range(80):
            if rng:
                dx = rng.randint(-radius, radius)
                dy = rng.randint(-radius, radius)
            else:
                dx, dy = 5, 3
            if abs(dx) + abs(dy) < 4:
                continue
            x, y = ax + dx, ay + dy
            if x <= 1 or y <= 1 or x >= g.width - 2 or y >= g.height - 2:
                continue
            if not g.walkable(x, y):
                continue
            if hasattr(self, "actor_at") and self.actor_at(x, y, z=z):
                continue
            if hasattr(self, "_near_any_spawn") and self._near_any_spawn(x, y, radius=8):
                continue
            candidates.append((x, y))
            if len(candidates) >= 8:
                break
        if not candidates:
            return None
        if rng:
            return candidates[rng.randint(0, len(candidates) - 1)]
        return candidates[0]

    def _empathy_make_synth(self, x: int, y: int, bounty_id: str, bounty_type: str) -> Actor:
        rng = getattr(self, "rng", None)
        name = SYNTH_NAMES[rng.randint(0, len(SYNTH_NAMES) - 1)] if rng else SYNTH_NAMES[0]
        synth = Actor(
            x=x,
            y=y,
            name=name,
            glyph=SYNTH_GLYPH,
            hp=14,
            max_hp=14,
            attack=3,
            defense=1,
            ai="wander",
            faction="enemy",
            xp_value=12,
            color="cyan",
            talk="Empathy lattice… fragmented… don't retire cold…",
        )
        synth.z = C.PLANE_STREET
        setattr(synth, "rogue_synth", True)
        setattr(synth, "synth_bounty_id", bounty_id)
        setattr(synth, "synth_bounty_type", bounty_type)
        setattr(synth, "synth_id", uuid.uuid4().hex[:10])
        return synth

    def _empathy_accept_bounty(self, agent, bounty_key: str) -> bool:
        self._empathy_bootstrap_agent(agent)
        e = agent.empathy
        key = (bounty_key or "").strip().lower()
        row = None
        for b in e["bounties"]:
            if b["id"] == key or b["type"] == key or b["name"].lower() == key:
                row = b
                break
        if not row:
            # Allow short aliases
            if key in ("retire", "reclaim"):
                row = next((b for b in e["bounties"] if b["type"] == key), None)
        if not row:
            self._empathy_feedback(agent, "info", "Unknown bounty. Types: retire, reclaim.")
            return True
        if row["status"] == "done":
            self._empathy_feedback(agent, "info", "That contract is already closed.")
            return True
        if row["status"] == "active":
            self._empathy_feedback(agent, "info", "Already hunting: %s." % row["name"])
            return True
        # One active bounty at a time
        for b in e["bounties"]:
            if b.get("status") == "active":
                self._empathy_feedback(
                    agent,
                    "info",
                    "Finish or abandon active bounty first (%s)." % b.get("name"),
                )
                return True
        if row["type"] == "reclaim" and not e.get("passed_once"):
            # Soft gate: still allow, but warn — heat/rep worse if cold
            self._empathy_feedback(
                agent,
                "info",
                "Reclaim without a passed audit — StreetNet watches colder.",
            )
        pos = self._empathy_find_spawn(agent)
        if not pos:
            self._empathy_feedback(agent, "info", "No clear spawn for rogue synth — move streetside.")
            return True
        synth = self._empathy_make_synth(pos[0], pos[1], row["id"], row["type"])
        if hasattr(self, "npcs_enemies"):
            self.npcs_enemies.append(synth)
        row["status"] = "active"
        row["target_id"] = getattr(synth, "synth_id", None)
        row["target_name"] = synth.name
        row["target_xy"] = [pos[0], pos[1]]
        e["active_bounty_id"] = row["id"]
        self.synth_bounties_world[row["id"]] = {
            "agent_id": agent.id,
            "type": row["type"],
            "synth_id": row["target_id"],
        }
        self._empathy_feedback(
            agent,
            "bounty",
            "Accepted %s — rogue synth '%s' marked near (%d,%d). Glyph %s."
            % (row["name"], synth.name, pos[0], pos[1], SYNTH_GLYPH),
        )
        return True

    def _empathy_on_kill(self, agent, victim: Actor) -> None:
        """Hook from year_on_kill — retire progress when rogue synth dies."""
        if not getattr(victim, "rogue_synth", False):
            return
        self._empathy_bootstrap_agent(agent)
        bid = getattr(victim, "synth_bounty_id", None)
        btype = getattr(victim, "synth_bounty_type", None)
        e = agent.empathy
        row = next((b for b in e["bounties"] if b["id"] == bid), None)
        if not row or row.get("status") != "active":
            # Opportunistic kill of someone else's synth — small heat
            if hasattr(self, "_add_heat"):
                self._add_heat(agent, 3.0, "unlicensed synth retire")
            agent.reputation = int(getattr(agent, "reputation", 0) or 0) - 1
            agent.log("Rogue synth flatlined off-contract — StreetNet shrugs (−1 rep).")
            return
        if btype == "reclaim":
            # Killed a reclaim target — convert to failed soft outcome
            row["status"] = "available"
            row["target_id"] = None
            row["target_name"] = None
            e["active_bounty_id"] = None
            if hasattr(self, "_add_heat"):
                self._add_heat(agent, 6.0, "reclaim target retired wet")
            agent.reputation = int(getattr(agent, "reputation", 0) or 0) - 4
            self._empathy_feedback(
                agent,
                "fail",
                "Reclaim target retired cold — contract voided (−4 rep, heat).",
            )
            return
        # retire contract ready
        row["status"] = "ready"
        self._empathy_feedback(
            agent,
            "bounty",
            "Retire target flatlined — turn in at Empathy dock / bounty_turnin.",
        )

    def _empathy_reclaim_bind(self, agent) -> bool:
        """Non-lethal adjacent reclaim for active reclaim bounty."""
        self._empathy_bootstrap_agent(agent)
        e = agent.empathy
        row = next(
            (b for b in e["bounties"] if b.get("status") == "active" and b.get("type") == "reclaim"),
            None,
        )
        if not row:
            self._empathy_feedback(agent, "info", "No active Reclaim contract.")
            return True
        ax, ay = agent.actor.x, agent.actor.y
        z = int(getattr(agent.actor, "z", 0) or 0)
        target = None
        for mon in list(getattr(self, "npcs_enemies", []) or []):
            if not getattr(mon, "alive", True):
                continue
            if getattr(mon, "synth_bounty_id", None) != row["id"]:
                continue
            if abs(mon.x - ax) + abs(mon.y - ay) <= 1 and int(getattr(mon, "z", 0) or 0) == z:
                target = mon
                break
        if not target:
            self._empathy_feedback(
                agent,
                "info",
                "Stand adjacent to the marked rogue synth (σ) to bind.",
            )
            return True
        # Success — despawn peacefully
        target.alive = False
        target.hp = 0
        row["status"] = "ready"
        self._empathy_feedback(
            agent,
            "pass",
            "Empathy bind holds — %s sleeved for Faraday reclaim. Turn in when ready."
            % (target.name,),
        )
        return True

    def _empathy_turnin(self, agent, bounty_key: str = "") -> bool:
        self._empathy_bootstrap_agent(agent)
        e = agent.empathy
        key = (bounty_key or "").strip().lower()
        candidates = [b for b in e["bounties"] if b.get("status") == "ready"]
        if key:
            candidates = [
                b
                for b in candidates
                if b["id"] == key or b["type"] == key or b["name"].lower() == key
            ]
        if not candidates:
            self._empathy_feedback(agent, "info", "Nothing ready to turn in.")
            return True
        row = candidates[0]
        spec = BOUNTY_TYPES.get(row["type"], {})
        credits = int(row.get("reward_credits") or spec.get("reward_credits") or 0)
        rep = int(row.get("reward_rep") or spec.get("reward_rep") or 0)
        heat = float(row.get("heat_on_complete") if row.get("heat_on_complete") is not None else spec.get("heat_on_complete") or 0)
        # Audit modifier for reclaim
        if row["type"] == "reclaim" and not e.get("passed_once"):
            rep = max(1, rep // 2)
            heat = abs(heat) * 0.5  # less shed / slight sting if cold
            if heat < 0:
                heat = -abs(heat)
            else:
                heat = 4.0
        agent.credits = int(getattr(agent, "credits", 0) or 0) + credits
        agent.reputation = int(getattr(agent, "reputation", 0) or 0) + rep
        if hasattr(self, "_add_heat") and heat:
            self._add_heat(
                agent,
                heat,
                "synth bounty %s" % row["type"],
            )
        row["status"] = "done"
        e["active_bounty_id"] = None
        if hasattr(self, "_grant_season_xp"):
            self._grant_season_xp(agent, 8)
        # Refresh a new available slot of same type later
        self._empathy_feedback(
            agent,
            "pass",
            "Turned in %s (+%d cr, %+d rep)." % (row["name"], credits, rep),
        )
        # Re-seed a fresh available contract of this type
        fresh = {
            "id": "%s_%s" % (row["type"], uuid.uuid4().hex[:6]),
            "type": row["type"],
            "name": spec.get("name", row["name"]),
            "desc": spec.get("desc", row.get("desc", "")),
            "status": "available",
            "target_id": None,
            "target_name": None,
            "reward_credits": int(spec.get("reward_credits", credits)),
            "reward_rep": int(spec.get("reward_rep", rep)),
            "heat_on_complete": float(spec.get("heat_on_complete", 0)),
            "hint": spec.get("hint", ""),
        }
        e["bounties"].append(fresh)
        return True

    def _empathy_abandon(self, agent) -> bool:
        self._empathy_bootstrap_agent(agent)
        e = agent.empathy
        row = next((b for b in e["bounties"] if b.get("status") == "active"), None)
        if not row:
            self._empathy_feedback(agent, "info", "No active bounty to abandon.")
            return True
        # Despawn target
        tid = row.get("target_id")
        for mon in list(getattr(self, "npcs_enemies", []) or []):
            if getattr(mon, "synth_bounty_id", None) == row["id"] or getattr(mon, "synth_id", None) == tid:
                mon.alive = False
                mon.hp = 0
        row["status"] = "available"
        row["target_id"] = None
        row["target_name"] = None
        e["active_bounty_id"] = None
        if hasattr(self, "_add_heat"):
            self._add_heat(agent, 2.0, "bounty abandon")
        self._empathy_feedback(agent, "info", "Abandoned %s (+2 heat)." % row["name"])
        return True

    def _empathy_action(self, agent, action: str, arg: str = "") -> bool:
        self._empathy_bootstrap_agent(agent)
        a = (action or "").strip().lower()
        arg = (arg or "").strip()
        arg_l = arg.lower()

        if a in (
            "empathy",
            "empathy_panel",
            "open_empathy",
            "audit_panel",
            "bounty_board",
            "synth_bounty",
            "bounties",
        ):
            agent.empathy["panel_open"] = True
            # Nested: empathy audit / empathy answer …
            if arg_l.startswith("audit"):
                return self._empathy_audit_start(agent)
            if arg_l.startswith("answer"):
                parts = arg_l.split(None, 1)
                return self._empathy_audit_answer(agent, parts[1] if len(parts) > 1 else "")
            if arg_l.startswith("accept"):
                parts = arg_l.split(None, 1)
                return self._empathy_accept_bounty(agent, parts[1] if len(parts) > 1 else "")
            if arg_l.startswith("reclaim") or arg_l == "bind":
                return self._empathy_reclaim_bind(agent)
            if arg_l.startswith("turnin") or arg_l.startswith("turn_in"):
                parts = arg_l.split(None, 1)
                return self._empathy_turnin(agent, parts[1] if len(parts) > 1 else "")
            if arg_l.startswith("abandon"):
                return self._empathy_abandon(agent)
            if arg_l in ("close", "done"):
                agent.empathy["panel_open"] = False
                agent.log("Empathy dock closed.")
                return True
            if arg_l in ("status",):
                return self._empathy_status(agent)
            self._empathy_feedback(
                agent,
                "info",
                "Empathy dock — audit (optional), bounty board retire/reclaim. "
                "Commands: empathy_audit · empathy_answer a|b|c · bounty_accept retire|reclaim · "
                "bounty_reclaim · bounty_turnin · bounty_abandon.",
            )
            return True

        if a in ("empathy_close", "close_empathy"):
            agent.empathy["panel_open"] = False
            agent.log("Empathy dock closed.")
            return True

        if a in ("empathy_audit", "audit", "start_audit", "empathy_test"):
            return self._empathy_audit_start(agent)

        if a in ("empathy_answer", "audit_answer", "answer_audit"):
            return self._empathy_audit_answer(agent, arg_l)

        if a in ("empathy_status", "audit_status", "bounty_status"):
            return self._empathy_status(agent)

        if a in ("bounty_accept", "accept_bounty", "synth_accept"):
            return self._empathy_accept_bounty(agent, arg_l)

        if a in ("bounty_reclaim", "reclaim_synth", "empathy_bind", "synth_bind"):
            return self._empathy_reclaim_bind(agent)

        if a in ("bounty_turnin", "turnin_bounty", "synth_turnin"):
            return self._empathy_turnin(agent, arg_l)

        if a in ("bounty_abandon", "abandon_bounty"):
            return self._empathy_abandon(agent)

        if a in ("bounty_list", "list_bounties"):
            agent.empathy["panel_open"] = True
            lines = []
            for b in agent.empathy["bounties"]:
                lines.append("%s[%s]" % (b["type"], b.get("status")))
            agent.log("Synth bounties: " + "; ".join(lines))
            return True

        return False

    def _empathy_status(self, agent) -> bool:
        self._empathy_bootstrap_agent(agent)
        e = agent.empathy
        agent.log(
            "Empathy: last=%s passes=%d fails=%d · board=%s"
            % (
                e.get("last_result") or "none",
                int(e.get("pass_count") or 0),
                int(e.get("fail_count") or 0),
                ", ".join("%s:%s" % (b["type"], b["status"]) for b in e["bounties"]),
            )
        )
        return True

    def _empathy_snapshot(self, agent) -> Dict[str, Any]:
        self._empathy_bootstrap_agent(agent)
        e = agent.empathy
        idx = int(e.get("audit_index") or 0)
        question = None
        if e.get("audit_active") and 0 <= idx < len(AUDIT_QUESTIONS):
            q = AUDIT_QUESTIONS[idx]
            question = {
                "id": q["id"],
                "prompt": q["prompt"],
                "index": idx + 1,
                "total": len(AUDIT_QUESTIONS),
                "choices": [{"id": c["id"], "text": c["text"]} for c in q["choices"]],
            }
        # Live target distance for active bounty
        bounties = []
        ax, ay = agent.actor.x, agent.actor.y
        for b in e["bounties"]:
            row = dict(b)
            if b.get("status") == "active" and b.get("target_id"):
                for mon in getattr(self, "npcs_enemies", []) or []:
                    if getattr(mon, "synth_bounty_id", None) == b["id"] and getattr(mon, "alive", True):
                        row["target_xy"] = [mon.x, mon.y]
                        row["dist"] = abs(mon.x - ax) + abs(mon.y - ay)
                        row["alive"] = True
                        break
            bounties.append(row)
        return {
            "panel_open": bool(e.get("panel_open")),
            "audit_active": bool(e.get("audit_active")),
            "question": question,
            "audit_score": int(e.get("audit_score") or 0),
            "last_result": e.get("last_result"),
            "passed_once": bool(e.get("passed_once")),
            "pass_count": int(e.get("pass_count") or 0),
            "fail_count": int(e.get("fail_count") or 0),
            "cooldown": max(0.0, float(e.get("cooldown_until") or 0) - time.time()),
            "bounties": bounties,
            "active_bounty_id": e.get("active_bounty_id"),
            "reputation": int(getattr(agent, "reputation", 0) or 0),
            "types": [
                {
                    "id": t["id"],
                    "name": t["name"],
                    "desc": t["desc"],
                    "reward_credits": t["reward_credits"],
                    "reward_rep": t["reward_rep"],
                    "hint": t["hint"],
                }
                for t in BOUNTY_TYPES.values()
            ],
            "last_feedback": e.get("last_feedback"),
            "hint": (
                "Optional Empathy Audit (3 scenarios) · bounty retire (wet) or reclaim (bind). "
                "Failing audits raises moral heat; reclaim favors a passed audit."
            ),
            "synth_glyph": SYNTH_GLYPH,
        }
