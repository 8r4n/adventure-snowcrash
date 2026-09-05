"""Player feature wishes → inventory items + keyword prototype grants.

Original game systems only — no novel text.
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional

from .items import (
    Item,
    make_datachip,
    make_pulse_pistol,
    make_stimpack,
)

MAX_WISHES = 8

# Keyword groups → grant id (checked in order)
WISH_CATALOG = [
    (("speed", "haste", "fast", "sprint", "dash"), "haste"),
    (("map", "reveal", "fog", "radar", "explore"), "reveal"),
    (("shield", "armor", "invuln", "protect", "bubble"), "shield"),
    (("drone", "pet", "companion", "buddy", "familiar"), "companion"),
    (("flashlight", "torch", "night", "vision", "lantern", "light"), "flashlight"),
    (("gun", "pulse", "pistol", "weapon", "blaster"), "pulse"),
    (("heal", "med", "stim", "health", "hp", "cure"), "heal"),
]


def wish_hash(text: str) -> str:
    norm = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:10]


def short_title(text: str, limit: int = 28) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return "Untitled"
    if len(t) <= limit:
        return t
    return t[: limit - 1].rstrip() + "…"


def make_wish_item(text: str) -> Item:
    h = wish_hash(text)
    title = short_title(text)
    return Item(
        id=f"wish_{h}",
        name=f"Wish: {title}",
        glyph="★",
        kind="wish",
        description=(text.strip() + "\nUse to petition the street layer."),
        consumable=True,
        extra={"wish_text": text.strip(), "wish_hash": h},
    )


def match_wish_grant(text: str) -> Optional[str]:
    low = (text or "").lower()
    for keys, grant_id in WISH_CATALOG:
        if any(k in low for k in keys):
            return grant_id
    return None


def make_backlog_token(wish_text: str = "") -> Item:
    snippet = short_title(wish_text, 40) if wish_text else "anonymous petition"
    return make_datachip(
        name="Backlog Token",
        desc=(
            f"Logged to Metaverse backlog: {snippet}. "
            "A soft receipt from the street layer — +1 hack when jacked."
        ),
    )


def make_haste_tab() -> Item:
    return Item(
        id="proto_haste",
        name="Prototype Haste Tab",
        glyph="!",
        kind="med",
        description="Street-lab stim. Doubles move for a short burst when used.",
        focus_restore=4,
        consumable=True,
        extra={"grant": "haste", "haste_steps": 8},
    )


def make_fog_flare() -> Item:
    return Item(
        id="proto_reveal",
        name="Fog Flare Chip",
        glyph="*",
        kind="datachip",
        description="Burns fog in a radius when jacked. Hack +1.",
        hack_bonus=1,
        consumable=True,
        extra={"grant": "reveal", "reveal_radius": 14},
    )


def make_shield_patch() -> Item:
    return Item(
        id="proto_shield",
        name="Hardlight Shield Patch",
        glyph="[",
        kind="armor",
        description="Brief spawn-grade invulnerability when used.",
        defense_bonus=1,
        consumable=True,
        equippable=False,
        extra={"grant": "shield", "shield_sec": 10},
    )


def make_night_lens() -> Item:
    return Item(
        id="proto_night",
        name="Night Lens Filament",
        glyph="*",
        kind="misc",
        description="Bumps VIEW_RADIUS for a while after use.",
        consumable=True,
        extra={"grant": "flashlight", "view_bonus": 4, "view_ticks": 80},
    )


def make_companion_beacon() -> Item:
    return Item(
        id="proto_companion",
        name="Drone Pet Beacon",
        glyph="d",
        kind="misc",
        description="Cosmetic street companion flag for your avatar snapshot.",
        consumable=True,
        extra={"grant": "companion"},
    )


def prototype_for_grant(grant_id: str) -> Optional[Item]:
    if grant_id == "haste":
        return make_haste_tab()
    if grant_id == "reveal":
        return make_fog_flare()
    if grant_id == "shield":
        return make_shield_patch()
    if grant_id == "companion":
        return make_companion_beacon()
    if grant_id == "flashlight":
        return make_night_lens()
    if grant_id == "pulse":
        return make_pulse_pistol()
    if grant_id == "heal":
        return make_stimpack()
    return None


def grant_label(grant_id: str) -> str:
    return {
        "haste": "Prototype Haste Tab",
        "reveal": "Fog Flare Chip",
        "shield": "Hardlight Shield Patch",
        "companion": "Drone Pet Beacon",
        "flashlight": "Night Lens Filament",
        "pulse": "Pulse Pistol",
        "heal": "Street Stimpack",
    }.get(grant_id, "Backlog Token")
