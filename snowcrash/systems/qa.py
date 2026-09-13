"""QA automation instrumentation (#112).

Env-gated helpers for bot/CI playtests. Enable with ADVENTURE_QA=1 (or true/yes/on).
Off by default — public tunnels stay safe.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

QA_ENV_VAR = "ADVENTURE_QA"
_TRUTHY = ("1", "true", "yes", "on")
_EVENT_CAP = 200
_CROP = 9  # odd → player-centered map crop


def qa_enabled(environ: Optional[Dict[str, str]] = None) -> bool:
    env = environ if environ is not None else os.environ
    raw = str(env.get(QA_ENV_VAR, "") or "").strip().lower()
    return raw in _TRUTHY


def ensure_event_log(world: Any) -> List[Dict[str, Any]]:
    """Attach a ring-buffer event log on the world when QA is on."""
    log = getattr(world, "qa_events", None)
    if log is None:
        log = []
        world.qa_events = log
    return log


def record_event(world: Any, kind: str, agent: Any = None, **extra: Any) -> None:
    if not qa_enabled():
        return
    log = ensure_event_log(world)
    row: Dict[str, Any] = {
        "t": time.time(),
        "kind": kind,
        "tick": int(getattr(world, "tick", 0) or 0),
    }
    if agent is not None:
        row["player_id"] = getattr(agent, "id", None)
        row["name"] = getattr(agent, "name", None)
        actor = getattr(agent, "actor", None)
        if actor is not None:
            row["x"] = getattr(actor, "x", None)
            row["y"] = getattr(actor, "y", None)
            row["hp"] = getattr(actor, "hp", None)
    row.update(extra)
    log.append(row)
    if len(log) > _EVENT_CAP:
        del log[:-_EVENT_CAP]


def find_agent(world: Any, name: Optional[str] = None, player_id: Optional[str] = None) -> Any:
    if player_id:
        return world.players.get(player_id)
    if not name:
        return None
    needle = str(name).strip()
    for agent in world.players.values():
        if agent.name == needle:
            return agent
    # case-insensitive fallback
    low = needle.lower()
    for agent in world.players.values():
        if agent.name.lower() == low:
            return agent
    return None


def _panel_open(blob: Any) -> bool:
    if isinstance(blob, dict):
        return bool(blob.get("panel_open"))
    return False


def _docks_from_full(snap: Dict[str, Any]) -> Dict[str, Any]:
    mods = snap.get("mods") or {}
    mod_panels = []
    if isinstance(mods, dict):
        for p in mods.get("ui_panels") or mods.get("panels") or []:
            if isinstance(p, dict):
                mod_panels.append(
                    {
                        "id": p.get("id") or p.get("key"),
                        "label": p.get("dock_label") or p.get("label") or p.get("title"),
                    }
                )
    ice = snap.get("ice") or {}
    return {
        "globe": _panel_open(snap.get("globe")),
        "primer": _panel_open(snap.get("primer")),
        "sleeves": _panel_open(snap.get("sleeves")),
        "jaunte": _panel_open(snap.get("jaunte")),
        "empathy": _panel_open(snap.get("empathy")),
        "forecast": _panel_open(snap.get("forecast")),
        "ice_dock": bool(ice.get("panel_open") or ice.get("dock_open") or ice.get("probes")),
        "cyberspace": bool((snap.get("cyberspace") or {}).get("active")),
        "heist": bool((snap.get("ice_heist") or {}).get("active")),
        "mod_panels": mod_panels,
    }


def _map_crop(rows: List[str], px: int, py: int, size: int = _CROP) -> Dict[str, Any]:
    if not rows:
        return {"size": size, "rows": [], "origin": [0, 0]}
    h = len(rows)
    w = len(rows[0]) if h else 0
    half = size // 2
    y0 = max(0, py - half)
    x0 = max(0, px - half)
    y1 = min(h, y0 + size)
    x1 = min(w, x0 + size)
    # re-anchor if near edges so crop stays size×size when possible
    if y1 - y0 < size:
        y0 = max(0, y1 - size)
    if x1 - x0 < size:
        x0 = max(0, x1 - size)
    crop = []
    for y in range(y0, y1):
        row = rows[y]
        crop.append(row[x0:x1] if isinstance(row, str) else "".join(row[x0:x1]))
    glyph = None
    if 0 <= py < h and 0 <= px < w:
        r = rows[py]
        glyph = r[px] if isinstance(r, str) else (r[px] if px < len(r) else None)
    return {
        "size": size,
        "origin": [x0, y0],
        "rows": crop,
        "glyph_at_player": glyph,
        "width": w,
        "height": h,
    }


def _errors_from_messages(messages: List[Any]) -> List[str]:
    out: List[str] = []
    needles = ("error", "fail", "can't", "cannot", "denied", "rate limit", "invalid", "no ")
    for m in messages[-8:]:
        text = str(m)
        low = text.lower()
        if any(n in low for n in needles):
            out.append(text)
    return out[-6:]


def structured_snapshot(world: Any, agent: Any) -> Dict[str, Any]:
    """Lean snapshot for assertions — same underlying state as web client."""
    full = world.snapshot(agent)
    player = full.get("player") or {}
    px = int(player.get("x", 0) or 0)
    py = int(player.get("y", 0) or 0)
    messages = list(full.get("messages") or [])
    inv = [
        {
            "id": it.get("id"),
            "name": it.get("name"),
            "kind": it.get("kind"),
            "equipped": bool(it.get("equipped")),
        }
        for it in (full.get("inventory") or [])
        if isinstance(it, dict)
    ]
    events = list(getattr(world, "qa_events", []) or [])[-40:]
    return {
        "qa": True,
        "seed": full.get("seed", getattr(world, "seed", None)),
        "tick": full.get("tick", getattr(world, "tick", 0)),
        "you": full.get("you", getattr(agent, "id", None)),
        "mode": full.get("mode"),
        "won": bool(full.get("won")),
        "lost": bool(full.get("lost")),
        "online_count": full.get("online_count"),
        "player": {
            "id": player.get("id") or getattr(agent, "id", None),
            "name": player.get("name") or getattr(agent, "name", None),
            "x": px,
            "y": py,
            "z": player.get("z", 0),
            "plane": player.get("plane") or full.get("plane"),
            "hp": player.get("hp"),
            "max_hp": player.get("max_hp"),
            "focus": player.get("focus"),
            "max_focus": player.get("max_focus"),
            "facing": player.get("facing"),
            "facing_name": player.get("facing_name"),
            "has_payload": player.get("has_payload"),
            "alive": not bool(full.get("dead") or full.get("lost")),
        },
        "inventory": inv,
        "map_summary": _map_crop(list(full.get("map") or []), px, py),
        "docks": _docks_from_full(full),
        "objective": full.get("objective"),
        "messages": messages[-12:],
        "errors": _errors_from_messages(messages),
        "events": events,
        "district": (full.get("district") or {}).get("id")
        if isinstance(full.get("district"), dict)
        else full.get("district"),
        "jackpoint": full.get("jackpoint"),
        "uplink": full.get("uplink"),
    }


__all__ = [
    "QA_ENV_VAR",
    "qa_enabled",
    "ensure_event_log",
    "record_event",
    "find_agent",
    "structured_snapshot",
]
