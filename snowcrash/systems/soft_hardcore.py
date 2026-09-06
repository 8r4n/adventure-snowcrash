"""Soft hardcore — opt-in death tax (#49).

On death while opted in: lose a percentage of street credits and drop one
non-quest inventory item onto the street. Levels and XP are kept. Quest gear,
Signal Keys, Payload-Zero, and wish tokens stay sleeved. Default OFF so casual
flatlines are unchanged. Original Metaverse prose only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..items import Item
from ..mapgen import FloorItem

# Direct credit burn on soft-hardcore death (clear, not debt-first).
HARDCORE_CREDIT_LOSS_PCT = 0.20

PROTECTED_KINDS = frozenset({"quest", "wish"})
PROTECTED_IDS = frozenset({"payload_zero"})


def is_hardcore_protected(item: Item) -> bool:
    """Quest / key / critical sleeve items never drop on soft-hardcore death."""
    if not item:
        return True
    if bool(getattr(item, "quest", False)):
        return True
    kind = (getattr(item, "kind", "") or "").lower()
    if kind in PROTECTED_KINDS:
        return True
    iid = getattr(item, "id", "") or ""
    if iid in PROTECTED_IDS or iid.startswith("signal_key"):
        return True
    extra = getattr(item, "extra", None) or {}
    if extra.get("signal_key") or extra.get("quest_flag"):
        return True
    return False


class SoftHardcoreMixin:
    """Mixed into YearFeaturesMixin / GameWorld."""

    def _soft_hardcore_init(self) -> None:
        # No world-level state required; agent fields hold the flag + last penalty.
        self._soft_hardcore_ready = True

    def _soft_hardcore_bootstrap_agent(self, agent) -> None:
        if not isinstance(getattr(agent, "soft_hardcore", None), dict):
            agent.soft_hardcore = {
                "enabled": False,
                "debt": 0,
                "last_penalty": None,
                "deaths": 0,
            }
            return
        sh = agent.soft_hardcore
        sh.setdefault("enabled", False)
        sh.setdefault("debt", 0)
        sh.setdefault("last_penalty", None)
        sh.setdefault("deaths", 0)
        sh["enabled"] = bool(sh.get("enabled"))
        sh["debt"] = max(0, int(sh.get("debt") or 0))
        sh["deaths"] = max(0, int(sh.get("deaths") or 0))

    def _soft_hardcore_set(self, agent, enabled: bool) -> None:
        self._soft_hardcore_bootstrap_agent(agent)
        agent.soft_hardcore["enabled"] = bool(enabled)
        if enabled:
            agent.log(
                "Soft hardcore ON — flatline burns %d%% credits and sheds one non-quest sleeve item. "
                "Levels stay. Quest gear and Signal Keys stay locked."
                % int(HARDCORE_CREDIT_LOSS_PCT * 100)
            )
        else:
            agent.log("Soft hardcore OFF — casual death rules restored.")

    def _soft_hardcore_drop_candidates(self, agent) -> List[Tuple[int, Item]]:
        inv = list(getattr(getattr(agent, "actor", None), "inventory", None) or [])
        out: List[Tuple[int, Item]] = []
        for idx, it in enumerate(inv):
            if is_hardcore_protected(it):
                continue
            out.append((idx, it))
        return out

    def _soft_hardcore_pick_drop(self, agent) -> Optional[Tuple[int, Item]]:
        cands = self._soft_hardcore_drop_candidates(agent)
        if not cands:
            return None
        # Prefer unequipped junk first (softer), then anything unprotected.
        soft = [(i, it) for i, it in cands if not getattr(it, "equipped", False)]
        pool = soft or cands
        rng = getattr(self, "rng", None)
        if rng is not None:
            return rng.choice(pool)
        return pool[0]

    def _soft_hardcore_apply_death_penalty(self, agent, killer_name: str = "unknown") -> Dict[str, Any]:
        """Apply opt-in death tax. Safe no-op when disabled. Returns penalty summary."""
        self._soft_hardcore_bootstrap_agent(agent)
        sh = agent.soft_hardcore
        if not sh.get("enabled"):
            return {"applied": False}

        credits_before = int(getattr(agent, "credits", 0) or 0)
        level_before = int(getattr(agent, "level", 1) or 1)
        xp_before = int(getattr(agent, "xp", 0) or 0)

        lost = int(credits_before * HARDCORE_CREDIT_LOSS_PCT)
        # When courier is broke, bank a small street debt instead of a no-op tax.
        debt_added = 0
        if lost <= 0 and credits_before <= 0:
            debt_added = 5
            sh["debt"] = int(sh.get("debt") or 0) + debt_added
        else:
            agent.credits = max(0, credits_before - lost)

        dropped_name = None
        dropped_id = None
        pick = self._soft_hardcore_pick_drop(agent)
        if pick is not None:
            idx, item = pick
            inv = agent.actor.inventory
            # Re-find by identity in case indices shifted (should not)
            if 0 <= idx < len(inv) and inv[idx] is item:
                inv.pop(idx)
            else:
                for j, it in enumerate(list(inv)):
                    if it is item:
                        inv.pop(j)
                        break
            item.equipped = False
            ax = int(getattr(agent.actor, "x", 0) or 0)
            ay = int(getattr(agent.actor, "y", 0) or 0)
            az = int(getattr(agent.actor, "z", 0) or 0)
            floor = getattr(self, "floor_items", None)
            if isinstance(floor, list):
                floor.append(FloorItem(ax, ay, item, z=az))
            dropped_name = item.name
            dropped_id = item.id

        # Levels / XP untouched by design (level_before / xp_before recorded below).

        parts = []
        if lost > 0:
            parts.append("−%d credits (%d%% sleeve burn)" % (lost, int(HARDCORE_CREDIT_LOSS_PCT * 100)))
        elif debt_added:
            parts.append("+%d hardcore debt (empty wallet)" % debt_added)
        else:
            parts.append("no credit burn (wallet empty, no new debt this tick)")
        if dropped_name:
            parts.append("dropped %s on the asphalt" % dropped_name)
        else:
            parts.append("no droppable non-quest gear")
        summary = "Soft hardcore tax: " + "; ".join(parts) + "."

        penalty = {
            "applied": True,
            "credits_before": credits_before,
            "credits_lost": lost,
            "debt_added": debt_added,
            "debt": int(sh.get("debt") or 0),
            "item_dropped": dropped_name,
            "item_dropped_id": dropped_id,
            "level_kept": level_before,
            "xp_kept": xp_before,
            "killer": killer_name,
            "summary": summary,
        }
        sh["last_penalty"] = penalty
        sh["deaths"] = int(sh.get("deaths") or 0) + 1

        agent.log(summary)
        agent.log("Levels and XP held. Quest / Signal Key sleeves stay locked.")
        return penalty

    def _soft_hardcore_death_cause(self, agent, killer_name: str = "unknown") -> str:
        self._soft_hardcore_bootstrap_agent(agent)
        base = "Flatlined by %s." % (killer_name or "unknown")
        sh = agent.soft_hardcore
        if not sh.get("enabled"):
            return base + " Press r to respawn."
        pen = sh.get("last_penalty") or {}
        if pen.get("applied"):
            return base + " Soft hardcore: " + str(pen.get("summary") or "tax applied.")
        return base + " Soft hardcore is on — tax applies on this flatline."

    def _soft_hardcore_snapshot(self, agent) -> Dict[str, Any]:
        self._soft_hardcore_bootstrap_agent(agent)
        sh = agent.soft_hardcore
        last = sh.get("last_penalty")
        return {
            "enabled": bool(sh.get("enabled")),
            "debt": int(sh.get("debt") or 0),
            "deaths": int(sh.get("deaths") or 0),
            "credit_loss_pct": HARDCORE_CREDIT_LOSS_PCT,
            "last_penalty": dict(last) if isinstance(last, dict) else None,
        }

    def _soft_hardcore_action(self, agent, action: str, arg: str = "") -> bool:
        self._soft_hardcore_bootstrap_agent(agent)
        a = (action or "").strip().lower()
        arg = (arg or "").strip().lower()

        if a in ("hardcore", "soft_hardcore", "hardcore_status", "soft_hardcore_status"):
            if arg in ("on", "1", "true", "enable", "optin", "opt_in"):
                self._soft_hardcore_set(agent, True)
                return True
            if arg in ("off", "0", "false", "disable", "optout", "opt_out"):
                self._soft_hardcore_set(agent, False)
                return True
            snap = self._soft_hardcore_snapshot(agent)
            state = "ON" if snap["enabled"] else "OFF"
            agent.log(
                "Soft hardcore %s — death burns %d%% credits + one non-quest drop; levels kept. "
                "Debt=%d. Toggle: hardcore on|off"
                % (state, int(HARDCORE_CREDIT_LOSS_PCT * 100), snap["debt"])
            )
            last = snap.get("last_penalty")
            if last and last.get("summary"):
                agent.log("Last tax: %s" % last["summary"])
            return True

        if a in ("hardcore_on", "soft_hardcore_on", "hardcore_optin"):
            self._soft_hardcore_set(agent, True)
            return True
        if a in ("hardcore_off", "soft_hardcore_off", "hardcore_optout"):
            self._soft_hardcore_set(agent, False)
            return True

        if a in ("pay_hardcore_debt", "hardcore_debt"):
            debt = int(agent.soft_hardcore.get("debt") or 0)
            if debt <= 0:
                agent.log("No soft-hardcore debt on the ledger.")
                return True
            credits = int(getattr(agent, "credits", 0) or 0)
            pay = min(debt, credits)
            if pay <= 0:
                agent.log("Need credits to clear hardcore debt (%d owed)." % debt)
                return True
            agent.credits = credits - pay
            agent.soft_hardcore["debt"] = debt - pay
            agent.log("Paid %d hardcore debt (%d remains)." % (pay, agent.soft_hardcore["debt"]))
            return True

        return False
