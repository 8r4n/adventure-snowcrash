"""Shared turn-based game engine used by TUI and web frontends."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import constants as C
from .entities import Actor
from .items import Item
from .mapgen import FloorItem, GameMap, WorldBundle, generate_world


@dataclass
class GameState:
    seed: Optional[int]
    rng: random.Random
    gmap: GameMap
    player: Actor
    actors: List[Actor]
    floor_items: List[FloorItem]
    uplink_pos: Tuple[int, int]
    jackpoint_pos: Tuple[int, int]
    story_beats: List[str]
    messages: List[str] = field(default_factory=list)
    turn: int = 0
    won: bool = False
    lost: bool = False
    quest_flags: Dict[str, bool] = field(default_factory=dict)
    selected_inv: int = 0
    mode: str = "play"  # play, inventory, help, dead, won
    story_seen: List[str] = field(default_factory=list)
    pending_sfx: List[str] = field(default_factory=list)
    pending_cutscenes: List[str] = field(default_factory=list)
    cutscenes_played: List[str] = field(default_factory=list)

    def log(self, msg: str) -> None:
        self.messages.append(msg)
        if len(self.messages) > 80:
            self.messages = self.messages[-80:]

    def sfx(self, event_id: str) -> None:
        """Queue a one-shot sound event for the next snapshot."""
        self.pending_sfx.append(event_id)

    def cutscene(self, cutscene_id: str, once: bool = True) -> None:
        """Queue a first-person ASCII cutscene for the web client."""
        if once and cutscene_id in self.cutscenes_played:
            return
        if once:
            self.cutscenes_played.append(cutscene_id)
        self.pending_cutscenes.append(cutscene_id)

    def actor_at(self, x: int, y: int) -> Optional[Actor]:
        for a in self.actors:
            if a.alive and a.x == x and a.y == y:
                return a
        return None

    def items_at(self, x: int, y: int) -> List[FloorItem]:
        return [fi for fi in self.floor_items if fi.x == x and fi.y == y]

    def has_payload(self) -> bool:
        return any(i.id == "payload_zero" for i in self.player.inventory)


def new_game(seed: Optional[int] = None) -> GameState:
    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    world: WorldBundle = generate_world(seed)
    gs = GameState(
        seed=seed,
        rng=random.Random(seed ^ 0xC0FFEE),
        gmap=world.gmap,
        player=world.player,
        actors=world.actors,
        floor_items=world.floor_items,
        uplink_pos=world.uplink_pos,
        jackpoint_pos=world.jackpoint_pos,
        story_beats=world.story_beats,
    )
    gs.log("You jack into the street layer. Fractured LA hums under neon rain.")
    gs.log("Talk to Relay Tran in the safehouse. Press ? for help.")
    gs.log(f"Seed: {seed}")
    update_fov(gs)
    return gs


def restart(gs: GameState) -> GameState:
    return new_game(gs.seed)


# ---- FOV (simple shadowless radius + LOS) ----

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


def update_fov(gs: GameState) -> None:
    gmap = gs.gmap
    px, py = gs.player.x, gs.player.y
    r = C.VIEW_RADIUS
    for y in range(gmap.height):
        for x in range(gmap.width):
            gmap.visible[y][x] = False
    for y in range(max(0, py - r), min(gmap.height, py + r + 1)):
        for x in range(max(0, px - r), min(gmap.width, px + r + 1)):
            if (x - px) ** 2 + (y - py) ** 2 <= r * r:
                if _los(gmap, px, py, x, y):
                    gmap.visible[y][x] = True
                    gmap.explored[y][x] = True


# ---- Combat / AI ----

def melee_attack(gs: GameState, attacker: Actor, defender: Actor) -> None:
    atk = attacker.total_attack() if hasattr(attacker, "total_attack") else attacker.attack
    # Recalc with defense properly
    raw = atk + gs.rng.randint(0, 2)
    dmg = defender.take_damage(raw)
    gs.log(f"{attacker.name} hits {defender.name} for {dmg}.")
    if attacker.is_player():
        gs.sfx("melee")
    if not defender.alive:
        gs.log(f"{defender.name} collapses into pixel dust.")
        if defender.faction == "enemy":
            gs.sfx("kill")
            if attacker.is_player():
                # small focus restore on kill
                attacker.restore_focus(2)
        elif defender.is_player():
            # death sfx emitted when mode flips in enemy_turn / callers
            pass
    elif defender.faction == "enemy":
        gs.sfx("hurt")


def try_ranged_or_hack(gs: GameState) -> bool:
    """Target nearest visible enemy; use pulse pistol or hack."""
    player = gs.player
    enemies = [
        a
        for a in gs.actors
        if a.alive
        and a.faction == "enemy"
        and gs.gmap.visible[a.y][a.x]
    ]
    if not enemies:
        gs.log("No hostile targets in sight.")
        return False

    def dist(a: Actor) -> int:
        return abs(a.x - player.x) + abs(a.y - player.y)

    target = min(enemies, key=dist)
    weapon = player.equipped_ranged()
    if weapon and weapon.ranged_damage > 0:
        cost = int(weapon.extra.get("focus_cost", 3))
        if player.focus < cost:
            gs.log("Not enough focus to fire.")
            return False
        player.focus -= cost
        dmg = target.take_damage(weapon.ranged_damage + gs.rng.randint(0, 2))
        gs.log(f"You pulse-fire {weapon.name} at {target.name} for {dmg}.")
        gs.sfx("pulse")
        if not target.alive:
            gs.log(f"{target.name} fries.")
            gs.sfx("kill")
        else:
            gs.sfx("hurt")
        return True

    # Hack attack
    cost = 4
    if player.focus < cost:
        gs.log("Focus too low to hack. Wait or use a Focus Tab.")
        return False
    player.focus -= cost
    power = player.total_hack() + gs.rng.randint(0, 3)
    if target.glyph == C.ENEMY_DRONE:
        power += 2  # drones are vulnerable to hack
    dmg = target.take_damage(power)
    gs.log(f"You inject a glitch into {target.name} for {dmg} (hack).")
    gs.sfx("pulse")
    if not target.alive:
        gs.log(f"{target.name} bluescreens.")
        gs.sfx("kill")
    else:
        gs.sfx("hurt")
    return True


def enemy_turn(gs: GameState) -> None:
    player = gs.player
    for a in gs.actors:
        if not a.alive or a.faction != "enemy":
            continue
        dx = player.x - a.x
        dy = player.y - a.y
        dist = abs(dx) + abs(dy)
        # Can see player? (visible tile of enemy relative to player FOV is approx)
        can_see = gs.gmap.visible[a.y][a.x] or dist <= C.VIEW_RADIUS
        if dist == 1:
            melee_attack(gs, a, player)
            if not player.alive:
                gs.lost = True
                gs.mode = "dead"
                gs.sfx("death")
                gs.log("Your avatar flatlines. Press r to restart or q to quit.")
            continue
        if can_see and dist <= C.VIEW_RADIUS + 2 and a.ai == "chase":
            step_x = 0 if dx == 0 else (1 if dx > 0 else -1)
            step_y = 0 if dy == 0 else (1 if dy > 0 else -1)
            # Prefer axis with larger delta
            if abs(dx) >= abs(dy):
                nx, ny = a.x + step_x, a.y
                if not _can_move(gs, a, nx, ny):
                    nx, ny = a.x, a.y + step_y
            else:
                nx, ny = a.x, a.y + step_y
                if not _can_move(gs, a, nx, ny):
                    nx, ny = a.x + step_x, a.y
            if _can_move(gs, a, nx, ny):
                a.x, a.y = nx, ny
        else:
            # wander
            opts = [(0, 1), (0, -1), (1, 0), (-1, 0), (0, 0)]
            gs.rng.shuffle(opts)
            for ox, oy in opts:
                nx, ny = a.x + ox, a.y + oy
                if _can_move(gs, a, nx, ny):
                    a.x, a.y = nx, ny
                    break


def _can_move(gs: GameState, actor: Actor, x: int, y: int) -> bool:
    if not gs.gmap.walkable(x, y):
        return False
    other = gs.actor_at(x, y)
    if other and other is not actor and other.alive:
        return False
    return True


def end_player_turn(gs: GameState) -> None:
    if gs.won or gs.lost:
        return
    # slight focus regen
    if gs.turn % 3 == 0:
        gs.player.restore_focus(1)
    enemy_turn(gs)
    gs.turn += 1
    update_fov(gs)
    check_win(gs)


def check_win(gs: GameState) -> None:
    if gs.won or gs.lost:
        return
    px, py = gs.player.x, gs.player.y
    ux, uy = gs.uplink_pos
    if abs(px - ux) + abs(py - uy) <= 1 and gs.has_payload():
        # Remove payload and win
        gs.player.inventory = [i for i in gs.player.inventory if i.id != "payload_zero"]
        gs.won = True
        gs.mode = "won"
        gs.quest_flags["payload_cleared"] = True
        gs.sfx("win")
        gs.cutscene("uplink")
        gs.log(
            "Node Custodian slots the Faraday sleeve. Payload-Zero dissolves into "
            "harmless checksums — or rides a clean packet into the Metaverse. "
            "Job done. YOU WIN."
        )
        if "victory" not in gs.story_seen:
            gs.story_seen.append("victory")


# ---- Input handling ----

def handle_action(gs: GameState, action: str, arg: Optional[str] = None) -> Dict[str, Any]:
    """Process one player action. Returns a small status dict."""
    action = (action or "").strip()
    if gs.mode == "help":
        if action in ("?", "escape", "Esc", " ", "enter", "q"):
            gs.mode = "play"
        return snapshot(gs)

    if gs.mode == "inventory":
        return _handle_inventory(gs, action, arg)

    if gs.mode in ("dead", "won"):
        if action in ("r", "restart"):
            new_gs = restart(gs)
            # mutate in place so callers keeping reference still work
            _replace_state(gs, new_gs)
            return snapshot(gs)
        if action == "q":
            return {**snapshot(gs), "quit": True}
        return snapshot(gs)

    # play mode
    if action in ("?", "help"):
        gs.mode = "help"
        return snapshot(gs)

    if action == "q":
        return {**snapshot(gs), "quit": True}

    if action in ("i", "inventory"):
        gs.mode = "inventory"
        gs.selected_inv = 0
        gs.log("Inventory — numbers select, e equip/unequip, u use, d drop, Esc back.")
        return snapshot(gs)

    if action in ("turn_left", "tl", ","):
        _turn(gs, -1)
        return snapshot(gs)
    if action in ("turn_right", "tr"):
        _turn(gs, 1)
        return snapshot(gs)

    # Relative movement (GTA / Doom-style: facing + move)
    if action in ("forward", "back", "strafe_left", "strafe_right"):
        dx, dy = _relative_delta(gs.player.facing, action)
        _try_move(gs, dx, dy)
        return snapshot(gs)

    # Absolute map moves (TUI hjkl / legacy wasd aliases still work via MOVE_KEYS)
    if action in C.MOVE_KEYS:
        dx, dy = C.MOVE_KEYS[action]
        # Keep facing pointed at move direction when using absolute keys
        _face_toward(gs, dx, dy)
        _try_move(gs, dx, dy)
        return snapshot(gs)

    if action in (".", " ", "wait"):
        gs.log("You wait. Neon flickers.")
        end_player_turn(gs)
        return snapshot(gs)

    if action in ("g", "get", "pickup"):
        _pickup(gs)
        return snapshot(gs)

    if action in ("f", "fire", "hack"):
        if try_ranged_or_hack(gs):
            end_player_turn(gs)
        return snapshot(gs)

    if action == "u" and arg:
        # use inventory index
        try:
            idx = int(arg)
            _use_item(gs, idx)
        except ValueError:
            gs.log("Usage: u <index>")
        return snapshot(gs)

    if action == "look":
        _look(gs)
        return snapshot(gs)

    return snapshot(gs)


def _replace_state(dst: GameState, src: GameState) -> None:
    for f in src.__dataclass_fields__:
        setattr(dst, f, getattr(src, f))


def _turn(gs: GameState, delta: int) -> None:
    gs.player.facing = (gs.player.facing + delta) % 4
    gs.sfx("click")


def _face_toward(gs: GameState, dx: int, dy: int) -> None:
    if dx == 0 and dy == 0:
        return
    # Prefer the dominant axis
    if abs(dx) >= abs(dy):
        gs.player.facing = 1 if dx > 0 else 3
    else:
        gs.player.facing = 2 if dy > 0 else 0


def _relative_delta(facing: int, action: str) -> Tuple[int, int]:
    fx, fy = C.FACING_DIRS[facing % 4]
    # left strafe = rotate facing vector -90°: (fx,fy) -> (fy, -fx)
    # right strafe: (fx,fy) -> (-fy, fx)
    if action == "forward":
        return fx, fy
    if action == "back":
        return -fx, -fy
    if action == "strafe_left":
        return fy, -fx
    if action == "strafe_right":
        return -fy, fx
    return 0, 0


def _try_move(gs: GameState, dx: int, dy: int) -> None:
    px, py = gs.player.x + dx, gs.player.y + dy
    if not gs.gmap.in_bounds(px, py):
        gs.sfx("bump")
        return
    target = gs.actor_at(px, py)
    if target and target.alive:
        if target.faction == "enemy":
            melee_attack(gs, gs.player, target)
            end_player_turn(gs)
            return
        if target.faction == "npc":
            gs.log(f'{target.name}: "{target.talk}"')
            gs.sfx("talk")
            gs.cutscene("talk")
            if target.quest_flag and target.quest_flag not in gs.quest_flags:
                gs.quest_flags[target.quest_flag] = True
                if target.quest_flag not in gs.story_seen:
                    gs.story_seen.append(target.quest_flag)
            # bump into NPC doesn't consume? still a turn of talking
            end_player_turn(gs)
            return
    if not gs.gmap.walkable(px, py):
        gs.log("Blocked.")
        gs.sfx("bump")
        return
    gs.player.x, gs.player.y = px, py
    if gs.gmap.tiles[py][px] == C.DOOR:
        gs.sfx("door")
        gs.cutscene("door")
    else:
        gs.sfx("step")
    # auto-describe items
    here = gs.items_at(px, py)
    for fi in here:
        gs.log(f"You see here: {fi.item.name}.")
    if (px, py) == gs.jackpoint_pos or (
        abs(px - gs.jackpoint_pos[0]) + abs(py - gs.jackpoint_pos[1]) <= 1
    ):
        if "jackpoint" not in gs.story_seen:
            gs.story_seen.append("jackpoint")
            gs.log("Jackpoint air tastes like ozone and old prayers.")
            gs.cutscene("jackpoint")
    # Adjacent uplink approach (before win) — brief jack sense
    ux, uy = gs.uplink_pos
    if abs(px - ux) + abs(py - uy) <= 1 and "uplink_approach" not in gs.story_seen:
        if not gs.has_payload():
            gs.story_seen.append("uplink_approach")
            gs.log("Uplink node thrums — needs Payload-Zero in the sleeve.")
    end_player_turn(gs)


def _pickup(gs: GameState) -> None:
    here = gs.items_at(gs.player.x, gs.player.y)
    if not here:
        gs.log("Nothing to pick up.")
        return
    fi = here[0]
    gs.floor_items.remove(fi)
    gs.player.inventory.append(fi.item)
    gs.log(f"Picked up {fi.item.name}.")
    gs.sfx("pickup")
    if fi.item.id == "payload_zero":
        gs.quest_flags["got_payload"] = True
        if "got_payload" not in gs.story_seen:
            gs.story_seen.append("got_payload")
        gs.log("Payload-Zero is heavy with unspoken syllables. Get to the uplink.")
        gs.cutscene("payload")
    end_player_turn(gs)


def _look(gs: GameState) -> None:
    gs.log(f"Pos ({gs.player.x},{gs.player.y}) turn {gs.turn}.")


def _handle_inventory(gs: GameState, action: str, arg: Optional[str]) -> Dict[str, Any]:
    inv = gs.player.inventory
    if action in ("escape", "Esc", "i", "q"):
        gs.mode = "play"
        return snapshot(gs)
    if action.isdigit():
        idx = int(action)
        if 0 <= idx < len(inv):
            gs.selected_inv = idx
            gs.log(f"Selected [{idx}] {inv[idx].name}")
        return snapshot(gs)
    if action == "u":
        _use_item(gs, gs.selected_inv)
        return snapshot(gs)
    if action == "e":
        _equip_item(gs, gs.selected_inv)
        return snapshot(gs)
    if action == "d":
        _drop_item(gs, gs.selected_inv)
        return snapshot(gs)
    if action in C.MOVE_KEYS:
        # allow navigating selection with j/k
        dx, dy = C.MOVE_KEYS[action]
        if dy != 0 and inv:
            gs.selected_inv = max(0, min(len(inv) - 1, gs.selected_inv + dy))
        return snapshot(gs)
    return snapshot(gs)


def _use_item(gs: GameState, idx: int) -> None:
    inv = gs.player.inventory
    if idx < 0 or idx >= len(inv):
        gs.log("No such item.")
        return
    item = inv[idx]
    if item.kind == "quest":
        gs.log("Quest items can't be 'used' here — deliver to the uplink.")
        return
    if item.equippable:
        _equip_item(gs, idx)
        return
    if not item.consumable and item.heal == 0 and item.focus_restore == 0 and item.hack_bonus == 0:
        gs.log(f"Can't use {item.name}.")
        return
    used = False
    if item.heal:
        healed = gs.player.heal(item.heal)
        gs.log(f"Used {item.name}: +{healed} HP.")
        used = True
    if item.focus_restore:
        got = gs.player.restore_focus(item.focus_restore)
        gs.log(f"Used {item.name}: +{got} focus.")
        used = True
    if item.kind == "datachip":
        gs.log(f"You jack the chip: {item.description}")
        if item.hack_bonus:
            # permanent small hack bump once
            gs.player.hack += item.hack_bonus
            gs.log(f"Hack skill +{item.hack_bonus}.")
        used = True
        gs.cutscene("terminal")
    if used:
        gs.sfx("use")
    if used and item.consumable:
        inv.pop(idx)
        if gs.selected_inv >= len(inv):
            gs.selected_inv = max(0, len(inv) - 1)
        if gs.mode == "play":
            end_player_turn(gs)
        else:
            end_player_turn(gs)
            gs.mode = "play"


def _equip_item(gs: GameState, idx: int) -> None:
    inv = gs.player.inventory
    if idx < 0 or idx >= len(inv):
        return
    item = inv[idx]
    if not item.equippable:
        gs.log(f"{item.name} isn't equippable.")
        return
    # Unequip same kind
    for other in inv:
        if other.kind == item.kind and other.equipped and other is not item:
            other.equipped = False
            gs.log(f"Unequipped {other.name}.")
    item.equipped = not item.equipped
    gs.log(("Equipped " if item.equipped else "Unequipped ") + item.name + ".")


def _drop_item(gs: GameState, idx: int) -> None:
    inv = gs.player.inventory
    if idx < 0 or idx >= len(inv):
        return
    item = inv.pop(idx)
    item.equipped = False
    gs.floor_items.append(FloorItem(gs.player.x, gs.player.y, item))
    gs.log(f"Dropped {item.name}.")
    if gs.selected_inv >= len(inv):
        gs.selected_inv = max(0, len(inv) - 1)
    end_player_turn(gs)
    gs.mode = "play"


# ---- Rendering helpers (shared ASCII frame) ----

def render_ascii(gs: GameState) -> List[str]:
    """Return list of map rows as strings with entities."""
    gmap = gs.gmap
    # glyph overlay
    overlay: Dict[Tuple[int, int], str] = {}
    for fi in gs.floor_items:
        overlay[(fi.x, fi.y)] = fi.item.glyph
    for a in gs.actors:
        if not a.alive:
            continue
        if a.is_player():
            continue
        overlay[(a.x, a.y)] = a.glyph
    overlay[(gs.player.x, gs.player.y)] = gs.player.glyph

    rows = []
    for y in range(gmap.height):
        chars = []
        for x in range(gmap.width):
            if gmap.visible[y][x]:
                chars.append(overlay.get((x, y), gmap.tiles[y][x]))
            elif gmap.explored[y][x]:
                # explored but not visible: show terrain only, dim conceptually
                t = gmap.tiles[y][x]
                chars.append(t if t != C.FLOOR else C.FLOOR)
            else:
                chars.append(" ")
        rows.append("".join(chars))
    return rows


def snapshot(gs: GameState) -> Dict[str, Any]:
    p = gs.player
    sfx_events = list(gs.pending_sfx)
    gs.pending_sfx.clear()
    cutscene_events = list(gs.pending_cutscenes)
    gs.pending_cutscenes.clear()
    return {
        "seed": gs.seed,
        "turn": gs.turn,
        "mode": gs.mode,
        "won": gs.won,
        "lost": gs.lost,
        "map": render_ascii(gs),
        "width": gs.gmap.width,
        "height": gs.gmap.height,
        "player": {
            "name": p.name,
            "x": p.x,
            "y": p.y,
            "hp": p.hp,
            "max_hp": p.max_hp,
            "focus": p.focus,
            "max_focus": p.max_focus,
            "attack": p.total_attack(),
            "defense": p.total_defense(),
            "hack": p.total_hack(),
            "has_payload": gs.has_payload(),
            "facing": p.facing % 4,
            "facing_name": C.FACING_NAMES[p.facing % 4],
        },
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
        "selected_inv": gs.selected_inv,
        "messages": gs.messages[-12:],
        "quest_flags": dict(gs.quest_flags),
        "story_seen": list(gs.story_seen),
        "help": C.HELP_TEXT,
        "visible": [row[:] for row in gs.gmap.visible],
        "explored": [row[:] for row in gs.gmap.explored],
        "jackpoint": list(gs.jackpoint_pos),
        "uplink": list(gs.uplink_pos),
        "sfx": sfx_events,
        "cutscenes": cutscene_events,
    }
