"""Globe map zoom-out + region teleport (#54).

Data-driven Earth regions (JSON). Teleport lands on a playable shard generated
with mapgen(region shard_seed). Home region keeps the live shared street world.
News pipeline (#51) can stamp region_id via attach_news_geo().
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .. import constants as C
from ..mapgen import FloorItem, generate_world

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
        self._push_event(
            "broadcast",
            "StreetNet globe layer online — zoom out and uplink-hop regions (#54 stub).",
        )

    def reload_region_defs(self) -> None:
        """Hot-reload regions.json (keeps loaded shards until next teleport)."""
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

    def _globe_bootstrap_agent(self, agent) -> None:
        g = getattr(agent, "globe", None)
        if not isinstance(g, dict):
            agent.globe = {
                "region_id": self.globe_home_id,
                "panel_open": False,
                "cooldown_until": 0.0,
                "last_safe_region_id": self.globe_home_id,
                "last_safe_x": int(getattr(agent, "last_good_x", 0) or 0),
                "last_safe_y": int(getattr(agent, "last_good_y", 0) or 0),
                "last_safe_z": int(getattr(agent, "last_good_z", 0) or 0),
                "teleports": 0,
                "fog_by_region": {},
            }
            return
        g.setdefault("region_id", self.globe_home_id)
        g.setdefault("panel_open", False)
        g.setdefault("cooldown_until", 0.0)
        g.setdefault("last_safe_region_id", self.globe_home_id)
        g.setdefault("last_safe_x", int(getattr(agent, "last_good_x", 0) or 0))
        g.setdefault("last_safe_y", int(getattr(agent, "last_good_y", 0) or 0))
        g.setdefault("last_safe_z", int(getattr(agent, "last_good_z", 0) or 0))
        g.setdefault("teleports", 0)
        g.setdefault("fog_by_region", {})
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
        agent.log(
            "Uplink hop complete — sleeved into %s%s. Cooldown %.0fs."
            % (name, paid, self.globe_teleport_cooldown)
        )
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
            cur = self._globe_agent_region(agent)
            reg = self._globe_region(cur) or {}
            agent.log(
                "Globe overlay open — you are in %s (%s). Teleport: teleport <region_id>."
                % (reg.get("name", cur), cur)
            )
            return True

        if a in ("globe_close", "close_globe"):
            agent.globe["panel_open"] = False
            agent.log("Globe overlay closed.")
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

        return False

    def _globe_snapshot(self, agent) -> Dict[str, Any]:
        self._globe_bootstrap_agent(agent)
        cur = self._globe_agent_region(agent)
        reg = self._globe_region(cur) or {"id": cur, "name": cur}
        now = time.time()
        cd_until = float(agent.globe.get("cooldown_until") or 0)
        regions_out: List[Dict[str, Any]] = []
        for r in self.globe_defs.get("regions", []):
            regions_out.append(
                {
                    "id": r.get("id"),
                    "name": r.get("name"),
                    "kind": r.get("kind"),
                    "continent": r.get("continent"),
                    "lat": r.get("lat"),
                    "lon": r.get("lon"),
                    "label": r.get("label"),
                    "home": bool(r.get("home")),
                }
            )
        shard_seed = None
        if cur == self.globe_home_id:
            shard_seed = getattr(self, "seed", None)
        elif cur in self.globe_shards:
            shard_seed = self.globe_shards[cur].get("seed")
        else:
            shard_seed = (reg or {}).get("shard_seed")
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
            },
            "home_region_id": self.globe_home_id,
            "regions": regions_out,
            "cost_credits": int(self.globe_teleport_cost),
            "cooldown_sec": float(self.globe_teleport_cooldown),
            "cooldown_remaining": max(0.0, cd_until - now),
            "teleports": int(agent.globe.get("teleports") or 0),
            "shards_loaded": sorted(self.globe_shards.keys()),
            "shard_seed": shard_seed,
            "zoom": "globe" if agent.globe.get("panel_open") else "street",
            "news_geo_hook": True,
            "hint": (
                "Globe open — pick a pin / region id, then teleport (credits + cooldown)."
                if agent.globe.get("panel_open")
                else "Open globe (dock Globe or action globe) to zoom out and uplink-hop."
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
