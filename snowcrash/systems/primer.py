"""StreetNet Primer — adaptive teaching tablet (#60).

Inventory quest item that opens mini-quests teaching ICE probes, globe travel,
and crews. Chapters grow with courier level. Completing grants cosmetics /
soft skills only (no P2W wall, no paywall). Mechanics inspired by adaptive
teaching-primer tropes; prose is **original Metaverse fiction only**.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..items import Item

PRIMER_ITEM_ID = "streetnet_primer"
PRIMER_GLYPH = "▣"

# Soft skills — utility / economy, not mandatory combat power (no P2W wall).
SKILL_FARADAY = "faraday_mind"
SKILL_BURB = "burb_charm"

QUESTS: Dict[str, Dict[str, Any]] = {
    "ice_101": {
        "id": "ice_101",
        "title": "ICE Sparks 101",
        "teaches": "ICE probes",
        "min_level": 1,
        "goal": 1,
        "goal_high": 2,  # level ≥4 needs two successful probes
        "kind": "ice_probe",
        "blurb_low": (
            "StreetNet Primer boots a chalk outline of Focus. "
            "Spend Focus on a Stun, Reveal, or Scramble probe — the tablet listens."
        ),
        "blurb_high": (
            "Primer advanced module: chain two live ICE probes. "
            "Cameras, drones, thug decks — teach the lattice your courier signature."
        ),
        "hint": "Open ICE dock (p) or press z/x/c near a camera, drone, or thug.",
        "reward_cosmetic": {
            "id": "trail_primer_ice",
            "name": "Primer ICE Afterglow",
            "slot": "trail",
        },
        "reward_skill": SKILL_FARADAY,
        "reward_credits": 15,
        "reward_season_xp": 8,
        "complete_line": (
            "Primer seals ICE Sparks 101. Faraday Mind etched; ICE Afterglow unlocked."
        ),
    },
    "globe_101": {
        "id": "globe_101",
        "title": "Uplink Globe Hop",
        "teaches": "globe travel",
        "min_level": 1,
        "goal": 1,
        "goal_high": 1,
        "kind": "globe_hop",
        "blurb_low": (
            "The tablet unfolds a schematic Earth. Open the Globe, then hop or recall — "
            "even a home recall counts as learning the uplink lattice."
        ),
        "blurb_high": (
            "Advanced hop drill: the Primer wants a real region teleport (not just panel peek). "
            "Credits for the hop are yours to spend — the lesson is the route."
        ),
        "hint": "Dock Globe / Shift+G → teleport <region> or globe_recall.",
        "reward_cosmetic": {
            "id": "trail_primer_orbit",
            "name": "Primer Orbit Ribbon",
            "slot": "trail",
        },
        "reward_skill": None,
        "reward_credits": 20,
        "reward_season_xp": 8,
        "complete_line": (
            "Primer stamps Uplink Globe Hop. Orbit Ribbon unlocked — no combat wall, just sky."
        ),
    },
    "crew_101": {
        "id": "crew_101",
        "title": "Crew Channel Drill",
        "teaches": "crews",
        "min_level": 2,
        "goal": 1,
        "goal_high": 1,
        "kind": "crew",
        "blurb_low": (
            "Lone couriers die loud. The Primer opens a blank crew charter — "
            "create a crew or join one so StreetNet can route your stash channel."
        ),
        "blurb_high": (
            "Crew doctrine upgrade: found or join a crew. Contested patrols and "
            "stash relays only listen when you carry a crew id."
        ),
        "hint": "Action crew_create <name> or crew_join <id> · Crew dock panel.",
        "reward_cosmetic": {
            "id": "badge_primer_crew",
            "name": "Primer Crew Sigil",
            "slot": "badge",
        },
        "reward_skill": SKILL_BURB,
        "reward_credits": 18,
        "reward_season_xp": 10,
        "complete_line": (
            "Primer closes Crew Channel Drill. Burb Charm + Crew Sigil — social soft power only."
        ),
    },
}

QUEST_ORDER = ("ice_101", "globe_101", "crew_101")


def make_streetnet_primer() -> Item:
    return Item(
        id=PRIMER_ITEM_ID,
        name="StreetNet Primer",
        glyph=PRIMER_GLYPH,
        kind="quest",
        description=(
            "A battered teaching tablet hard-wired to StreetNet. "
            "Adaptive chapters teach ICE, globe hops, and crews. Use to open the Primer."
        ),
        quest=True,
        consumable=False,
        equippable=False,
        extra={"primer": True, "opens": "primer"},
    )


def _skill_name(sid: str) -> str:
    names = {
        SKILL_FARADAY: "Faraday Mind",
        SKILL_BURB: "Burb Charm",
    }
    return names.get(sid, sid)


class PrimerMixin:
    """Mixed into YearFeaturesMixin / GameWorld."""

    def _primer_init(self) -> None:
        self._primer_ready = True

    def _primer_bootstrap_agent(self, agent) -> None:
        if not isinstance(getattr(agent, "primer", None), dict):
            agent.primer = {
                "owned": False,
                "panel_open": False,
                "active_quest": None,
                "quests": {},
                "completed": [],
                "voice_level": 1,
                "lessons_done": 0,
            }
        pr = agent.primer
        pr.setdefault("owned", False)
        pr.setdefault("panel_open", False)
        pr.setdefault("active_quest", None)
        if not isinstance(pr.get("quests"), dict):
            pr["quests"] = {}
        if not isinstance(pr.get("completed"), list):
            pr["completed"] = []
        pr.setdefault("voice_level", 1)
        pr.setdefault("lessons_done", 0)

        # Ensure each known quest row exists
        for qid in QUEST_ORDER:
            row = pr["quests"].get(qid)
            if not isinstance(row, dict):
                pr["quests"][qid] = {
                    "id": qid,
                    "progress": 0,
                    "status": "locked",  # locked | available | active | done
                }
            else:
                row.setdefault("id", qid)
                row.setdefault("progress", 0)
                row.setdefault("status", "locked")

        self._primer_ensure_item(agent)
        self._primer_refresh_availability(agent)

    def _primer_ensure_item(self, agent) -> None:
        actor = getattr(agent, "actor", None)
        if actor is None:
            return
        inv = getattr(actor, "inventory", None) or []
        has = any(getattr(i, "id", None) == PRIMER_ITEM_ID for i in inv)
        if not has:
            inv.append(make_streetnet_primer())
            actor.inventory = inv
            agent.log(
                "StreetNet Primer sleeved into inventory — use it (or action `primer`) to open chapters."
            )
        agent.primer["owned"] = True

    def _primer_player_level(self, agent) -> int:
        return max(1, int(getattr(agent, "level", 1) or 1))

    def _primer_refresh_availability(self, agent) -> None:
        """Unlock chapters from courier level; grow voice copy.

        Assumes agent.primer dict already exists (call bootstrap first).
        """
        if not isinstance(getattr(agent, "primer", None), dict):
            return
        lv = self._primer_player_level(agent)
        pr = agent.primer
        pr["voice_level"] = lv
        for qid in QUEST_ORDER:
            defn = QUESTS[qid]
            row = pr["quests"][qid]
            if row.get("status") == "done" or qid in (pr.get("completed") or []):
                row["status"] = "done"
                continue
            if lv < int(defn.get("min_level", 1)):
                if row.get("status") not in ("active", "done"):
                    row["status"] = "locked"
                continue
            if row.get("status") in ("locked",):
                row["status"] = "available"

    def _primer_goal_for(self, agent, qid: str) -> int:
        defn = QUESTS[qid]
        lv = self._primer_player_level(agent)
        if lv >= 4:
            return int(defn.get("goal_high", defn.get("goal", 1)))
        return int(defn.get("goal", 1))

    def _primer_blurb(self, agent, qid: str) -> str:
        defn = QUESTS[qid]
        lv = self._primer_player_level(agent)
        if lv >= 4:
            return str(defn.get("blurb_high") or defn.get("blurb_low") or "")
        return str(defn.get("blurb_low") or "")

    def _primer_on_level_up(self, agent) -> None:
        self._primer_bootstrap_agent(agent)
        before = {qid: agent.primer["quests"][qid].get("status") for qid in QUEST_ORDER}
        self._primer_refresh_availability(agent)
        unlocked = []
        for qid in QUEST_ORDER:
            if before.get(qid) == "locked" and agent.primer["quests"][qid].get("status") == "available":
                unlocked.append(QUESTS[qid]["title"])
        if unlocked:
            agent.log(
                "StreetNet Primer grows with you (Lv %d) — new chapter(s): %s."
                % (self._primer_player_level(agent), ", ".join(unlocked))
            )
        else:
            agent.log(
                "StreetNet Primer retunes voice to courier level %d."
                % self._primer_player_level(agent)
            )

    def _primer_grant_cosmetic(self, agent, cos: Dict[str, Any]) -> bool:
        season = getattr(agent, "season", None)
        if not isinstance(season, dict):
            season = {"id": None, "xp": 0, "tier": 0, "unlocked": [], "equipped": None}
            agent.season = season
        unlocked = list(season.get("unlocked") or [])
        cos_id = cos["id"]
        newly = False
        if cos_id not in unlocked:
            unlocked.append(cos_id)
            season["unlocked"] = unlocked
            newly = True
        if newly and not season.get("equipped"):
            season["equipped"] = cos_id
        return newly

    def _primer_grant_skill(self, agent, sid: Optional[str]) -> bool:
        if not sid:
            return False
        skills = getattr(agent, "skills", None)
        if not isinstance(skills, dict):
            skills = {}
            agent.skills = skills
        if sid in skills:
            return False
        name = _skill_name(sid)
        catalog = getattr(self, "SKILL_CATALOG", None)
        # YearFeaturesMixin defines module-level SKILL_CATALOG; prefer instance/class lookup via globals
        try:
            from snowcrash.systems import year_features as yf
            if sid in getattr(yf, "SKILL_CATALOG", {}):
                name = yf.SKILL_CATALOG[sid]["name"]
        except Exception:
            pass
        skills[sid] = name
        return True


    def _primer_complete(self, agent, qid: str) -> None:
        defn = QUESTS.get(qid)
        if not defn:
            return
        pr = agent.primer
        row = pr["quests"].get(qid) or {}
        if row.get("status") == "done" or qid in (pr.get("completed") or []):
            return
        row["status"] = "done"
        row["progress"] = self._primer_goal_for(agent, qid)
        pr["quests"][qid] = row
        completed = list(pr.get("completed") or [])
        if qid not in completed:
            completed.append(qid)
        pr["completed"] = completed
        pr["lessons_done"] = len(completed)
        if pr.get("active_quest") == qid:
            pr["active_quest"] = None

        credits = int(defn.get("reward_credits", 0) or 0)
        if credits:
            agent.credits = int(getattr(agent, "credits", 0) or 0) + credits

        cos = defn.get("reward_cosmetic") or {}
        newly_cos = False
        if cos:
            newly_cos = self._primer_grant_cosmetic(agent, cos)

        newly_sk = self._primer_grant_skill(agent, defn.get("reward_skill"))

        grant = getattr(self, "_grant_season_xp", None)
        if callable(grant):
            grant(agent, int(defn.get("reward_season_xp", 0) or 0))

        agent.log(str(defn.get("complete_line") or ("Primer chapter complete: %s" % defn["title"])))
        bits = ["+%d credits" % credits] if credits else []
        if newly_cos and cos:
            bits.append("cosmetic %s (season_equip %s)" % (cos["name"], cos["id"]))
        elif cos:
            bits.append("cosmetic already owned")
        if newly_sk and defn.get("reward_skill"):
            bits.append("skill %s" % _skill_name(defn["reward_skill"]))
        elif defn.get("reward_skill"):
            bits.append("skill already known")
        if bits:
            agent.log("Primer rewards (no P2W wall): " + " · ".join(bits) + ".")
        try:
            agent.sfx("use")
        except Exception:
            pass
        push = getattr(self, "_push_event", None)
        if callable(push):
            push(
                "primer",
                "%s finished Primer chapter %s."
                % (getattr(agent, "name", "Courier"), defn["title"]),
                quest=qid,
            )

    def _primer_note_progress(self, agent, kind: str, amount: int = 1) -> None:
        """Called from ICE / globe / crew hooks when a teaching action succeeds."""
        self._primer_bootstrap_agent(agent)
        self._primer_refresh_availability(agent)
        pr = agent.primer
        for qid in QUEST_ORDER:
            defn = QUESTS[qid]
            if defn.get("kind") != kind:
                continue
            row = pr["quests"][qid]
            if row.get("status") != "active":
                # Only count progress for an explicitly started chapter
                # (avoids surprising reward side-effects during unrelated play).
                continue
            goal = self._primer_goal_for(agent, qid)
            row["progress"] = min(goal, int(row.get("progress") or 0) + amount)
            pr["quests"][qid] = row
            agent.log(
                "Primer [%s] progress %d/%d."
                % (defn["title"], row["progress"], goal)
            )
            if row["progress"] >= goal:
                self._primer_complete(agent, qid)
            return

    def _primer_start_quest(self, agent, qid: str) -> bool:
        self._primer_bootstrap_agent(agent)
        self._primer_refresh_availability(agent)
        qid = (qid or "").strip().lower()
        if qid not in QUESTS:
            agent.log("Unknown Primer chapter. Options: %s" % ", ".join(QUEST_ORDER))
            return True
        row = agent.primer["quests"][qid]
        if row.get("status") == "done":
            agent.log("Chapter already complete: %s." % QUESTS[qid]["title"])
            return True
        if row.get("status") == "locked":
            agent.log(
                "Chapter locked — reach courier level %d for %s."
                % (QUESTS[qid]["min_level"], QUESTS[qid]["title"])
            )
            return True
        row["status"] = "active"
        agent.primer["active_quest"] = qid
        agent.primer["panel_open"] = True
        agent.log(
            "Primer chapter active: %s — %s"
            % (QUESTS[qid]["title"], self._primer_blurb(agent, qid))
        )
        agent.log("Hint: %s" % QUESTS[qid]["hint"])
        return True

    def _primer_open(self, agent) -> bool:
        self._primer_bootstrap_agent(agent)
        self._primer_refresh_availability(agent)
        agent.primer["panel_open"] = True
        snap = self._primer_snapshot(agent)
        agent.log(
            "StreetNet Primer open — voice Lv %d · lessons %d/%d. Pick a chapter or press Start."
            % (
                snap["voice_level"],
                snap["lessons_done"],
                snap["quest_count"],
            )
        )
        for q in snap["quests"]:
            agent.log(
                " · %s [%s] %d/%d — %s"
                % (q["title"], q["status"], q["progress"], q["goal"], q["teaches"])
            )
        return True

    def _primer_snapshot(self, agent) -> Dict[str, Any]:
        self._primer_bootstrap_agent(agent)
        self._primer_refresh_availability(agent)
        pr = agent.primer
        quests_out: List[Dict[str, Any]] = []
        for qid in QUEST_ORDER:
            defn = QUESTS[qid]
            row = pr["quests"][qid]
            goal = self._primer_goal_for(agent, qid)
            quests_out.append({
                "id": qid,
                "title": defn["title"],
                "teaches": defn["teaches"],
                "min_level": int(defn["min_level"]),
                "status": row.get("status") or "locked",
                "progress": int(row.get("progress") or 0),
                "goal": goal,
                "blurb": self._primer_blurb(agent, qid),
                "hint": defn["hint"],
                "reward": {
                    "credits": int(defn.get("reward_credits") or 0),
                    "cosmetic": dict(defn["reward_cosmetic"]) if defn.get("reward_cosmetic") else None,
                    "skill": defn.get("reward_skill"),
                    "skill_name": _skill_name(defn["reward_skill"]) if defn.get("reward_skill") else None,
                    "season_xp": int(defn.get("reward_season_xp") or 0),
                    "p2w": False,
                },
            })
        return {
            "owned": bool(pr.get("owned")),
            "item_id": PRIMER_ITEM_ID,
            "item_name": "StreetNet Primer",
            "panel_open": bool(pr.get("panel_open")),
            "active_quest": pr.get("active_quest"),
            "voice_level": int(pr.get("voice_level") or self._primer_player_level(agent)),
            "player_level": self._primer_player_level(agent),
            "lessons_done": int(pr.get("lessons_done") or 0),
            "quest_count": len(QUEST_ORDER),
            "quests": quests_out,
            "completed": list(pr.get("completed") or []),
            "hint": (
                "Use the StreetNet Primer from inventory, dock Primer, or Shift+P. "
                "Chapters grow with your level — rewards are cosmetics/soft skills only."
            ),
        }

    def _primer_action(self, agent, action: str, arg: str = "") -> bool:
        self._primer_bootstrap_agent(agent)
        a = (action or "").strip().lower()
        arg = (arg or "").strip()
        arg_l = arg.lower()

        if a in ("primer_close", "close_primer"):
            agent.primer["panel_open"] = False
            agent.log("StreetNet Primer folded shut.")
            return True

        if a in ("primer_status", "primer_list"):
            return self._primer_open(agent)

        if a in (
            "primer", "open_primer", "primer_panel", "streetnet_primer",
            "primer_open", "use_primer",
        ):
            # `primer ice_101` starts; bare `primer` opens
            if arg_l in QUEST_ORDER or arg_l in ("ice", "globe", "crew"):
                alias = {
                    "ice": "ice_101",
                    "globe": "globe_101",
                    "crew": "crew_101",
                }
                return self._primer_start_quest(agent, alias.get(arg_l, arg_l))
            if arg_l in ("status", "list", "help", "?"):
                return self._primer_open(agent)
            if arg_l in ("close",):
                return self._primer_action(agent, "primer_close", "")
            return self._primer_open(agent)

        if a in ("primer_start", "start_primer", "primer_quest"):
            qid = arg_l.split()[0] if arg_l else ""
            alias = {"ice": "ice_101", "globe": "globe_101", "crew": "crew_101"}
            qid = alias.get(qid, qid)
            if not qid:
                # Start first available
                self._primer_refresh_availability(agent)
                for cand in QUEST_ORDER:
                    st = agent.primer["quests"][cand].get("status")
                    if st in ("available", "active"):
                        qid = cand
                        break
            if not qid:
                agent.log("No Primer chapter available yet.")
                return True
            return self._primer_start_quest(agent, qid)

        return False

    def _primer_try_use_item(self, agent, item: Item) -> bool:
        """Return True if this item is the Primer and was handled."""
        if getattr(item, "id", None) != PRIMER_ITEM_ID and not (getattr(item, "extra", None) or {}).get("primer"):
            return False
        self._primer_open(agent)
        try:
            agent.sfx("use")
        except Exception:
            pass
        return True
