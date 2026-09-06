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
from .items import (
    Item,
    make_mono_knife,
    make_payload_zero,
    make_stimpack,
    make_street_credits,
    make_pulse_shim,
    make_kevlar_vest,
    make_focus_tab,
)
from .mapgen import FloorItem, GameMap, generate_world
from .systems import YearFeaturesMixin
from .wishes import (
    MAX_WISHES,
    grant_label,
    make_backlog_token,
    make_wish_item,
    match_wish_grant,
    prototype_for_grant,
    wish_hash,
)

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
    kind: str = "say"  # say | system | action | notice | pm | join | part | nick
    channel: str = "#streets"


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
    haste_steps: int = 0
    view_bonus: int = 0
    view_bonus_until_tick: int = 0
    companion: bool = False
    private_chat: List[ChatLine] = field(default_factory=list)
    irc_channel: str = "#streets"
    irc_channels: List[str] = field(default_factory=lambda: ["#streets"])
    xp: int = 0
    level: int = 1
    credits: int = 0
    kills: int = 0
    skills: Dict[str, str] = field(default_factory=dict)
    loadout: Dict[str, Optional[str]] = field(default_factory=lambda: {"weapon": None, "armor": None, "trinket": None})
    skill_picks_available: int = 0
    party_id: Optional[str] = None
    party_invites: List[str] = field(default_factory=list)
    crew_id: Optional[str] = None
    housing: Dict[str, Any] = field(default_factory=dict)
    journal: Dict[str, Any] = field(default_factory=dict)
    reputation: int = 0
    contracts: List[Dict[str, Any]] = field(default_factory=list)
    pvp: Dict[str, Any] = field(default_factory=dict)
    season: Dict[str, Any] = field(default_factory=dict)
    dead: bool = False
    respawn_options: List[Dict[str, Any]] = field(default_factory=list)
    spectating: Optional[str] = None
    muted: set = field(default_factory=set)
    reports_filed: int = 0
    auth_nick: Optional[str] = None
    raid_id: Optional[str] = None
    raid_lockout_until: float = 0.0
    bandwidth_debt: int = 0
    repair_needed: int = 0

    def is_invulnerable(self) -> bool:
        return time.time() < self.invuln_until

    def spawn_shield_remaining(self) -> float:
        """Seconds of spawn shield left (0 if expired)."""
        return max(0.0, float(self.invuln_until) - time.time())

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


