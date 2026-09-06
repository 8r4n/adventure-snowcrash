"""Signal Keys scavenger hunt (#45).

Three layered district keys (Burbclave / Club / Uplink Rim). Collecting all
unlocks a Flotilla finale uplink room + broadcast. Original Metaverse prose only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .. import constants as C
from ..items import Item
from ..mapgen import FloorItem

SIGNAL_KEY_DEFS = (
    {
        "id": "signal_key_burbclave",
        "district": "burbclave",
        "name": "Signal Key · Burbclave",
        "clue": (
            "StreetNet rumor (Burbclave): a franchise key hums behind a gated kiosk "
            "neon — listen for the soft click of a Faraday latch."
        ),
        "hint": "Search near Burbclave franchise pads and the kiosk glow.",
    },
    {
        "id": "signal_key_club",
        "district": "club",
        "name": "Signal Key · Club Glassline",
        "clue": (
            "StreetNet rumor (Club District): bass-line static hides a second key "
            "along the Glassline corridor — watch for a glyph that refuses to dance."
        ),
        "hint": "Sweep Club Glassline floors and Black Neon approaches.",
    },
    {
        "id": "signal_key_uplink_rim",
        "district": "uplink_rim",
        "name": "Signal Key · Uplink Rim",
        "clue": (
            "StreetNet rumor (Uplink Rim): rim towers braid a third key into the "
            "Faraday benches — signal-storm frost marks the sleeve."
        ),
        "hint": "Check Uplink Rim benches and parts stalls near the towers.",
    },
)

SIGNAL_KEY_IDS = tuple(d["id"] for d in SIGNAL_KEY_DEFS)
SIGNAL_KEY_BY_ID = {d["id"]: d for d in SIGNAL_KEY_DEFS}

SIGNAL_SIDE_ID = "signal_keys"
SIGNAL_SIDE_TEXT = (
    "Recover three Signal Keys across Burbclave, Club Glassline, and Uplink Rim — "
    "then open the Flotilla broadcast room at the uplink."
)

FINALE_ENTER_RADIUS = 2


def make_signal_key(key_id: str) -> Item:
    meta = SIGNAL_KEY_BY_ID[key_id]
    return Item(
        id=key_id,
        name=meta["name"],
        glyph="*",
        kind="quest",
        description=(
            "%s. Layered StreetNet shard — sleeve all three to unlock the "
            "Flotilla finale uplink room."
        )
        % meta["hint"],
        quest=True,
        extra={
            "signal_key": True,
            "district": meta["district"],
            "key": True,
        },
    )


class SignalKeysMixin:
    """Mixed into YearFeaturesMixin / GameWorld."""

    def _signal_keys_init(self) -> None:
        self.signal_key_positions: Dict[str, Tuple[int, int]] = {}
        self.flotilla_pad: Optional[Tuple[int, int]] = None
        self._seed_signal_keys()
        self._seed_flotilla_pad()

    def _seed_signal_keys(self) -> None:
        """Place one floor key inside each district AABB (walkable street tile)."""
        existing = {
            fi.item.id
            for fi in getattr(self, "floor_items", [])
            if getattr(fi, "item", None) is not None
        }
        for meta in SIGNAL_KEY_DEFS:
            kid = meta["id"]
            if kid in existing:
                # Remember position if already present
                for fi in self.floor_items:
                    if fi.item.id == kid and int(getattr(fi, "z", 0) or 0) == 0:
                        self.signal_key_positions[kid] = (fi.x, fi.y)
                        break
                continue
            pos = self._find_walkable_in_district(meta["district"])
            if pos is None:
                continue
            x, y = pos
            self.floor_items.append(FloorItem(x, y, make_signal_key(kid), z=0))
            self.signal_key_positions[kid] = (x, y)

    def _seed_flotilla_pad(self) -> None:
        """Finale pad near uplink — enter once all keys are sleeved."""
        ux, uy = self.uplink_pos
        gmap = self.gmap
        candidates = [
            (ux + 2, uy),
            (ux - 2, uy),
            (ux, uy + 2),
            (ux, uy - 2),
            (ux + 1, uy + 1),
            (ux - 1, uy - 1),
        ]
        for x, y in candidates:
            if gmap.in_bounds(x, y) and gmap.walkable(x, y):
                self.flotilla_pad = (x, y)
                return
        self.flotilla_pad = (ux, uy)

    def _find_walkable_in_district(self, district_id: str) -> Optional[Tuple[int, int]]:
        defs = getattr(self, "district_defs", {}) or {}
        meta = None
        for d in defs.get("districts", []):
            if d.get("id") == district_id and d.get("plane") != -1:
                meta = d
                break
        if not meta:
            return None
        w, h = max(1, self.gmap.width), max(1, self.gmap.height)
        x0 = max(1, int(float(meta["x0"]) * w))
        y0 = max(1, int(float(meta["y0"]) * h))
        x1 = min(w - 2, int(float(meta["x1"]) * w))
        y1 = min(h - 2, int(float(meta["y1"]) * h))
        if x1 <= x0 or y1 <= y0:
            return None
        occupied = {
            (fi.x, fi.y)
            for fi in self.floor_items
            if int(getattr(fi, "z", 0) or 0) == 0
        }
        spawn_set = set(getattr(self, "spawn_points", []) or [])
        rng = getattr(self, "rng", None)
        # Prefer center-ish samples, then scan
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        attempts: List[Tuple[int, int]] = [(cx, cy)]
        if rng is not None:
            for _ in range(80):
                attempts.append((rng.randint(x0, x1), rng.randint(y0, y1)))
        else:
            for y in range(y0, y1 + 1, 2):
                for x in range(x0, x1 + 1, 2):
                    attempts.append((x, y))
        for x, y in attempts:
            if not self.gmap.in_bounds(x, y) or not self.gmap.walkable(x, y):
                continue
            if (x, y) in occupied or (x, y) in spawn_set:
                continue
            if (x, y) == tuple(self.jackpoint_pos) or (x, y) == tuple(self.uplink_pos):
                continue
            # Confirm district membership (handles overlapping AABBs)
            d = self._district_at(x, y, 0)
            if d.get("id") != district_id:
                continue
            return (x, y)
        # Fallback: any walkable in AABB even if overlapping district label differs
        for x, y in attempts:
            if (
                self.gmap.in_bounds(x, y)
                and self.gmap.walkable(x, y)
                and (x, y) not in occupied
            ):
                return (x, y)
        return None

    def _signal_keys_bootstrap_agent(self, agent) -> None:
        if not isinstance(getattr(agent, "signal_keys", None), dict):
            agent.signal_keys = {
                "collected": [],
                "clues_seen": [],
                "finale_unlocked": False,
                "finale_entered": False,
                "broadcast_done": False,
            }
        j = getattr(agent, "journal", None)
        if not isinstance(j, dict):
            return
        side = list(j.get("side", []) or [])
        if SIGNAL_SIDE_ID not in [s.get("id") for s in side if isinstance(s, dict)]:
            side.append({
                "id": SIGNAL_SIDE_ID,
                "title": "Signal Keys",
                "text": SIGNAL_SIDE_TEXT,
                "done": False,
                "status": "active",
            })
            j["side"] = side
            agent.journal = j

    def _agent_has_signal_key(self, agent, key_id: str) -> bool:
        sk = getattr(agent, "signal_keys", None) or {}
        if key_id in (sk.get("collected") or []):
            return True
        inv = getattr(getattr(agent, "actor", None), "inventory", None) or []
        return any(getattr(i, "id", None) == key_id for i in inv)

    def _agent_signal_key_ids(self, agent) -> List[str]:
        held = []
        for kid in SIGNAL_KEY_IDS:
            if self._agent_has_signal_key(agent, kid):
                held.append(kid)
        return held

    def _on_signal_key_pickup(self, agent, item: Item) -> None:
        if not item or item.id not in SIGNAL_KEY_BY_ID:
            return
        self._signal_keys_bootstrap_agent(agent)
        sk = agent.signal_keys
        meta = SIGNAL_KEY_BY_ID[item.id]
        if item.id not in sk["collected"]:
            sk["collected"].append(item.id)
        flags = getattr(agent, "quest_flags", None)
        if not isinstance(flags, dict):
            flags = {}
            agent.quest_flags = flags
        flags[item.id] = True
        flags["signal_keys_held"] = len(self._agent_signal_key_ids(agent))
        j = agent.journal if isinstance(agent.journal, dict) else {}
        notes = list(j.get("notes", []) or [])
        notes.append(
            "Signal Key sleeved: %s (%s). %d/3."
            % (meta["name"], meta["district"], len(self._agent_signal_key_ids(agent)))
        )
        j["notes"] = notes[-8:]
        # Update side quest text with progress
        side = list(j.get("side", []) or [])
        progress = "Keys: %s (%d/3)." % (
            ", ".join(SIGNAL_KEY_BY_ID[k]["district"] for k in self._agent_signal_key_ids(agent)),
            len(self._agent_signal_key_ids(agent)),
        )
        for s in side:
            if isinstance(s, dict) and s.get("id") == SIGNAL_SIDE_ID:
                s["text"] = SIGNAL_SIDE_TEXT + " " + progress
                s["status"] = "active"
                s["done"] = False
                break
        j["side"] = side
        agent.journal = j
        agent.log(
            "Journal: %s sleeved — compass retargets. (%d/3)"
            % (meta["name"], len(self._agent_signal_key_ids(agent)))
        )
        if len(self._agent_signal_key_ids(agent)) >= 3:
            self._unlock_signal_finale(agent)

    def _unlock_signal_finale(self, agent) -> None:
        self._signal_keys_bootstrap_agent(agent)
        sk = agent.signal_keys
        if sk.get("finale_unlocked"):
            return
        sk["finale_unlocked"] = True
        flags = agent.quest_flags if isinstance(agent.quest_flags, dict) else {}
        agent.quest_flags = flags
        flags["signal_finale_unlocked"] = True
        agent.log(
            "All Signal Keys resonating — Flotilla uplink room unlocked near U. "
            "Stand on the pad and enter_flotilla."
        )
        j = agent.journal if isinstance(agent.journal, dict) else {}
        notes = list(j.get("notes", []) or [])
        notes.append("Finale unlocked: Flotilla broadcast room near the uplink pad.")
        j["notes"] = notes[-8:]
        side = list(j.get("side", []) or [])
        for s in side:
            if isinstance(s, dict) and s.get("id") == SIGNAL_SIDE_ID:
                s["text"] = (
                    "All keys sleeved — enter the Flotilla broadcast room at the uplink pad."
                )
                s["status"] = "active"
        j["side"] = side
        agent.journal = j
        if hasattr(self, "_push_event"):
            self._push_event(
                "broadcast",
                "%s assembled the Signal Keys — Flotilla room humming." % agent.name,
            )
        if hasattr(self, "_grant_season_xp"):
            self._grant_season_xp(agent, 12)

    def _maybe_district_signal_clue(self, agent) -> None:
        """Whisper district-gated clue once per district visit when key still missing."""
        if not getattr(agent, "actor", None) or not agent.actor.alive:
            return
        if getattr(agent, "mode", "play") not in ("play", None):
            return
        z = int(getattr(agent.actor, "z", 0) or 0)
        if z != C.PLANE_STREET:
            return
        self._signal_keys_bootstrap_agent(agent)
        d = self._district_at(agent.actor.x, agent.actor.y, z)
        did = d.get("id")
        sk = agent.signal_keys
        for meta in SIGNAL_KEY_DEFS:
            if meta["district"] != did:
                continue
            kid = meta["id"]
            if self._agent_has_signal_key(agent, kid):
                continue
            if kid in (sk.get("clues_seen") or []):
                continue
            sk.setdefault("clues_seen", []).append(kid)
            agent.log(meta["clue"])
            j = agent.journal if isinstance(agent.journal, dict) else {}
            notes = list(j.get("notes", []) or [])
            notes.append("Clue (%s): %s" % (meta["district"], meta["hint"]))
            j["notes"] = notes[-8:]
            agent.journal = j
            break

    def _signal_keys_objective(self, agent) -> Optional[Dict[str, Any]]:
        """Override compass when Signal Keys hunt is the active side objective.

        Returns None to keep the default Payload-Zero compass unless the courier
        has engaged the hunt (clue seen / key held / finale unlocked) and payload
        arc is idle or already complete.
        """
        self._signal_keys_bootstrap_agent(agent)
        sk = agent.signal_keys
        # Compass retargets only after a key is sleeved / finale, or payload arc is done
        # (district clues alone stay journal-only so Payload-Zero remains primary).
        payload_done = bool(
            getattr(agent, "won", False)
            or (getattr(agent, "quest_flags", {}) or {}).get("payload_cleared")
        )
        hunt_active = bool(
            sk.get("collected")
            or sk.get("finale_unlocked")
            or sk.get("broadcast_done")
            or payload_done
        )
        if not hunt_active:
            return None
        if sk.get("broadcast_done"):
            return {
                "id": "signal_done",
                "text": "Signal Keys complete · Flotilla broadcast logged",
                "target": None,
                "dist": None,
                "bearing": None,
                "compass": "★",
            }
        # Prefer payload compass if carrying payload and not yet cleared
        if hasattr(agent, "has_payload") and agent.has_payload() and not payload_done:
            return None

        held = set(self._agent_signal_key_ids(agent))
        missing = [d for d in SIGNAL_KEY_DEFS if d["id"] not in held]
        px, py = agent.actor.x, agent.actor.y

        if not missing:
            # Point at flotilla pad
            tx, ty = self.flotilla_pad or self.uplink_pos
            text = "Enter Flotilla uplink room (enter_flotilla) · all keys sleeved"
            oid = "flotilla_finale"
        else:
            nxt = missing[0]
            pos = self.signal_key_positions.get(nxt["id"])
            if pos is None:
                # Point toward district center
                pos = self._district_center_xy(nxt["district"]) or self.spawn_xy
            tx, ty = pos
            text = "Find %s · %s" % (nxt["name"], nxt["hint"])
            oid = nxt["id"]

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
            "id": oid,
            "text": text,
            "target": [tx, ty],
            "dist": dist,
            "bearing": bearing,
            "compass": compass,
        }

    def _district_center_xy(self, district_id: str) -> Optional[Tuple[int, int]]:
        defs = getattr(self, "district_defs", {}) or {}
        for d in defs.get("districts", []):
            if d.get("id") == district_id and d.get("plane") != -1:
                w, h = max(1, self.gmap.width), max(1, self.gmap.height)
                cx = int(((float(d["x0"]) + float(d["x1"])) / 2) * w)
                cy = int(((float(d["y0"]) + float(d["y1"])) / 2) * h)
                return (cx, cy)
        return None

    def _signal_keys_snapshot(self, agent) -> Dict[str, Any]:
        self._signal_keys_bootstrap_agent(agent)
        sk = agent.signal_keys
        held = self._agent_signal_key_ids(agent)
        keys = []
        for meta in SIGNAL_KEY_DEFS:
            kid = meta["id"]
            keys.append({
                "id": kid,
                "name": meta["name"],
                "district": meta["district"],
                "held": kid in held,
                "clue_seen": kid in (sk.get("clues_seen") or []),
                "hint": meta["hint"] if kid in (sk.get("clues_seen") or []) or kid in held else None,
            })
        pad = self.flotilla_pad
        return {
            "keys": keys,
            "held_count": len(held),
            "total": len(SIGNAL_KEY_DEFS),
            "finale_unlocked": bool(sk.get("finale_unlocked") or len(held) >= 3),
            "finale_entered": bool(sk.get("finale_entered")),
            "broadcast_done": bool(sk.get("broadcast_done")),
            "flotilla_pad": list(pad) if pad else None,
            "can_enter_finale": bool(
                (sk.get("finale_unlocked") or len(held) >= 3)
                and not sk.get("broadcast_done")
                and self._near_flotilla_pad(agent)
            ),
        }

    def _near_flotilla_pad(self, agent) -> bool:
        pad = self.flotilla_pad or self.uplink_pos
        z = int(getattr(agent.actor, "z", 0) or 0)
        if z != C.PLANE_STREET:
            return False
        return abs(agent.actor.x - pad[0]) + abs(agent.actor.y - pad[1]) <= FINALE_ENTER_RADIUS

    def _enter_flotilla_room(self, agent) -> bool:
        self._signal_keys_bootstrap_agent(agent)
        sk = agent.signal_keys
        held = self._agent_signal_key_ids(agent)
        if len(held) < 3 and not sk.get("finale_unlocked"):
            agent.log("Flotilla room sealed — sleeve all three Signal Keys first.")
            return True
        if not self._near_flotilla_pad(agent):
            pad = self.flotilla_pad or self.uplink_pos
            agent.log(
                "Flotilla pad cold — move within %d of uplink rim pad (%d,%d)."
                % (FINALE_ENTER_RADIUS, pad[0], pad[1])
            )
            return True
        sk["finale_unlocked"] = True
        sk["finale_entered"] = True
        agent.mode = "flotilla"
        agent.cutscene("terminal")
        agent.sfx("pulse")
        agent.log(
            "You step into the Flotilla uplink room — refugee signal-ships braid "
            "overhead. The three keys fuse into a broadcast lattice."
        )
        if not sk.get("broadcast_done"):
            self._complete_flotilla_broadcast(agent)
        return True

    def _leave_flotilla_room(self, agent) -> bool:
        if getattr(agent, "mode", None) != "flotilla":
            agent.log("Not in the Flotilla room.")
            return True
        agent.mode = "play"
        agent.log("You jack back to street asphalt. Flotilla lattice dims behind the Faraday glass.")
        if hasattr(self, "update_fov"):
            self.update_fov(agent)
        return True

    def _complete_flotilla_broadcast(self, agent) -> None:
        sk = agent.signal_keys
        if sk.get("broadcast_done"):
            return
        sk["broadcast_done"] = True
        flags = agent.quest_flags if isinstance(agent.quest_flags, dict) else {}
        agent.quest_flags = flags
        flags["signal_broadcast"] = True
        flags["signal_keys_complete"] = True
        agent.credits = int(getattr(agent, "credits", 0) or 0) + 40
        agent.log(
            "Flotilla broadcast punched through StreetNet — Cassian Vox's rim "
            "ships echo your courier sigil. +40 credits."
        )
        j = agent.journal if isinstance(agent.journal, dict) else {}
        notes = list(j.get("notes", []) or [])
        notes.append("Flotilla broadcast complete — Signal Keys arc closed.")
        j["notes"] = notes[-8:]
        side = list(j.get("side", []) or [])
        for s in side:
            if isinstance(s, dict) and s.get("id") == SIGNAL_SIDE_ID:
                s["done"] = True
                s["completed"] = True
                s["status"] = "done"
                s["text"] = "Signal Keys recovered — Flotilla broadcast delivered."
        j["side"] = side
        agent.journal = j
        if hasattr(self, "_push_event"):
            self._push_event(
                "broadcast",
                "Flotilla uplink: %s opened the layered Signal Keys lattice." % agent.name,
            )
        if hasattr(self, "_grant_season_xp"):
            self._grant_season_xp(agent, 25)
        if hasattr(self, "_analytics"):
            self._analytics("signal_keys", agent)

    def _signal_keys_action(self, agent, action: str, arg: str = "") -> bool:
        a = (action or "").strip().lower()
        if a in ("enter_flotilla", "flotilla", "flotilla_enter", "signal_finale"):
            return self._enter_flotilla_room(agent)
        if a in ("leave_flotilla", "flotilla_leave", "exit_flotilla"):
            return self._leave_flotilla_room(agent)
        if a in ("signal_keys", "signal_status", "keys_status"):
            snap = self._signal_keys_snapshot(agent)
            parts = [
                ("%s%s" % (k["district"], "✓" if k["held"] else "·"))
                for k in snap["keys"]
            ]
            agent.log(
                "Signal Keys %d/%d [%s] finale=%s"
                % (
                    snap["held_count"],
                    snap["total"],
                    " ".join(parts),
                    "open" if snap["finale_unlocked"] else "sealed",
                )
            )
            return True
        return False

    def _signal_keys_handle_mode(self, agent, action: str) -> bool:
        """While mode==flotilla, intercept leave / status."""
        if getattr(agent, "mode", None) != "flotilla":
            return False
        a = (action or "").strip().lower()
        if a in ("escape", "esc", "q", "leave_flotilla", "flotilla_leave", "exit_flotilla", "jack_out"):
            return self._leave_flotilla_room(agent)
        if a in ("signal_keys", "signal_status", "keys_status", "look", "wait", "."):
            agent.log(
                "Flotilla room: layered keys sing. Refugee banners scroll. "
                "leave_flotilla to return to street."
            )
            return True
        # Soft-mute street verbs
        if a in ("forward", "back", "strafe_left", "strafe_right", "fire", "hack", "fly"):
            agent.log("Street verbs muted in Flotilla room — leave_flotilla to exit.")
            return True
        return False
