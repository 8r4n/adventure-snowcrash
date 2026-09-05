"""Item definitions and factories."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Item:
    id: str
    name: str
    glyph: str = "*"
    kind: str = "misc"  # med, weapon, armor, datachip, quest, misc
    description: str = ""
    heal: int = 0
    focus_restore: int = 0
    attack_bonus: int = 0
    defense_bonus: int = 0
    hack_bonus: int = 0
    ranged_damage: int = 0
    consumable: bool = False
    quest: bool = False
    equippable: bool = False
    equipped: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def copy(self) -> "Item":
        return Item(
            id=self.id,
            name=self.name,
            glyph=self.glyph,
            kind=self.kind,
            description=self.description,
            heal=self.heal,
            focus_restore=self.focus_restore,
            attack_bonus=self.attack_bonus,
            defense_bonus=self.defense_bonus,
            hack_bonus=self.hack_bonus,
            ranged_damage=self.ranged_damage,
            consumable=self.consumable,
            quest=self.quest,
            equippable=self.equippable,
            equipped=False,
            extra=dict(self.extra),
        )


def make_stimpack() -> Item:
    return Item(
        id="stimpack",
        name="Street Stimpack",
        glyph="!",
        kind="med",
        description="Industrial-grade clotting foam. Heals 12 HP.",
        heal=12,
        consumable=True,
    )


def make_focus_tab() -> Item:
    return Item(
        id="focus_tab",
        name="Focus Tab",
        glyph="!",
        kind="med",
        description="Microdose that clears the static. Restores 10 focus.",
        focus_restore=10,
        consumable=True,
    )


def make_mono_knife() -> Item:
    return Item(
        id="mono_knife",
        name="Monofilament Knife",
        glyph="/",
        kind="weapon",
        description="Cuts through cheap armor like gossip through a burbclave.",
        attack_bonus=3,
        equippable=True,
    )


def make_stun_baton() -> Item:
    return Item(
        id="stun_baton",
        name="Stun Baton",
        glyph="/",
        kind="weapon",
        description="Short-range spark. +2 attack.",
        attack_bonus=2,
        equippable=True,
    )


def make_leather_jacket() -> Item:
    return Item(
        id="leather_jacket",
        name="Reinforced Jacket",
        glyph="[",
        kind="armor",
        description="Kevlar weave under neon paint. +2 defense.",
        defense_bonus=2,
        equippable=True,
    )


def make_datachip(name: str = "Street Datachip", desc: str = "") -> Item:
    return Item(
        id="datachip",
        name=name,
        glyph="*",
        kind="datachip",
        description=desc or "Encrypted gossip and map scraps.",
        hack_bonus=1,
        consumable=True,
    )


def make_payload_zero() -> Item:
    return Item(
        id="payload_zero",
        name="Payload-Zero Core",
        glyph="%",
        kind="quest",
        description=(
            "A nam-shub-shaped linguistic virus in a Faraday sleeve. "
            "Do not speak its true name. Deliver or scrub at the uplink."
        ),
        quest=True,
    )


def make_pulse_pistol() -> Item:
    return Item(
        id="pulse_pistol",
        name="Pulse Pistol",
        glyph="}",
        kind="weapon",
        description="One-shot capacitor gun. Ranged damage 6. Costs 3 focus.",
        ranged_damage=6,
        attack_bonus=1,
        equippable=True,
        extra={"focus_cost": 3},
    )


def random_loot(rng) -> Optional[Item]:
    roll = rng.random()
    if roll < 0.35:
        return make_stimpack()
    if roll < 0.55:
        return make_focus_tab()
    if roll < 0.70:
        return make_stun_baton()
    if roll < 0.82:
        return make_leather_jacket()
    if roll < 0.92:
        return make_datachip()
    return make_mono_knife()


def make_street_credits(amount: int = 5) -> Item:
    return Item(
        id="credits",
        name="Street Credits ×%d" % max(1, amount),
        glyph="$",
        kind="misc",
        description="Franchise scrip — spend later at black-market stalls.",
        extra={"credits": max(1, amount)},
    )


def make_pulse_shim() -> Item:
    return Item(
        id="pulse_shim",
        name="Pulse Shim",
        glyph="*",
        kind="weapon",
        description="One-shot street hack spike. +2 hack while equipped.",
        hack_bonus=2,
        equippable=True,
    )


def make_kevlar_vest() -> Item:
    return Item(
        id="kevlar_vest",
        name="Kevlar Vest",
        glyph="[",
        kind="armor",
        description="Cheap plates under a courier jacket. +2 defense.",
        defense_bonus=2,
        equippable=True,
    )