class GameWorld(YearFeaturesMixin):
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
        self.club_rects: List[Tuple[int, int, int, int]] = list(
            getattr(world, "club_rects", None) or []
        )
        # Ensure street actors default z=0; keep under/air as tagged
        for a in self.npcs_enemies:
            if not hasattr(a, "z") or a.z is None:
                a.z = C.PLANE_STREET
        self.players: Dict[str, PlayerAgent] = {}
        self.name_index: Dict[str, str] = {}  # lower name -> id
        self.chat: List[ChatLine] = []
        # IRC-style channel logs (default street net + topic channels)
        self.channel_chat: Dict[str, List[ChatLine]] = {
            "#streets": [],
            "#metaverse": [],
            "#flotilla": [],
            "#wish": [],
        }
        self.channel_topics: Dict[str, str] = {
            "#streets": "Shared Metaverse street layer — keep it civil, courier.",
            "#metaverse": "Overlay gossip, jackpoint rumors, uplink chatter.",
            "#flotilla": "Cassian Vox signal-rim · refugee broadcasts · propaganda scrub.",
            "#wish": "Feature petitions · /wish spills here as notices.",
        }
        self.tick = 0
        self.created_at = time.time()
        self._glyph_i = 0
        self._ensure_world_payload()
        self._purge_enemies_near_spawns()
        self._seed_extra_encounters()
        self.system_chat("Metaverse street layer online. Seed %s." % seed)
        self._year_init()

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

    def system_chat(self, text: str, channel: str = "#streets") -> None:
        ch = self._norm_channel(channel)
        line = ChatLine(time.time(), "SYSTEM", text, "system", ch)
        self._push_channel(ch, line)
        # legacy mirror for older clients
        self.chat.append(line)
        if len(self.chat) > CHAT_MAX:
            self.chat = self.chat[-CHAT_MAX:]

    def _norm_channel(self, name: str) -> str:
        n = (name or "").strip().lower()
        if not n:
            return "#streets"
        if not n.startswith("#") and not n.startswith("&"):
            n = "#" + n
        return n[:24]

    def _push_channel(self, channel: str, line: ChatLine) -> None:
        ch = self._norm_channel(channel)
        bucket = self.channel_chat.setdefault(ch, [])
        bucket.append(line)
        if len(bucket) > CHAT_MAX:
            self.channel_chat[ch] = bucket[-CHAT_MAX:]

    def _irc_notice(self, agent: PlayerAgent, text: str) -> None:
        agent.private_chat.append(
            ChatLine(time.time(), "irc", text, "notice", agent.irc_channel or "#streets")
        )
        if len(agent.private_chat) > 24:
            agent.private_chat = agent.private_chat[-24:]

    def _ensure_irc(self, agent: PlayerAgent) -> None:
        if not getattr(agent, "irc_channel", None):
            agent.irc_channel = "#streets"
        if not getattr(agent, "irc_channels", None):
            agent.irc_channels = ["#streets"]
        if "#streets" not in agent.irc_channels:
            agent.irc_channels.insert(0, "#streets")

    def say(self, agent: PlayerAgent, text: str) -> Optional[str]:
        text = (text or "").strip()
        if not text:
            return "empty"
        if len(text) > 240:
            text = text[:240]
        now = time.time()
        if now - agent.last_chat_ts < 1.0 / CHAT_RATE_HZ:
            return "rate"
        agent.last_chat_ts = now
        self._ensure_irc(agent)
        low = text.lower()

        # --- slash commands (IRC aesthetic) ---
        if low.startswith("/"):
            parts = text.split(None, 2)
            cmd = parts[0].lower()
            arg1 = parts[1] if len(parts) > 1 else ""
            rest = parts[2] if len(parts) > 2 else ""

            if cmd in ("/wish", "/feature"):
                body = text.split(" ", 1)[1].strip() if " " in text else ""
                if not body:
                    agent.log("Usage: /wish <feature request>  (alias: /feature)")
                    return None
                err = self._handle_wish(agent, body)
                # echo petition into #wish as notice
                self._push_channel(
                    "#wish",
                    ChatLine(now, "SYSTEM", "%s filed a wish: %s" % (agent.name, body[:120]), "notice", "#wish"),
                )
                return err

            if cmd in ("/help", "/irc"):
                self._irc_notice(
                    agent,
                    "IRC: /join #chan · /part [#chan] · /msg nick text · /me action · "
                    "/nick newname · /names · /list · /topic · /query nick · /wish …",
                )
                return None

            if cmd == "/list":
                names = sorted(self.channel_chat.keys())
                self._irc_notice(agent, "Channels: " + ", ".join(names))
                return None

            if cmd == "/topic":
                ch = self._norm_channel(arg1) if arg1.startswith("#") else agent.irc_channel
                topic = self.channel_topics.get(ch, "(no topic)")
                self._irc_notice(agent, "Topic for %s: %s" % (ch, topic))
                return None

            if cmd == "/names":
                ch = self._norm_channel(arg1) if arg1 else agent.irc_channel
                nicks = [
                    p.name
                    for p in self.players.values()
                    if p.connected and ch in getattr(p, "irc_channels", ["#streets"])
                ]
                self._irc_notice(agent, "Names on %s: %s" % (ch, " ".join(nicks) or "(empty)"))
                return None

            if cmd == "/join":
                if not arg1:
                    self._irc_notice(agent, "Usage: /join #channel")
                    return None
                ch = self._norm_channel(arg1)
                fresh = ch not in agent.irc_channels
                if fresh:
                    agent.irc_channels.append(ch)
                agent.irc_channel = ch
                self.channel_chat.setdefault(ch, [])
                self.channel_topics.setdefault(ch, "Courier ad-hoc channel.")
                if fresh:
                    self._push_channel(
                        ch,
                        ChatLine(now, "SYSTEM", "%s has joined %s" % (agent.name, ch), "join", ch),
                    )
                topic = self.channel_topics.get(ch, "")
                self._irc_notice(
                    agent,
                    ("Joined %s — %s" % (ch, topic)) if fresh else ("Now talking on %s — %s" % (ch, topic)),
                )
                return None

            if cmd == "/part":
                ch = self._norm_channel(arg1) if arg1 else agent.irc_channel
                if ch == "#streets":
                    self._irc_notice(agent, "Cannot part #streets (home channel).")
                    return None
                if ch in agent.irc_channels:
                    agent.irc_channels = [c for c in agent.irc_channels if c != ch]
                self._push_channel(
                    ch,
                    ChatLine(now, "SYSTEM", "%s has left %s" % (agent.name, ch), "part", ch),
                )
                if agent.irc_channel == ch:
                    agent.irc_channel = agent.irc_channels[0] if agent.irc_channels else "#streets"
                self._irc_notice(agent, "Left %s · now on %s" % (ch, agent.irc_channel))
                return None

            if cmd in ("/nick", "/name"):
                new_name = (arg1 or "").strip()[:24]
                if not new_name:
                    self._irc_notice(agent, "Usage: /nick <newname>")
                    return None
                if self.name_index.get(new_name.lower()) not in (None, agent.id):
                    self._irc_notice(agent, "Nickname already in use.")
                    return None
                old = agent.name
                self.name_index.pop(old.lower(), None)
                agent.name = new_name
                agent.actor.name = new_name
                self.name_index[new_name.lower()] = agent.id
                for ch in list(getattr(agent, "irc_channels", ["#streets"])):
                    self._push_channel(
                        ch,
                        ChatLine(now, "SYSTEM", "%s is now known as %s" % (old, new_name), "nick", ch),
                    )
                return None

            if cmd in ("/me", "/action"):
                body = text.split(" ", 1)[1].strip() if " " in text else ""
                if not body:
                    self._irc_notice(agent, "Usage: /me <action>")
                    return None
                ch = agent.irc_channel
                line = ChatLine(now, agent.name, body, "action", ch)
                self._push_channel(ch, line)
                self.chat.append(line)
                if len(self.chat) > CHAT_MAX:
                    self.chat = self.chat[-CHAT_MAX:]
                return None

            if cmd in ("/msg", "/privmsg", "/query"):
                if not arg1 or (cmd != "/query" and not rest and " " not in text):
                    # /query nick  OR  /msg nick text
                    if cmd == "/query" and arg1:
                        agent.irc_channel = "@" + arg1[:24]
                        self._irc_notice(agent, "Query window → %s (type /msg %s hi)" % (arg1, arg1))
                        return None
                    self._irc_notice(agent, "Usage: /msg <nick> <text> · /query <nick>")
                    return None
                target_name = arg1
                msg = rest if rest else (text.split(" ", 2)[2] if len(text.split(" ", 2)) > 2 else "")
                if cmd == "/query" and not msg:
                    agent.irc_channel = "@" + target_name[:24]
                    self._irc_notice(agent, "Query → %s" % target_name)
                    return None
                tid = self.name_index.get(target_name.lower())
                target = self.players.get(tid) if tid else None
                if not target or not target.connected:
                    self._irc_notice(agent, "No such nick online: %s" % target_name)
                    return None
                pm = ChatLine(now, agent.name, msg, "pm", "@" + target.name)
                target.private_chat.append(pm)
                if len(target.private_chat) > 24:
                    target.private_chat = target.private_chat[-24:]
                # echo to sender
                agent.private_chat.append(
                    ChatLine(now, agent.name, "→ %s: %s" % (target.name, msg), "pm", "@" + target.name)
                )
                if len(agent.private_chat) > 24:
                    agent.private_chat = agent.private_chat[-24:]
                self._irc_notice(agent, "PM sent to %s" % target.name)
                return None

            if cmd == "/say":
                text = text.split(" ", 1)[1].strip() if " " in text else ""
                if not text:
                    return "empty"
                low = text.lower()
            else:
                self._irc_notice(agent, "Unknown command %s — try /help" % cmd)
                return None

        # Plain channel say (or after /say)
        ch = agent.irc_channel or "#streets"
        if ch.startswith("@"):
            # treat as PM shortcut to open query target
            target_name = ch[1:]
            tid = self.name_index.get(target_name.lower())
            target = self.players.get(tid) if tid else None
            if not target or not target.connected:
                self._irc_notice(agent, "Query target offline — /join #streets")
                return None
            pm = ChatLine(now, agent.name, text, "pm", ch)
            target.private_chat.append(pm)
            agent.private_chat.append(
                ChatLine(now, agent.name, "→ %s: %s" % (target.name, text), "pm", ch)
            )
            return None

        line = ChatLine(now, agent.name, text, "say", ch)
        self._push_channel(ch, line)
        self.chat.append(line)
        if len(self.chat) > CHAT_MAX:
            self.chat = self.chat[-CHAT_MAX:]
        return None

    def _handle_wish(self, agent: PlayerAgent, body: str) -> Optional[str]:
        if not body:
            agent.log("Usage: /wish <feature request>")
            return None
        wishes = [i for i in agent.actor.inventory if i.kind == "wish"]
        h = wish_hash(body)
        existing = next((i for i in wishes if i.id == f"wish_{h}"), None)
        if existing:
            existing.description = body.strip() + "\nUse to petition the street layer."
            existing.name = "Wish: " + (body.strip()[:28] + ("…" if len(body.strip()) > 28 else ""))
            existing.extra["wish_text"] = body.strip()
            agent.log("Wish refreshed in inventory: %s" % existing.name)
        else:
            if len(wishes) >= MAX_WISHES:
                # drop oldest wish
                for i, it in enumerate(agent.actor.inventory):
                    if it.kind == "wish":
                        agent.actor.inventory.pop(i)
                        agent.log("Oldest wish discarded (max %d)." % MAX_WISHES)
                        break
            item = make_wish_item(body)
            agent.actor.inventory.append(item)
            agent.log("Wish filed as inventory item: %s" % item.name)
        agent.sfx("pickup")
        # soft self-log only (not global spam)
        agent.private_chat.append(
            ChatLine(time.time(), "SYSTEM", "%s requested: %s" % (agent.name, body.strip()[:80]), "system")
        )
        if len(agent.private_chat) > 12:
            agent.private_chat = agent.private_chat[-12:]
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
            "Spawn shield active (%.0fs) — hostiles won't aggro you yet."
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

    def _spawn_contest_score(self, x: int, y: int) -> int:
        """Lower is safer. Counts living enemies near the pad (contested bias)."""
        r = int(getattr(C, "CONTESTED_SPAWN_RADIUS", 14))
        score = 0
        for a in self.npcs_enemies:
            if not a.alive or a.faction != "enemy":
                continue
            if int(getattr(a, "z", 0) or 0) != C.PLANE_STREET:
                continue
            d = abs(a.x - x) + abs(a.y - y)
            if d <= r:
                # Closer hostiles weigh more
                score += 1 + max(0, (r - d) // 3)
        return score

    def _find_spawn(self) -> Tuple[int, int]:
        """Pick a free spawn pad, biased away from contested pads. Never stack."""
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
            # Prefer quieter pads; mild jitter so we don't always pick the same one
            ranked = sorted(free, key=lambda p: (self._spawn_contest_score(p[0], p[1]), self.rng.random()))
            # Pick among the quietest third (at least 1)
            cutoff = max(1, (len(ranked) + 2) // 3)
            return self.rng.choice(ranked[:cutoff])

        # Busy pads: try neighborhoods, still prefer lower contest scores
        candidates: List[Tuple[int, int]] = []
        for sx, sy in points:
            hit = try_around(sx, sy, max_r=10)
            if hit:
                candidates.append(hit)
        if candidates:
            ranked = sorted(candidates, key=lambda p: (self._spawn_contest_score(p[0], p[1]), self.rng.random()))
            return ranked[0]

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

    def join(self, name: str, reconnect_id: Optional[str] = None, soft_hardcore: bool = False) -> PlayerAgent:
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
        agent.irc_channel = "#streets"
        agent.irc_channels = ["#streets"]
        self.system_chat("%s jacked in (%s)." % (name, glyph))
        agent.log("You jack into the shared street layer. Fractured LA hums under neon rain.")
        agent.log("Talk to Relay Tran. Open chat with Enter. Personal Payload-Zero quest — others keep theirs.")
        agent.log("IRC net on #streets — /help for /join /msg /me /nick.")
        self._irc_notice(
            agent,
            "*** Welcome to the StreetNet IRC bridge. Motd: keep Payload-Zero talk in-channel. Type /help",
        )
        agent.log("Seed: %s · You are glyph %s · spawn (%d,%d)" % (self.seed, glyph, x, y))
        self._force_set_pos(agent, x, y, C.PLANE_STREET, "new join spawn")
        n = self.clear_spawn_threats(x, y, C.PLANE_STREET)
        if n:
            agent.log("Cleared %d hostiles near pad." % n)
        self._grant_spawn_invuln(agent)
        self._year_bootstrap_agent(agent)
        if soft_hardcore:
            self._soft_hardcore_set(agent, True)
        self._analytics("join", agent)
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
        # Expire view bonus
        if agent.view_bonus and self.tick >= agent.view_bonus_until_tick:
            agent.view_bonus = 0
        r = C.VIEW_RADIUS + max(0, int(agent.view_bonus))
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


    def _seed_extra_encounters(self) -> None:
        """Pack denser hostiles away from spawn pads (Diablo-lite street pressure)."""
        from .entities import make_infected, make_thug, make_drone
        n_extra = int(getattr(C, "ENCOUNTER_EXTRA_STREET", 18))
        g = self.gmap
        added = 0
        attempts = 0
        while added < n_extra and attempts < 1200:
            attempts += 1
            x = self.rng.randint(1, max(2, g.width - 2))
            y = self.rng.randint(1, max(2, g.height - 2))
            if not g.walkable(x, y):
                continue
            if self._near_any_spawn(x, y, radius=max(12, C.SAFE_SPAWN_RADIUS + 2)):
                continue
            if self.actor_at(x, y, z=C.PLANE_STREET):
                continue
            roll = self.rng.random()
            if roll < 0.4:
                mon = make_infected(x, y)
            elif roll < 0.75:
                mon = make_thug(x, y)
            else:
                mon = make_drone(x, y)
            mon.z = C.PLANE_STREET
            self.npcs_enemies.append(mon)
            added += 1
        if added:
            self.system_chat("StreetNet: %d extra hostiles seeded beyond safe pads." % added)

    def _quest_objective(self, agent: PlayerAgent) -> Dict[str, Any]:
        """GTA/WoW-style active objective + compass toward jackpoint/uplink."""
        # Signal Keys (#45) may retarget compass when hunt engaged / payload done
        sk_obj = getattr(self, "_signal_keys_objective", None)
        if callable(sk_obj):
            alt = sk_obj(agent)
            if alt:
                return alt
        jx, jy = self.jackpoint_pos
        ux, uy = self.uplink_pos
        px, py = agent.actor.x, agent.actor.y
        if agent.won:
            return {
                "id": "idle",
                "text": "Patrol streets · hunt infected · chat on StreetNet IRC",
                "target": None,
                "dist": None,
                "bearing": None,
                "compass": "·",
            }
        if agent.has_payload():
            tx, ty = ux, uy
            text = "Reach uplink (U) · scrub Payload-Zero"
            oid = "uplink"
        else:
            tx, ty = jx, jy
            text = "Find jackpoint (J) · sleeve Payload-Zero"
            oid = "jackpoint"
        dx, dy = tx - px, ty - py
        dist = abs(dx) + abs(dy)
        # 8-way bearing
        if dx == 0 and dy == 0:
            bearing, compass = "here", "★"
        else:
            sx = 0 if abs(dx) * 2 < abs(dy) else (1 if dx > 0 else -1)
            sy = 0 if abs(dy) * 2 < abs(dx) else (1 if dy > 0 else -1)
            # y+ is south in this map
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

    def _landmarks(self) -> List[Dict[str, Any]]:
        marks = [
            {"id": "jackpoint", "name": "Jackpoint", "glyph": "J", "x": self.jackpoint_pos[0], "y": self.jackpoint_pos[1], "z": 0},
            {"id": "uplink", "name": "Uplink", "glyph": "U", "x": self.uplink_pos[0], "y": self.uplink_pos[1], "z": 0},
        ]
        for i, rect in enumerate(getattr(self, "club_rects", []) or []):
            if len(rect) >= 4:
                cx = rect[0] + rect[2] // 2
                cy = rect[1] + rect[3] // 2
                marks.append({"id": "club_%d" % i, "name": "Club Glassline", "glyph": "C", "x": cx, "y": cy, "z": 0})
                break
        for vid, (vx, vy) in getattr(self, "vendor_positions", {}).items():
            marks.append({"id": "vendor_%s" % vid, "name": "Vendor", "glyph": "$", "x": vx, "y": vy, "z": 0})
        for kid, (kx, ky) in getattr(self, "signal_key_positions", {}).items():
            marks.append({"id": kid, "name": "Signal Key", "glyph": "*", "x": kx, "y": ky, "z": 0})
        pad = getattr(self, "flotilla_pad", None)
        if pad:
            marks.append({"id": "flotilla_pad", "name": "Flotilla Pad", "glyph": "U", "x": pad[0], "y": pad[1], "z": 0})
        dash_marks = getattr(self, "_neon_dash_landmarks", None)
        if callable(dash_marks):
            marks.extend(dash_marks())
        corp_marks = getattr(self, "_corp_patrol_landmarks", None)
        if callable(corp_marks):
            marks.extend(corp_marks())
        return marks

    def _grant_kill_rewards(self, agent: PlayerAgent, victim: Actor) -> None:
        agent.kills += 1
        gain = int(getattr(C, "XP_PER_KILL", 12))
        agent.xp += gain
        agent.log("+%d XP (%s)." % (gain, victim.name))
        # level up
        need = int(getattr(C, "XP_PER_LEVEL", 40))
        max_lv = int(getattr(C, "MAX_COURIER_LEVEL", 12))
        while agent.xp >= need and agent.level < max_lv:
            agent.xp -= need
            agent.level += 1
            agent.actor.max_hp += 4
            agent.actor.hp = min(agent.actor.max_hp, agent.actor.hp + 4)
            agent.actor.attack += 1
            if agent.level % 2 == 0:
                agent.actor.hack += 1
            agent.log("LEVEL UP → %d  (HP+4 Atk+1)." % agent.level)
            agent.sfx("pickup")
            self._year_on_level_up(agent)
        if self.rng.random() < float(getattr(C, "CREDIT_DROP_CHANCE", 0.45)):
            amt = self.rng.randint(3, 12)
            agent.credits += amt
            agent.log("Looted %d street credits." % amt)
        if self.rng.random() < float(getattr(C, "LOOT_DROP_CHANCE", 0.28)):
            roll = self.rng.random()
            if roll < 0.4:
                item = make_stimpack()
            elif roll < 0.6:
                item = make_focus_tab()
            elif roll < 0.8:
                item = make_pulse_shim()
            else:
                item = make_kevlar_vest()
            agent.actor.inventory.append(item)
            agent.log("Loot: %s" % item.name)
            agent.sfx("pickup")
        self.year_on_kill(agent, victim)

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
                    killer = observer if observer and observer.actor is attacker else self._agent_for_actor(attacker)
                    if killer:
                        self._grant_kill_rewards(killer, defender)
            elif defender.faction == "player":
                victim = self._agent_for_actor(defender)
                if victim:
                    victim.lost = True
                    victim.mode = "dead"
                    victim.sfx("death")
                    victim.log("Your avatar flatlines. Press r to respawn (or respawn <option>).")
                    self._year_on_player_death(victim, killer_name=attacker.name)
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
                self._grant_kill_rewards(agent, target)
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
            self._grant_kill_rewards(agent, target)
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

        now_ai = time.time()
        for a in self.npcs_enemies:
            if not a.alive or a.faction != "enemy":
                continue
            az = int(getattr(a, "z", 0) or 0)
            # ICE stun: frozen in place (#46)
            if float(getattr(a, "stunned_until", 0) or 0) > now_ai:
                continue
            # ICE scramble: wander only, ignore chase (#46)
            if float(getattr(a, "scrambled_until", 0) or 0) > now_ai:
                _wander(a, az)
                continue
            same_plane = [
                p for p in living if int(getattr(p.actor, "z", 0) or 0) == az
            ]
            # NEVER target or path toward invulnerable couriers, or anyone
            # still standing inside a spawn safe bubble (pad camping soft-zone).
            def _aggro_ok(p: PlayerAgent) -> bool:
                if p.is_invulnerable():
                    return False
                if getattr(p, "mode", "") in ("cyberspace", "heist"):
                    return False
                if az == C.PLANE_STREET and self._near_any_spawn(p.actor.x, p.actor.y):
                    return False
                return True

            vulnerable = [p for p in same_plane if _aggro_ok(p)]
            if not vulnerable:
                _wander(a, az)
                continue

            prefer = None
            prefer_fn = getattr(self, "_corp_patrol_prefer_target", None)
            if callable(prefer_fn):
                prefer = prefer_fn(a, vulnerable)
            if prefer is not None:
                target_agent = prefer
            else:
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
        self.year_tick()

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
            agent.cutscene("namshub_counter")
            agent.cutscene("street_victory")
            agent.cutscene("babel_clear")
            agent.log(
                "Node Custodian slots YOUR Faraday sleeve. Counter-incantation "
                "fractures Payload-Zero into harmless checksums — personal run complete. "
                "Others can still finish theirs. YOU WIN."
            )
            self.system_chat("%s cleared Payload-Zero." % agent.name)
            self.year_on_uplink(agent)

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

        if agent.mode == "cyberspace":
            self._cyber_handle_action(agent, action, arg)
            return
        if agent.mode == "heist":
            self._ice_heist_handle_action(agent, action, arg)
            return

        if agent.mode == "flotilla":
            if self._signal_keys_handle_mode(agent, action):
                self.update_fov(agent)
            return

        if agent.mode in ("dead", "won"):
            if action in ("r", "restart", "respawn"):
                if agent.mode == "dead" and hasattr(self, "_year_respawn"):
                    self._year_respawn(agent, (arg or "safe_pad").strip() or "safe_pad")
                else:
                    self._respawn(agent)
            return
        if agent.mode == "spectate":
            if action in ("unspectate", "escape", "Esc", "r"):
                self.handle_year_action(agent, "unspectate", arg)
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

        # Year-backend actions (#12–#39)
        if self.handle_year_action(agent, action, arg):
            self.update_fov(agent)
            return

    def _respawn(self, agent: PlayerAgent) -> None:
        agent.won = False
        agent.lost = False
        agent.mode = "play"
        agent.death_cause = None
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
                talk = self._npc_schedule_line(target) if hasattr(self, "_npc_schedule_line") else target.talk
                agent.log('%s: "%s"' % (target.name, talk))
                agent.sfx("talk")
                agent.cutscene("talk")
                if target.quest_flag and target.quest_flag not in agent.quest_flags:
                    agent.quest_flags[target.quest_flag] = True
                    if target.quest_flag not in agent.story_seen:
                        agent.story_seen.append(target.quest_flag)
                # Story cutscenes
                if target.quest_flag in ("briefing", "archive_briefing"):
                    agent.cutscene("briefing_librarian")
                if target.quest_flag == "club_tip" or "Glassline" in target.name:
                    agent.cutscene("club_black_neon")
                self.update_fov(agent)
                return
            if target.faction == "player":
                other = self._agent_for_actor(target)
                label = other.name if other else target.name
                arena_ok = (
                    other is not None
                    and getattr(agent, "pvp", {}).get("opt_in")
                    and getattr(other, "pvp", {}).get("opt_in")
                    and agent.pvp.get("arena")
                    and agent.pvp.get("arena") == other.pvp.get("arena")
                )
                if C.PVP_ENABLED or arena_ok:
                    self.melee_attack(agent.actor, target, observer=agent)
                else:
                    agent.log("Blocked by courier %s (streets PvP-off; use arena)." % label)
                    agent.sfx("bump")
                self.update_fov(agent)
                return
        if not gmap.walkable(px, py):
            agent.log("Blocked.")
            agent.sfx("bump")
            return
        agent.actor.x, agent.actor.y = px, py
        self._remember_pos(agent)
        on_dash = getattr(self, "_neon_dash_on_move", None)
        if callable(on_dash) and z == C.PLANE_STREET:
            on_dash(agent)
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
            # Enter club room → Black Neon cutscene
            for cx, cy, cw, ch in self.club_rects:
                if cx <= px < cx + cw and cy <= py < cy + ch:
                    if "club_enter" not in agent.story_seen:
                        agent.story_seen.append("club_enter")
                        agent.log("Bass hits like a firewall. Black Neon swallows the street noise.")
                        agent.cutscene("club_black_neon")
                    break
        # Haste: free extra step in same direction
        if agent.haste_steps > 0 and (dx or dy) and not agent.won and agent.actor.alive:
            agent.haste_steps -= 1
            nx, ny = agent.actor.x + dx, agent.actor.y + dy
            if gmap.in_bounds(nx, ny) and gmap.walkable(nx, ny):
                if not self.actor_at(nx, ny, ignore=agent.actor, z=z):
                    agent.actor.x, agent.actor.y = nx, ny
                    self._remember_pos(agent)
                    on_dash = getattr(self, "_neon_dash_on_move", None)
                    if callable(on_dash) and z == C.PLANE_STREET:
                        on_dash(agent)
                    if agent.haste_steps == 0:
                        agent.log("Haste fades.")
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
            self.year_on_payload(agent)
            self._ensure_world_payload()
            self.update_fov(agent)
            return
        self.floor_items.remove(fi)
        agent.actor.inventory.append(fi.item)
        agent.log("Picked up %s." % fi.item.name)
        agent.sfx("pickup")
        on_sk = getattr(self, "_on_signal_key_pickup", None)
        if callable(on_sk):
            on_sk(agent, fi.item)
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
        if item.kind == "wish":
            self._use_wish(agent, idx)
            return
        if item.equippable and not item.extra.get("grant"):
            self._equip_item(agent, idx)
            return
        used = False
        # Prototype grant extras (from wish catalog toys)
        grant = item.extra.get("grant")
        if grant:
            self._apply_grant(agent, grant, item)
            used = True
        if item.heal:
            healed = agent.actor.heal(item.heal)
            agent.log("Used %s: +%d HP." % (item.name, healed))
            used = True
        if item.focus_restore and not grant:
            got = agent.actor.restore_focus(item.focus_restore)
            agent.log("Used %s: +%d focus." % (item.name, got))
            used = True
        if item.kind == "datachip" or item.id == "flotilla_radio":
            agent.log("You jack the chip: %s" % item.description)
            if item.hack_bonus:
                agent.actor.hack += item.hack_bonus
                agent.log("Hack skill +%d." % item.hack_bonus)
            used = True
            cs = item.extra.get("cutscene") or "terminal"
            agent.cutscene(cs)
            qf = item.extra.get("quest_flag")
            if qf:
                agent.quest_flags[qf] = True
                if qf not in agent.story_seen:
                    agent.story_seen.append(qf)
        if item.kind == "misc" and item.extra.get("grant") and not used:
            used = True
        if not used and item.equippable:
            self._equip_item(agent, idx)
            return
        if not used:
            agent.log("Can't use %s." % item.name)
            return
        if used:
            agent.sfx("use")
        if used and item.consumable:
            inv.pop(idx)
            if agent.selected_inv >= len(inv):
                agent.selected_inv = max(0, len(inv) - 1)
            agent.mode = "play"

    def _use_wish(self, agent: PlayerAgent, idx: int) -> None:
        inv = agent.actor.inventory
        item = inv[idx]
        wish_text = item.extra.get("wish_text") or item.description.split("\n")[0]
        agent.cutscene("wish_granted", once=False)
        agent.sfx("use")
        grant = match_wish_grant(wish_text)
        inv.pop(idx)
        if agent.selected_inv >= len(inv):
            agent.selected_inv = max(0, len(inv) - 1)
        agent.mode = "play"
        if grant == "pulse" and any(i.id == "pulse_pistol" for i in agent.actor.inventory):
            agent.log("Wish granted — you already pack a Pulse Pistol. Backlog Token instead.")
            agent.actor.inventory.append(make_backlog_token(wish_text))
            agent.log("Wish logged to Metaverse backlog.")
            return
        if grant:
            proto = prototype_for_grant(grant)
            if proto:
                # pulse / heal grant the real item directly; others are usable prototypes
                if grant in ("pulse", "heal"):
                    agent.actor.inventory.append(proto)
                    agent.log("Wish granted: %s" % grant_label(grant))
                else:
                    agent.actor.inventory.append(proto)
                    agent.log("Wish granted prototype: %s — use it from inventory." % grant_label(grant))
                return
        agent.actor.inventory.append(make_backlog_token(wish_text))
        agent.log("Wish logged to Metaverse backlog.")

    def _apply_grant(self, agent: PlayerAgent, grant: str, item: Item) -> None:
        if grant == "haste":
            steps = int(item.extra.get("haste_steps", 8))
            agent.haste_steps = max(agent.haste_steps, steps)
            if item.focus_restore:
                agent.actor.restore_focus(item.focus_restore)
            agent.log("Haste online — double-step for %d moves." % agent.haste_steps)
        elif grant == "reveal":
            rad = int(item.extra.get("reveal_radius", 14))
            self._reveal_fog(agent, rad)
            if item.hack_bonus:
                agent.actor.hack += item.hack_bonus
            agent.log("Fog flare — explored radius %d." % rad)
            agent.cutscene("terminal")
        elif grant == "shield":
            sec = float(item.extra.get("shield_sec", 10))
            agent.invuln_until = max(agent.invuln_until, time.time() + sec)
            agent.log("Hardlight shield up for %.0fs." % sec)
        elif grant == "companion":
            agent.companion = True
            agent.log("Drone pet beacon latched — companion flag on your snapshot.")
        elif grant == "flashlight":
            bonus = int(item.extra.get("view_bonus", 4))
            ticks = int(item.extra.get("view_ticks", 80))
            agent.view_bonus = max(agent.view_bonus, bonus)
            agent.view_bonus_until_tick = self.tick + ticks
            agent.log("Night lens online — VIEW_RADIUS +%d for a while." % bonus)
            self.update_fov(agent)

    def _reveal_fog(self, agent: PlayerAgent, radius: int) -> None:
        z = int(getattr(agent.actor, "z", 0) or 0)
        self._bind_agent_fog(agent, z)
        gmap = self.plane_map(z)
        px, py = agent.actor.x, agent.actor.y
        r2 = radius * radius
        for y in range(max(0, py - radius), min(gmap.height, py + radius + 1)):
            for x in range(max(0, px - radius), min(gmap.width, px + radius + 1)):
                if (x - px) ** 2 + (y - py) ** 2 <= r2:
                    agent.explored[y][x] = True

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

    def _irc_snapshot_lines(self, agent: PlayerAgent) -> List[Dict[str, Any]]:
        self._ensure_irc(agent)
        ch = agent.irc_channel or "#streets"
        out: List[ChatLine] = []
        if ch.startswith("@"):
            out = [c for c in agent.private_chat if c.kind == "pm"][-20:]
        else:
            out = list(self.channel_chat.get(ch, [])[-20:])
        # notices always visible
        notices = [c for c in agent.private_chat if c.kind == "notice"][-6:]
        merged = notices + out
        # de-dupe by identity while preserving order
        seen = set()
        lines = []
        for c in merged:
            key = (c.t, c.name, c.text, c.kind, getattr(c, "channel", ""))
            if key in seen:
                continue
            seen.add(key)
            lines.append(
                {
                    "t": c.t,
                    "name": c.name,
                    "text": c.text,
                    "kind": c.kind,
                    "channel": getattr(c, "channel", ch),
                }
            )
        return lines[-24:]

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

        # Street cameras (#46) — show when visible or recently ICE-scanned
        now_cam = time.time()
        for cam in getattr(self, "ice_cameras", []) or []:
            if int(cam.get("z", 0) or 0) != az:
                continue
            cx, cy = int(cam["x"]), int(cam["y"])
            if cy < 0 or cx < 0 or cy >= len(agent.visible) or cx >= len(agent.visible[0]):
                continue
            revealed = float(cam.get("revealed_until", 0) or 0) > now_cam
            if not (agent.visible[cy][cx] or revealed):
                continue
            stunned = float(cam.get("stunned_until", 0) or 0) > now_cam
            entities.append({
                "x": cx, "y": cy, "glyph": "c",
                "name": cam.get("name", "Street Cam") + (" [STUN]" if stunned else ""),
                "faction": "ice", "hp": 1,
                "kind": "camera",
            })

        snap = {
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
                    "id": it.id,
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
            "chat": self._irc_snapshot_lines(agent),
            "irc": {
                "channel": getattr(agent, "irc_channel", "#streets"),
                "channels": list(getattr(agent, "irc_channels", ["#streets"])),
                "topics": {ch: self.channel_topics.get(ch, "") for ch in getattr(agent, "irc_channels", ["#streets"])},
                "nicks": [
                    {"name": o.name, "glyph": o.glyph, "color": o.color, "you": o.id == agent.id}
                    for o in self.players.values()
                    if o.connected
                    and getattr(agent, "irc_channel", "#streets")
                    in getattr(o, "irc_channels", ["#streets"])
                ]
                if not str(getattr(agent, "irc_channel", "")).startswith("@")
                else [],
            },
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
            "spawn_shield_remaining": round(agent.spawn_shield_remaining(), 1),
            "spawn_shield": bool(agent.is_invulnerable()),
            "z": int(getattr(p, "z", 0) or 0),
            "plane": C.PLANE_NAMES.get(int(getattr(p, "z", 0) or 0), "STREET"),
            "plane_label": C.PLANE_LABELS.get(int(getattr(p, "z", 0) or 0), ""),
            "sfx": sfx_events,
            "cutscenes": cutscene_events,
            "objective": self._quest_objective(agent),
            "landmarks": self._landmarks(),
            "xp": agent.xp,
            "level": agent.level,
            "credits": agent.credits,
            "kills": agent.kills,
            "xp_next": int(getattr(C, "XP_PER_LEVEL", 40)),
        }
        snap.update(self.year_snapshot_fields(agent))
        # Cyberspace (#47): swap ASCII map to node lattice while jacked
        cyber = snap.get("cyberspace") or {}
        if agent.mode == "cyberspace" and cyber.get("active") and cyber.get("map"):
            snap["map"] = list(cyber["map"])
            snap["width"] = int(cyber.get("width") or len(cyber["map"][0]))
            snap["height"] = int(cyber.get("height") or len(cyber["map"]))
            snap["street_map_paused"] = True
        # Deep ICE heist (#56): swap ASCII map to vault layer while running
        heist = snap.get("ice_heist") or {}
        if agent.mode == "heist" and heist.get("active") and heist.get("map"):
            snap["map"] = list(heist["map"])
            snap["width"] = int(heist.get("width") or len(heist["map"][0]))
            snap["height"] = int(heist.get("height") or len(heist["map"]))
            snap["street_map_paused"] = True
        # Spectate: overlay target camera lightly
        if getattr(agent, "spectating", None) and agent.spectating in self.players:
            tgt = self.players[agent.spectating]
            snap["spectate_target"] = {
                "id": tgt.id, "name": tgt.name,
                "x": tgt.actor.x, "y": tgt.actor.y,
                "z": int(getattr(tgt.actor, "z", 0) or 0),
            }
        return snap


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
