"""Actors: player, enemies, NPCs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

from . import constants as C
from .items import Item

if TYPE_CHECKING:
    pass


@dataclass
class Actor:
    x: int
    y: int
    name: str
    glyph: str
    hp: int
    max_hp: int
    focus: int = 0
    max_focus: int = 0
    attack: int = 2
    defense: int = 0
    hack: int = 0
    alive: bool = True
    ai: str = "none"  # none, wander, chase, attack
    faction: str = "neutral"  # player, enemy, npc
    inventory: List[Item] = field(default_factory=list)
    talk: str = ""
    quest_flag: str = ""
    xp_value: int = 0
    color: str = "white"
    facing: int = 0  # 0=N 1=E 2=S 3=W (player camera)
    z: int = 0  # plane: -1 under, 0 street, +1 air

    def is_player(self) -> bool:
        return self.faction == "player"

    def take_damage(self, amount: int) -> int:
        dmg = max(1, amount - self.defense // 2)
        self.hp -= dmg
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
        return dmg

    def heal(self, amount: int) -> int:
        before = self.hp
        self.hp = min(self.max_hp, self.hp + amount)
        return self.hp - before

    def restore_focus(self, amount: int) -> int:
        before = self.focus
        self.focus = min(self.max_focus, self.focus + amount)
        return self.focus - before

    def total_attack(self) -> int:
        bonus = sum(i.attack_bonus for i in self.inventory if i.equipped)
        return self.attack + bonus

    def total_defense(self) -> int:
        bonus = sum(i.defense_bonus for i in self.inventory if i.equipped)
        return self.defense + bonus

    def total_hack(self) -> int:
        eq = sum(i.hack_bonus for i in self.inventory if i.equipped)
        # Held datachips contribute until consumed
        chips = sum(i.hack_bonus for i in self.inventory if i.kind == "datachip")
        return self.hack + eq + chips

    def equipped_ranged(self) -> Optional[Item]:
        for i in self.inventory:
            if i.equipped and i.ranged_damage > 0:
                return i
        return None


def make_player(x: int, y: int, name: str = "Rin Vale") -> Actor:
    return Actor(
        x=x,
        y=y,
        name=name,
        glyph=C.PLAYER,
        hp=C.START_HP,
        max_hp=C.START_HP,
        focus=C.START_FOCUS,
        max_focus=C.START_FOCUS,
        attack=C.START_ATTACK,
        defense=C.START_DEFENSE,
        hack=C.START_HACK,
        faction="player",
        color="cyan",
    )


def make_infected(x: int, y: int) -> Actor:
    return Actor(
        x=x,
        y=y,
        name="Infected Avatar",
        glyph=C.ENEMY_INFECTED,
        hp=8,
        max_hp=8,
        attack=3,
        defense=0,
        ai="chase",
        faction="enemy",
        xp_value=5,
        color="green",
        talk="...static... name... speak...",
    )


def make_thug(x: int, y: int) -> Actor:
    return Actor(
        x=x,
        y=y,
        name="Street Thug",
        glyph=C.ENEMY_THUG,
        hp=12,
        max_hp=12,
        attack=4,
        defense=1,
        ai="chase",
        faction="enemy",
        xp_value=8,
        color="yellow",
    )


def make_drone(x: int, y: int) -> Actor:
    return Actor(
        x=x,
        y=y,
        name="Security Drone",
        glyph=C.ENEMY_DRONE,
        hp=10,
        max_hp=10,
        attack=5,
        defense=2,
        ai="chase",
        faction="enemy",
        xp_value=10,
        color="magenta",
    )


def make_npc(x: int, y: int, name: str, talk: str, quest_flag: str = "") -> Actor:
    return Actor(
        x=x,
        y=y,
        name=name,
        glyph=C.NPC,
        hp=20,
        max_hp=20,
        attack=0,
        defense=5,
        ai="none",
        faction="npc",
        talk=talk,
        quest_flag=quest_flag,
        color="blue",
    )
