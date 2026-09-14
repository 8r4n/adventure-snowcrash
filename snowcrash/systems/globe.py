"""Globe map zoom-out + region teleport (#54).

Data-driven Earth regions (JSON). Teleport prefers a prebuilt
snowcrash_ascii_shard_v1 pack (regions.json chunk_path / OSM→ASCII) when
present, else mapgen(region shard_seed). Home region keeps the live shared
street world. News pipeline (#51) can stamp region_id via attach_news_geo().
Zoom ladder: street → region list → schematic globe.
Region search / ASCII filter + cross-region geo compass for daily beats.
Pin preview / street flavor + hop cost/cooldown quote before teleport.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .. import constants as C
from ..mapgen import FloorItem, generate_world
from .ascii_shard import try_load_region_shard

DATA_DIR = Path(__file__).resolve().parent / "data"

DEFAULT_TELEPORT_COST = 15
DEFAULT_TELEPORT_COOLDOWN = 45.0


def _load_regions_doc() -> Dict[str, Any]:
    path = DATA_DIR / "regions.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


class GlobeMixin:
    """Mixed into YearFeaturesMixin / GameWorld."""

    def _globe_init(self) -> None:
        doc = _load_regions_doc()
        self.globe_defs = doc
        self.globe_home_id = str(doc.get("home_region_id") or "fractured_la")
        self.globe_teleport_cost = int(doc.get("teleport_cost_credits", DEFAULT_TELEPORT_COST))
        self.globe_teleport_cooldown = float(
            doc.get("teleport_cooldown_sec", DEFAULT_TELEPORT_COOLDOWN)
        )
        self.globe_regions: Dict[str, Dict[str, Any]] = {
            str(r["id"]): dict(r) for r in doc.get("regions", []) if r.get("id")
        }
        # Lazy shards: region_id -> packed world slice (not home)
        self.globe_shards: Dict[str, Dict[str, Any]] = {}
        self._globe_ctx_region: str = self.globe_home_id
        self._globe_home_pack: Optional[Dict[str, Any]] = None
        self._globe_bind_depth = 0
        self._globe_shard_meta_cache: Dict[str, Dict[str, Any]] = {}
        self._push_event(
            "broadcast",
            "StreetNet globe layer online — zoom out and uplink-hop regions (#54 stub).",
        )

    def reload_region_defs(self, *, drop_stale_shards: bool = True) -> None:
        """Hot-reload regions.json; optionally drop shards whose chunk_path changed."""
        old_paths = {
            rid: (reg or {}).get("chunk_path")
            for rid, reg in getattr(self, "globe_regions", {}).items()
        }
        doc = _load_regions_doc()
        self.globe_defs = doc
        self.globe_home_id = str(doc.get("home_region_id") or self.globe_home_id)
        self.globe_teleport_cost = int(doc.get("teleport_cost_credits", DEFAULT_TELEPORT_COST))
        self.globe_teleport_cooldown = float(
            doc.get("teleport_cooldown_sec", DEFAULT_TELEPORT_COOLDOWN)
        )
        self.globe_regions = {
            str(r["id"]): dict(r) for r in doc.get("regions", []) if r.get("id")
        }
        if drop_stale_shards:
            self.reload_shard_packs(force=False, old_paths=old_paths)

    def reload_shard_packs(
        self,
        *,
        force: bool = False,
        old_paths: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Invalidate cached shards so next hop reloads JSON/mapgen packs.

        When force=False, only drop shards whose chunk_path changed or whose
        region disappeared. Returns dropped region ids.
        """
        dropped: List[str] = []
        shards = getattr(self, "globe_shards", None)
        if not isinstance(shards, dict):
            return dropped
        for rid in list(shards.keys()):
            reg = self._globe_region(rid)
            if force or reg is None:
                shards.pop(rid, None)
                dropped.append(rid)
                continue
            if old_paths is not None:
                prev = old_paths.get(rid)
                cur = reg.get("chunk_path")
                if prev != cur:
                    shards.pop(rid, None)
                    dropped.append(rid)
        return dropped

    def _globe_bootstrap_agent(self, agent) -> None:
        g = getattr(agent, "globe", None)
        if not isinstance(g, dict):
            agent.globe = {
                "region_id": self.globe_home_id,
                "panel_open": False,
                "zoom": "globe",
                "cooldown_until": 0.0,
                "last_safe_region_id": self.globe_home_id,
                "last_safe_x": int(getattr(agent, "last_good_x", 0) or 0),
                "last_safe_y": int(getattr(agent, "last_good_y", 0) or 0),
                "last_safe_z": int(getattr(agent, "last_good_z", 0) or 0),
                "teleports": 0,
                "fog_by_region": {},
                "search": "",
                "filter_ascii": False,
                "tracked_geo_region": None,
                "tracked_geo_beat": None,
                "preview_region_id": None,
            }
            return
        g.setdefault("region_id", self.globe_home_id)
        g.setdefault("panel_open", False)
        g.setdefault("zoom", "globe")
        g.setdefault("cooldown_until", 0.0)
        g.setdefault("last_safe_region_id", self.globe_home_id)
        g.setdefault("last_safe_x", int(getattr(agent, "last_good_x", 0) or 0))
        g.setdefault("last_safe_y", int(getattr(agent, "last_good_y", 0) or 0))
        g.setdefault("last_safe_z", int(getattr(agent, "last_good_z", 0) or 0))
        g.setdefault("teleports", 0)
        g.setdefault("fog_by_region", {})
        g.setdefault("search", "")
        g.setdefault("filter_ascii", False)
        g.setdefault("tracked_geo_region", None)
        g.setdefault("tracked_geo_beat", None)
        g.setdefault("preview_region_id", None)
        if g["region_id"] not in self.globe_regions:
            g["region_id"] = self.globe_home_id

    def _globe_agent_region(self, agent) -> str:
        self._globe_bootstrap_agent(agent)
        rid = str(agent.globe.get("region_id") or self.globe_home_id)
        if rid not in self.globe_regions:
            return self.globe_home_id
        return rid

    def _globe_region(self, region_id: str) -> Optional[Dict[str, Any]]:
        return self.globe_regions.get(str(region_id or ""))

    def _globe_pack_world(self) -> Dict[str, Any]:
        cur = getattr(self, "_globe_ctx_region", self.globe_home_id)
        prev = {}
        if cur == self.globe_home_id and isinstance(self._globe_home_pack, dict):
            prev = self._globe_home_pack
        elif cur in self.globe_shards:
            prev = self.globe_shards[cur]
        return {
            "seed": getattr(self, "seed", 0),
            "gmap": self.gmap,
            "planes": dict(self.planes),
            "npcs_enemies": self.npcs_enemies,
            "floor_items": self.floor_items,
            "jackpoint_pos": tuple(self.jackpoint_pos),
            "uplink_pos": tuple(self.uplink_pos),
            "spawn_points": list(self.spawn_points),
            "spawn_xy": tuple(self.spawn_xy),
            "shafts": set(getattr(self, "shafts", set()) or set()),
            "club_rects": list(getattr(self, "club_rects", []) or []),
            "region_id": cur,
            "shard_source": prev.get("shard_source"),
            "chunk_path": prev.get("chunk_path"),
        }

    def _globe_apply_pack(self, pack: Dict[str, Any]) -> None:
        self.seed = pack["seed"]
        self.gmap = pack["gmap"]
        self.planes = dict(pack["planes"])
        self.npcs_enemies = pack["npcs_enemies"]
        self.floor_items = pack["floor_items"]
        self.jackpoint_pos = tuple(pack["jackpoint_pos"])
        self.uplink_pos = tuple(pack["uplink_pos"])
        self.spawn_points = list(pack["spawn_points"])
        self.spawn_xy = tuple(pack["spawn_xy"])
        self.shafts = set(pack.get("shafts") or set())
        self.club_rects = list(pack.get("club_rects") or [])

    def _globe_ensure_home_pack(self) -> None:
        if self._globe_home_pack is None:
            self._globe_home_pack = self._globe_pack_world()

    def _globe_ensure_shard(self, region_id: str) -> Dict[str, Any]:
        rid = str(region_id)
        if rid == self.globe_home_id:
            self._globe_ensure_home_pack()
            return self._globe_home_pack  # type: ignore[return-value]
        if rid in self.globe_shards:
            return self.globe_shards[rid]
        reg = self._globe_region(rid)
        if not reg:
            raise KeyError("unknown region %s" % rid)
        seed = reg.get("shard_seed")
        if seed is None:
            seed = (hash(rid) & 0x7FFFFFFF) ^ 0x54C10BE
        seed = int(seed)
        shard_source = "mapgen"
        world = None
        chunk_path = reg.get("chunk_path")
        if chunk_path:
            world = try_load_region_shard(str(chunk_path), seed=seed, region_id=rid)
            if world is not None:
                shard_source = "osm_ascii"
        if world is None:
            world = generate_world(seed)
        gmap = world.gmap
        planes = dict(getattr(world, "planes", None) or {})
        if not planes:
            planes = {C.PLANE_STREET: gmap}
        elif C.PLANE_STREET not in planes:
            planes[C.PLANE_STREET] = gmap
        npcs = [a for a in world.actors if not a.is_player()]
        for a in npcs:
            if not hasattr(a, "z") or a.z is None:
                a.z = C.PLANE_STREET
            setattr(a, "region_id", rid)
        floor_items = list(world.floor_items)
        # Ensure Payload-Zero near jackpoint on every shard
        jx, jy = world.jackpoint_pos
        has_payload = any(
            getattr(fi.item, "id", "") == "payload_zero"
            and abs(fi.x - jx) + abs(fi.y - jy) <= 4
            for fi in floor_items
        )
        if not has_payload:
            from ..items import make_payload_zero

            floor_items.append(FloorItem(jx, jy, make_payload_zero()))
        spawn_xy = (world.player.x, world.player.y)
        spawn_points = list(getattr(world, "spawn_points", None) or [spawn_xy])
        if not spawn_points:
            spawn_points = [spawn_xy]
        pack = {
            "seed": seed,
            "gmap": planes[C.PLANE_STREET],
            "planes": planes,
            "npcs_enemies": npcs,
            "floor_items": floor_items,
            "jackpoint_pos": tuple(world.jackpoint_pos),
            "uplink_pos": tuple(world.uplink_pos),
            "spawn_points": spawn_points,
            "spawn_xy": spawn_xy,
            "shafts": set(getattr(world, "shafts", None) or set()),
            "club_rects": list(getattr(world, "club_rects", None) or []),
            "region_id": rid,
            "shard_source": shard_source,
            "chunk_path": str(chunk_path) if chunk_path and shard_source == "osm_ascii" else None,
        }
        self.globe_shards[rid] = pack
        return pack

    def _globe_stash_fog(self, agent, region_id: str) -> None:
        self._globe_bootstrap_agent(agent)
        fog = agent.globe.setdefault("fog_by_region", {})
        fog[region_id] = {
            "explored_planes": dict(getattr(agent, "explored_planes", {}) or {}),
            "visible_planes": dict(getattr(agent, "visible_planes", {}) or {}),
        }

    def _globe_restore_fog(self, agent, region_id: str) -> None:
        self._globe_bootstrap_agent(agent)
        fog = (agent.globe.get("fog_by_region") or {}).get(region_id)
        if not fog:
            # Fresh shard fog
            z = C.PLANE_STREET
            exp, vis = self._blank_fog(z)
            agent.explored_planes = {z: exp}
            agent.visible_planes = {z: vis}
            agent.explored = exp
            agent.visible = vis
            return
        agent.explored_planes = dict(fog.get("explored_planes") or {})
        agent.visible_planes = dict(fog.get("visible_planes") or {})
        z = int(getattr(agent.actor, "z", 0) or 0)
        if z not in agent.explored_planes:
            exp, vis = self._blank_fog(z)
            agent.explored_planes[z] = exp
            agent.visible_planes[z] = vis
        agent.explored = agent.explored_planes[z]
        agent.visible = agent.visible_planes[z]

    def _globe_persist_current(self) -> None:
        cur = getattr(self, "_globe_ctx_region", self.globe_home_id)
        pack = self._globe_pack_world()
        if cur == self.globe_home_id:
            self._globe_home_pack = pack
        else:
            pack["region_id"] = cur
            self.globe_shards[cur] = pack

    def _globe_load_region_pack(self, rid: str) -> None:
        if rid == self.globe_home_id:
            self._globe_ensure_home_pack()
            self._globe_apply_pack(self._globe_home_pack)  # type: ignore[arg-type]
        else:
            pack = self._globe_ensure_shard(rid)
            self._globe_apply_pack(pack)
        self._globe_ctx_region = rid

    @contextmanager
    def _globe_bind(self, region_id: str) -> Iterator[str]:
        """Swap live world pointers to a region shard (safe under app asyncio.Lock)."""
        rid = str(region_id or self.globe_home_id)
        if rid not in self.globe_regions:
            rid = self.globe_home_id
        self._globe_ensure_home_pack()
        prev = getattr(self, "_globe_ctx_region", self.globe_home_id)
        # Persist whatever is currently live before switching
        self._globe_persist_current()
        self._globe_load_region_pack(rid)
        self._globe_bind_depth = int(getattr(self, "_globe_bind_depth", 0) or 0) + 1
        try:
            yield rid
        finally:
            # Persist the bound region, then restore previous context
            self._globe_persist_current()
            self._globe_load_region_pack(prev)
            self._globe_bind_depth = max(0, int(getattr(self, "_globe_bind_depth", 1) or 1) - 1)

    def _globe_players_on_region(self, region_id: str):
        rid = str(region_id)
        for p in self.players.values():
            if not p.connected:
                continue
            if self._globe_agent_region(p) == rid:
                yield p

    def _globe_match_region(self, query: str, reg: Dict[str, Any]) -> bool:
        """Case-insensitive match against id/name/continent/label/kind."""
        q = (query or "").strip().lower()
        if not q:
            return True
        hay = " ".join(
            str(reg.get(k) or "")
            for k in ("id", "name", "continent", "label", "kind")
        ).lower()
        tokens = [t for t in q.replace(",", " ").split() if t]
        if not tokens:
            return True
        return all(t in hay for t in tokens)

    def _globe_search_regions(
        self,
        query: str = "",
        *,
        ascii_only: bool = False,
    ) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for r in self.globe_defs.get("regions", []):
            if not isinstance(r, dict) or not r.get("id"):
                continue
            if ascii_only and not r.get("chunk_path"):
                continue
            if not self._globe_match_region(query, r):
                continue
            out.append(dict(r))
        return out


    def _globe_shard_meta(self, region_id: str) -> Dict[str, Any]:
        """Lightweight pilot metadata (pilot_note, landmarks, ascii strip) — cached."""
        rid = str(region_id or "")
        cache = getattr(self, "_globe_shard_meta_cache", None)
        if not isinstance(cache, dict):
            self._globe_shard_meta_cache = {}
            cache = self._globe_shard_meta_cache
        if rid in cache:
            return dict(cache[rid])
        reg = self._globe_region(rid) or {}
        meta: Dict[str, Any] = {
            "pilot_note": None,
            "landmarks": [],
            "ascii_strip": None,
            "width": None,
            "height": None,
        }
        chunk_path = reg.get("chunk_path")
        if chunk_path:
            try:
                from .ascii_shard import load_shard_json

                doc = load_shard_json(str(chunk_path))
                meta["pilot_note"] = doc.get("pilot_note")
                lm = doc.get("landmarks") or {}
                if isinstance(lm, dict):
                    meta["landmarks"] = sorted(str(k) for k in lm.keys())
                meta["width"] = doc.get("width")
                meta["height"] = doc.get("height")
                tiles = doc.get("tiles") or []
                if isinstance(tiles, list) and tiles:
                    mid = len(tiles) // 2
                    rows = []
                    for y in range(max(0, mid - 2), min(len(tiles), mid + 3)):
                        row = str(tiles[y])
                        if len(row) > 28:
                            cx = len(row) // 2
                            row = row[max(0, cx - 14) : cx + 14]
                        rows.append(row)
                    meta["ascii_strip"] = "\n".join(rows)
            except Exception:
                pass
        cache[rid] = dict(meta)
        return dict(meta)

    def _globe_street_flavor(self, region_id: str) -> str:
        """Human street flavor line for pin tooltips / preview cards."""
        reg = self._globe_region(region_id) or {}
        meta = self._globe_shard_meta(region_id)
        parts: List[str] = []
        label = (reg.get("label") or "").strip()
        if label:
            parts.append(label)
        note = (meta.get("pilot_note") or "").strip()
        if note and "ASCII pilot" not in note:
            parts.append(note[:96])
        lms = meta.get("landmarks") or []
        if lms:
            parts.append("landmarks: " + ", ".join(lms[:5]))
        if not parts:
            kind = reg.get("kind") or "region"
            cont = reg.get("continent") or "?"
            parts.append("%s pad · continent %s" % (kind, cont))
        return " · ".join(parts)

    def _globe_hop_quote(self, agent, region_id: str) -> Dict[str, Any]:
        """Cost / cooldown / affordability quote for a hop target (UI authority)."""
        self._globe_bootstrap_agent(agent)
        rid = (region_id or "").strip().lower()
        if rid in ("home", "la", "recall", "fractured"):
            rid = self.globe_home_id
        reg = self._globe_region(rid)
        cur = self._globe_agent_region(agent)
        credits = int(getattr(agent, "credits", 0) or 0)
        now = time.time()
        cd_until = float(agent.globe.get("cooldown_until") or 0)
        cd_left = max(0.0, cd_until - now)
        cost = int(self.globe_teleport_cost)
        is_home = rid == self.globe_home_id
        if is_home:
            cost = max(0, cost // 2)
        mode = getattr(agent, "mode", "play")
        blocked = None
        if not reg:
            blocked = "unknown_region"
        elif reg.get("metadata_only") or reg.get("mod_overlay") or reg.get("teleport") is False:
            blocked = "metadata_only"
        elif rid == cur:
            blocked = "already_here"
        elif mode in ("cyberspace", "heist", "flotilla", "dead", "won"):
            blocked = "mode_%s" % mode
        elif cd_left > 0.05:
            blocked = "cooldown"
        elif cost > 0 and credits < cost:
            blocked = "credits"
        reasons = {
            "unknown_region": "Unknown region id.",
            "metadata_only": "Mod metadata pin — not a hop target.",
            "already_here": "Already sleeved here.",
            "cooldown": "Uplink cooldown — %.0fs left." % cd_left,
            "credits": "Need %d credits (have %d)." % (cost, credits),
        }
        if blocked and blocked.startswith("mode_"):
            reasons[blocked] = "Cannot hop while %s." % mode
        return {
            "region_id": rid,
            "cost_credits": cost,
            "recall": is_home,
            "credits": credits,
            "can_afford": credits >= cost,
            "cooldown_remaining": cd_left,
            "on_cooldown": cd_left > 0.05,
            "hop_ready": blocked is None,
            "blocked_reason": blocked,
            "blocked_message": reasons.get(blocked) if blocked else None,
            "here": rid == cur,
        }

    def _globe_preview_card(self, agent, region_id: str) -> Optional[Dict[str, Any]]:
        """Full pin preview: street flavor, landmarks, news beats, hop quote."""
        self._globe_bootstrap_agent(agent)
        rid = (region_id or "").strip().lower()
        if rid in ("home", "la", "recall", "fractured"):
            rid = self.globe_home_id
        reg = self._globe_region(rid)
        if not reg:
            return None
        meta = self._globe_shard_meta(rid)
        quote = self._globe_hop_quote(agent, rid)
        news = [
            {
                "beat_id": o.get("beat_id"),
                "headline": o.get("headline"),
                "lat": o.get("lat"),
                "lon": o.get("lon"),
            }
            for o in self._globe_geo_objectives()
            if o.get("region_id") == rid
        ]
        shard_kind = (
            "home"
            if rid == self.globe_home_id
            else ("osm_ascii" if reg.get("chunk_path") else "mapgen")
        )
        return {
            "id": rid,
            "name": reg.get("name") or rid,
            "label": reg.get("label"),
            "kind": reg.get("kind"),
            "continent": reg.get("continent"),
            "lat": reg.get("lat"),
            "lon": reg.get("lon"),
            "home": bool(reg.get("home")),
            "has_ascii_shard": bool(reg.get("chunk_path")),
            "chunk_path": reg.get("chunk_path"),
            "shard_kind": shard_kind,
            "street_flavor": self._globe_street_flavor(rid),
            "landmarks": list(meta.get("landmarks") or []),
            "ascii_strip": meta.get("ascii_strip"),
            "pilot_note": meta.get("pilot_note"),
            "news": news,
            "has_news": bool(news),
            **quote,
        }

    def _globe_geo_objectives(self) -> List[Dict[str, Any]]:
        """Active daily (#51) beats that carry a region_id for cross-region tracking."""
        active = getattr(self, "daily_storylines_active", None) or {}
        objs: List[Dict[str, Any]] = []
        for b in active.get("beats") or []:
            if not isinstance(b, dict):
                continue
            rid = b.get("region_id") or (b.get("geo") or {}).get("region_id")
            if not rid:
                continue
            reg = self._globe_region(str(rid)) or {}
            geo = b.get("geo") if isinstance(b.get("geo"), dict) else {}
            blat = blon = None
            for src in (geo, b):
                if blat is None and src.get("lat") is not None:
                    try:
                        blat = float(src["lat"])
                    except (TypeError, ValueError):
                        pass
                if blon is None and src.get("lon") is not None:
                    try:
                        blon = float(src["lon"])
                    except (TypeError, ValueError):
                        pass
            objs.append(
                {
                    "beat_id": b.get("id"),
                    "headline": b.get("headline") or b.get("summary") or b.get("text"),
                    "region_id": str(rid),
                    "region_name": reg.get("name") or rid,
                    "lat": blat if blat is not None else reg.get("lat"),
                    "lon": blon if blon is not None else reg.get("lon"),
                    "continent": reg.get("continent") or geo.get("continent"),
                    "pin_lat": blat if blat is not None else reg.get("lat"),
                    "pin_lon": blon if blon is not None else reg.get("lon"),
                }
            )
        return objs

    def _globe_objective(self, agent) -> Optional[Dict[str, Any]]:
        """Compass override: point at a geo-tagged cross-region daily objective."""
        self._globe_bootstrap_agent(agent)
        # Skip when payload is mid-delivery (core loop owns compass)
        if agent.has_payload() and not agent.won:
            return None
        tracked = agent.globe.get("tracked_geo_region")
        objs = self._globe_geo_objectives()
        target = None
        if tracked:
            for o in objs:
                if o.get("region_id") == tracked:
                    target = o
                    break
            if target is None:
                reg = self._globe_region(str(tracked))
                if reg:
                    target = {
                        "beat_id": agent.globe.get("tracked_geo_beat"),
                        "headline": "Tracked region",
                        "region_id": str(tracked),
                        "region_name": reg.get("name") or tracked,
                        "lat": reg.get("lat"),
                        "lon": reg.get("lon"),
                        "continent": reg.get("continent"),
                    }
        if target is None and objs:
            # Prefer a beat not on the courier's current region
            cur = self._globe_agent_region(agent)
            remote = [o for o in objs if o.get("region_id") != cur]
            target = (remote or objs)[0]
        if not target:
            return None
        rid = str(target["region_id"])
        cur = self._globe_agent_region(agent)
        name = target.get("region_name") or rid
        headline = str(target.get("headline") or "StreetNet geo beat")[:72]
        if rid == cur:
            # Same shard — nudge toward jackpoint so the beat "lands"
            jx, jy = self.jackpoint_pos
            px, py = agent.actor.x, agent.actor.y
            dx, dy = jx - px, jy - py
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
                "id": "geo_%s" % rid,
                "text": "StreetNet @ %s — %s (local jackpoint)" % (name, headline),
                "target": [jx, jy],
                "dist": dist,
                "bearing": bearing,
                "compass": compass,
                "region_id": rid,
                "geo": True,
            }
        # Cross-region: bearing from current region lat/lon → target
        cur_reg = self._globe_region(cur) or {}
        try:
            clat = float(cur_reg.get("lat", 0))
            clon = float(cur_reg.get("lon", 0))
            tlat = float(target.get("lat") or 0)
            tlon = float(target.get("lon") or 0)
        except (TypeError, ValueError):
            clat = clon = tlat = tlon = 0.0
        dlat = tlat - clat
        dlon = tlon - clon
        # Rough km for UI only
        dist_km = int(abs(dlat) * 111 + abs(dlon) * 85)
        if abs(dlat) < 0.05 and abs(dlon) < 0.05:
            bearing, compass = "here", "★"
        else:
            sx = 0 if abs(dlon) * 2 < abs(dlat) else (1 if dlon > 0 else -1)
            sy = 0 if abs(dlat) * 2 < abs(dlon) else (-1 if dlat > 0 else 1)  # N = +lat → "up"
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
            "id": "geo_%s" % rid,
            "text": "Uplink-hop to %s — %s (teleport %s)" % (name, headline, rid),
            "target": None,
            "dist": dist_km,
            "bearing": bearing,
            "compass": compass,
            "region_id": rid,
            "geo": True,
            "cross_region": True,
        }

    def attach_news_geo(
        self,
        beat: Optional[Dict[str, Any]] = None,
        region_id: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Hook for daily news (#51): stamp geo / region_id onto a story beat.

        Prefer an explicit region_id. If only lat/lon are given, snap to nearest
        defined region. Returns the mutated (or new) beat dict.
        """
        out: Dict[str, Any] = dict(beat or {})
        rid = region_id
        reg = self._globe_region(rid) if rid else None
        if reg is None and lat is not None and lon is not None:
            rid = self._globe_nearest_region(float(lat), float(lon))
            reg = self._globe_region(rid)
        if reg is None:
            rid = self.globe_home_id
            reg = self._globe_region(rid)
        out["region_id"] = rid
        out["geo"] = {
            "region_id": rid,
            "name": (reg or {}).get("name"),
            "lat": float((reg or {}).get("lat", lat if lat is not None else 0.0)),
            "lon": float((reg or {}).get("lon", lon if lon is not None else 0.0)),
            "continent": (reg or {}).get("continent"),
        }
        if lat is not None:
            out["geo"]["lat"] = float(lat)
        if lon is not None:
            out["geo"]["lon"] = float(lon)
        # Soft tie-in for season forecasts (#58) when daily news only stamps geo
        if hasattr(self, "forecast_state") and isinstance(getattr(self, "forecast_state", None), dict):
            out.setdefault("forecast_hook", True)
            # Prefer full attach_news_arc from pipelines; geo-only stamps mark the hook
            hooks = list(self.forecast_state.get("news_hooks") or [])
            if not out.get("_forecast_bumped"):
                # Tiny ambient bump so #51 geo stamps still move the needle
                metrics = self.forecast_state.setdefault("metrics", {})
                cur = float(metrics.get("news_arc_intensity", 0.35))
                metrics["news_arc_intensity"] = max(0.0, min(1.0, cur + 0.015))
                hooks.append({
                    "t": __import__("time").time(),
                    "text": (out.get("text") or out.get("summary") or "geo news stamp")[:120],
                    "region_id": out.get("region_id"),
                    "bump": 0.015,
                    "news_arc_intensity": round(metrics["news_arc_intensity"], 3),
                    "via": "attach_news_geo",
                })
                self.forecast_state["news_hooks"] = hooks[-12:]
                if hasattr(self, "_forecast_compose_headline"):
                    self.forecast_state["headline"] = self._forecast_compose_headline()
        return out

    def _globe_nearest_region(self, lat: float, lon: float) -> str:
        best = self.globe_home_id
        best_d = 1e18
        for rid, reg in self.globe_regions.items():
            try:
                rlat = float(reg.get("lat", 0))
                rlon = float(reg.get("lon", 0))
            except (TypeError, ValueError):
                continue
            # Cheap equirectangular distance (good enough for city snap)
            dy = (rlat - lat) * 111.0
            dx = (rlon - lon) * 111.0 * max(0.2, abs(__import__("math").cos(__import__("math").radians(lat))))
            d = dx * dx + dy * dy
            if d < best_d:
                best_d = d
                best = rid
        return best

    def _globe_remember_safe(self, agent) -> None:
        self._globe_bootstrap_agent(agent)
        agent.globe["last_safe_region_id"] = self._globe_agent_region(agent)
        agent.globe["last_safe_x"] = int(agent.actor.x)
        agent.globe["last_safe_y"] = int(agent.actor.y)
        agent.globe["last_safe_z"] = int(getattr(agent.actor, "z", 0) or 0)
        self._remember_pos(agent)

    def _globe_failsafe(self, agent, reason: str = "globe fail-safe") -> bool:
        """Return courier to last safe region (or home). Never soft-locks."""
        self._globe_bootstrap_agent(agent)
        rid = str(agent.globe.get("last_safe_region_id") or self.globe_home_id)
        if rid not in self.globe_regions:
            rid = self.globe_home_id
        x = int(agent.globe.get("last_safe_x", 0) or 0)
        y = int(agent.globe.get("last_safe_y", 0) or 0)
        z = int(agent.globe.get("last_safe_z", 0) or 0)
        try:
            with self._globe_bind(rid):
                if not self._can_stand(x, y, ignore=agent.actor, z=z):
                    x, y = self._find_spawn()
                    z = C.PLANE_STREET
                self._globe_stash_fog(agent, self._globe_agent_region(agent))
                agent.globe["region_id"] = rid
                self._globe_restore_fog(agent, rid)
                self._force_set_pos(agent, x, y, z, reason)
                self._grant_spawn_invuln(agent)
                self.update_fov(agent)
            agent.log("Uplink fail-safe — returned to %s." % (
                (self._globe_region(rid) or {}).get("name") or rid
            ))
            return True
        except Exception:
            # Last resort: home spawn
            with self._globe_bind(self.globe_home_id):
                agent.globe["region_id"] = self.globe_home_id
                sx, sy = self._find_spawn()
                self._force_set_pos(agent, sx, sy, C.PLANE_STREET, reason + " home")
                self._globe_restore_fog(agent, self.globe_home_id)
                self.update_fov(agent)
            agent.log("Hard fail-safe — Fractured LA pad restored.")
            return True

    def _globe_teleport(self, agent, region_id: str, *, force: bool = False) -> bool:
        self._globe_bootstrap_agent(agent)
        rid = (region_id or "").strip().lower()
        # allow aliases
        if rid in ("home", "la", "recall", "fractured"):
            rid = self.globe_home_id
        reg = self._globe_region(rid)
        if not reg:
            agent.log(
                "Unknown region. Open globe and pick an id (e.g. neo_tokyo, cont_eu)."
            )
            return True
        if reg.get("metadata_only") or reg.get("mod_overlay") or reg.get("teleport") is False:
            agent.log(
                "%s is mod metadata only — pin visible on globe, not a hop target."
                % reg.get("name", rid)
            )
            agent.globe["panel_open"] = True
            return True
        cur = self._globe_agent_region(agent)
        if rid == cur and not force:
            agent.log("Already sleeved in %s." % reg.get("name", rid))
            agent.globe["panel_open"] = True
            return True
        # Modes that must not mid-teleport
        mode = getattr(agent, "mode", "play")
        if mode in ("cyberspace", "heist", "flotilla", "dead", "won"):
            agent.log("Cannot uplink-hop while %s. Jack out / finish first." % mode)
            return True
        now = time.time()
        cd_until = float(agent.globe.get("cooldown_until") or 0)
        if not force and now < cd_until:
            left = int(cd_until - now) + 1
            agent.log("Uplink cooldown — %ds before next globe hop." % left)
            return True
        cost = int(self.globe_teleport_cost)
        # Home recall is cheaper
        if rid == self.globe_home_id:
            cost = max(0, cost // 2)
        credits = int(getattr(agent, "credits", 0) or 0)
        if not force and cost > 0 and credits < cost:
            agent.log("Need %d credits for uplink hop (have %d)." % (cost, credits))
            return True

        # Remember safe pad on current region before leaving
        self._globe_remember_safe(agent)
        self._globe_stash_fog(agent, cur)

        try:
            with self._globe_bind(rid):
                # Place near spawn
                sx, sy = self._find_spawn()
                agent.globe["region_id"] = rid
                self._globe_restore_fog(agent, rid)
                if not force and cost > 0:
                    agent.credits = max(0, credits - cost)
                agent.globe["cooldown_until"] = now + float(self.globe_teleport_cooldown)
                agent.globe["teleports"] = int(agent.globe.get("teleports") or 0) + 1
                agent.globe["panel_open"] = True
                self._force_set_pos(agent, sx, sy, C.PLANE_STREET, "globe teleport %s" % rid)
                n = 0
                if hasattr(self, "clear_spawn_threats"):
                    n = self.clear_spawn_threats(sx, sy, C.PLANE_STREET)
                self._grant_spawn_invuln(agent)
                self.update_fov(agent)
                if n:
                    agent.log("Cleared %d hostiles near shard pad." % n)
        except Exception as exc:
            agent.log("Uplink hop failed (%s) — fail-safe." % exc)
            self._globe_failsafe(agent, "teleport failure")
            return True

        name = reg.get("name") or rid
        paid = "" if force or cost <= 0 else (" (−%d cr)" % cost)
        src = ""
        pack = self.globe_shards.get(rid) if rid != self.globe_home_id else None
        if isinstance(pack, dict) and pack.get("shard_source") == "osm_ascii":
            src = " · ASCII shard"
        elif rid != self.globe_home_id:
            src = " · mapgen shard"
        agent.log(
            "Uplink hop complete — sleeved into %s%s%s. Cooldown %.0fs."
            % (name, paid, src, self.globe_teleport_cooldown)
        )
        # After hop, drop zoom to street so GPS closes onto the pad
        agent.globe["zoom"] = "street"
        agent.globe["preview_region_id"] = rid
        if hasattr(self, "_primer_note_progress"):
            self._primer_note_progress(agent, "globe_hop", 1)
        agent.sfx("uplink")
        if hasattr(self, "system_chat"):
            self.system_chat("%s uplink-hopped to %s." % (agent.name, name))
        self._push_event(
            "globe",
            "%s teleported to %s" % (agent.name, name),
            region_id=rid,
            agent=agent.name,
        )
        # Journal / quest flavor for news geo later
        qf = getattr(agent, "quest_flags", None)
        if isinstance(qf, dict):
            qf["globe_hopped"] = True
            qf["globe_region"] = rid
        return True

    def _globe_action(self, agent, action: str, arg: str = "") -> bool:
        self._globe_bootstrap_agent(agent)
        a = (action or "").strip().lower()
        arg = (arg or "").strip()

        if a in ("globe", "open_globe", "map_globe", "earth", "gps_globe"):
            agent.globe["panel_open"] = True
            # Opening dock zooms out to schematic Earth unless already mid-ladder
            z = str(agent.globe.get("zoom") or "globe")
            if z == "street":
                agent.globe["zoom"] = "globe"
            cur = self._globe_agent_region(agent)
            reg = self._globe_region(cur) or {}
            agent.log(
                "Globe overlay open (%s zoom) — you are in %s (%s). Teleport: teleport <region_id>."
                % (agent.globe.get("zoom"), reg.get("name", cur), cur)
            )
            return True

        if a in ("globe_close", "close_globe"):
            agent.globe["panel_open"] = False
            agent.globe["zoom"] = "street"
            agent.log("Globe overlay closed — street GPS.")
            return True

        if a in ("globe_zoom", "zoom_globe", "zoom"):
            level = (arg or "").strip().lower()
            aliases = {
                "street": "street",
                "gps": "street",
                "local": "street",
                "region": "region",
                "regions": "region",
                "list": "region",
                "district": "region",
                "globe": "globe",
                "earth": "globe",
                "world": "globe",
                "out": "globe",
                "in": "street",
            }
            level = aliases.get(level, level)
            if level not in ("street", "region", "globe"):
                agent.log("Usage: globe_zoom street|region|globe")
                return True
            agent.globe["zoom"] = level
            agent.globe["panel_open"] = level != "street"
            agent.log("Globe zoom → %s." % level)
            return True

        if a in ("globe_status", "region_status", "where"):
            cur = self._globe_agent_region(agent)
            reg = self._globe_region(cur) or {}
            left = max(0.0, float(agent.globe.get("cooldown_until") or 0) - time.time())
            agent.log(
                "Region %s · lat %.2f lon %.2f · cooldown %.0fs · cost %d cr · shards loaded %d"
                % (
                    reg.get("name", cur),
                    float(reg.get("lat", 0)),
                    float(reg.get("lon", 0)),
                    left,
                    self.globe_teleport_cost,
                    len(self.globe_shards),
                )
            )
            return True

        if a in ("teleport", "globe_teleport", "uplink_hop", "hop", "tp"):
            if not arg:
                agent.globe["panel_open"] = True
                agent.log("Usage: teleport <region_id> (e.g. teleport neo_tokyo)")
                return True
            return self._globe_teleport(agent, arg)

        if a in ("globe_recall", "recall", "home_hop"):
            return self._globe_teleport(agent, self.globe_home_id)

        if a in ("globe_failsafe", "globe_rescue"):
            return self._globe_failsafe(agent)

        if a in ("globe_search", "search_globe", "region_search"):
            q = (arg or "").strip()
            agent.globe["search"] = q[:64]
            agent.globe["panel_open"] = True
            if str(agent.globe.get("zoom") or "street") == "street":
                agent.globe["zoom"] = "region"
            hits = self._globe_search_regions(
                q, ascii_only=bool(agent.globe.get("filter_ascii"))
            )
            if not q:
                agent.log("Globe search cleared — showing all regions.")
            else:
                agent.log(
                    "Globe search %r → %d region(s). Tip: filter ascii with globe_filter ascii."
                    % (q, len(hits))
                )
            return True

        if a in ("globe_filter", "filter_globe"):
            mode = (arg or "").strip().lower()
            if mode in ("ascii", "shard", "shards", "osm", "on", "1", "true"):
                agent.globe["filter_ascii"] = True
                agent.log("Globe filter → ASCII shard pilots only.")
            elif mode in ("all", "clear", "off", "0", "false", "any", ""):
                agent.globe["filter_ascii"] = False
                agent.log("Globe filter cleared — all regions.")
            else:
                agent.log("Usage: globe_filter ascii|all")
                return True
            agent.globe["panel_open"] = True
            if str(agent.globe.get("zoom") or "street") == "street":
                agent.globe["zoom"] = "region"
            return True

        if a in ("globe_track", "track_geo", "geo_track"):
            rid = (arg or "").strip().lower()
            if not rid or rid in ("clear", "none", "off"):
                agent.globe["tracked_geo_region"] = None
                agent.globe["tracked_geo_beat"] = None
                agent.log("Cleared geo track — compass returns to payload loop.")
                return True
            if rid not in self.globe_regions:
                agent.log("Unknown region to track. Example: globe_track neo_tokyo")
                return True
            agent.globe["tracked_geo_region"] = rid
            # Prefer matching daily beat if any
            beat_id = None
            for o in self._globe_geo_objectives():
                if o.get("region_id") == rid:
                    beat_id = o.get("beat_id")
                    break
            agent.globe["tracked_geo_beat"] = beat_id
            name = (self._globe_region(rid) or {}).get("name") or rid
            agent.log("Tracking geo objective → %s (%s). Compass retargets." % (name, rid))
            # Journal side note
            j = getattr(agent, "journal", None)
            if isinstance(j, dict):
                notes = list(j.get("notes") or [])
                notes.append("Geo track: %s (%s)" % (name, rid))
                j["notes"] = notes[-8:]
            return True


        if a in ("globe_preview", "preview_region", "preview_globe", "pin_preview"):
            if not arg or arg.lower() in ("clear", "none", "-"):
                agent.globe["preview_region_id"] = None
                agent.log("Globe pin preview cleared.")
                return True
            card = self._globe_preview_card(agent, arg)
            if not card:
                agent.log("Unknown region to preview. Example: globe_preview neo_tokyo")
                agent.globe["panel_open"] = True
                return True
            agent.globe["preview_region_id"] = card["id"]
            agent.globe["panel_open"] = True
            flavor = card.get("street_flavor") or card.get("label") or ""
            news_n = len(card.get("news") or [])
            if card.get("hop_ready"):
                quote = "hop ready · %d cr" % int(card.get("cost_credits") or 0)
            else:
                quote = card.get("blocked_message") or "hop blocked"
            agent.log(
                "Pin preview %s — %s · %s%s"
                % (
                    card.get("name") or card["id"],
                    (flavor[:72] + ("…" if len(flavor) > 72 else "")),
                    quote,
                    (" · %d news beat(s)" % news_n) if news_n else "",
                )
            )
            return True

        return False

    def _globe_snapshot(self, agent) -> Dict[str, Any]:
        self._globe_bootstrap_agent(agent)
        cur = self._globe_agent_region(agent)
        reg = self._globe_region(cur) or {"id": cur, "name": cur}
        now = time.time()
        cd_until = float(agent.globe.get("cooldown_until") or 0)
        regions_out: List[Dict[str, Any]] = []
        geo_by_region: Dict[str, List[Dict[str, Any]]] = {}
        for o in self._globe_geo_objectives():
            gr = str(o.get("region_id") or "")
            if gr:
                geo_by_region.setdefault(gr, []).append(o)
        for r in self.globe_defs.get("regions", []):
            rid = r.get("id")
            eco_nodes = []
            if hasattr(self, "_ecology_nodes_for_region"):
                eco_nodes = [
                    {
                        "id": n.get("id"),
                        "resource": n.get("resource"),
                        "name": n.get("name"),
                    }
                    for n in self._ecology_nodes_for_region(str(rid or ""))
                ]
            news_here = geo_by_region.get(str(rid or ""), [])
            meta = self._globe_shard_meta(str(rid or "")) if r.get("chunk_path") else {}
            regions_out.append(
                {
                    "id": rid,
                    "name": r.get("name"),
                    "kind": r.get("kind"),
                    "continent": r.get("continent"),
                    "lat": r.get("lat"),
                    "lon": r.get("lon"),
                    "label": r.get("label"),
                    "home": bool(r.get("home")),
                    "ecology": eco_nodes,
                    "has_ecology": bool(eco_nodes),
                    "has_ascii_shard": bool(r.get("chunk_path")),
                    "chunk_path": r.get("chunk_path"),
                    "street_flavor": self._globe_street_flavor(str(rid or "")),
                    "landmarks": list(meta.get("landmarks") or []),
                    "has_news": bool(news_here),
                    "news_count": len(news_here),
                    "news_headline": (news_here[0].get("headline") if news_here else None),
                    "news_lat": (news_here[0].get("lat") if news_here else None),
                    "news_lon": (news_here[0].get("lon") if news_here else None),
                }
            )

        search_q = str(agent.globe.get("search") or "")
        ascii_only = bool(agent.globe.get("filter_ascii"))
        # Snapshot always ships the full catalog; UI / TUI filter via search fields.

        shard_seed = None
        if cur == self.globe_home_id:
            shard_seed = getattr(self, "seed", None)
        elif cur in self.globe_shards:
            shard_seed = self.globe_shards[cur].get("seed")
        else:
            shard_seed = (reg or {}).get("shard_seed")
        zoom = str(agent.globe.get("zoom") or ("globe" if agent.globe.get("panel_open") else "street"))
        if not agent.globe.get("panel_open") and zoom != "street":
            zoom = "street"
        shard_source = None
        chunk_path = None
        if cur == self.globe_home_id:
            shard_source = "home"
        elif cur in self.globe_shards:
            shard_source = self.globe_shards[cur].get("shard_source") or "mapgen"
            chunk_path = self.globe_shards[cur].get("chunk_path")
        elif (reg or {}).get("chunk_path"):
            shard_source = "osm_ascii"  # available on next hop
            chunk_path = (reg or {}).get("chunk_path")
        else:
            shard_source = "mapgen"
        ascii_count = sum(1 for r in self.globe_defs.get("regions", []) if r.get("chunk_path"))
        geo_objs = self._globe_geo_objectives()
        credits = int(getattr(agent, "credits", 0) or 0)
        cost = int(self.globe_teleport_cost)
        recall_cost = max(0, cost // 2)
        cd_left = max(0.0, cd_until - now)
        preview_id = agent.globe.get("preview_region_id")
        preview = self._globe_preview_card(agent, str(preview_id)) if preview_id else None
        hop_quote = self._globe_hop_quote(agent, str(preview_id or cur))
        hints = {
            "street": "Street GPS — open Globe or zoom region/globe to uplink-hop.",
            "region": "Region list — preview a locale, then hop when ready.",
            "globe": "Schematic Earth — tap a pin to preview street flavor, then Hop.",
        }
        return {
            "panel_open": bool(agent.globe.get("panel_open")),
            "region_id": cur,
            "region": {
                "id": reg.get("id", cur),
                "name": reg.get("name", cur),
                "label": reg.get("label"),
                "kind": reg.get("kind"),
                "continent": reg.get("continent"),
                "lat": reg.get("lat"),
                "lon": reg.get("lon"),
                "home": bool(reg.get("home")),
                "has_ascii_shard": bool((reg or {}).get("chunk_path")),
                "street_flavor": self._globe_street_flavor(cur),
            },
            "home_region_id": self.globe_home_id,
            "regions": regions_out,
            "cost_credits": cost,
            "recall_cost_credits": recall_cost,
            "cooldown_sec": float(self.globe_teleport_cooldown),
            "cooldown_remaining": cd_left,
            "credits": credits,
            "can_afford_hop": credits >= cost,
            "can_afford_recall": credits >= recall_cost,
            "hop_ready": hop_quote.get("hop_ready"),
            "hop_block_reason": hop_quote.get("blocked_reason"),
            "hop_block_message": hop_quote.get("blocked_message"),
            "teleports": int(agent.globe.get("teleports") or 0),
            "shards_loaded": sorted(self.globe_shards.keys()),
            "shard_seed": shard_seed,
            "shard_source": shard_source,
            "chunk_path": chunk_path,
            "zoom": zoom,
            "zoom_levels": ["street", "region", "globe"],
            "news_geo_hook": True,
            "search": search_q,
            "filter_ascii": ascii_only,
            "ascii_shard_count": ascii_count,
            "geo_objectives": geo_objs,
            "tracked_geo_region": agent.globe.get("tracked_geo_region"),
            "preview_region_id": preview_id,
            "preview": preview,
            "ecology_nodes": (
                self._ecology_globe_overlay()
                if hasattr(self, "_ecology_globe_overlay")
                else []
            ),
            "hint": hints.get(zoom, hints["globe"]),
            **(
                self._mod_globe_snapshot_extras()
                if hasattr(self, "_mod_globe_snapshot_extras")
                else {"mod_pins": [], "mod_regions": []}
            ),
        }

    def _globe_enemy_tick_all(self) -> None:
        """Tick AI on home + every loaded remote shard."""
        regions = [self.globe_home_id] + [
            rid for rid in self.globe_shards.keys() if rid != self.globe_home_id
        ]
        # Only tick regions that have living couriers (perf: interest streaming)
        active = set()
        for p in self.players.values():
            if p.connected and p.actor.alive and p.actor.x >= 0:
                active.add(self._globe_agent_region(p))
        if not active:
            return
        for rid in regions:
            if rid not in active:
                continue
            with self._globe_bind(rid):
                self._enemy_tick_region()
