"""Shared multiplayer Metaverse world (MMORPG MVP).

One GameWorld instance hosts many PlayerAgents. Clients send intents over
WebSockets; the server applies them authoritatively and broadcasts snapshots.

Quest design (anti-grief): each courier can complete a *personal* Payload-Zero
run. Picking up the jackpoint payload clones it into your inventory; the world
copy stays (or respawns) so other players are not soft-locked.
"""

from __future__ import annotations

import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import constants as C
from .entities import Actor, make_player
from .items import Item, make_mono_knife, make_payload_zero, make_stimpack
from .mapgen import FloorItem, GameMap, generate_world

# Distinct glyphs / neon colors for other avatars
PLAYER_GLYPHS = list("ABCDEFGHJKLMNPQRSTUVWXYZ23456789")
PLAYER_COLORS = [
    "#39c5cf",
    "#ff2a6d",
    "#f0b429",
    "#3dd68c",
    "#d2a8ff",
    "#79c0ff",
    "#ff7b72",
    "#ffa657",
    "#7ee787",
    "#a5d6ff",
]

CHAT_MAX = 60
MSG_MAX = 40
ACTION_RATE_HZ = 12.0  # soft rate limit per player
CHAT_RATE_HZ = 2.0
TICK_HZ = 4.0


def _clone_item(item: Item) -> Item:
    return item.copy()


@dataclass
class ChatLine:
    t: float
    name: str
    text: str
    kind: str = "say"  # say | system


@dataclass
class PlayerAgent:
    id: str
    name: str
    actor: Actor
    glyph: str
    color: str
    quest_flags: Dict[str, bool] = field(default_factory=dict)
    story_seen: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)
    pending_sfx: List[str] = field(default_factory=list)
    pending_cutscenes: List[str] = field(default_factory=list)
    cutscenes_played: List[str] = field(default_factory=list)
    mode: str = "play"
    won: bool = False
    lost: bool = False
    selected_inv: int = 0
    explored: List[List[bool]] = field(default_factory=list)
    visible: List[List[bool]] = field(default_factory=list)
    last_action_ts: float = 0.0
    last_chat_ts: float = 0.0
    connected: bool = True
    invuln_until: float = 0.0  # spawn protection timestamp
    explored_planes: Dict[int, List[List[bool]]] = field(default_factory=dict)
    visible_planes: Dict[int, List[List[bool]]] = field(default_factory=dict)
    last_good_x: int = 0
    last_good_y: int = 0
    last_good_z: int = 0

    def is_invulnerable(self) -> bool:
        return time.time() < self.invuln_until

    @property
    def z(self) -> int:
        return int(getattr(self.actor, "z", 0) or 0)

    def log(self, msg: str) -> None:
        self.messages.append(msg)
        if len(self.messages) > MSG_MAX:
            self.messages = self.messages[-MSG_MAX:]

    def sfx(self, event_id: str) -> None:
        self.pending_sfx.append(event_id)

    def cutscene(self, cutscene_id: str, once: bool = True) -> None:
        if once and cutscene_id in self.cutscenes_played:
            return
        if once:
            self.cutscenes_played.append(cutscene_id)
        self.pending_cutscenes.append(cutscene_id)

    def has_payload(self) -> bool:
        return any(i.id == "payload_zero" for i in self.actor.inventory)


