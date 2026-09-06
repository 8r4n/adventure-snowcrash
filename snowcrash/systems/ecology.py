"""Scarce resource ecology wars on globe regions (#57).

Dune-*inspired* planetary ecology / resource control — remix as StreetNet
**bandwidth**, **condensate water**, and **uplink spectrum** wars. Original
Metaverse lore only (no Arrakis / spice clones).

Globe regions (#54) host contested nodes; crews/corps flip control via
resource contracts and raids; weather/ecology labels shift with control.
Visible on globe pins + StreetNet ticker / Ecology dock.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DATA_DIR = Path(__file__).resolve().parent / "data"

DEFAULT_CLAIM_FOCUS = 3
DEFAULT_CLAIM_CREDITS = 20
DEFAULT_RAID_FOCUS = 4
DEFAULT_RAID_CREDITS = 25
DEFAULT_COOLDOWN = 40.0
DEFAULT_TICK_INTERVAL = 55


def _load_ecology_doc() -> Dict[str, Any]:
    path = DATA_DIR / "ecology.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _ctrl_copy(ctrl: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(ctrl, dict):
        return {"kind": "commons", "id": "streetnet", "name": "StreetNet Commons"}
    return {
        "kind": str(ctrl.get("kind") or "commons"),
        "id": str(ctrl.get("id") or "streetnet"),
        "name": str(ctrl.get("name") or "StreetNet Commons"),
    }


class EcologyMixin:
    """Mixed into YearFeaturesMixin / GameWorld — scarce resource ecology wars."""

    def _ecology_init(self) -> None:
        doc = _load_ecology_doc()
        self.ecology_defs = doc
        self.ecology_resources: Dict[str, Dict[str, Any]] = {
            str(k): dict(v) for k, v in (doc.get("resources") or {}).items()
        }
        self.ecology_claim_focus = int(doc.get("claim_focus_cost", DEFAULT_CLAIM_FOCUS))
        self.ecology_claim_credits = int(doc.get("claim_credit_cost", DEFAULT_CLAIM_CREDITS))
        self.ecology_raid_focus = int(doc.get("raid_focus_cost", DEFAULT_RAID_FOCUS))
        self.ecology_raid_credits = int(doc.get("raid_credit_cost", DEFAULT_RAID_CREDITS))
        self.ecology_contract_reward = int(doc.get("contract_reward_credits", 45))
        self.ecology_contract_rep = int(doc.get("contract_reward_rep", 8))
        self.ecology_cooldown = float(doc.get("contest_cooldown_sec", DEFAULT_COOLDOWN))
        self.ecology_tick_interval = int(doc.get("ecology_tick_interval", DEFAULT_TICK_INTERVAL))
        self.ecology_weather_by_resource = dict(doc.get("weather_by_resource") or {})

        self.ecology_nodes: Dict[str, Dict[str, Any]] = {}
        for raw in doc.get("nodes") or []:
            nid = str(raw.get("id") or "")
            if not nid:
                continue
            node = dict(raw)
            node["id"] = nid
            node["controller"] = _ctrl_copy(raw.get("default_controller"))
            node["pressure"] = 0.35
            node["flips"] = 0
            node["last_flip_at"] = 0.0
            node["last_flip_by"] = None
            node["contest_log"] = []
            self.ecology_nodes[nid] = node

        self.ecology_raids: Dict[str, Dict[str, Any]] = {}
        self.ecology_streetnet: List[Dict[str, Any]] = []
        self._ecology_last_tick_at = 0

        n = len(self.ecology_nodes)
        regions = {n["region_id"] for n in self.ecology_nodes.values()}
        self._push_event(
            "broadcast",
            "StreetNet ecology lattice online — %d scarce nodes across %d regions "
            "(bandwidth / water / uplink spectrum) (#57)."
            % (n, len(regions)),
        )

    def reload_ecology_defs(self) -> None:
        """Hot-reload ecology.json; preserve live controllers when node ids match."""
        doc = _load_ecology_doc()
        self.ecology_defs = doc
        self.ecology_resources = {
            str(k): dict(v) for k, v in (doc.get("resources") or {}).items()
        }
        self.ecology_claim_focus = int(doc.get("claim_focus_cost", DEFAULT_CLAIM_FOCUS))
        self.ecology_claim_credits = int(doc.get("claim_credit_cost", DEFAULT_CLAIM_CREDITS))
        self.ecology_raid_focus = int(doc.get("raid_focus_cost", DEFAULT_RAID_FOCUS))
        self.ecology_raid_credits = int(doc.get("raid_credit_cost", DEFAULT_RAID_CREDITS))
        self.ecology_contract_reward = int(doc.get("contract_reward_credits", 45))
        self.ecology_contract_rep = int(doc.get("contract_reward_rep", 8))
        self.ecology_cooldown = float(doc.get("contest_cooldown_sec", DEFAULT_COOLDOWN))
        self.ecology_tick_interval = int(doc.get("ecology_tick_interval", DEFAULT_TICK_INTERVAL))
        self.ecology_weather_by_resource = dict(doc.get("weather_by_resource") or {})
        prev = dict(self.ecology_nodes)
        self.ecology_nodes = {}
        for raw in doc.get("nodes") or []:
            nid = str(raw.get("id") or "")
            if not nid:
                continue
            node = dict(raw)
            node["id"] = nid
            if nid in prev:
                node["controller"] = _ctrl_copy(prev[nid].get("controller"))
                node["pressure"] = float(prev[nid].get("pressure", 0.35))
                node["flips"] = int(prev[nid].get("flips", 0))
                node["last_flip_at"] = float(prev[nid].get("last_flip_at", 0))
                node["last_flip_by"] = prev[nid].get("last_flip_by")
                node["contest_log"] = list(prev[nid].get("contest_log") or [])
            else:
                node["controller"] = _ctrl_copy(raw.get("default_controller"))
                node["pressure"] = 0.35
                node["flips"] = 0
                node["last_flip_at"] = 0.0
                node["last_flip_by"] = None
                node["contest_log"] = []
            self.ecology_nodes[nid] = node

    def _ecology_bootstrap_agent(self, agent) -> None:
        eco = getattr(agent, "ecology", None)
        if not isinstance(eco, dict):
            eco = {}
        eco.setdefault("panel_open", False)
        eco.setdefault("cooldown_until", 0.0)
        eco.setdefault("claims", 0)
        eco.setdefault("raids", 0)
        eco.setdefault("active_contract_node", None)
        eco.setdefault("active_raid_id", None)
        eco.setdefault("last_feedback", None)
        agent.ecology = eco

    def _ecology_feedback(self, agent, kind: str, text: str) -> None:
        self._ecology_bootstrap_agent(agent)
        agent.ecology["last_feedback"] = {"kind": kind, "text": text, "t": time.time()}
        agent.log(text)

    def _ecology_resource(self, resource_id: str) -> Dict[str, Any]:
        return dict(self.ecology_resources.get(str(resource_id)) or {"id": resource_id, "name": resource_id, "short": resource_id})

    def _ecology_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self.ecology_nodes.get(str(node_id or ""))

    def _ecology_nodes_for_region(self, region_id: str) -> List[Dict[str, Any]]:
        rid = str(region_id or "")
        return [n for n in self.ecology_nodes.values() if str(n.get("region_id")) == rid]

    def _ecology_agent_faction(self, agent) -> Dict[str, Any]:
        """Resolve claiming faction — prefer crew, else solo courier corp-tag."""
        self._ecology_bootstrap_agent(agent)
        crew_id = getattr(agent, "crew_id", None)
        crews = getattr(self, "crews", None) or {}
        if crew_id and crew_id in crews:
            c = crews[crew_id]
            return {
                "kind": "crew",
                "id": str(c.get("id") or crew_id),
                "name": str(c.get("name") or "Crew"),
            }
        # Solo courier acts as a micro-corp sleeve
        return {
            "kind": "courier",
            "id": "courier_%s" % getattr(agent, "id", "x"),
            "name": "%s · Solo Sleeve" % getattr(agent, "name", "Courier"),
        }

    def _ecology_same_ctrl(self, a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        return (
            str(a.get("kind")) == str(b.get("kind"))
            and str(a.get("id")) == str(b.get("id"))
        )

    def _ecology_streetnet_push(self, text: str, **extra: Any) -> None:
        row = {"t": time.time(), "tick": int(getattr(self, "tick", 0) or 0), "text": text, **extra}
        self.ecology_streetnet.append(row)
        if len(self.ecology_streetnet) > 24:
            self.ecology_streetnet = self.ecology_streetnet[-24:]
        self._push_event("ecology", text, **extra)
        if hasattr(self, "system_chat"):
            # Keep StreetNet IRC visible without spamming every ambient tick
            if extra.get("chat", True):
                self.system_chat(text)

    def _ecology_apply_weather(self, node: Dict[str, Any], *, friendly: bool) -> None:
        """Shift world weather label from the contested resource ecology."""
        rid = str(node.get("resource") or "")
        table = (self.ecology_weather_by_resource or {}).get(rid) or {}
        key = "friendly" if friendly else "hostile"
        weather = dict(table.get(key) or {})
        if not weather:
            return
        until = int(getattr(self, "tick", 0) or 0) + 90
        self.weather_state = {
            "id": str(weather.get("id") or "ecology_shift"),
            "label": str(weather.get("label") or "Ecology shift"),
            "until_tick": until,
            "ecology_node": node.get("id"),
            "ecology_resource": rid,
            "ecology_friendly": bool(friendly),
        }

    def _ecology_flip(
        self,
        node: Dict[str, Any],
        new_ctrl: Dict[str, Any],
        *,
        agent=None,
        via: str = "contest",
    ) -> None:
        old = _ctrl_copy(node.get("controller"))
        node["controller"] = _ctrl_copy(new_ctrl)
        node["flips"] = int(node.get("flips") or 0) + 1
        node["last_flip_at"] = time.time()
        node["last_flip_by"] = getattr(agent, "name", None) if agent else None
        node["pressure"] = min(1.0, float(node.get("pressure") or 0.35) + 0.12)
        log = list(node.get("contest_log") or [])
        log.append(
            {
                "t": time.time(),
                "via": via,
                "from": old,
                "to": _ctrl_copy(new_ctrl),
                "agent": getattr(agent, "name", None) if agent else None,
            }
        )
        node["contest_log"] = log[-8:]

        res = self._ecology_resource(str(node.get("resource")))
        region_name = str(node.get("region_id") or "")
        if hasattr(self, "_globe_region"):
            reg = self._globe_region(region_name) or {}
            region_name = str(reg.get("name") or region_name)

        msg = (
            "Ecology flip — %s (%s) on %s: %s → %s [%s]."
            % (
                node.get("name") or node.get("id"),
                res.get("short") or res.get("id"),
                region_name,
                old.get("name"),
                new_ctrl.get("name"),
                via,
            )
        )
        self._ecology_streetnet_push(
            msg,
            node_id=node.get("id"),
            region_id=node.get("region_id"),
            resource=node.get("resource"),
            via=via,
            chat=True,
        )
        # Holder ecology is "friendly" for the winning side's weather bias
        self._ecology_apply_weather(node, friendly=True)

    def _ecology_ensure_contract(self, agent, node_id: str) -> Dict[str, Any]:
        """Attach / refresh a scarce-resource claim contract on the courier."""
        self._ecology_bootstrap_agent(agent)
        node = self._ecology_node(node_id)
        if not node:
            raise KeyError(node_id)
        res = self._ecology_resource(str(node.get("resource")))
        contracts = list(getattr(agent, "contracts", []) or [])
        cid = "ecology_%s" % node_id
        existing = next((c for c in contracts if c.get("id") == cid), None)
        if existing:
            existing["status"] = "active"
            existing["progress"] = int(existing.get("progress") or 0)
            existing["goal"] = 1
            existing["kind"] = "ecology_claim"
            existing["ecology_node"] = node_id
            agent.contracts = contracts
            agent.ecology["active_contract_node"] = node_id
            return existing
        row = {
            "id": cid,
            "name": "Claim %s" % (node.get("name") or node_id),
            "desc": "Contest %s node — hop to region, claim or raid (#57)."
            % (res.get("short") or "resource"),
            "goal": 1,
            "kind": "ecology_claim",
            "progress": 0,
            "status": "active",
            "reward_credits": int(self.ecology_contract_reward),
            "reward_rep": int(self.ecology_contract_rep),
            "ecology_node": node_id,
            "region_id": node.get("region_id"),
            "resource": node.get("resource"),
        }
        contracts.append(row)
        agent.contracts = contracts
        agent.ecology["active_contract_node"] = node_id
        return row

    def _ecology_complete_contract(self, agent, node_id: str) -> None:
        contracts = list(getattr(agent, "contracts", []) or [])
        cid = "ecology_%s" % node_id
        for c in contracts:
            if c.get("id") == cid or (
                c.get("kind") == "ecology_claim" and c.get("ecology_node") == node_id
            ):
                c["progress"] = max(int(c.get("goal") or 1), int(c.get("progress") or 0) + 1)
                if c["progress"] >= int(c.get("goal") or 1):
                    c["status"] = "ready"
                    # Auto-turnin scarce-resource contract
                    if c.get("status") == "ready":
                        reward = int(c.get("reward_credits") or self.ecology_contract_reward)
                        rep = int(c.get("reward_rep") or self.ecology_contract_rep)
                        agent.credits = int(getattr(agent, "credits", 0) or 0) + reward
                        agent.reputation = int(getattr(agent, "reputation", 0) or 0) + rep
                        c["status"] = "done"
                        agent.log(
                            "Resource contract cleared — +%d cr / +%d rep (%s)."
                            % (reward, rep, c.get("name") or cid)
                        )
                        if hasattr(self, "_grant_season_xp"):
                            self._grant_season_xp(agent, 4)
        agent.contracts = contracts
        if getattr(agent, "ecology", None):
            if agent.ecology.get("active_contract_node") == node_id:
                agent.ecology["active_contract_node"] = None

    def _ecology_require_region(self, agent, node: Dict[str, Any]) -> bool:
        """Courier must be sleeved in the node's globe region."""
        rid = str(node.get("region_id") or "")
        if hasattr(self, "_globe_agent_region"):
            cur = self._globe_agent_region(agent)
            if cur != rid:
                reg = {}
                if hasattr(self, "_globe_region"):
                    reg = self._globe_region(rid) or {}
                self._ecology_feedback(
                    agent,
                    "error",
                    "Not in node region — teleport to %s (%s) first."
                    % (reg.get("name") or rid, rid),
                )
                return False
        return True

    def _ecology_cooldown_ok(self, agent) -> bool:
        self._ecology_bootstrap_agent(agent)
        now = time.time()
        until = float(agent.ecology.get("cooldown_until") or 0)
        if now < until:
            left = int(until - now) + 1
            self._ecology_feedback(
                agent, "error", "Ecology contest cooldown — %ds remaining." % left
            )
            return False
        return True

    def _ecology_claim(self, agent, node_id: str) -> bool:
        """Contract-style claim: spend focus+credits in-region to flip control."""
        self._ecology_bootstrap_agent(agent)
        nid = (node_id or "").strip()
        node = self._ecology_node(nid)
        if not node:
            # Allow region_id shorthand → first node on that region
            matches = self._ecology_nodes_for_region(nid)
            if matches:
                node = matches[0]
                nid = str(node["id"])
            else:
                self._ecology_feedback(
                    agent,
                    "error",
                    "Unknown ecology node. Try ecology_list or ecology_claim <node_id>.",
                )
                return True
        if not self._ecology_require_region(agent, node):
            return True
        if not self._ecology_cooldown_ok(agent):
            return True
        mode = getattr(agent, "mode", "play")
        if mode in ("cyberspace", "heist", "flotilla", "dead", "won", "pilgrimage"):
            self._ecology_feedback(
                agent, "error", "Cannot claim ecology nodes while %s." % mode
            )
            return True

        faction = self._ecology_agent_faction(agent)
        ctrl = _ctrl_copy(node.get("controller"))
        if self._ecology_same_ctrl(ctrl, faction):
            self._ecology_feedback(
                agent,
                "info",
                "Already hold %s (%s)." % (node.get("name"), ctrl.get("name")),
            )
            return True

        focus_cost = int(self.ecology_claim_focus)
        credit_cost = int(self.ecology_claim_credits)
        focus = int(getattr(agent.actor, "focus", 0) or 0)
        credits = int(getattr(agent, "credits", 0) or 0)
        if focus < focus_cost:
            self._ecology_feedback(
                agent, "error", "Need %d Focus to run the claim contract." % focus_cost
            )
            return True
        if credits < credit_cost:
            self._ecology_feedback(
                agent,
                "error",
                "Need %d credits for claim paperwork (have %d)." % (credit_cost, credits),
            )
            return True

        # Ensure contract exists, then flip
        self._ecology_ensure_contract(agent, nid)
        agent.actor.focus = max(0, focus - focus_cost)
        agent.credits = max(0, credits - credit_cost)
        agent.ecology["cooldown_until"] = time.time() + float(self.ecology_cooldown)
        agent.ecology["claims"] = int(agent.ecology.get("claims") or 0) + 1

        self._ecology_flip(node, faction, agent=agent, via="contract")
        self._ecology_complete_contract(agent, nid)
        res = self._ecology_resource(str(node.get("resource")))
        self._ecology_feedback(
            agent,
            "ok",
            "Claim sealed — %s now flies your colors (−%d Focus / −%d cr). %s"
            % (
                node.get("name"),
                focus_cost,
                credit_cost,
                res.get("ecology_held") or "",
            ),
        )
        if hasattr(self, "_primer_note_progress"):
            self._primer_note_progress(agent, "ecology_claim", 1)
        return True

    def _ecology_raid(self, agent, node_id: str) -> bool:
        """Raid-style flip: party/crew raid instance contests the node."""
        self._ecology_bootstrap_agent(agent)
        nid = (node_id or "").strip()
        node = self._ecology_node(nid)
        if not node:
            matches = self._ecology_nodes_for_region(nid)
            if matches:
                node = matches[0]
                nid = str(node["id"])
            else:
                self._ecology_feedback(
                    agent,
                    "error",
                    "Unknown ecology node for raid. Usage: ecology_raid <node_id>",
                )
                return True
        if not self._ecology_require_region(agent, node):
            return True
        if not self._ecology_cooldown_ok(agent):
            return True
        mode = getattr(agent, "mode", "play")
        if mode in ("cyberspace", "heist", "flotilla", "dead", "won", "pilgrimage"):
            self._ecology_feedback(
                agent, "error", "Cannot raid ecology nodes while %s." % mode
            )
            return True

        faction = self._ecology_agent_faction(agent)
        ctrl = _ctrl_copy(node.get("controller"))
        if self._ecology_same_ctrl(ctrl, faction):
            self._ecology_feedback(
                agent, "info", "You already control %s — no raid needed." % node.get("name")
            )
            return True

        focus_cost = int(self.ecology_raid_focus)
        credit_cost = int(self.ecology_raid_credits)
        focus = int(getattr(agent.actor, "focus", 0) or 0)
        credits = int(getattr(agent, "credits", 0) or 0)
        if focus < focus_cost:
            self._ecology_feedback(
                agent, "error", "Need %d Focus to open a resource raid." % focus_cost
            )
            return True
        if credits < credit_cost:
            self._ecology_feedback(
                agent,
                "error",
                "Need %d credits to stage the raid (have %d)." % (credit_cost, credits),
            )
            return True

        # Build raid instance (ties into #35 raid surface)
        members = [agent.id]
        if getattr(agent, "party_id", None) and agent.party_id in getattr(self, "parties", {}):
            members = list(self.parties[agent.party_id]["members"])[:5]
        if getattr(agent, "crew_id", None) and agent.crew_id in getattr(self, "crews", {}):
            # Prefer crew roster when present (still cap 5)
            crew_members = list(self.crews[agent.crew_id].get("members") or [])
            if crew_members:
                members = crew_members[:5]
        if agent.id not in members:
            members = [agent.id] + [m for m in members if m != agent.id]
            members = members[:5]

        rid = "eco_" + uuid.uuid4().hex[:8]
        raid = {
            "id": rid,
            "kind": "ecology",
            "node_id": nid,
            "region_id": node.get("region_id"),
            "resource": node.get("resource"),
            "members": members,
            "started": time.time(),
            "boss_hp": 60,
            "target_controller": ctrl,
            "lockout_sec": 180,
        }
        self.ecology_raids[rid] = raid
        # Mirror into world raid_instances for snapshot compatibility (#35)
        if hasattr(self, "raid_instances") and isinstance(self.raid_instances, dict):
            self.raid_instances[rid] = {
                "id": rid,
                "members": members,
                "boss_hp": 60,
                "started": time.time(),
                "lockout_sec": 180,
                "ecology_node": nid,
                "kind": "ecology",
            }

        agent.actor.focus = max(0, focus - focus_cost)
        agent.credits = max(0, credits - credit_cost)
        agent.ecology["cooldown_until"] = time.time() + float(self.ecology_cooldown)
        agent.ecology["raids"] = int(agent.ecology.get("raids") or 0) + 1
        agent.ecology["active_raid_id"] = rid
        agent.raid_id = rid

        for mid in members:
            m = (getattr(self, "players", {}) or {}).get(mid)
            if m:
                m.raid_id = rid
                if hasattr(m, "ecology") or True:
                    self._ecology_bootstrap_agent(m)
                    m.ecology["active_raid_id"] = rid
                    m.log(
                        "Ecology raid %s on %s — hold the node. ecology_raid_resolve to seal."
                        % (rid, node.get("name"))
                    )

        # Instant resolve for solo/stub playability (full multiplayer can extend)
        return self._ecology_raid_resolve(agent, rid, force=True)

    def _ecology_raid_resolve(self, agent, raid_id: str = "", *, force: bool = False) -> bool:
        self._ecology_bootstrap_agent(agent)
        rid = (raid_id or agent.ecology.get("active_raid_id") or getattr(agent, "raid_id", None) or "").strip()
        raid = self.ecology_raids.get(rid)
        if not raid and hasattr(self, "raid_instances"):
            inst = (self.raid_instances or {}).get(rid)
            if inst and inst.get("kind") == "ecology":
                raid = inst
        if not raid:
            self._ecology_feedback(agent, "error", "No active ecology raid to resolve.")
            return True
        nid = str(raid.get("node_id") or raid.get("ecology_node") or "")
        node = self._ecology_node(nid)
        if not node:
            self._ecology_feedback(agent, "error", "Raid node missing — aborting.")
            self._ecology_raid_cleanup(rid)
            return True

        faction = self._ecology_agent_faction(agent)
        # Stub clear: deplete boss_hp and flip
        raid["boss_hp"] = 0
        self._ecology_ensure_contract(agent, nid)
        self._ecology_flip(node, faction, agent=agent, via="raid")
        self._ecology_complete_contract(agent, nid)
        self._ecology_raid_cleanup(rid)
        agent.raid_lockout_until = time.time() + float(raid.get("lockout_sec") or 180)
        res = self._ecology_resource(str(node.get("resource")))
        self._ecology_feedback(
            agent,
            "ok",
            "Resource raid cleared — %s seized. %s"
            % (node.get("name"), res.get("ecology_held") or ""),
        )
        return True

    def _ecology_raid_cleanup(self, raid_id: str) -> None:
        raid = self.ecology_raids.pop(raid_id, None)
        if hasattr(self, "raid_instances"):
            self.raid_instances.pop(raid_id, None)
        members = list((raid or {}).get("members") or [])
        for mid in members:
            m = (getattr(self, "players", {}) or {}).get(mid)
            if not m:
                continue
            if getattr(m, "raid_id", None) == raid_id:
                m.raid_id = None
            self._ecology_bootstrap_agent(m)
            if m.ecology.get("active_raid_id") == raid_id:
                m.ecology["active_raid_id"] = None

    def _ecology_contract_offer(self, agent, node_id: str = "") -> bool:
        """List / accept a scarce-resource contract without flipping yet."""
        self._ecology_bootstrap_agent(agent)
        nid = (node_id or "").strip()
        if not nid:
            # Offer first uncontrolled / corp-held node as suggestion
            faction = self._ecology_agent_faction(agent)
            pick = None
            for n in self.ecology_nodes.values():
                if not self._ecology_same_ctrl(_ctrl_copy(n.get("controller")), faction):
                    pick = n
                    break
            if not pick:
                pick = next(iter(self.ecology_nodes.values()), None)
            if not pick:
                self._ecology_feedback(agent, "error", "No ecology nodes configured.")
                return True
            nid = str(pick["id"])
        node = self._ecology_node(nid)
        if not node:
            matches = self._ecology_nodes_for_region(nid)
            node = matches[0] if matches else None
            nid = str(node["id"]) if node else nid
        if not node:
            self._ecology_feedback(agent, "error", "Unknown node for ecology contract.")
            return True
        row = self._ecology_ensure_contract(agent, nid)
        res = self._ecology_resource(str(node.get("resource")))
        agent.ecology["panel_open"] = True
        self._ecology_feedback(
            agent,
            "ok",
            "Contract live: %s — hop to %s, then ecology_claim %s or ecology_raid %s (%s)."
            % (
                row.get("name"),
                node.get("region_id"),
                nid,
                nid,
                res.get("short"),
            ),
        )
        return True

    def _tick_ecology(self) -> None:
        """Ambient pressure + ecology weather drift when nodes are contested."""
        interval = max(20, int(self.ecology_tick_interval or DEFAULT_TICK_INTERVAL))
        tick = int(getattr(self, "tick", 0) or 0)
        if tick <= 0 or tick % interval != 0:
            return
        if not self.ecology_nodes:
            return
        # Mild pressure drift; announce one ambient StreetNet beat
        rng = getattr(self, "rng", None)
        nodes = list(self.ecology_nodes.values())
        if not nodes:
            return
        if rng is not None:
            node = rng.choice(nodes)
            delta = (rng.random() - 0.45) * 0.08
        else:
            node = nodes[tick % len(nodes)]
            delta = 0.02
        node["pressure"] = max(0.05, min(1.0, float(node.get("pressure") or 0.35) + delta))
        ctrl = _ctrl_copy(node.get("controller"))
        res = self._ecology_resource(str(node.get("resource")))
        # Hostile ecology bias when corp holds commons-feeling resources at high pressure
        friendly = ctrl.get("kind") in ("crew", "commons", "courier")
        if float(node.get("pressure") or 0) >= 0.72 and ctrl.get("kind") == "corp":
            friendly = False
            self._ecology_apply_weather(node, friendly=False)
        elif float(node.get("pressure") or 0) <= 0.28 and friendly:
            self._ecology_apply_weather(node, friendly=True)
        # Soft StreetNet ticker (no IRC spam every tick — only every other ecology tick)
        if tick // interval % 2 == 0:
            region = str(node.get("region_id") or "")
            if hasattr(self, "_globe_region"):
                region = str((self._globe_region(region) or {}).get("name") or region)
            line = (
                "StreetNet ecology: %s · %s held by %s (pressure %d%%)."
                % (
                    node.get("name") or node.get("id"),
                    res.get("short") or res.get("id"),
                    ctrl.get("name"),
                    int(round(float(node.get("pressure") or 0) * 100)),
                )
            )
            self._ecology_streetnet_push(line, node_id=node.get("id"), chat=False)
            # Still push event ticker without IRC
            pass

    def _ecology_action(self, agent, action: str, arg: str = "") -> bool:
        self._ecology_bootstrap_agent(agent)
        a = (action or "").strip().lower()
        arg = (arg or "").strip()

        if a in (
            "ecology", "ecology_panel", "open_ecology", "resource_wars",
            "scarce", "ecology_open",
        ):
            agent.ecology["panel_open"] = True
            regions = {n.get("region_id") for n in self.ecology_nodes.values()}
            self._ecology_feedback(
                agent,
                "info",
                "Ecology overlay — %d nodes / %d regions. Claim via ecology_claim "
                "<node> (contract) or ecology_raid <node>. List: ecology_list."
                % (len(self.ecology_nodes), len(regions)),
            )
            return True

        if a in ("ecology_close", "close_ecology"):
            agent.ecology["panel_open"] = False
            self._ecology_feedback(agent, "info", "Ecology overlay closed.")
            return True

        if a in ("ecology_status", "resource_status", "ecology_where"):
            cur_region = None
            if hasattr(self, "_globe_agent_region"):
                cur_region = self._globe_agent_region(agent)
            local = self._ecology_nodes_for_region(cur_region) if cur_region else []
            left = max(0.0, float(agent.ecology.get("cooldown_until") or 0) - time.time())
            if local:
                bits = []
                for n in local:
                    c = _ctrl_copy(n.get("controller"))
                    bits.append(
                        "%s[%s→%s]" % (n.get("id"), n.get("resource"), c.get("name"))
                    )
                self._ecology_feedback(
                    agent,
                    "info",
                    "Local ecology: %s · cooldown %.0fs · claims %d / raids %d"
                    % ("; ".join(bits), left, int(agent.ecology.get("claims") or 0), int(agent.ecology.get("raids") or 0)),
                )
            else:
                self._ecology_feedback(
                    agent,
                    "info",
                    "No scarce node on this region (%s). Open ecology_list · cooldown %.0fs."
                    % (cur_region or "?", left),
                )
            return True

        if a in ("ecology_list", "resource_list", "list_nodes", "scarce_list"):
            agent.ecology["panel_open"] = True
            lines = []
            for n in sorted(self.ecology_nodes.values(), key=lambda x: str(x.get("id"))):
                c = _ctrl_copy(n.get("controller"))
                res = self._ecology_resource(str(n.get("resource")))
                lines.append(
                    "%s @ %s · %s · %s"
                    % (
                        n.get("id"),
                        n.get("region_id"),
                        res.get("short") or n.get("resource"),
                        c.get("name"),
                    )
                )
            agent.log("Ecology nodes: " + " | ".join(lines[:12]))
            if len(lines) > 12:
                agent.log("… +%d more (see Ecology dock / globe pins)." % (len(lines) - 12))
            return True

        if a in (
            "ecology_claim", "claim_resource", "resource_claim", "claim_node",
            "ecology_contract_claim",
        ):
            if not arg:
                # Prefer local node
                rid = self._globe_agent_region(agent) if hasattr(self, "_globe_agent_region") else ""
                local = self._ecology_nodes_for_region(rid)
                if local:
                    arg = str(local[0]["id"])
                else:
                    self._ecology_feedback(
                        agent,
                        "error",
                        "Usage: ecology_claim <node_id> (or stand on a node region).",
                    )
                    return True
            return self._ecology_claim(agent, arg)

        if a in (
            "ecology_raid", "resource_raid", "raid_resource", "raid_node",
            "ecology_contest",
        ):
            if not arg:
                rid = self._globe_agent_region(agent) if hasattr(self, "_globe_agent_region") else ""
                local = self._ecology_nodes_for_region(rid)
                if local:
                    arg = str(local[0]["id"])
                else:
                    self._ecology_feedback(
                        agent,
                        "error",
                        "Usage: ecology_raid <node_id>",
                    )
                    return True
            return self._ecology_raid(agent, arg)

        if a in (
            "ecology_raid_resolve", "resolve_ecology_raid", "ecology_raid_clear",
        ):
            return self._ecology_raid_resolve(agent, arg)

        if a in (
            "ecology_contract", "resource_contract", "accept_ecology_contract",
            "ecology_offer",
        ):
            return self._ecology_contract_offer(agent, arg)

        return False

    def _ecology_node_public(self, node: Dict[str, Any]) -> Dict[str, Any]:
        res = self._ecology_resource(str(node.get("resource")))
        ctrl = _ctrl_copy(node.get("controller"))
        region = {"id": node.get("region_id")}
        if hasattr(self, "_globe_region"):
            reg = self._globe_region(str(node.get("region_id") or "")) or {}
            region = {
                "id": reg.get("id") or node.get("region_id"),
                "name": reg.get("name"),
                "lat": reg.get("lat"),
                "lon": reg.get("lon"),
                "continent": reg.get("continent"),
            }
        return {
            "id": node.get("id"),
            "name": node.get("name"),
            "label": node.get("label"),
            "region_id": node.get("region_id"),
            "region": region,
            "resource": node.get("resource"),
            "resource_name": res.get("name"),
            "resource_short": res.get("short"),
            "glyph": res.get("glyph"),
            "color": res.get("color"),
            "tagline": res.get("tagline"),
            "controller": ctrl,
            "pressure": round(float(node.get("pressure") or 0), 3),
            "pressure_pct": int(round(float(node.get("pressure") or 0) * 100)),
            "flips": int(node.get("flips") or 0),
            "last_flip_at": float(node.get("last_flip_at") or 0),
            "last_flip_by": node.get("last_flip_by"),
        }

    def _ecology_snapshot(self, agent) -> Dict[str, Any]:
        self._ecology_bootstrap_agent(agent)
        now = time.time()
        cd_until = float(agent.ecology.get("cooldown_until") or 0)
        nodes_out = [
            self._ecology_node_public(n)
            for n in sorted(self.ecology_nodes.values(), key=lambda x: str(x.get("id")))
        ]
        cur_region = None
        if hasattr(self, "_globe_agent_region"):
            cur_region = self._globe_agent_region(agent)
        local_ids = [
            n["id"] for n in nodes_out if n.get("region_id") == cur_region
        ]
        resources_out = [
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "short": r.get("short"),
                "glyph": r.get("glyph"),
                "color": r.get("color"),
                "tagline": r.get("tagline"),
            }
            for r in self.ecology_resources.values()
        ]
        faction = self._ecology_agent_faction(agent)
        weather = dict(getattr(self, "weather_state", None) or {})
        return {
            "panel_open": bool(agent.ecology.get("panel_open")),
            "nodes": nodes_out,
            "node_count": len(nodes_out),
            "region_count": len({n.get("region_id") for n in nodes_out}),
            "resources": resources_out,
            "local_node_ids": local_ids,
            "region_id": cur_region,
            "faction": faction,
            "claims": int(agent.ecology.get("claims") or 0),
            "raids": int(agent.ecology.get("raids") or 0),
            "active_contract_node": agent.ecology.get("active_contract_node"),
            "active_raid_id": agent.ecology.get("active_raid_id"),
            "cooldown_sec": float(self.ecology_cooldown),
            "cooldown_remaining": max(0.0, cd_until - now),
            "claim_focus_cost": int(self.ecology_claim_focus),
            "claim_credit_cost": int(self.ecology_claim_credits),
            "raid_focus_cost": int(self.ecology_raid_focus),
            "raid_credit_cost": int(self.ecology_raid_credits),
            "streetnet": list(self.ecology_streetnet[-8:]),
            "weather": {
                "id": weather.get("id"),
                "label": weather.get("label"),
                "ecology_node": weather.get("ecology_node"),
                "ecology_resource": weather.get("ecology_resource"),
                "ecology_friendly": weather.get("ecology_friendly"),
            },
            "last_feedback": agent.ecology.get("last_feedback"),
            "hooks": {
                "globe": True,
                "contracts": True,
                "raids": True,
                "streetnet": True,
                "weather": True,
            },
            "hint": (
                "Ecology open — claim (contract) or raid a scarce node on your region / globe pin."
                if agent.ecology.get("panel_open")
                else "Open Ecology (dock) or action ecology — contest bandwidth / water / spectrum nodes."
            ),
        }

    def _ecology_globe_overlay(self) -> List[Dict[str, Any]]:
        """Compact node list for globe snapshot pins."""
        out = []
        for n in self.ecology_nodes.values():
            pub = self._ecology_node_public(n)
            out.append(
                {
                    "id": pub["id"],
                    "region_id": pub["region_id"],
                    "resource": pub["resource"],
                    "resource_short": pub["resource_short"],
                    "glyph": pub["glyph"],
                    "color": pub["color"],
                    "name": pub["name"],
                    "controller": pub["controller"],
                    "pressure_pct": pub["pressure_pct"],
                    "lat": (pub.get("region") or {}).get("lat"),
                    "lon": (pub.get("region") or {}).get("lon"),
                }
            )
        return out
