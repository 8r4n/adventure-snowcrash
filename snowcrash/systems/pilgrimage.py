"""Canticle Pilgrimage — multi-courier story arcs (#61).

Hyperion / Canterbury *structure* only (party pilgrimage, rotating POV beats,
shared finale). All prose is original Metaverse fiction — no copyrighted text.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .. import constants as C

PILGRIMAGE_MIN = 3
PILGRIMAGE_MAX = 5
PILGRIMAGE_HIT_RADIUS = 1
FINALE_ENTER_RADIUS = 2

PILGRIMAGE_REWARD_CREDITS = 45
PILGRIMAGE_REWARD_SEASON_XP = 18
PILGRIMAGE_COSMETIC = {
    "id": "trail_canticle_ash",
    "name": "Canticle Ash Trail",
    "slot": "trail",
}

PILGRIMAGE_SIDE_ID = "canticle_pilgrimage"

# Five original Canticle beats (assign one per courier; order is rotation index).
CANTICLE_BEATS: Tuple[Dict[str, Any], ...] = (
    {
        "id": "latch_neon",
        "title": "Canticle of the Faraday Latch",
        "district": "burbclave",
        "shrine_label": "Latch Shrine",
        "prose": (
            "You write of franchise neon that never blinks — a Faraday latch "
            "humming behind a gated kiosk. The pilgrimage asks you to touch the "
            "latch and leave a courier sigil in the static."
        ),
        "complete": (
            "Latch Canticle sealed. Your journal page burns ash-white — the "
            "party lattice feels you online."
        ),
    },
    {
        "id": "glassline_bass",
        "title": "Canticle of the Glassline Bass",
        "district": "club",
        "shrine_label": "Bass Shrine",
        "prose": (
            "Club Glassline hides a shrine that refuses to dance. You walk the "
            "bass cut until the glyph stops fighting the beat, then stamp your "
            "tale into StreetNet ash."
        ),
        "complete": (
            "Glassline Canticle sealed. Bass folds into silence; the pilgrimage "
            "counts your page."
        ),
    },
    {
        "id": "rim_frost",
        "title": "Canticle of Rim Frost",
        "district": "uplink_rim",
        "shrine_label": "Rim Shrine",
        "prose": (
            "Uplink Rim towers braid frost into Faraday benches. Your beat is "
            "to stand in the signal-storm cold until the shrine accepts a "
            "courier oath without melting."
        ),
        "complete": (
            "Rim Canticle sealed. Frost glyphs lock; Spire resonance ticks up."
        ),
    },
    {
        "id": "street_oath",
        "title": "Canticle of the Street Oath",
        "district": "burbclave",
        "shrine_label": "Oath Shrine",
        "prose": (
            "Near the franchise pads, an older courier left an oath stone. You "
            "retell the street vow in your own words — original ash, no copied "
            "gospel — and the stone answers with a soft StreetNet chime."
        ),
        "complete": (
            "Oath Canticle sealed. The stone keeps your wording; the lattice "
            "remembers."
        ),
    },
    {
        "id": "spawn_wake",
        "title": "Canticle of the Spawn Wake",
        "district": "club",
        "shrine_label": "Wake Shrine",
        "prose": (
            "Every pilgrimage starts with a wake: the moment a sleeve hits "
            "asphalt. You revisit a wake shrine and write how the neon first "
            "looked when you jacked in — then close the page for the Spire."
        ),
        "complete": (
            "Wake Canticle sealed. Spawn ash settles; finale pad warms if all "
            "pages are in."
        ),
    },
)

CANTICLE_BY_ID = {b["id"]: b for b in CANTICLE_BEATS}

LOBBY_OPEN_LINES = (
    "StreetNet: Canticle Pilgrimage lobby {id} open — need {min}–{max} couriers.",
    "Pilgrimage channel spins up ({id}). Sleeve in; tales rotate; Spire waits.",
)

START_LINES = (
    "Canticle Pilgrimage {id} begins — each courier walks a private beat, then the Spire.",
    "Pilgrimage lattice live ({id}). Journal pages unlock. Finale sealed until all beats clear.",
)

FINALE_LINES = (
    "Canticle Spire opens — all pilgrim pages braided. enter_pilgrimage near the pad.",
    "Shared finale unlocked. The Spire drinks ash trails; approach the pilgrimage pad.",
)

REWARD_LINES = (
    "Spire broadcast seals your ash trail. +{credits} credits · cosmetic unlocked.",
    "Canticle finale complete. StreetNet stamps the party lattice. +{credits} credits.",
)


class PilgrimageMixin:
    """Mixed into YearFeaturesMixin / GameWorld."""

    def _pilgrimage_init(self) -> None:
        self.pilgrimage_lobbies: Dict[str, Dict[str, Any]] = {}
        self.pilgrimage_instances: Dict[str, Dict[str, Any]] = {}
        self.pilgrimage_pad: Optional[Tuple[int, int]] = None
        self._seed_pilgrimage_pad()

    def _seed_pilgrimage_pad(self) -> None:
        """Shared finale pad near uplink (distinct from Flotilla when possible)."""
        ux, uy = self.uplink_pos
        gmap = self.gmap
        flotilla = getattr(self, "flotilla_pad", None)
        candidates = [
            (ux + 3, uy),
            (ux - 3, uy),
            (ux, uy + 3),
            (ux, uy - 3),
            (ux + 2, uy + 2),
            (ux - 2, uy + 2),
            (ux + 2, uy - 2),
            (ux - 2, uy - 2),
            (ux + 1, uy),
            (ux, uy + 1),
        ]
        for x, y in candidates:
            if flotilla and (x, y) == flotilla:
                continue
            if gmap.in_bounds(x, y) and gmap.walkable(x, y):
                self.pilgrimage_pad = (x, y)
                return
        self.pilgrimage_pad = (ux, uy)

    def _pilgrimage_bootstrap_agent(self, agent) -> None:
        pg = getattr(agent, "pilgrimage", None)
        if not isinstance(pg, dict):
            agent.pilgrimage = {
                "lobby_id": None,
                "instance_id": None,
                "ready": False,
                "beat_id": None,
                "beat_done": False,
                "finale_entered": False,
                "rewards_claimed": False,
                "host": False,
            }
            return
        pg.setdefault("lobby_id", None)
        pg.setdefault("instance_id", None)
        pg.setdefault("ready", False)
        pg.setdefault("beat_id", None)
        pg.setdefault("beat_done", False)
        pg.setdefault("finale_entered", False)
        pg.setdefault("rewards_claimed", False)
        pg.setdefault("host", False)

    def _pilgrimage_find_walkable(self, district_id: str) -> Optional[Tuple[int, int]]:
        find = getattr(self, "_find_walkable_in_district", None)
        if callable(find):
            pos = find(district_id)
            if pos:
                return pos
        # Fallback near spawn / jackpoint
        sx, sy = getattr(self, "spawn_xy", self.jackpoint_pos)
        gmap = self.gmap
        for dx in range(-6, 7):
            for dy in range(-6, 7):
                x, y = sx + dx, sy + dy
                if gmap.in_bounds(x, y) and gmap.walkable(x, y):
                    return (x, y)
        return (sx, sy)

    def _pilgrimage_lobby_members(self, lobby: Dict[str, Any]) -> List[Any]:
        out = []
        for mid in list(lobby.get("members") or []):
            m = self.players.get(mid)
            if m and getattr(m, "connected", True):
                out.append(m)
        return out

    def _pilgrimage_instance_members(self, inst: Dict[str, Any]) -> List[Any]:
        out = []
        for mid in list(inst.get("members") or []):
            m = self.players.get(mid)
            if m:
                out.append(m)
        return out

    def _pilgrimage_sync_side_quest(self, agent, text: str, done: bool = False) -> None:
        j = agent.journal if isinstance(getattr(agent, "journal", None), dict) else None
        if j is None:
            return
        side = list(j.get("side") or [])
        found = False
        for s in side:
            if isinstance(s, dict) and s.get("id") == PILGRIMAGE_SIDE_ID:
                s["text"] = text
                s["done"] = done
                s["completed"] = done
                s["status"] = "done" if done else "active"
                found = True
                break
        if not found:
            side.append(
                {
                    "id": PILGRIMAGE_SIDE_ID,
                    "text": text,
                    "done": done,
                    "completed": done,
                    "status": "done" if done else "active",
                }
            )
        j["side"] = side
        notes = list(j.get("notes") or [])
        if text and (not notes or notes[-1] != text):
            notes.append(text)
            j["notes"] = notes[-10:]
        agent.journal = j

    def _pilgrimage_open_lobby(self, agent) -> bool:
        self._pilgrimage_bootstrap_agent(agent)
        pg = agent.pilgrimage
        if pg.get("instance_id"):
            agent.log("Already on a pilgrimage instance — pilgrimage_leave first.")
            return True
        if pg.get("lobby_id") and pg["lobby_id"] in self.pilgrimage_lobbies:
            agent.log("Already in pilgrimage lobby %s." % pg["lobby_id"])
            return True
        lid = uuid.uuid4().hex[:8]
        self.pilgrimage_lobbies[lid] = {
            "id": lid,
            "host": agent.id,
            "members": [agent.id],
            "ready": {agent.id: False},
            "created": time.time(),
            "phase": "lobby",
        }
        pg.update(
            {
                "lobby_id": lid,
                "instance_id": None,
                "ready": False,
                "beat_id": None,
                "beat_done": False,
                "finale_entered": False,
                "rewards_claimed": False,
                "host": True,
            }
        )
        line = LOBBY_OPEN_LINES[0].format(id=lid, min=PILGRIMAGE_MIN, max=PILGRIMAGE_MAX)
        rng = getattr(self, "rng", None)
        if rng is not None:
            line = rng.choice(LOBBY_OPEN_LINES).format(
                id=lid, min=PILGRIMAGE_MIN, max=PILGRIMAGE_MAX
            )
        agent.log(
            "Opened Canticle Pilgrimage lobby %s (need %d–%d). Others: pilgrimage_join %s"
            % (lid, PILGRIMAGE_MIN, PILGRIMAGE_MAX, lid)
        )
        if hasattr(self, "_push_event"):
            self._push_event("pilgrimage", line, phase="lobby", lobby_id=lid)
        if hasattr(self, "system_chat"):
            try:
                self.system_chat(line)
            except Exception:
                pass
        self._pilgrimage_sync_side_quest(
            agent,
            "Canticle lobby %s — gather %d–%d couriers, then ready/start."
            % (lid, PILGRIMAGE_MIN, PILGRIMAGE_MAX),
        )
        return True

    def _pilgrimage_join_lobby(self, agent, lobby_id: str) -> bool:
        self._pilgrimage_bootstrap_agent(agent)
        pg = agent.pilgrimage
        if pg.get("instance_id"):
            agent.log("Already on a pilgrimage instance.")
            return True
        lid = (lobby_id or "").strip()
        if not lid:
            # Join newest open lobby if only one
            open_ids = [
                k
                for k, v in self.pilgrimage_lobbies.items()
                if v.get("phase") == "lobby"
            ]
            if len(open_ids) == 1:
                lid = open_ids[0]
            else:
                agent.log("Usage: pilgrimage_join <lobby_id>")
                return True
        lobby = self.pilgrimage_lobbies.get(lid)
        if not lobby or lobby.get("phase") != "lobby":
            agent.log("No open pilgrimage lobby %s." % lid)
            return True
        members = list(lobby.get("members") or [])
        if agent.id in members:
            pg["lobby_id"] = lid
            agent.log("Already in lobby %s." % lid)
            return True
        if len(members) >= PILGRIMAGE_MAX:
            agent.log("Lobby full (%d/%d)." % (len(members), PILGRIMAGE_MAX))
            return True
        # Leave prior lobby
        old = pg.get("lobby_id")
        if old and old in self.pilgrimage_lobbies and old != lid:
            self._pilgrimage_remove_from_lobby(agent, silent=True)
        members.append(agent.id)
        lobby["members"] = members
        ready = dict(lobby.get("ready") or {})
        ready[agent.id] = False
        lobby["ready"] = ready
        pg.update(
            {
                "lobby_id": lid,
                "ready": False,
                "host": lobby.get("host") == agent.id,
                "beat_id": None,
                "beat_done": False,
            }
        )
        agent.log(
            "Joined Canticle lobby %s (%d/%d). pilgrimage_ready when set."
            % (lid, len(members), PILGRIMAGE_MAX)
        )
        for m in self._pilgrimage_lobby_members(lobby):
            if m.id != agent.id:
                m.log("%s joined pilgrimage lobby %s (%d)." % (agent.name, lid, len(members)))
        self._pilgrimage_sync_side_quest(
            agent,
            "In Canticle lobby %s — mark ready; host starts at %d+."
            % (lid, PILGRIMAGE_MIN),
        )
        return True

    def _pilgrimage_remove_from_lobby(self, agent, silent: bool = False) -> None:
        self._pilgrimage_bootstrap_agent(agent)
        pg = agent.pilgrimage
        lid = pg.get("lobby_id")
        if not lid or lid not in self.pilgrimage_lobbies:
            pg["lobby_id"] = None
            pg["ready"] = False
            pg["host"] = False
            return
        lobby = self.pilgrimage_lobbies[lid]
        lobby["members"] = [m for m in lobby.get("members") or [] if m != agent.id]
        ready = dict(lobby.get("ready") or {})
        ready.pop(agent.id, None)
        lobby["ready"] = ready
        if lobby.get("host") == agent.id:
            if lobby["members"]:
                lobby["host"] = lobby["members"][0]
                host = self.players.get(lobby["host"])
                if host:
                    self._pilgrimage_bootstrap_agent(host)
                    host.pilgrimage["host"] = True
                    host.log("You are now Canticle lobby host.")
            else:
                self.pilgrimage_lobbies.pop(lid, None)
        pg["lobby_id"] = None
        pg["ready"] = False
        pg["host"] = False
        if not silent:
            agent.log("Left pilgrimage lobby.")

    def _pilgrimage_leave(self, agent) -> bool:
        self._pilgrimage_bootstrap_agent(agent)
        pg = agent.pilgrimage
        if getattr(agent, "mode", None) == "pilgrimage":
            return self._leave_pilgrimage_room(agent)
        iid = pg.get("instance_id")
        if iid and iid in self.pilgrimage_instances:
            inst = self.pilgrimage_instances[iid]
            inst["members"] = [m for m in inst.get("members") or [] if m != agent.id]
            pg["instance_id"] = None
            pg["beat_id"] = None
            pg["beat_done"] = False
            agent.log("Left pilgrimage instance %s." % iid)
            if not inst["members"]:
                self.pilgrimage_instances.pop(iid, None)
            return True
        if pg.get("lobby_id"):
            self._pilgrimage_remove_from_lobby(agent)
            return True
        agent.log("Not in a pilgrimage lobby or instance.")
        return True

    def _pilgrimage_set_ready(self, agent, ready: bool = True) -> bool:
        self._pilgrimage_bootstrap_agent(agent)
        pg = agent.pilgrimage
        lid = pg.get("lobby_id")
        if not lid or lid not in self.pilgrimage_lobbies:
            agent.log("Join a pilgrimage lobby first.")
            return True
        lobby = self.pilgrimage_lobbies[lid]
        if lobby.get("phase") != "lobby":
            agent.log("Lobby already started.")
            return True
        pg["ready"] = bool(ready)
        ready_map = dict(lobby.get("ready") or {})
        ready_map[agent.id] = bool(ready)
        lobby["ready"] = ready_map
        n_ready = sum(1 for v in ready_map.values() if v)
        n = len(lobby.get("members") or [])
        agent.log(
            "Pilgrimage ready=%s · lobby %d ready / %d members (need %d–%d)."
            % (ready, n_ready, n, PILGRIMAGE_MIN, PILGRIMAGE_MAX)
        )
        return True

    def _pilgrimage_can_start(self, lobby: Dict[str, Any], force: bool = False) -> Tuple[bool, str]:
        members = list(lobby.get("members") or [])
        n = len(members)
        if n < PILGRIMAGE_MIN and not force:
            return False, "Need at least %d couriers (have %d)." % (PILGRIMAGE_MIN, n)
        if n > PILGRIMAGE_MAX:
            return False, "Lobby exceeds max %d." % PILGRIMAGE_MAX
        if force:
            return True, "ok"
        ready_map = dict(lobby.get("ready") or {})
        if not all(ready_map.get(mid) for mid in members):
            return False, "All members must pilgrimage_ready first."
        return True, "ok"

    def _pilgrimage_start(self, agent, force: bool = False) -> bool:
        self._pilgrimage_bootstrap_agent(agent)
        pg = agent.pilgrimage
        lid = pg.get("lobby_id")
        if not lid or lid not in self.pilgrimage_lobbies:
            agent.log("Open or join a lobby before pilgrimage_start.")
            return True
        lobby = self.pilgrimage_lobbies[lid]
        if lobby.get("host") != agent.id and not force:
            agent.log("Only the lobby host can start.")
            return True
        ok, reason = self._pilgrimage_can_start(lobby, force=force)
        if not ok:
            agent.log(reason)
            return True
        members = list(lobby.get("members") or [])[:PILGRIMAGE_MAX]
        if force and len(members) < PILGRIMAGE_MIN:
            # Dev: allow undersized only when explicitly forced; still need ≥1
            if len(members) < 1:
                agent.log("Empty lobby.")
                return True
        iid = uuid.uuid4().hex[:8]
        # Assign unique beats
        beats = list(CANTICLE_BEATS)
        rng = getattr(self, "rng", None)
        if rng is not None:
            beats = list(beats)
            rng.shuffle(beats)
        shrines: Dict[str, Dict[str, Any]] = {}
        used_pos = set()
        for i, mid in enumerate(members):
            beat = beats[i % len(beats)]
            # Prefer unique district shrine positions
            pos = None
            for _ in range(24):
                cand = self._pilgrimage_find_walkable(beat["district"])
                if cand and cand not in used_pos:
                    pos = cand
                    break
            if pos is None:
                pos = self._pilgrimage_find_walkable(beat["district"]) or self.jackpoint_pos
            used_pos.add(pos)
            shrines[mid] = {
                "beat_id": beat["id"],
                "title": beat["title"],
                "district": beat["district"],
                "label": beat["shrine_label"],
                "x": int(pos[0]),
                "y": int(pos[1]),
                "done": False,
            }
        pad = self.pilgrimage_pad or self.uplink_pos
        inst = {
            "id": iid,
            "lobby_id": lid,
            "members": members,
            "shrines": shrines,
            "started": time.time(),
            "started_tick": getattr(self, "tick", 0),
            "finale_unlocked": False,
            "finale_entered": [],
            "pad": {"x": int(pad[0]), "y": int(pad[1])},
            "phase": "beats",
        }
        self.pilgrimage_instances[iid] = inst
        lobby["phase"] = "started"
        lobby["instance_id"] = iid
        # Drop lobby entry from open list (keep for id reference briefly)
        self.pilgrimage_lobbies.pop(lid, None)

        line_tpl = START_LINES[0]
        if rng is not None:
            line_tpl = rng.choice(START_LINES)
        msg = line_tpl.format(id=iid)
        if hasattr(self, "_push_event"):
            self._push_event("pilgrimage", msg, phase="start", instance_id=iid)
        if hasattr(self, "system_chat"):
            try:
                self.system_chat(msg)
            except Exception:
                pass

        for mid in members:
            m = self.players.get(mid)
            if not m:
                continue
            self._pilgrimage_bootstrap_agent(m)
            shrine = shrines[mid]
            beat = CANTICLE_BY_ID[shrine["beat_id"]]
            m.pilgrimage.update(
                {
                    "lobby_id": None,
                    "instance_id": iid,
                    "ready": False,
                    "beat_id": beat["id"],
                    "beat_done": False,
                    "finale_entered": False,
                    "rewards_claimed": False,
                    "host": lobby.get("host") == mid,
                }
            )
            m.log(
                "Pilgrimage %s — your beat: %s. Shrine @ (%d,%d) · %s"
                % (
                    iid,
                    beat["title"],
                    shrine["x"],
                    shrine["y"],
                    beat["district"],
                )
            )
            m.log(beat["prose"])
            self._pilgrimage_sync_side_quest(
                m,
                "%s — reach %s (%d,%d)."
                % (beat["title"], shrine["label"], shrine["x"], shrine["y"]),
            )
        agent.log(
            "Canticle Pilgrimage started (%d couriers). Complete personal shrines, then shared Spire."
            % len(members)
        )
        return True

    def _pilgrimage_near_shrine(self, agent) -> bool:
        self._pilgrimage_bootstrap_agent(agent)
        pg = agent.pilgrimage
        iid = pg.get("instance_id")
        if not iid or iid not in self.pilgrimage_instances:
            return False
        inst = self.pilgrimage_instances[iid]
        shrine = (inst.get("shrines") or {}).get(agent.id)
        if not shrine or shrine.get("done") or pg.get("beat_done"):
            return False
        if int(getattr(agent.actor, "z", 0) or 0) != C.PLANE_STREET:
            return False
        return (
            abs(agent.actor.x - int(shrine["x"]))
            + abs(agent.actor.y - int(shrine["y"]))
            <= PILGRIMAGE_HIT_RADIUS
        )

    def _pilgrimage_complete_beat(self, agent) -> bool:
        self._pilgrimage_bootstrap_agent(agent)
        pg = agent.pilgrimage
        iid = pg.get("instance_id")
        if not iid or iid not in self.pilgrimage_instances:
            agent.log("Not on an active pilgrimage.")
            return True
        inst = self.pilgrimage_instances[iid]
        shrine = (inst.get("shrines") or {}).get(agent.id)
        if not shrine:
            agent.log("No Canticle beat assigned.")
            return True
        if pg.get("beat_done") or shrine.get("done"):
            agent.log("Your Canticle beat is already sealed.")
            return True
        if not self._pilgrimage_near_shrine(agent):
            agent.log(
                "Shrine cold — stand on %s @ (%d,%d)."
                % (shrine.get("label", "shrine"), shrine["x"], shrine["y"])
            )
            return True
        shrine["done"] = True
        pg["beat_done"] = True
        beat = CANTICLE_BY_ID.get(shrine["beat_id"], {})
        agent.log(beat.get("complete") or "Canticle beat sealed.")
        self._pilgrimage_sync_side_quest(
            agent,
            "Beat sealed — wait for party, then enter Canticle Spire.",
        )
        if hasattr(self, "_push_event"):
            self._push_event(
                "pilgrimage",
                "%s sealed %s." % (agent.name, beat.get("title", "a Canticle")),
                phase="beat",
                instance_id=iid,
                courier=agent.name,
            )
        # Check all done
        shrines = inst.get("shrines") or {}
        if shrines and all(s.get("done") for s in shrines.values()):
            self._pilgrimage_unlock_finale(inst)
        else:
            done_n = sum(1 for s in shrines.values() if s.get("done"))
            for m in self._pilgrimage_instance_members(inst):
                if m.id != agent.id:
                    m.log(
                        "Pilgrimage beat progress %d/%d — Spire still sealed."
                        % (done_n, len(shrines))
                    )
        return True

    def _pilgrimage_unlock_finale(self, inst: Dict[str, Any]) -> None:
        if inst.get("finale_unlocked"):
            return
        inst["finale_unlocked"] = True
        inst["phase"] = "finale"
        iid = inst["id"]
        rng = getattr(self, "rng", None)
        line_tpl = FINALE_LINES[0]
        if rng is not None:
            line_tpl = rng.choice(FINALE_LINES)
        msg = line_tpl
        if hasattr(self, "_push_event"):
            self._push_event("pilgrimage", msg, phase="finale", instance_id=iid)
        if hasattr(self, "system_chat"):
            try:
                self.system_chat(msg)
            except Exception:
                pass
        pad = inst.get("pad") or {}
        for m in self._pilgrimage_instance_members(inst):
            m.log(
                "All Canticle pages braided — Spire open. Approach pad (%d,%d) · enter_pilgrimage"
                % (int(pad.get("x", 0)), int(pad.get("y", 0)))
            )
            self._pilgrimage_sync_side_quest(
                m,
                "Shared finale — enter_pilgrimage at Canticle Spire pad (%d,%d)."
                % (int(pad.get("x", 0)), int(pad.get("y", 0))),
            )

    def _pilgrimage_near_pad(self, agent, inst: Optional[Dict[str, Any]] = None) -> bool:
        if int(getattr(agent.actor, "z", 0) or 0) != C.PLANE_STREET:
            return False
        if inst is None:
            pg = getattr(agent, "pilgrimage", {}) or {}
            iid = pg.get("instance_id")
            inst = self.pilgrimage_instances.get(iid) if iid else None
        pad = None
        if inst:
            p = inst.get("pad") or {}
            if "x" in p and "y" in p:
                pad = (int(p["x"]), int(p["y"]))
        if not pad:
            pad = self.pilgrimage_pad or self.uplink_pos
        return abs(agent.actor.x - pad[0]) + abs(agent.actor.y - pad[1]) <= FINALE_ENTER_RADIUS

    def _enter_pilgrimage_room(self, agent) -> bool:
        self._pilgrimage_bootstrap_agent(agent)
        pg = agent.pilgrimage
        iid = pg.get("instance_id")
        if not iid or iid not in self.pilgrimage_instances:
            agent.log("No active pilgrimage — open a lobby first.")
            return True
        inst = self.pilgrimage_instances[iid]
        if not pg.get("beat_done"):
            agent.log("Seal your personal Canticle beat before the Spire.")
            return True
        if not inst.get("finale_unlocked"):
            agent.log("Spire sealed — wait until all pilgrims finish their beats.")
            return True
        if not self._pilgrimage_near_pad(agent, inst):
            pad = inst.get("pad") or {}
            agent.log(
                "Spire pad cold — move within %d of (%d,%d)."
                % (
                    FINALE_ENTER_RADIUS,
                    int(pad.get("x", 0)),
                    int(pad.get("y", 0)),
                )
            )
            return True
        pg["finale_entered"] = True
        entered = list(inst.get("finale_entered") or [])
        if agent.id not in entered:
            entered.append(agent.id)
            inst["finale_entered"] = entered
        agent.mode = "pilgrimage"
        if hasattr(agent, "cutscene"):
            agent.cutscene("terminal")
        if hasattr(agent, "sfx"):
            agent.sfx("pulse")
        agent.log(
            "You enter the Canticle Spire — ash trails braid overhead. "
            "Pilgrim pages sing in a shared lattice. leave_pilgrimage to exit."
        )
        if not pg.get("rewards_claimed"):
            self._pilgrimage_grant_rewards(agent, inst)
        return True

    def _pilgrimage_grant_rewards(self, agent, inst: Dict[str, Any]) -> None:
        pg = agent.pilgrimage
        if pg.get("rewards_claimed"):
            return
        pg["rewards_claimed"] = True
        credits = PILGRIMAGE_REWARD_CREDITS
        agent.credits = int(getattr(agent, "credits", 0) or 0) + credits
        season = getattr(agent, "season", None)
        if not isinstance(season, dict):
            season = {"id": None, "xp": 0, "tier": 0, "unlocked": [], "equipped": None}
            agent.season = season
        unlocked = list(season.get("unlocked") or [])
        cos_id = PILGRIMAGE_COSMETIC["id"]
        newly = False
        if cos_id not in unlocked:
            unlocked.append(cos_id)
            season["unlocked"] = unlocked
            newly = True
            if not season.get("equipped"):
                season["equipped"] = cos_id
        grant = getattr(self, "_grant_season_xp", None)
        if callable(grant):
            grant(agent, PILGRIMAGE_REWARD_SEASON_XP)
        rng = getattr(self, "rng", None)
        line_tpl = REWARD_LINES[0]
        if rng is not None:
            line_tpl = rng.choice(REWARD_LINES)
        agent.log(line_tpl.format(credits=credits))
        if newly:
            agent.log(
                "Cosmetic unlocked: %s (season_equip %s)."
                % (PILGRIMAGE_COSMETIC["name"], cos_id)
            )
        flags = agent.quest_flags if isinstance(getattr(agent, "quest_flags", None), dict) else {}
        agent.quest_flags = flags
        flags["pilgrimage_complete"] = True
        flags["canticle_spire"] = True
        self._pilgrimage_sync_side_quest(
            agent,
            "Canticle Pilgrimage complete — Spire broadcast delivered.",
            done=True,
        )
        if hasattr(self, "_push_event"):
            self._push_event(
                "pilgrimage",
                "%s entered Canticle Spire finale." % agent.name,
                phase="reward",
                instance_id=inst.get("id"),
                courier=agent.name,
            )
        if hasattr(self, "_analytics"):
            self._analytics("pilgrimage", agent)

    def _leave_pilgrimage_room(self, agent) -> bool:
        if getattr(agent, "mode", None) != "pilgrimage":
            agent.log("Not in the Canticle Spire.")
            return True
        agent.mode = "play"
        agent.log("You step back to street asphalt. Spire lattice dims behind ash glass.")
        if hasattr(self, "update_fov"):
            self.update_fov(agent)
        return True

    def _pilgrimage_on_move(self, agent) -> None:
        """Auto-complete beat when stepping the personal shrine."""
        self._pilgrimage_bootstrap_agent(agent)
        pg = agent.pilgrimage
        if not pg.get("instance_id") or pg.get("beat_done"):
            return
        if self._pilgrimage_near_shrine(agent):
            self._pilgrimage_complete_beat(agent)

    def _pilgrimage_objective(self, agent) -> Optional[Dict[str, Any]]:
        """Compass retarget while pilgrimage beats / finale are active."""
        self._pilgrimage_bootstrap_agent(agent)
        pg = agent.pilgrimage
        iid = pg.get("instance_id")
        if not iid or iid not in self.pilgrimage_instances:
            return None
        # Don't steal Payload-Zero mid-run unless payload already cleared/won
        if not getattr(agent, "won", False) and not (
            isinstance(getattr(agent, "quest_flags", None), dict)
            and agent.quest_flags.get("payload_cleared")
        ):
            if agent.has_payload() if hasattr(agent, "has_payload") else False:
                return None
            # Allow pilgrimage compass when actively on instance even mid-payload arc
            # if beat assigned — still prefer pilgrimage while instance live
            pass
        inst = self.pilgrimage_instances[iid]
        px, py = agent.actor.x, agent.actor.y

        def _bearing(tx: int, ty: int) -> Dict[str, Any]:
            dx, dy = tx - px, ty - py
            dist = abs(dx) + abs(dy)
            if dx == 0 and dy == 0:
                bearing, compass = "here", "★"
            else:
                sx = 0 if abs(dx) * 2 < abs(dy) else (1 if dx > 0 else -1)
                sy = 0 if abs(dy) * 2 < abs(dx) else (1 if dy > 0 else -1)
                table = {
                    (0, -1): ("N", "↑"),
                    (0, 1): ("S", "↓"),
                    (1, 0): ("E", "→"),
                    (-1, 0): ("W", "←"),
                    (1, -1): ("NE", "↗"),
                    (-1, -1): ("NW", "↖"),
                    (1, 1): ("SE", "↘"),
                    (-1, 1): ("SW", "↙"),
                }
                bearing, compass = table.get((sx, sy), ("?", "·"))
            return {
                "target": [tx, ty],
                "dist": dist,
                "bearing": bearing,
                "compass": compass,
            }

        if not pg.get("beat_done"):
            shrine = (inst.get("shrines") or {}).get(agent.id)
            if shrine:
                meta = _bearing(int(shrine["x"]), int(shrine["y"]))
                beat = CANTICLE_BY_ID.get(shrine["beat_id"], {})
                return {
                    "id": "pilgrim_beat_%s" % shrine["beat_id"],
                    "text": "Pilgrim beat · %s (%s)"
                    % (beat.get("title", "Canticle"), shrine.get("label", "shrine")),
                    **meta,
                }
        if inst.get("finale_unlocked") and not pg.get("rewards_claimed"):
            pad = inst.get("pad") or {}
            tx, ty = int(pad.get("x", 0)), int(pad.get("y", 0))
            meta = _bearing(tx, ty)
            return {
                "id": "pilgrim_finale",
                "text": "Enter Canticle Spire (enter_pilgrimage) · shared finale",
                **meta,
            }
        return None

    def _pilgrimage_landmarks(self) -> List[Dict[str, Any]]:
        marks: List[Dict[str, Any]] = []
        pad = self.pilgrimage_pad
        if pad:
            marks.append(
                {
                    "id": "pilgrimage_pad",
                    "name": "Canticle Spire Pad",
                    "glyph": "P",
                    "x": pad[0],
                    "y": pad[1],
                    "z": 0,
                }
            )
        for inst in self.pilgrimage_instances.values():
            if inst.get("phase") not in ("beats", "finale"):
                continue
            for mid, shrine in (inst.get("shrines") or {}).items():
                if shrine.get("done"):
                    continue
                marks.append(
                    {
                        "id": "pilgrim_shrine_%s_%s" % (inst["id"], mid[:4]),
                        "name": "Pilgrim · %s" % shrine.get("label", "Shrine"),
                        "glyph": "P",
                        "x": int(shrine["x"]),
                        "y": int(shrine["y"]),
                        "z": 0,
                    }
                )
        return marks

    def _pilgrimage_snapshot(self, agent) -> Dict[str, Any]:
        self._pilgrimage_bootstrap_agent(agent)
        pg = agent.pilgrimage
        lid = pg.get("lobby_id")
        lobby = self.pilgrimage_lobbies.get(lid) if lid else None
        iid = pg.get("instance_id")
        inst = self.pilgrimage_instances.get(iid) if iid else None
        lobby_snap = None
        if lobby:
            members = []
            ready_map = dict(lobby.get("ready") or {})
            for mid in lobby.get("members") or []:
                m = self.players.get(mid)
                members.append(
                    {
                        "name": m.name if m else mid,
                        "ready": bool(ready_map.get(mid)),
                        "host": lobby.get("host") == mid,
                    }
                )
            lobby_snap = {
                "id": lobby["id"],
                "phase": lobby.get("phase"),
                "members": members,
                "count": len(members),
                "min": PILGRIMAGE_MIN,
                "max": PILGRIMAGE_MAX,
                "can_start": self._pilgrimage_can_start(lobby)[0],
            }
        beat = None
        finale = None
        if inst:
            shrine = (inst.get("shrines") or {}).get(agent.id)
            if shrine:
                meta = CANTICLE_BY_ID.get(shrine["beat_id"], {})
                beat = {
                    "id": shrine["beat_id"],
                    "title": shrine.get("title") or meta.get("title"),
                    "district": shrine.get("district"),
                    "label": shrine.get("label"),
                    "x": int(shrine["x"]),
                    "y": int(shrine["y"]),
                    "done": bool(shrine.get("done") or pg.get("beat_done")),
                    "prose": meta.get("prose"),
                }
            pad = inst.get("pad") or {}
            done_n = sum(1 for s in (inst.get("shrines") or {}).values() if s.get("done"))
            total = len(inst.get("shrines") or {})
            finale = {
                "unlocked": bool(inst.get("finale_unlocked")),
                "pad": {"x": int(pad.get("x", 0)), "y": int(pad.get("y", 0))},
                "beats_done": done_n,
                "beats_total": total,
                "can_enter": bool(
                    inst.get("finale_unlocked")
                    and pg.get("beat_done")
                    and self._pilgrimage_near_pad(agent, inst)
                    and not pg.get("rewards_claimed")
                ),
                "entered": bool(pg.get("finale_entered")),
            }
        return {
            "lobby": lobby_snap,
            "instance_id": iid,
            "in_lobby": bool(lobby_snap),
            "in_instance": bool(inst),
            "ready": bool(pg.get("ready")),
            "host": bool(pg.get("host")),
            "beat": beat,
            "beat_done": bool(pg.get("beat_done")),
            "finale": finale,
            "mode_pilgrimage": getattr(agent, "mode", None) == "pilgrimage",
            "rewards_claimed": bool(pg.get("rewards_claimed")),
            "reward": {
                "credits": PILGRIMAGE_REWARD_CREDITS,
                "cosmetic": dict(PILGRIMAGE_COSMETIC),
                "season_xp": PILGRIMAGE_REWARD_SEASON_XP,
                "p2w": False,
            },
            "min_players": PILGRIMAGE_MIN,
            "max_players": PILGRIMAGE_MAX,
        }

    def _pilgrimage_status_log(self, agent) -> bool:
        snap = self._pilgrimage_snapshot(agent)
        if snap.get("lobby"):
            lob = snap["lobby"]
            names = ", ".join(
                ("%s%s" % (m["name"], "✓" if m["ready"] else "·")) for m in lob["members"]
            )
            agent.log(
                "Pilgrimage lobby %s · %d/%d [%s] can_start=%s"
                % (lob["id"], lob["count"], lob["max"], names, lob["can_start"])
            )
            return True
        if snap.get("in_instance"):
            beat = snap.get("beat") or {}
            fin = snap.get("finale") or {}
            agent.log(
                "Pilgrimage %s · beat %s%s · finale %s (%d/%d) · reward %scr + %s"
                % (
                    snap.get("instance_id"),
                    beat.get("title") or "?",
                    "✓" if snap.get("beat_done") else "",
                    "OPEN" if fin.get("unlocked") else "sealed",
                    fin.get("beats_done", 0),
                    fin.get("beats_total", 0),
                    PILGRIMAGE_REWARD_CREDITS,
                    PILGRIMAGE_COSMETIC["name"],
                )
            )
            return True
        agent.log(
            "Canticle Pilgrimage idle — pilgrimage_open (lobby %d–%d) or pilgrimage_join <id>."
            % (PILGRIMAGE_MIN, PILGRIMAGE_MAX)
        )
        return True

    def _pilgrimage_action(self, agent, action: str, arg: str = "") -> bool:
        self._pilgrimage_bootstrap_agent(agent)
        a = (action or "").strip().lower()
        arg = (arg or "").strip()

        if a in (
            "pilgrimage",
            "pilgrim_status",
            "pilgrimage_status",
            "canticle_status",
            "pilgrim",
        ):
            return self._pilgrimage_status_log(agent)

        if a in ("pilgrimage_open", "pilgrim_lobby", "open_pilgrimage", "canticle_lobby"):
            return self._pilgrimage_open_lobby(agent)

        if a in ("pilgrimage_join", "join_pilgrimage", "pilgrim_join"):
            return self._pilgrimage_join_lobby(agent, arg)

        if a in ("pilgrimage_leave", "leave_pilgrimage", "pilgrim_leave", "exit_pilgrimage"):
            if getattr(agent, "mode", None) == "pilgrimage":
                return self._leave_pilgrimage_room(agent)
            return self._pilgrimage_leave(agent)

        if a in ("pilgrimage_ready", "pilgrim_ready"):
            return self._pilgrimage_set_ready(agent, True)

        if a in ("pilgrimage_unready", "pilgrim_unready"):
            return self._pilgrimage_set_ready(agent, False)

        if a in ("pilgrimage_start", "start_pilgrimage", "canticle_start"):
            force = arg.lower() == "dev"
            return self._pilgrimage_start(agent, force=force)

        if a in (
            "pilgrim_complete",
            "complete_beat",
            "seal_canticle",
            "pilgrimage_beat",
            "complete_pilgrim",
        ):
            return self._pilgrimage_complete_beat(agent)

        if a in (
            "enter_pilgrimage",
            "pilgrim_finale",
            "canticle_finale",
            "enter_spire",
            "canticle_spire",
        ):
            return self._enter_pilgrimage_room(agent)

        if a in ("leave_spire", "exit_spire"):
            return self._leave_pilgrimage_room(agent)

        # Dev: force undersized start after open+join
        if a in ("pilgrimage_force", "force_pilgrimage") and arg.lower() == "dev":
            if not agent.pilgrimage.get("lobby_id"):
                self._pilgrimage_open_lobby(agent)
            return self._pilgrimage_start(agent, force=True)

        return False

    def _pilgrimage_handle_mode(self, agent, action: str) -> bool:
        """While mode==pilgrimage, intercept leave / status."""
        if getattr(agent, "mode", None) != "pilgrimage":
            return False
        a = (action or "").strip().lower()
        if a in (
            "escape",
            "esc",
            "q",
            "leave_pilgrimage",
            "pilgrimage_leave",
            "exit_pilgrimage",
            "leave_spire",
            "jack_out",
        ):
            return self._leave_pilgrimage_room(agent)
        if a in (
            "pilgrimage",
            "pilgrim_status",
            "pilgrimage_status",
            "look",
            "wait",
            ".",
        ):
            agent.log(
                "Canticle Spire: ash trails braid pilgrim pages. "
                "leave_pilgrimage to return to street."
            )
            return True
        if a in ("forward", "back", "strafe_left", "strafe_right", "fire", "hack", "fly"):
            agent.log("Street verbs muted in Canticle Spire — leave_pilgrimage to exit.")
            return True
        return False
