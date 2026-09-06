"""Sleeve / avatar hop with stat tradeoffs (#59).

Courier shells: street / club / undercity kits with clear combat tradeoffs.
Swap only at safehouse/housing. Premium shells optionally rent for credits.
Mechanics inspired by body-sleeving / class immortality tropes; prose is
**original Metaverse fiction only** (no Altered Carbon text).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .. import constants as C

# Catalog — deltas vs baseline START_* constants (applied as absolute bases).
# street: free default. club / undercity: optional credit rent each hop.
SHELL_CATALOG: Dict[str, Dict[str, Any]] = {
    "street": {
        "id": "street",
        "name": "Street Courier",
        "district": "streets",
        "tagline": "Balanced asphalt kit — free sleeve, no rent.",
        "premium": False,
        "rent_credits": 0,
        "stats": {
            "max_hp": C.START_HP,
            "max_focus": C.START_FOCUS,
            "attack": C.START_ATTACK,
            "defense": C.START_DEFENSE,
            "hack": C.START_HACK,
        },
        "tradeoffs": "Even attack / defense / hack — jack-of-all-routes.",
    },
    "club": {
        "id": "club",
        "name": "Club Glassline",
        "district": "club",
        "tagline": "Neon peacock chassis — soft plates, hot signal.",
        "premium": True,
        "rent_credits": 25,
        "stats": {
            "max_hp": C.START_HP - 6,       # 24
            "max_focus": C.START_FOCUS + 6,  # 26
            "attack": C.START_ATTACK - 1,    # 3
            "defense": C.START_DEFENSE - 1,  # 1
            "hack": C.START_HACK + 3,        # 6
        },
        "tradeoffs": "+hack +focus / −hp −defense −attack — glassline charm.",
    },
    "undercity": {
        "id": "undercity",
        "name": "Undercity Tunnel Rat",
        "district": "undercity",
        "tagline": "Thick plates for the sewers — dim signal, hard knuckles.",
        "premium": True,
        "rent_credits": 20,
        "stats": {
            "max_hp": C.START_HP + 10,       # 40
            "max_focus": C.START_FOCUS - 4,  # 16
            "attack": C.START_ATTACK + 1,    # 5
            "defense": C.START_DEFENSE + 3,  # 5
            "hack": C.START_HACK - 2,        # 1
        },
        "tradeoffs": "+hp +defense +attack / −focus −hack — tunnel armor.",
    },
}

DEFAULT_SHELL_ID = "street"


def shell_def(shell_id: str) -> Optional[Dict[str, Any]]:
    return SHELL_CATALOG.get((shell_id or "").strip().lower())


def list_shells() -> List[Dict[str, Any]]:
    return [dict(SHELL_CATALOG[k]) for k in ("street", "club", "undercity")]


class SleevesMixin:
    """Mixed into YearFeaturesMixin / GameWorld."""

    def _sleeves_init(self) -> None:
        self._sleeves_ready = True

    def _sleeves_bootstrap_agent(self, agent) -> None:
        if not isinstance(getattr(agent, "sleeves", None), dict):
            agent.sleeves = {
                "current": DEFAULT_SHELL_ID,
                "owned": [DEFAULT_SHELL_ID],
                "rented": {},  # shell_id -> True while rented this session
                "hops": 0,
                "last_rent": None,
                "panel_open": False,
            }
        else:
            sl = agent.sleeves
            sl.setdefault("current", DEFAULT_SHELL_ID)
            owned = sl.get("owned") or []
            if DEFAULT_SHELL_ID not in owned:
                owned = [DEFAULT_SHELL_ID] + list(owned)
            sl["owned"] = list(dict.fromkeys(owned))
            if not isinstance(sl.get("rented"), dict):
                sl["rented"] = {}
            sl.setdefault("hops", 0)
            sl.setdefault("last_rent", None)
            sl.setdefault("panel_open", False)
            if sl["current"] not in SHELL_CATALOG:
                sl["current"] = DEFAULT_SHELL_ID
        # Ensure actor base stats match current shell (idempotent on join)
        self._sleeves_apply_stats(agent, heal_full=False, quiet=True)

    def _sleeves_at_safehouse(self, agent) -> bool:
        housing = getattr(agent, "housing", None) or {}
        return bool(housing.get("at_home"))

    def _sleeves_can_access(self, agent, shell_id: str) -> bool:
        """Owned shells or currently rented premium shells."""
        sl = agent.sleeves
        if shell_id in (sl.get("owned") or []):
            return True
        if shell_id in (sl.get("rented") or {}):
            return True
        return False

    def _sleeves_apply_stats(self, agent, heal_full: bool = False, quiet: bool = False) -> None:
        """Rewrite actor base combat stats from the active shell definition.

        Skill bonuses (streetwise etc.) that permanently mutated actor stats
        are not re-derived here — skills still grant one-shot bumps on learn.
        Ratio of current HP/focus is preserved unless heal_full.
        """
        actor = getattr(agent, "actor", None)
        if actor is None:
            return
        sid = (agent.sleeves or {}).get("current") or DEFAULT_SHELL_ID
        defn = shell_def(sid) or SHELL_CATALOG[DEFAULT_SHELL_ID]
        stats = defn["stats"]
        old_max_hp = max(1, int(getattr(actor, "max_hp", C.START_HP) or C.START_HP))
        old_max_focus = max(1, int(getattr(actor, "max_focus", C.START_FOCUS) or C.START_FOCUS))
        hp_ratio = float(getattr(actor, "hp", old_max_hp)) / old_max_hp
        focus_ratio = float(getattr(actor, "focus", old_max_focus)) / old_max_focus

        actor.max_hp = int(stats["max_hp"])
        actor.max_focus = int(stats["max_focus"])
        actor.attack = int(stats["attack"])
        actor.defense = int(stats["defense"])
        actor.hack = int(stats["hack"])

        # Re-apply passive skill bumps that year skills already granted
        skills = getattr(agent, "skills", None) or {}
        if "streetwise" in skills:
            actor.defense += 1
        if "jacker" in skills:
            actor.hack += 1
        if "courier_legs" in skills:
            actor.max_focus += 1
        if "mono_form" in skills:
            actor.attack += 1

        if heal_full:
            actor.hp = actor.max_hp
            actor.focus = actor.max_focus
        else:
            actor.hp = max(1, min(actor.max_hp, int(round(actor.max_hp * hp_ratio))))
            actor.focus = max(0, min(actor.max_focus, int(round(actor.max_focus * focus_ratio))))
        if not quiet:
            agent.log(
                "Sleeve locked: %s — ATK %d DEF %d HACK %d · HP %d/%d · Focus %d/%d"
                % (
                    defn["name"],
                    actor.attack,
                    actor.defense,
                    actor.hack,
                    actor.hp,
                    actor.max_hp,
                    actor.focus,
                    actor.max_focus,
                )
            )

    def _sleeves_rent(self, agent, shell_id: str) -> bool:
        """Pay credits to rent a premium shell for this session."""
        self._sleeves_bootstrap_agent(agent)
        defn = shell_def(shell_id)
        if not defn:
            agent.log("Unknown shell. Catalog: street, club, undercity.")
            return True
        if not defn.get("premium"):
            agent.log("%s is free — no rent required." % defn["name"])
            return True
        if shell_id in (agent.sleeves.get("owned") or []):
            agent.log("You already own %s." % defn["name"])
            return True
        if shell_id in (agent.sleeves.get("rented") or {}):
            agent.log("%s rental already active this session." % defn["name"])
            return True
        cost = int(defn.get("rent_credits") or 0)
        credits = int(getattr(agent, "credits", 0) or 0)
        if credits < cost:
            agent.log("Need %d credits to rent %s (have %d)." % (cost, defn["name"], credits))
            return True
        agent.credits = credits - cost
        agent.sleeves.setdefault("rented", {})[shell_id] = True
        agent.sleeves["last_rent"] = {"shell_id": shell_id, "credits": cost}
        agent.log(
            "Rented %s for %d credits — hop into it at the safehouse (sleeve %s)."
            % (defn["name"], cost, shell_id)
        )
        try:
            agent.sfx("use")
        except Exception:
            pass
        return True

    def _sleeves_hop(self, agent, shell_id: str, *, force_rent: bool = False) -> bool:
        """Swap into a shell. Requires safehouse. May auto-rent premium if needed."""
        self._sleeves_bootstrap_agent(agent)
        shell_id = (shell_id or "").strip().lower()
        defn = shell_def(shell_id)
        if not defn:
            agent.log("Unknown shell id. Use: street | club | undercity")
            return True
        if not self._sleeves_at_safehouse(agent):
            agent.log(
                "Shell hop only at safehouse — enter housing first (`house`), then `sleeve %s`."
                % shell_id
            )
            return True
        if agent.sleeves.get("current") == shell_id:
            agent.log("Already sleeved as %s." % defn["name"])
            return True
        # Block while dead / cyberspace / heist
        mode = getattr(agent, "mode", None)
        if mode in ("dead", "cyberspace", "heist", "flotilla") or getattr(agent, "dead", False):
            agent.log("Cannot sleeve-hop while %s — jack out / respawn first." % (mode or "down"))
            return True

        if not self._sleeves_can_access(agent, shell_id):
            if defn.get("premium"):
                # Optional: auto-rent on hop if force_rent or enough credits
                cost = int(defn.get("rent_credits") or 0)
                credits = int(getattr(agent, "credits", 0) or 0)
                if force_rent or credits >= cost:
                    # Charge then continue
                    if credits < cost:
                        agent.log("Need %d credits to rent %s." % (cost, defn["name"]))
                        return True
                    agent.credits = credits - cost
                    agent.sleeves.setdefault("rented", {})[shell_id] = True
                    agent.sleeves["last_rent"] = {"shell_id": shell_id, "credits": cost}
                    agent.log("Rented %s (−%d credits) and hopping now." % (defn["name"], cost))
                else:
                    agent.log(
                        "%s is premium — rent first (`sleeve_rent %s`, %d cr) or bring credits to hop."
                        % (defn["name"], shell_id, cost)
                    )
                    return True
            else:
                agent.log("Shell not available.")
                return True

        agent.sleeves["current"] = shell_id
        agent.sleeves["hops"] = int(agent.sleeves.get("hops") or 0) + 1
        self._sleeves_apply_stats(agent, heal_full=True, quiet=False)
        agent.log(
            "Avatar hop complete — %s chassis online. %s"
            % (defn["name"], defn.get("tradeoffs", ""))
        )
        try:
            agent.sfx("use")
        except Exception:
            pass
        return True

    def _sleeves_snapshot(self, agent) -> Dict[str, Any]:
        self._sleeves_bootstrap_agent(agent)
        sl = agent.sleeves
        cur = sl.get("current") or DEFAULT_SHELL_ID
        defn = shell_def(cur) or SHELL_CATALOG[DEFAULT_SHELL_ID]
        shells_out = []
        for s in list_shells():
            sid = s["id"]
            accessible = self._sleeves_can_access(agent, sid)
            shells_out.append({
                "id": sid,
                "name": s["name"],
                "district": s["district"],
                "tagline": s["tagline"],
                "premium": bool(s["premium"]),
                "rent_credits": int(s["rent_credits"]),
                "stats": dict(s["stats"]),
                "tradeoffs": s["tradeoffs"],
                "owned": sid in (sl.get("owned") or []),
                "rented": sid in (sl.get("rented") or {}),
                "accessible": accessible,
                "current": sid == cur,
            })
        actor = getattr(agent, "actor", None)
        return {
            "current": cur,
            "current_name": defn["name"],
            "tradeoffs": defn.get("tradeoffs"),
            "tagline": defn.get("tagline"),
            "stats": {
                "attack": int(getattr(actor, "attack", 0) or 0) if actor else defn["stats"]["attack"],
                "defense": int(getattr(actor, "defense", 0) or 0) if actor else defn["stats"]["defense"],
                "hack": int(getattr(actor, "hack", 0) or 0) if actor else defn["stats"]["hack"],
                "max_hp": int(getattr(actor, "max_hp", 0) or 0) if actor else defn["stats"]["max_hp"],
                "max_focus": int(getattr(actor, "max_focus", 0) or 0) if actor else defn["stats"]["max_focus"],
            },
            "shells": shells_out,
            "at_safehouse": self._sleeves_at_safehouse(agent),
            "hops": int(sl.get("hops") or 0),
            "last_rent": sl.get("last_rent"),
            "panel_open": bool(sl.get("panel_open")),
            "hint": (
                "Enter safehouse (`house`) then hop street / club / undercity. "
                "Premium shells rent credits."
                if not self._sleeves_at_safehouse(agent)
                else "Safehouse locker open — pick a shell to hop."
            ),
        }

    def _sleeves_action(self, agent, action: str, arg: str = "") -> bool:
        self._sleeves_bootstrap_agent(agent)
        a = (action or "").strip().lower()
        arg = (arg or "").strip()
        arg_l = arg.lower()

        if a in ("sleeves", "sleeve_panel", "open_sleeves", "avatar_hop", "shells"):
            agent.sleeves["panel_open"] = True
            snap = self._sleeves_snapshot(agent)
            agent.log(
                "Sleeves locker — current: %s. At safehouse: %s. Catalog: street (free), "
                "club (%d cr rent), undercity (%d cr rent). Hop: sleeve <id>"
                % (
                    snap["current_name"],
                    "yes" if snap["at_safehouse"] else "no — use `house` first",
                    SHELL_CATALOG["club"]["rent_credits"],
                    SHELL_CATALOG["undercity"]["rent_credits"],
                )
            )
            return True

        if a in ("sleeve_close", "close_sleeves"):
            agent.sleeves["panel_open"] = False
            agent.log("Sleeves panel closed.")
            return True

        if a in ("sleeve_status", "shell_status", "avatar_status"):
            snap = self._sleeves_snapshot(agent)
            agent.log(
                "Sleeved as %s — %s · hops=%d · safehouse=%s"
                % (
                    snap["current_name"],
                    snap["tradeoffs"],
                    snap["hops"],
                    "yes" if snap["at_safehouse"] else "no",
                )
            )
            return True

        if a in ("sleeve_rent", "rent_sleeve", "rent_shell"):
            # arg may be "club" or empty
            sid = arg_l.split()[0] if arg_l else ""
            if not sid:
                agent.log("Usage: sleeve_rent <club|undercity>")
                return True
            return self._sleeves_rent(agent, sid)

        if a in ("sleeve", "shell", "sleeve_hop", "hop_sleeve", "avatar_sleeve"):
            # `sleeve` alone → status/panel; `sleeve club` → hop; `sleeve rent club` → rent
            parts = arg_l.split()
            if not parts:
                return self._sleeves_action(agent, "sleeves", "")
            if parts[0] in ("rent", "lease"):
                sid = parts[1] if len(parts) > 1 else ""
                if not sid:
                    agent.log("Usage: sleeve rent <club|undercity>")
                    return True
                return self._sleeves_rent(agent, sid)
            if parts[0] in ("status", "list", "info"):
                return self._sleeves_action(agent, "sleeve_status", "")
            if parts[0] in ("close",):
                return self._sleeves_action(agent, "sleeve_close", "")
            # Direct hop — auto-rent premium if player has credits
            return self._sleeves_hop(agent, parts[0], force_rent=True)

        if a in ("sleeve_street", "shell_street"):
            return self._sleeves_hop(agent, "street")
        if a in ("sleeve_club", "shell_club"):
            return self._sleeves_hop(agent, "club", force_rent=True)
        if a in ("sleeve_undercity", "shell_undercity", "sleeve_tunnel"):
            return self._sleeves_hop(agent, "undercity", force_rent=True)

        return False