class GameWorld:
    """Authoritative shared street layer."""

    def __init__(self, seed: Optional[int] = None) -> None:
        if seed is None:
            seed = random.randint(0, 2**31 - 1)
        self.seed = seed
        self.rng = random.Random(seed ^ 0xC0FFEE)
        world = generate_world(seed)
        self.gmap: GameMap = world.gmap
        # Drop the seeded single-player actor; we spawn players on join
        self.npcs_enemies: List[Actor] = [a for a in world.actors if not a.is_player()]
        self.floor_items: List[FloorItem] = world.floor_items
        self.uplink_pos = world.uplink_pos
        self.jackpoint_pos = world.jackpoint_pos
        self.story_beats = world.story_beats
        self.spawn_xy = (world.player.x, world.player.y)
        self.spawn_points: List[Tuple[int, int]] = list(
            getattr(world, "spawn_points", None) or [self.spawn_xy]
        )
        if not self.spawn_points:
            self.spawn_points = [self.spawn_xy]
        # Multiplane stack
        self.planes: Dict[int, GameMap] = dict(getattr(world, "planes", None) or {})
        if not self.planes:
            self.planes = {C.PLANE_STREET: self.gmap}
        elif C.PLANE_STREET not in self.planes:
            self.planes[C.PLANE_STREET] = self.gmap
        self.gmap = self.planes[C.PLANE_STREET]
        self.shafts: set = set(getattr(world, "shafts", None) or [])
        # Ensure street actors default z=0; keep under/air as tagged
        for a in self.npcs_enemies:
            if not hasattr(a, "z") or a.z is None:
                a.z = C.PLANE_STREET
        self.players: Dict[str, PlayerAgent] = {}
        self.name_index: Dict[str, str] = {}  # lower name -> id
        self.chat: List[ChatLine] = []
        self.tick = 0
        self.created_at = time.time()
        self._glyph_i = 0
        self._ensure_world_payload()
        self._purge_enemies_near_spawns()
        self.system_chat("Metaverse street layer online. Seed %s." % seed)

    def _ensure_world_payload(self) -> None:
        """Keep at least one Payload-Zero on the jackpoint for personal quests."""
        jx, jy = self.jackpoint_pos
        has = any(
            fi.item.id == "payload_zero"
            and abs(fi.x - jx) + abs(fi.y - jy) <= 4
            for fi in self.floor_items
        )
        if not has:
            # place near jack center
            self.floor_items.append(FloorItem(jx, jy, make_payload_zero()))

    def system_chat(self, text: str) -> None:
        self.chat.append(ChatLine(time.time(), "SYSTEM", text, "system"))
        if len(self.chat) > CHAT_MAX:
            self.chat = self.chat[-CHAT_MAX:]

    def say(self, agent: PlayerAgent, text: str) -> Optional[str]:
        text = (text or "").strip()
        if not text:
            return "empty"
        if len(text) > 200:
            text = text[:200]
        now = time.time()
        if now - agent.last_chat_ts < 1.0 / CHAT_RATE_HZ:
            return "rate"
        agent.last_chat_ts = now
        self.chat.append(ChatLine(now, agent.name, text, "say"))
        if len(self.chat) > CHAT_MAX:
            self.chat = self.chat[-CHAT_MAX:]
        return None

    def _alloc_glyph_color(self) -> Tuple[str, str]:
        g = PLAYER_GLYPHS[self._glyph_i % len(PLAYER_GLYPHS)]
        c = PLAYER_COLORS[self._glyph_i % len(PLAYER_COLORS)]
        self._glyph_i += 1
        return g, c

    def plane_map(self, z: int) -> GameMap:
        return self.planes.get(int(z), self.gmap)

    def _blank_fog(self, z: int) -> Tuple[List[List[bool]], List[List[bool]]]:
        g = self.plane_map(z)
        return (
            [[False] * g.width for _ in range(g.height)],
            [[False] * g.width for _ in range(g.height)],
        )

    def _bind_agent_fog(self, agent: PlayerAgent, z: int) -> None:
        z = int(z)
        if z not in agent.explored_planes:
            exp, vis = self._blank_fog(z)
            agent.explored_planes[z] = exp
            agent.visible_planes[z] = vis
        agent.explored = agent.explored_planes[z]
        agent.visible = agent.visible_planes[z]

    def _grant_spawn_invuln(self, agent: "PlayerAgent") -> None:
        agent.invuln_until = time.time() + float(C.SPAWN_INVULN_SEC)
        agent.log(
            "Spawn shield active (%.1fs) — AI can't flatline you yet."
            % float(C.SPAWN_INVULN_SEC)
        )


    def _near_any_spawn(self, x: int, y: int, radius: Optional[int] = None) -> bool:
        """True if (x,y) is within Manhattan radius of any street spawn pad."""
        r = int(C.SAFE_SPAWN_RADIUS if radius is None else radius)
        for sx, sy in self.spawn_points:
            if abs(x - sx) + abs(y - sy) <= r:
                return True
        sx, sy = self.spawn_xy
        return abs(x - sx) + abs(y - sy) <= r

    def _purge_enemies_near_spawns(self) -> None:
        """After mapgen load: relocate or delete enemies inside SAFE_SPAWN_RADIUS."""
        kept: List[Actor] = []
        purged = 0
        for a in self.npcs_enemies:
            if a.faction != "enemy" or not a.alive:
                kept.append(a)
                continue
            if not self._near_any_spawn(a.x, a.y):
                kept.append(a)
                continue
            az = int(getattr(a, "z", 0) or 0)
            gmap = self.plane_map(az)
            placed = False
            for _ in range(40):
                nx = self.rng.randint(2, max(2, gmap.width - 3))
                ny = self.rng.randint(2, max(2, gmap.height - 3))
                if not gmap.walkable(nx, ny):
                    continue
                if self._near_any_spawn(nx, ny):
                    continue
                if any(
                    b.alive and b.x == nx and b.y == ny
                    and int(getattr(b, "z", 0) or 0) == az
                    for b in kept
                ):
                    continue
                a.x, a.y = nx, ny
                kept.append(a)
                placed = True
                purged += 1
                break
            if not placed:
                purged += 1
        self.npcs_enemies = kept
        if purged:
            self.system_chat("Cleared %d hostiles from spawn safe zones." % purged)

    def clear_spawn_threats(self, x: int, y: int, z: int = 0) -> int:
        """Knock back or delete enemies within CLEAR_SPAWN_THREAT_RADIUS of a pad."""
        r = int(getattr(C, "CLEAR_SPAWN_THREAT_RADIUS", 6))
        z = int(z)
        cleared = 0
        kept: List[Actor] = []
        for a in self.npcs_enemies:
            if (
                a.alive
                and a.faction == "enemy"
                and int(getattr(a, "z", 0) or 0) == z
                and abs(a.x - x) + abs(a.y - y) <= r
            ):
                gmap = self.plane_map(z)
                placed = False
                for _ in range(30):
                    nx = self.rng.randint(2, max(2, gmap.width - 3))
                    ny = self.rng.randint(2, max(2, gmap.height - 3))
                    if not gmap.walkable(nx, ny):
                        continue
                    if self._near_any_spawn(nx, ny):
                        continue
                    if any(
                        b.alive and b.x == nx and b.y == ny
                        and int(getattr(b, "z", 0) or 0) == z
                        for b in kept
                    ):
                        continue
                    a.x, a.y = nx, ny
                    kept.append(a)
                    placed = True
                    cleared += 1
                    break
                if not placed:
                    cleared += 1
                continue
            kept.append(a)
        self.npcs_enemies = kept
        return cleared

    def _remember_pos(self, agent: PlayerAgent) -> None:
        """Persist last stable tile — used to survive WS blips."""
        if agent.actor.x >= 0 and agent.actor.y >= 0:
            agent.last_good_x = int(agent.actor.x)
            agent.last_good_y = int(agent.actor.y)
            agent.last_good_z = int(getattr(agent.actor, "z", 0) or 0)

    def _force_set_pos(
        self,
        agent: PlayerAgent,
        x: int,
        y: int,
        z: int,
        reason: str,
    ) -> None:
        """Only path that forcibly relocates a courier (logged)."""
        agent.actor.x = int(x)
        agent.actor.y = int(y)
        agent.actor.z = int(z)
        agent.last_good_x = int(x)
        agent.last_good_y = int(y)
        agent.last_good_z = int(z)
        agent.log("POS_SET (%d,%d,z=%d) — %s" % (x, y, z, reason))

    def _find_spawn(self) -> Tuple[int, int]:
        """Pick a random free spawn point; search radius if busy. Never stack."""
        points = list(self.spawn_points) if self.spawn_points else [self.spawn_xy]
        self.rng.shuffle(points)

        def try_around(sx: int, sy: int, max_r: int = 8) -> Optional[Tuple[int, int]]:
            for radius in range(0, max_r + 1):
                ring: List[Tuple[int, int]] = []
                for dy in range(-radius, radius + 1):
                    for dx in range(-radius, radius + 1):
                        if radius and max(abs(dx), abs(dy)) != radius:
                            continue
                        x, y = sx + dx, sy + dy
                        if self._can_stand(x, y):
                            ring.append((x, y))
                if ring:
                    return self.rng.choice(ring)
            return None

        free = [p for p in points if self._can_stand(p[0], p[1])]
        if free:
            return self.rng.choice(free)

        for sx, sy in points:
            hit = try_around(sx, sy, max_r=10)
            if hit:
                return hit

        hit = try_around(self.spawn_xy[0], self.spawn_xy[1], max_r=20)
        if hit:
            return hit
        return self.spawn_xy

    def _can_stand(
        self,
        x: int,
        y: int,
        ignore: Optional[Actor] = None,
        z: Optional[int] = None,
    ) -> bool:
        if z is None:
            z = C.PLANE_STREET if ignore is None else int(getattr(ignore, "z", 0) or 0)
        gmap = self.plane_map(z)
        if not gmap.walkable(x, y):
            return False
        # Hard safe zone: enemies cannot stand/move onto tiles near spawn pads
        if (
            ignore is not None
            and getattr(ignore, "faction", None) == "enemy"
            and self._near_any_spawn(x, y)
        ):
            return False
        for a in self._all_actors():
            if ignore is not None and a is ignore:
                continue
            if not a.alive:
                continue
            if int(getattr(a, "z", 0) or 0) != int(z):
                continue
            if a.x == x and a.y == y:
                return False
        return True

    def _all_actors(self) -> List[Actor]:
        out = list(self.npcs_enemies)
        for p in self.players.values():
            # Disconnected bodies stay at last_good coords but do not block tiles
            if p.connected:
                out.append(p.actor)
        return out

    def actor_at(
        self,
        x: int,
        y: int,
        ignore: Optional[Actor] = None,
        z: Optional[int] = None,
    ) -> Optional[Actor]:
        if z is None and ignore is not None:
            z = int(getattr(ignore, "z", 0) or 0)
        for a in self._all_actors():
            if ignore is not None and a is ignore:
                continue
            if not a.alive:
                continue
            if z is not None and int(getattr(a, "z", 0) or 0) != int(z):
                continue
            if a.x == x and a.y == y:
                return a
        return None

    def items_at(self, x: int, y: int, z: int = 0) -> List[FloorItem]:
        return [
            fi
            for fi in self.floor_items
            if fi.x == x and fi.y == y and int(getattr(fi, "z", 0) or 0) == int(z)
        ]

    def join(self, name: str, reconnect_id: Optional[str] = None) -> PlayerAgent:
        name = (name or "").strip()[:24] or "Courier"
        # Reconnect by id — restore last_good, never re-roll spawn
        if reconnect_id and reconnect_id in self.players:
            agent = self.players[reconnect_id]
            agent.connected = True
            agent.name = name
            self.name_index[name.lower()] = agent.id
            self._restore_last_good(agent, reason="reconnect-id")
            self.system_chat("%s reconnected." % name)
            agent.log("Rejacked — same pad (%d,%d,z=%d)." % (
                agent.actor.x, agent.actor.y, int(getattr(agent.actor, "z", 0) or 0)
            ))
            self.update_fov(agent)
            return agent
        # Reconnect by name — same rule
        existing = self.name_index.get(name.lower())
        if existing and existing in self.players:
            agent = self.players[existing]
            agent.connected = True
            self._restore_last_good(agent, reason="reconnect-name")
            self.system_chat("%s reconnected." % name)
            agent.log("Rejacked — same pad (%d,%d,z=%d)." % (
                agent.actor.x, agent.actor.y, int(getattr(agent.actor, "z", 0) or 0)
            ))
            self.update_fov(agent)
            return agent

        pid = uuid.uuid4().hex[:10]
        glyph, color = self._alloc_glyph_color()
        x, y = self._find_spawn()
        actor = make_player(x, y, name=name)
        actor.glyph = glyph
        actor.color = color
        actor.inventory.append(make_stimpack())
        actor.inventory.append(make_mono_knife())
        actor.inventory[-1].equipped = True
        actor.z = C.PLANE_STREET
        agent = PlayerAgent(
            id=pid,
            name=name,
            actor=actor,
            glyph=glyph,
            color=color,
            last_good_x=x,
            last_good_y=y,
            last_good_z=C.PLANE_STREET,
        )
        self._bind_agent_fog(agent, C.PLANE_STREET)
        self.players[pid] = agent
        self.name_index[name.lower()] = pid
        self.system_chat("%s jacked in (%s)." % (name, glyph))
        agent.log("You jack into the shared street layer. Fractured LA hums under neon rain.")
        agent.log("Talk to Relay Tran. Open chat with Enter. Personal Payload-Zero quest — others keep theirs.")
        agent.log("Seed: %s · You are glyph %s · spawn (%d,%d)" % (self.seed, glyph, x, y))
        self._force_set_pos(agent, x, y, C.PLANE_STREET, "new join spawn")
        n = self.clear_spawn_threats(x, y, C.PLANE_STREET)
        if n:
            agent.log("Cleared %d hostiles near pad." % n)
        self._grant_spawn_invuln(agent)
        self.update_fov(agent)
        return agent

    def leave(self, player_id: str) -> None:
        agent = self.players.get(player_id)
        if not agent:
            return
        # Remember pad BEFORE marking disconnected — never limbo to (-1,-1)
        self._remember_pos(agent)
        agent.connected = False
        self.system_chat("%s jacked out." % agent.name)
        # Body stays at last_good coords (ghost). AI/collision ignore disconnected.

    def _restore_last_good(self, agent: PlayerAgent, reason: str = "reconnect") -> None:
        """Restore last_good if coords invalid. Never calls _find_spawn."""
        ax, ay = agent.actor.x, agent.actor.y
        if ax >= 0 and ay >= 0:
            self._remember_pos(agent)
            return
        lx, ly, lz = agent.last_good_x, agent.last_good_y, agent.last_good_z
        if lx >= 0 and ly >= 0:
            self._force_set_pos(agent, lx, ly, lz, "%s restore last_good" % reason)
            self._bind_agent_fog(agent, lz)
            return
        # Truly missing last_good (should be rare) — only then spawn once
        x, y = self._find_spawn()
        self._force_set_pos(agent, x, y, C.PLANE_STREET, "%s fallback spawn (no last_good)" % reason)
        self._bind_agent_fog(agent, C.PLANE_STREET)

    def reconnect_parked(self, agent: PlayerAgent) -> None:
        """Safe reconnect hook — restores last_good, never random teleport while alive."""
        self._restore_last_good(agent, reason="reconnect_parked")
        # Do not auto-revive / re-invuln here — that is explicit respawn only

    # ---- FOV ----
    def update_fov(self, agent: PlayerAgent) -> None:
        z = int(getattr(agent.actor, "z", 0) or 0)
        self._bind_agent_fog(agent, z)
        gmap = self.plane_map(z)
        px, py = agent.actor.x, agent.actor.y
        if px < 0:
            return
        r = C.VIEW_RADIUS
        pad = r + 2
        for y in range(max(0, py - pad), min(gmap.height, py + pad + 1)):
            for x in range(max(0, px - pad), min(gmap.width, px + pad + 1)):
                agent.visible[y][x] = False
        for y in range(max(0, py - r), min(gmap.height, py + r + 1)):
            for x in range(max(0, px - r), min(gmap.width, px + r + 1)):
                if (x - px) ** 2 + (y - py) ** 2 <= r * r:
                    if _los(gmap, px, py, x, y):
                        agent.visible[y][x] = True
                        agent.explored[y][x] = True

    # ---- Combat / AI ----
    def melee_attack(self, attacker: Actor, defender: Actor, observer: Optional[PlayerAgent] = None) -> None:
        # MVP: no player-vs-player damage
        if attacker.faction == "player" and defender.faction == "player" and not C.PVP_ENABLED:
            return
        # Spawn invulnerability
        if defender.faction == "player":
            victim = self._agent_for_actor(defender)
            if victim and victim.is_invulnerable():
                if observer and observer.actor is attacker:
                    observer.log("%s's spawn shield flares — no damage." % defender.name)
                elif victim:
                    victim.log("Spawn shield absorbs a hit from %s." % attacker.name)
                return
        raw = (attacker.total_attack() if hasattr(attacker, "total_attack") else attacker.attack) + self.rng.randint(0, 2)
        # MVP: soft-cap enemy melee vs players so post-shield isn't instant death
        if attacker.faction == "enemy" and defender.faction == "player":
            cap = int(getattr(C, "ENEMY_MELEE_CAP_VS_PLAYER", 2))
            raw = min(raw, cap)
        dmg = defender.take_damage(raw)
        line = "%s hits %s for %d." % (attacker.name, defender.name, dmg)
        self._broadcast_log_near(attacker.x, attacker.y, line, also=observer)
        if attacker.faction == "player" and observer:
            observer.sfx("melee")
        if not defender.alive:
            self._broadcast_log_near(attacker.x, attacker.y, "%s collapses into pixel dust." % defender.name)
            if defender.faction == "enemy":
                if observer:
                    observer.sfx("kill")
                if attacker.faction == "player":
                    attacker.restore_focus(2)
            elif defender.faction == "player":
                victim = self._agent_for_actor(defender)
                if victim:
                    victim.lost = True
                    victim.mode = "dead"
                    victim.sfx("death")
                    victim.log("Your avatar flatlines. Press r to respawn.")
        elif defender.faction == "enemy" and observer:
            observer.sfx("hurt")

    def _agent_for_actor(self, actor: Actor) -> Optional[PlayerAgent]:
        for p in self.players.values():
            if p.actor is actor:
                return p
        return None

    def _broadcast_log_near(self, x: int, y: int, msg: str, also: Optional[PlayerAgent] = None, radius: int = 12) -> None:
        for p in self.players.values():
            if not p.connected:
                continue
            if p.actor.x < 0:
                continue
            if abs(p.actor.x - x) + abs(p.actor.y - y) <= radius or p is also:
                p.log(msg)

    def try_ranged_or_hack(self, agent: PlayerAgent) -> bool:
        player = agent.actor
        pz = int(getattr(agent.actor, "z", 0) or 0)
        enemies = [
            a
            for a in self.npcs_enemies
            if a.alive
            and a.faction == "enemy"
            and int(getattr(a, "z", 0) or 0) == pz
            and 0 <= a.y < len(agent.visible)
            and 0 <= a.x < len(agent.visible[0])
            and agent.visible[a.y][a.x]
        ]
        if not enemies:
            agent.log("No hostile targets in sight.")
            return False

        def dist(a: Actor) -> int:
            return abs(a.x - player.x) + abs(a.y - player.y)

        target = min(enemies, key=dist)
        weapon = player.equipped_ranged()
        if weapon and weapon.ranged_damage > 0:
            cost = int(weapon.extra.get("focus_cost", 3))
            if player.focus < cost:
                agent.log("Not enough focus to fire.")
                return False
            player.focus -= cost
            dmg = target.take_damage(weapon.ranged_damage + self.rng.randint(0, 2))
            agent.log("You pulse-fire %s at %s for %d." % (weapon.name, target.name, dmg))
            agent.sfx("pulse")
            if not target.alive:
                agent.log("%s fries." % target.name)
                agent.sfx("kill")
            else:
                agent.sfx("hurt")
            return True
        cost = 4
        if player.focus < cost:
            agent.log("Focus too low to hack. Wait or use a Focus Tab.")
            return False
        player.focus -= cost
        power = player.total_hack() + self.rng.randint(0, 3)
        if target.glyph == C.ENEMY_DRONE:
            power += 2
        dmg = target.take_damage(power)
        agent.log("You inject a glitch into %s for %d (hack)." % (target.name, dmg))
        agent.sfx("pulse")
        if not target.alive:
            agent.log("%s bluescreens." % target.name)
            agent.sfx("kill")
        else:
            agent.sfx("hurt")
        return True

    def enemy_tick(self) -> None:
        """Server AI tick (~TICK_HZ): chase vulnerable players; never path to invuln."""
        living = [p for p in self.players.values() if p.connected and p.actor.alive and p.actor.x >= 0]
        if not living:
            return

        def _wander(a: Actor, az: int) -> None:
            opts = [(0, 1), (0, -1), (1, 0), (-1, 0), (0, 0)]
            self.rng.shuffle(opts)
            for ox, oy in opts:
                nx, ny = a.x + ox, a.y + oy
                if self._can_stand(nx, ny, ignore=a, z=az):
                    a.x, a.y = nx, ny
                    break

        for a in self.npcs_enemies:
            if not a.alive or a.faction != "enemy":
                continue
            az = int(getattr(a, "z", 0) or 0)
            same_plane = [
                p for p in living if int(getattr(p.actor, "z", 0) or 0) == az
            ]
            # NEVER target or path toward invulnerable couriers
            vulnerable = [p for p in same_plane if not p.is_invulnerable()]
            if not vulnerable:
                _wander(a, az)
                continue

            target_agent = min(
                vulnerable,
                key=lambda p: abs(p.actor.x - a.x) + abs(p.actor.y - a.y),
            )
            player = target_agent.actor
            dx = player.x - a.x
            dy = player.y - a.y
            dist = abs(dx) + abs(dy)
            can_see = dist <= C.VIEW_RADIUS + 2
            if dist == 1:
                self.melee_attack(a, player, observer=target_agent)
                continue
            if can_see and a.ai == "chase":
                step_x = 0 if dx == 0 else (1 if dx > 0 else -1)
                step_y = 0 if dy == 0 else (1 if dy > 0 else -1)
                if abs(dx) >= abs(dy):
                    nx, ny = a.x + step_x, a.y
                    if not self._can_stand(nx, ny, ignore=a, z=az):
                        nx, ny = a.x, a.y + step_y
                else:
                    nx, ny = a.x, a.y + step_y
                    if not self._can_stand(nx, ny, ignore=a, z=az):
                        nx, ny = a.x + step_x, a.y
                if self._can_stand(nx, ny, ignore=a, z=az):
                    a.x, a.y = nx, ny
            else:
                _wander(a, az)
        self.tick += 1
        # light focus regen for connected players
        if self.tick % 3 == 0:
            for p in living:
                p.actor.restore_focus(1)
        for p in living:
            self.update_fov(p)
            self.check_win(p)

    def check_win(self, agent: PlayerAgent) -> None:
        if agent.won or agent.lost:
            return
        if int(getattr(agent.actor, "z", 0) or 0) != C.PLANE_STREET:
            return
        px, py = agent.actor.x, agent.actor.y
        ux, uy = self.uplink_pos
        if abs(px - ux) + abs(py - uy) <= 1 and agent.has_payload():
            agent.actor.inventory = [i for i in agent.actor.inventory if i.id != "payload_zero"]
            agent.won = True
            agent.mode = "won"
            agent.quest_flags["payload_cleared"] = True
            agent.sfx("win")
            agent.cutscene("uplink")
            agent.log(
                "Node Custodian slots YOUR Faraday sleeve. Payload-Zero dissolves — "
                "personal run complete. Others can still finish theirs. YOU WIN."
            )
            self.system_chat("%s cleared Payload-Zero." % agent.name)

    # ---- Actions ----
    def handle_action(self, agent: PlayerAgent, action: str, arg: Optional[str] = None) -> None:
        action = (action or "").strip()
        now = time.time()
        if action not in ("noop", "look", "?", "help", "escape", "Esc", "i", "inventory"):
            if now - agent.last_action_ts < 1.0 / ACTION_RATE_HZ:
                return
            agent.last_action_ts = now

        if agent.actor.x < 0 and action not in ("r", "restart"):
            # Restore last pad only — never random mid-action teleport
            self._restore_last_good(agent, reason="action-while-invalid-pos")

        if agent.mode == "help":
            if action in ("?", "escape", "Esc", " ", "enter", "q"):
                agent.mode = "play"
            return

        if agent.mode == "inventory":
            self._handle_inventory(agent, action, arg)
            return

        if agent.mode in ("dead", "won"):
            if action in ("r", "restart"):
                self._respawn(agent)
            return

        if action in ("?", "help"):
            agent.mode = "help"
            return

        if action in ("i", "inventory"):
            agent.mode = "inventory"
            agent.selected_inv = 0
            agent.log("Inventory — numbers select, e equip, u use, d drop, Esc back.")
            return

        if action in ("turn_left", "tl", ","):
            agent.actor.facing = (agent.actor.facing - 1) % 4
            agent.sfx("click")
            return
        if action in ("turn_right", "tr"):
            agent.actor.facing = (agent.actor.facing + 1) % 4
            agent.sfx("click")
            return

        if action in ("plane_up", "ascend", "fly_up"):
            self._change_plane(agent, +1)
            return
        if action in ("plane_down", "descend", "fly_down"):
            self._change_plane(agent, -1)
            return

        if action in C.REL_MOVE_ACTIONS:
            dx, dy = _relative_delta(agent.actor.facing, action)
            self._try_move(agent, dx, dy)
            return

        if action in C.MOVE_8:
            dx, dy = C.MOVE_8[action]
            _face_toward(agent.actor, dx, dy)
            self._try_move(agent, dx, dy)
            return

        if action in C.MOVE_KEYS:
            dx, dy = C.MOVE_KEYS[action]
            _face_toward(agent.actor, dx, dy)
            self._try_move(agent, dx, dy)
            return

        if action in (".", " ", "wait"):
            agent.log("You wait. Neon flickers.")
            self.update_fov(agent)
            return

        if action in ("g", "get", "pickup"):
            self._pickup(agent)
            return

        if action in ("f", "fire", "hack"):
            if self.try_ranged_or_hack(agent):
                self.update_fov(agent)
            return

        if action == "u" and arg:
            try:
                self._use_item(agent, int(arg))
            except ValueError:
                agent.log("Usage: u <index>")
            return

        if action == "look":
            agent.log("Pos (%d,%d) tick %d." % (agent.actor.x, agent.actor.y, self.tick))
            return

    def _respawn(self, agent: PlayerAgent) -> None:
        agent.won = False
        agent.lost = False
        agent.mode = "play"
        agent.actor.alive = True
        agent.actor.hp = agent.actor.max_hp
        agent.actor.focus = agent.actor.max_focus
        # Clear personal payload progress but keep other flags
        agent.quest_flags.pop("got_payload", None)
        agent.quest_flags.pop("payload_cleared", None)
        agent.actor.inventory = [i for i in agent.actor.inventory if i.id != "payload_zero"]
        if not any(i.id == "stimpack" for i in agent.actor.inventory):
            agent.actor.inventory.append(make_stimpack())
        sx, sy = self._find_spawn()
        self._force_set_pos(agent, sx, sy, C.PLANE_STREET, "explicit death respawn")
        self._bind_agent_fog(agent, C.PLANE_STREET)
        agent.pending_cutscenes.clear()
        agent.pending_sfx.clear()
        agent.log("Respawned at a safe street pad. Streets still shared.")
        n = self.clear_spawn_threats(sx, sy, C.PLANE_STREET)
        if n:
            agent.log("Cleared %d hostiles near pad." % n)
        self._grant_spawn_invuln(agent)
        self._ensure_world_payload()
        self.update_fov(agent)
        self.system_chat("%s respawned." % agent.name)

    def _try_move(self, agent: PlayerAgent, dx: int, dy: int) -> None:
        if agent.lost or not agent.actor.alive:
            return
        if dx == 0 and dy == 0:
            return
        z = int(getattr(agent.actor, "z", 0) or 0)
        gmap = self.plane_map(z)
        px, py = agent.actor.x + dx, agent.actor.y + dy
        if not gmap.in_bounds(px, py):
            agent.sfx("bump")
            return
        # No corner-cutting on diagonals — both adjacent cardinals must be open
        if dx != 0 and dy != 0:
            if not gmap.walkable(agent.actor.x + dx, agent.actor.y) or not gmap.walkable(
                agent.actor.x, agent.actor.y + dy
            ):
                agent.sfx("bump")
                return
        target = self.actor_at(px, py, ignore=agent.actor, z=z)
        if target and target.alive:
            if target.faction == "enemy":
                self.melee_attack(agent.actor, target, observer=agent)
                self.update_fov(agent)
                return
            if target.faction == "npc":
                agent.log('%s: "%s"' % (target.name, target.talk))
                agent.sfx("talk")
                agent.cutscene("talk")
                if target.quest_flag and target.quest_flag not in agent.quest_flags:
                    agent.quest_flags[target.quest_flag] = True
                    if target.quest_flag not in agent.story_seen:
                        agent.story_seen.append(target.quest_flag)
                self.update_fov(agent)
                return
            if target.faction == "player":
                other = self._agent_for_actor(target)
                label = other.name if other else target.name
                if C.PVP_ENABLED:
                    self.melee_attack(agent.actor, target, observer=agent)
                else:
                    agent.log("Blocked by courier %s (no PvP)." % label)
                    agent.sfx("bump")
                self.update_fov(agent)
                return
        if not gmap.walkable(px, py):
            agent.log("Blocked.")
            agent.sfx("bump")
            return
        agent.actor.x, agent.actor.y = px, py
        self._remember_pos(agent)
        tile = gmap.tiles[py][px]
        if tile == C.DOOR:
            agent.sfx("door")
            agent.cutscene("door")
        else:
            agent.sfx("step")
        # Auto-use stairs/manhole when stepping on them (optional nudge)
        if tile in (C.STAIRS_UP, C.MANHOLE) and z < C.PLANE_AIR:
            agent.log("Vertical access here — press t to ascend / b to descend.")
        elif tile == C.STAIRS_DOWN and z > C.PLANE_UNDER:
            agent.log("Shaft down — press b to descend.")
        for fi in self.items_at(px, py, z=z):
            agent.log("You see here: %s." % fi.item.name)
        if z == C.PLANE_STREET:
            jx, jy = self.jackpoint_pos
            if abs(px - jx) + abs(py - jy) <= 1:
                if "jackpoint" not in agent.story_seen:
                    agent.story_seen.append("jackpoint")
                    agent.log("Jackpoint air tastes like ozone and old prayers.")
                    agent.cutscene("jackpoint")
            ux, uy = self.uplink_pos
            if abs(px - ux) + abs(py - uy) <= 1 and "uplink_approach" not in agent.story_seen:
                if not agent.has_payload():
                    agent.story_seen.append("uplink_approach")
                    agent.log("Uplink node thrums — needs YOUR Payload-Zero in the sleeve.")
        self.update_fov(agent)
        self.check_win(agent)

    def _change_plane(self, agent: PlayerAgent, delta: int) -> None:
        if agent.lost or not agent.actor.alive:
            return
        old_z = int(getattr(agent.actor, "z", 0) or 0)
        new_z = old_z + int(delta)
        if new_z not in self.planes:
            agent.log("No plane that way.")
            agent.sfx("bump")
            return
        x, y = agent.actor.x, agent.actor.y
        on_shaft = (x, y) in self.shafts
        g_old = self.plane_map(old_z)
        tile = g_old.tiles[y][x] if g_old.in_bounds(x, y) else C.WALL
        free = on_shaft or tile in (C.STAIRS_UP, C.STAIRS_DOWN, C.MANHOLE)
        # Street ↔ air free-fly with focus cost when not on shaft
        if not free:
            if {old_z, new_z} == {C.PLANE_STREET, C.PLANE_AIR}:
                cost = int(C.FLY_FOCUS_COST)
                if agent.actor.focus < cost:
                    agent.log("Need %d focus to jump planes off-shaft." % cost)
                    return
                agent.actor.focus -= cost
                agent.log("You kick into the Metaverse vertical — focus -%d." % cost)
            elif {old_z, new_z} == {C.PLANE_STREET, C.PLANE_UNDER}:
                agent.log("Need a manhole (o) or stairs to reach the sewers.")
                agent.sfx("bump")
                return
            else:
                agent.log("Need a shaft or stairs for that transition.")
                agent.sfx("bump")
                return
        if not self._can_stand(x, y, ignore=agent.actor, z=new_z):
            # Stay put — do NOT jump to a random nearby tile (teleport bug)
            agent.log(
                "Landing blocked on %s — stay put." % C.PLANE_NAMES.get(new_z, str(new_z))
            )
            agent.sfx("bump")
            return
        agent.actor.z = new_z
        self._remember_pos(agent)
        self._bind_agent_fog(agent, new_z)
        label = C.PLANE_NAMES.get(new_z, str(new_z))
        agent.log("Plane shift → %s (%s)." % (label, C.PLANE_LABELS.get(new_z, "")))
        agent.sfx("door")
        self.update_fov(agent)

    def _pickup(self, agent: PlayerAgent) -> None:
        here = self.items_at(agent.actor.x, agent.actor.y, z=int(getattr(agent.actor, "z", 0) or 0))
        if not here:
            agent.log("Nothing to pick up.")
            return
        fi = here[0]
        if fi.item.id == "payload_zero":
            # Personal clone — leave world copy for other couriers
            if agent.has_payload():
                agent.log("You already carry a Payload-Zero sleeve.")
                return
            agent.actor.inventory.append(_clone_item(fi.item))
            agent.quest_flags["got_payload"] = True
            if "got_payload" not in agent.story_seen:
                agent.story_seen.append("got_payload")
            agent.log("Cloned Payload-Zero into YOUR sleeve (shared world copy remains). Get to the uplink.")
            agent.sfx("pickup")
            agent.cutscene("payload")
            self._ensure_world_payload()
            self.update_fov(agent)
            return
        self.floor_items.remove(fi)
        agent.actor.inventory.append(fi.item)
        agent.log("Picked up %s." % fi.item.name)
        agent.sfx("pickup")
        self.update_fov(agent)

    def _handle_inventory(self, agent: PlayerAgent, action: str, arg: Optional[str]) -> None:
        inv = agent.actor.inventory
        if action in ("escape", "Esc", "i", "q"):
            agent.mode = "play"
            return
        if action.isdigit():
            idx = int(action)
            if 0 <= idx < len(inv):
                agent.selected_inv = idx
                agent.log("Selected [%d] %s" % (idx, inv[idx].name))
            return
        if action == "u":
            self._use_item(agent, agent.selected_inv)
            return
        if action == "e":
            self._equip_item(agent, agent.selected_inv)
            return
        if action == "d":
            self._drop_item(agent, agent.selected_inv)
            return

    def _use_item(self, agent: PlayerAgent, idx: int) -> None:
        inv = agent.actor.inventory
        if idx < 0 or idx >= len(inv):
            agent.log("No such item.")
            return
        item = inv[idx]
        if item.kind == "quest":
            agent.log("Quest items can't be 'used' here — deliver to the uplink.")
            return
        if item.equippable:
            self._equip_item(agent, idx)
            return
        used = False
        if item.heal:
            healed = agent.actor.heal(item.heal)
            agent.log("Used %s: +%d HP." % (item.name, healed))
            used = True
        if item.focus_restore:
            got = agent.actor.restore_focus(item.focus_restore)
            agent.log("Used %s: +%d focus." % (item.name, got))
            used = True
        if item.kind == "datachip":
            agent.log("You jack the chip: %s" % item.description)
            if item.hack_bonus:
                agent.actor.hack += item.hack_bonus
                agent.log("Hack skill +%d." % item.hack_bonus)
            used = True
            agent.cutscene("terminal")
        if used:
            agent.sfx("use")
        if used and item.consumable:
            inv.pop(idx)
            if agent.selected_inv >= len(inv):
                agent.selected_inv = max(0, len(inv) - 1)
            agent.mode = "play"

    def _equip_item(self, agent: PlayerAgent, idx: int) -> None:
        inv = agent.actor.inventory
        if idx < 0 or idx >= len(inv):
            return
        item = inv[idx]
        if not item.equippable:
            agent.log("%s isn't equippable." % item.name)
            return
        for other in inv:
            if other.kind == item.kind and other.equipped and other is not item:
                other.equipped = False
                agent.log("Unequipped %s." % other.name)
        item.equipped = not item.equipped
        agent.log(("Equipped " if item.equipped else "Unequipped ") + item.name + ".")

    def _drop_item(self, agent: PlayerAgent, idx: int) -> None:
        inv = agent.actor.inventory
        if idx < 0 or idx >= len(inv):
            return
        item = inv.pop(idx)
        item.equipped = False
        # Dropping personal payload clones a floor copy (others can still get world one)
        self.floor_items.append(
            FloorItem(agent.actor.x, agent.actor.y, item, z=int(getattr(agent.actor, "z", 0) or 0))
        )
        agent.log("Dropped %s." % item.name)
        if agent.selected_inv >= len(inv):
            agent.selected_inv = max(0, len(inv) - 1)
        agent.mode = "play"

    # ---- Rendering / snapshot ----
    def render_ascii_for(self, agent: PlayerAgent) -> List[str]:
        z = int(getattr(agent.actor, "z", 0) or 0)
        gmap = self.plane_map(z)
        overlay: Dict[Tuple[int, int], str] = {}
        for fi in self.floor_items:
            if int(getattr(fi, "z", 0) or 0) != z:
                continue
            overlay[(fi.x, fi.y)] = fi.item.glyph
        for a in self.npcs_enemies:
            if a.alive and int(getattr(a, "z", 0) or 0) == z:
                overlay[(a.x, a.y)] = a.glyph
        for p in self.players.values():
            if not p.connected or p.actor.x < 0 or not p.actor.alive:
                continue
            if p.id == agent.id:
                continue
            if int(getattr(p.actor, "z", 0) or 0) != z:
                continue
            overlay[(p.actor.x, p.actor.y)] = p.glyph
        if agent.actor.x >= 0 and agent.actor.alive:
            overlay[(agent.actor.x, agent.actor.y)] = C.PLAYER

        rows = []
        for y in range(gmap.height):
            chars = []
            for x in range(gmap.width):
                if agent.visible[y][x]:
                    chars.append(overlay.get((x, y), gmap.tiles[y][x]))
                elif agent.explored[y][x]:
                    chars.append(gmap.tiles[y][x])
                else:
                    chars.append(" ")
            rows.append("".join(chars))
        return rows

    def snapshot(self, agent: PlayerAgent) -> Dict[str, Any]:
        p = agent.actor
        sfx_events = list(agent.pending_sfx)
        agent.pending_sfx.clear()
        cutscene_events = list(agent.pending_cutscenes)
        agent.pending_cutscenes.clear()

        players_list = []
        for other in self.players.values():
            if not other.connected and other.actor.x < 0:
                continue
            if not other.connected:
                continue
            oz = int(getattr(other.actor, "z", 0) or 0)
            players_list.append(
                {
                    "id": other.id,
                    "name": other.name,
                    "x": other.actor.x,
                    "y": other.actor.y,
                    "z": oz,
                    "plane": C.PLANE_NAMES.get(oz, str(oz)),
                    "facing": other.actor.facing % 4,
                    "hp": other.actor.hp,
                    "max_hp": other.actor.max_hp,
                    "glyph": other.glyph,
                    "color": other.color,
                    "alive": other.actor.alive,
                    "has_payload": other.has_payload(),
                    "won": other.won,
                }
            )

        entities = []
        az = int(getattr(agent.actor, "z", 0) or 0)
        for a in self.npcs_enemies:
            if not a.alive:
                continue
            if a.y < 0 or a.x < 0:
                continue
            if int(getattr(a, "z", 0) or 0) != az:
                continue
            if not agent.visible[a.y][a.x]:
                continue
            entities.append(
                {
                    "x": a.x,
                    "y": a.y,
                    "glyph": a.glyph,
                    "name": a.name,
                    "faction": a.faction,
                    "hp": a.hp,
                }
            )

        return {
            "mmorpg": True,
            "seed": self.seed,
            "turn": self.tick,
            "tick": self.tick,
            "mode": agent.mode,
            "won": agent.won,
            "lost": agent.lost,
            "you": agent.id,
            "map": self.render_ascii_for(agent),
            "width": self.gmap.width,
            "height": self.gmap.height,
            "player": {
                "id": agent.id,
                "name": p.name,
                "x": p.x,
                "y": p.y,
                "z": int(getattr(p, "z", 0) or 0),
                "plane": C.PLANE_NAMES.get(int(getattr(p, "z", 0) or 0), "STREET"),
                "hp": p.hp,
                "max_hp": p.max_hp,
                "focus": p.focus,
                "max_focus": p.max_focus,
                "attack": p.total_attack(),
                "defense": p.total_defense(),
                "hack": p.total_hack(),
                "has_payload": agent.has_payload(),
                "facing": p.facing % 4,
                "facing_name": C.FACING_NAMES[p.facing % 4],
                "glyph": agent.glyph,
                "color": agent.color,
            },
            "players": players_list,
            "online_count": sum(1 for o in self.players.values() if o.connected),
            "entities": entities,
            "inventory": [
                {
                    "name": it.name,
                    "kind": it.kind,
                    "equipped": it.equipped,
                    "description": it.description,
                    "glyph": it.glyph,
                }
                for it in p.inventory
            ],
            "selected_inv": agent.selected_inv,
            "messages": agent.messages[-12:],
            "chat": [
                {"t": c.t, "name": c.name, "text": c.text, "kind": c.kind}
                for c in self.chat[-20:]
            ],
            "quest_flags": dict(agent.quest_flags),
            "story_seen": list(agent.story_seen),
            "help": C.HELP_TEXT
            + "\n\nMMORPG\n  Enter or /say — chat\n  Other couriers show as letter glyphs\n"
            + "  Personal Payload-Zero quest (shared streets)\n",
            "visible": [row[:] for row in agent.visible],
            "explored": [row[:] for row in agent.explored],
            "jackpoint": list(self.jackpoint_pos),
            "uplink": list(self.uplink_pos),
            "spawn_count": len(self.spawn_points),
            "invulnerable": agent.is_invulnerable(),
            "z": int(getattr(p, "z", 0) or 0),
            "plane": C.PLANE_NAMES.get(int(getattr(p, "z", 0) or 0), "STREET"),
            "plane_label": C.PLANE_LABELS.get(int(getattr(p, "z", 0) or 0), ""),
            "sfx": sfx_events,
            "cutscenes": cutscene_events,
        }


def _los(gmap: GameMap, x0: int, y0: int, x1: int, y1: int) -> bool:
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    while True:
        if (x, y) != (x0, y0) and (x, y) != (x1, y1):
            if gmap.blocks_sight(x, y):
                return False
        if x == x1 and y == y1:
            return True
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy


def _relative_delta(facing: int, action: str) -> Tuple[int, int]:
    """8-way deltas relative to facing (0=N,1=E,2=S,3=W)."""
    fx, fy = C.FACING_DIRS[facing % 4]
    # left strafe = rotate forward 90° CCW: (fx,fy)->(fy,-fx)
    lx, ly = fy, -fx
    rx, ry = -fy, fx
    table = {
        "forward": (fx, fy),
        "back": (-fx, -fy),
        "strafe_left": (lx, ly),
        "strafe_right": (rx, ry),
        "forward_left": (fx + lx, fy + ly),
        "forward_right": (fx + rx, fy + ry),
        "back_left": (-fx + lx, -fy + ly),
        "back_right": (-fx + rx, -fy + ry),
    }
    dx, dy = table.get(action, (0, 0))
    # Normalize octile step to -1..1
    if dx != 0:
        dx = 1 if dx > 0 else -1
    if dy != 0:
        dy = 1 if dy > 0 else -1
    return dx, dy


def _face_toward(actor: Actor, dx: int, dy: int) -> None:
    if dx == 0 and dy == 0:
        return
    if abs(dx) >= abs(dy):
        actor.facing = 1 if dx > 0 else 3
    else:
        actor.facing = 2 if dy > 0 else 0
