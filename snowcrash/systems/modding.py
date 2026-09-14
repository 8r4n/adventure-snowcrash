"""Modder / plugin framework (#72) — data-driven JSON mods, fail-closed.

Loads manifests from ``mods/`` and ``examples/plugins/`` and registers
JSON-defined items, street events, journal beats, StreetNet broadcasts,
ICE probes / light cyberspace nodes, globe pins, CSP-friendly UI panels,
StreetNet slash commands, capability flags, and a fail-closed FS/network sandbox.
No arbitrary Python/WASM/mod-JS exec.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from ..items import Item

log = logging.getLogger("snowcrash.modding")

# Public plugin API semver — bump minor for additive hooks, major for breaks.
PLUGIN_API_VERSION = "1.4.0"

MANIFEST_NAMES = ("mod.json", "manifest.json")

# Capabilities a mod may request. Anything else is rejected (fail closed).
KNOWN_PERMISSIONS: Set[str] = {
    "items",
    "street_events",
    "journal",
    "ice_nodes",
    "globe_regions",
    "streetnet",
    "ui_panel",
}

# Implemented in this slice — others may appear in manifests but are ignored
# with a clear warning until a later phase hooks them.
IMPLEMENTED_PERMISSIONS: Set[str] = {
    "items",
    "street_events",
    "journal",
    "streetnet",
    "ice_nodes",
    "globe_regions",
    "ui_panel",
}

# Dangerous / never granted in v1 without explicit future design.
DENIED_PERMISSIONS: Set[str] = {
    "fs_read",
    "fs_write",
    "network",
    "exec",
    "python",
    "wasm",
    "host",
}

_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}(\.[a-z0-9_]{1,63}){0,4}$")
_CORE_ITEM_IDS: Set[str] = {
    "stimpack",
    "focus_tab",
    "mono_knife",
    "stun_baton",
    "leather_jacket",
    "datachip",
    "payload_zero",
    "pulse_pistol",
    "pulse_shim",
    "kevlar_vest",
    "streetnet_primer",
    "baron_core",
}

_ITEM_KINDS = {"misc", "med", "weapon", "armor", "datachip", "quest", "trinket"}
_EVENT_KINDS = {"broadcast", "job", "street", "ambush", "mod"}
_JOURNAL_TRIGGERS = {"join", "payload", "manual", "always"}
_PROBE_EFFECTS = {"stun", "reveal", "scramble"}
_NODE_TYPES = {"maze", "ice_gate", "custom"}
_REGION_KINDS = {"city", "continent", "poi", "pin", "mod_pin", "region", "hub"}
_UI_BODY_FORMATS = {"text", "markdown", "md"}
# Buttons may only fire these existing game actions (no arbitrary / host commands).
_ALLOWED_UI_ACTIONS: Set[str] = {
    "mods", "mod_list", "plugins", "list_mods",
    "mod_item", "grant_mod_item", "mod_grant",
    "mod_reload", "reload_mods",
    "globe", "open_globe", "globe_open", "close_globe", "globe_close",
    "globe_zoom", "globe_recall", "teleport", "tp",
    "sleeves", "sleeve", "sleeve_list", "sleeve_hop", "sleeve_rent",
    "primer", "jaunte", "empathy", "forecast", "ecology",
    "ice_probe", "ice", "jack_in", "jack_out",
    "journal", "look", "help", "status", "inventory", "inv",
    "shop", "party", "crew", "contracts", "craft", "stash",
    "season", "raid", "contest_patrol",
}
_UI_ACTION_RE = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
_UI_ARG_RE = re.compile(r"^[A-Za-z0-9_./:-]{0,64}$")
_UI_DOCK_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _./+-]{0,23}$")
# StreetNet slash verbs mods must not steal (core IRC + common game verbs).
_RESERVED_STREETNET_SLASHES: Set[str] = {
    "help", "irc", "join", "part", "nick", "name", "me", "action",
    "msg", "privmsg", "query", "say", "wish", "feature", "list", "topic", "names",
    "mods", "mod_item", "mod_reload", "reload", "qa",
}
_SLASH_RE = re.compile(r"^[a-z][a-z0-9_]{1,23}$")


def _parse_semver(v: str) -> Optional[Tuple[int, int, int]]:
    if not isinstance(v, str):
        return None
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$", v.strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def api_incompatibility_reason(
    required: str, provided: str = PLUGIN_API_VERSION
) -> Optional[str]:
    """None if compatible; otherwise a fail-closed reason string."""
    req = _parse_semver(required)
    got = _parse_semver(provided)
    if req is None:
        return "unparseable api_version %r (need X.Y.Z) — fail closed" % (required,)
    if got is None:
        return "host api_version %r unparseable — fail closed" % (provided,)
    if req[0] != got[0]:
        return "api_version %s major != host %s (major mismatch) — fail closed" % (
            required,
            provided,
        )
    if req > got:
        return "api_version %s requires newer host (host %s) — fail closed" % (
            required,
            provided,
        )
    return None


def api_compatible(required: str, provided: str = PLUGIN_API_VERSION) -> bool:
    """True if *required* major matches and minor/patch <= *provided* (same major)."""
    return api_incompatibility_reason(required, provided) is None


def permission_status(perm: str) -> str:
    """Classify a permission name: implemented | denied | known | unknown."""
    p = (perm or "").strip().lower()
    if not p:
        return "unknown"
    if p in DENIED_PERMISSIONS:
        return "denied"
    if p in IMPLEMENTED_PERMISSIONS:
        return "implemented"
    if p in KNOWN_PERMISSIONS:
        return "known"
    return "unknown"


def host_capability_flags() -> Dict[str, Any]:
    """Version negotiation / capability flags for clients and mod authors (API 1.4).

    Safe-by-default: FS/network/exec are always ``denied``. Implemented data
    hooks are ``implemented``. Snapshot exposes this so Godot/web can negotiate
    UI without guessing the host contract.
    """
    perm_flags: Dict[str, str] = {}
    for p in sorted(IMPLEMENTED_PERMISSIONS):
        perm_flags[p] = "implemented"
    for p in sorted(DENIED_PERMISSIONS):
        perm_flags[p] = "denied"
    for p in sorted(KNOWN_PERMISSIONS - IMPLEMENTED_PERMISSIONS - DENIED_PERMISSIONS):
        perm_flags.setdefault(p, "known")
    return {
        "api_version": PLUGIN_API_VERSION,
        "permissions": perm_flags,
        "sandbox": {
            "code_execution": "denied",
            "fs": "mod_dir_jail",
            "network": "denied",
            "symlinks": "denied",
            "partial_apply": False,
            "unsigned_auto_download": False,
        },
        "clients": {
            "web_ui_panel": True,
            "godot_ui_panel": True,
        },
    }


def mod_has_permission(mod: "LoadedMod", perm: str) -> bool:
    """True if the loaded mod was granted *perm* (manifest allowlist)."""
    return perm in (getattr(mod, "permissions", None) or [])


def _repo_root() -> Path:
    # snowcrash/systems/modding.py → repo root
    return Path(__file__).resolve().parents[2]


def default_search_roots() -> List[Path]:
    """Ordered discovery roots. Disabled entirely when SNOWCRASH_DISABLE_MODS=1."""
    if os.environ.get("SNOWCRASH_DISABLE_MODS", "").strip().lower() in ("1", "true", "yes"):
        return []
    roots: List[Path] = []
    extra = os.environ.get("SNOWCRASH_MODS_PATH", "").strip()
    if extra:
        for part in extra.split(os.pathsep):
            part = part.strip()
            if part:
                roots.append(Path(part).expanduser().resolve())
    root = _repo_root()
    mods = root / "mods"
    examples = root / "examples" / "plugins"
    # Always prefer local user mods first.
    if mods.is_dir():
        roots.append(mods.resolve())
    # First-party examples (JSON only) — skip if SNOWCRASH_EXAMPLE_PLUGINS=0.
    ex_flag = os.environ.get("SNOWCRASH_EXAMPLE_PLUGINS", "1").strip().lower()
    if ex_flag not in ("0", "false", "no") and examples.is_dir():
        roots.append(examples.resolve())
    # Dedup preserve order
    seen: Set[Path] = set()
    out: List[Path] = []
    for r in roots:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


_ENTRY_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def _safe_child(base: Path, rel: str) -> Optional[Path]:
    """Resolve *rel* under *base*; reject absolute / traversal / URLs / symlinks.

    FS/network sandbox: entry paths are relative files inside the mod directory
    only. Schemes (``http:``, ``file:``, …), ``..``, absolutes, and symlinks
    are fail-closed — mods never get host FS or network via the loader.
    """
    if not rel or not isinstance(rel, str):
        return None
    rel = rel.strip()
    if not rel:
        return None
    # Network / URL / scheme — never allow (fs/network sandbox).
    if _ENTRY_SCHEME_RE.match(rel) or "://" in rel or rel.startswith("//"):
        return None
    if "\\" in rel or chr(0) in rel:
        return None
    if os.path.isabs(rel) or ".." in Path(rel).parts:
        return None
    try:
        base_r = base.resolve()
        # Walk components; reject symlinks at any step (no host FS via link).
        cur = base_r
        for part in Path(rel).parts:
            if part in ("", ".", ".."):
                return None
            nxt = cur / part
            if nxt.is_symlink():
                return None
            cur = nxt
        target = (base / rel).resolve()
    except OSError:
        return None
    try:
        target.relative_to(base_r)
    except ValueError:
        return None
    # Final path must not be a symlink (even if it points inside the jail).
    if target.exists() and target.is_symlink():
        return None
    return target


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


@dataclass
class ModLoadError:
    mod_id: str
    path: str
    message: str


@dataclass
class LoadedMod:
    id: str
    name: str
    version: str
    api_version: str
    description: str
    author: str
    license: str
    attribution: str
    permissions: List[str]
    root: Path
    items: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    street_events: List[Dict[str, Any]] = field(default_factory=list)
    journal_arcs: List[Dict[str, Any]] = field(default_factory=list)
    journal_beats: List[Dict[str, Any]] = field(default_factory=list)
    streetnet_broadcasts: List[Dict[str, Any]] = field(default_factory=list)
    streetnet_commands: List[Dict[str, Any]] = field(default_factory=list)
    ice_probes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    cyber_nodes: List[Dict[str, Any]] = field(default_factory=list)
    globe_pins: List[Dict[str, Any]] = field(default_factory=list)
    globe_regions: List[Dict[str, Any]] = field(default_factory=list)
    ui_panels: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def summary(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "api_version": self.api_version,
            "author": self.author,
            "license": self.license,
            "attribution": self.attribution,
            "permissions": list(self.permissions),
            "items": sorted(self.items.keys()),
            "street_events": [e.get("id") for e in self.street_events],
            "journal_arcs": [a.get("id") for a in self.journal_arcs],
            "journal_beats": [b.get("id") for b in self.journal_beats],
            "streetnet_broadcasts": [b.get("id") for b in self.streetnet_broadcasts],
            "streetnet_commands": [c.get("slash") for c in self.streetnet_commands],
            "ice_probes": sorted(self.ice_probes.keys()),
            "cyber_nodes": [n.get("id") for n in self.cyber_nodes],
            "globe_pins": [p.get("id") for p in self.globe_pins],
            "globe_regions": [r.get("id") for r in self.globe_regions],
            "ui_panels": [p.get("id") for p in self.ui_panels],
            "warnings": list(self.warnings),
            "path": str(self.root),
        }


@dataclass
class ModRegistry:
    api_version: str = PLUGIN_API_VERSION
    mods: Dict[str, LoadedMod] = field(default_factory=dict)
    items: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # item_id -> def
    item_owners: Dict[str, str] = field(default_factory=dict)  # item_id -> mod_id
    street_events: List[Dict[str, Any]] = field(default_factory=list)
    journal_arcs: List[Dict[str, Any]] = field(default_factory=list)
    journal_beats: List[Dict[str, Any]] = field(default_factory=list)
    streetnet_broadcasts: List[Dict[str, Any]] = field(default_factory=list)
    streetnet_commands: List[Dict[str, Any]] = field(default_factory=list)
    ice_probes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    cyber_nodes: List[Dict[str, Any]] = field(default_factory=list)
    globe_pins: List[Dict[str, Any]] = field(default_factory=list)
    globe_regions: List[Dict[str, Any]] = field(default_factory=list)
    ui_panels: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[ModLoadError] = field(default_factory=list)
    skipped: List[Dict[str, str]] = field(default_factory=list)

    def clear(self) -> None:
        self.mods.clear()
        self.items.clear()
        self.item_owners.clear()
        self.street_events.clear()
        self.journal_arcs.clear()
        self.journal_beats.clear()
        self.streetnet_broadcasts.clear()
        self.streetnet_commands.clear()
        self.ice_probes.clear()
        self.cyber_nodes.clear()
        self.globe_pins.clear()
        self.globe_regions.clear()
        self.ui_panels.clear()
        self.errors.clear()
        self.skipped.clear()

    def snapshot(self) -> Dict[str, Any]:
        return {
            "api_version": self.api_version,
            "enabled": True,
            "mod_count": len(self.mods),
            "item_count": len(self.items),
            "street_event_count": len(self.street_events),
            "journal_arc_count": len(self.journal_arcs),
            "journal_beat_count": len(self.journal_beats),
            "streetnet_count": len(self.streetnet_broadcasts),
            "streetnet_command_count": len(self.streetnet_commands),
            "ice_probe_count": len(self.ice_probes),
            "cyber_node_count": len(self.cyber_nodes),
            "globe_pin_count": len(self.globe_pins),
            "globe_region_count": len(self.globe_regions),
            "ui_panel_count": len(self.ui_panels),
            "panels": [dict(p) for p in self.ui_panels],
            "streetnet_commands": [
                {"slash": c.get("slash"), "help": c.get("help"), "id": c.get("id")}
                for c in self.streetnet_commands
            ],
            "mods": [m.summary() for m in self.mods.values()],
            "errors": [
                {"mod_id": e.mod_id, "path": e.path, "message": e.message}
                for e in self.errors
            ],
            "skipped": list(self.skipped),
            "implemented_permissions": sorted(IMPLEMENTED_PERMISSIONS),
            "denied_permissions": sorted(DENIED_PERMISSIONS),
            "capabilities": host_capability_flags(),
        }


def item_from_def(defn: Dict[str, Any]) -> Item:
    """Build an Item from a validated mod item dict (copy-safe)."""
    extra = dict(defn.get("extra") or {})
    extra.setdefault("mod_id", defn.get("mod_id"))
    return Item(
        id=str(defn["id"]),
        name=str(defn.get("name") or defn["id"]),
        glyph=str(defn.get("glyph") or "*")[:2] or "*",
        kind=str(defn.get("kind") or "misc"),
        description=str(defn.get("description") or ""),
        heal=int(defn.get("heal") or 0),
        focus_restore=int(defn.get("focus_restore") or 0),
        attack_bonus=int(defn.get("attack_bonus") or 0),
        defense_bonus=int(defn.get("defense_bonus") or 0),
        hack_bonus=int(defn.get("hack_bonus") or 0),
        ranged_damage=int(defn.get("ranged_damage") or 0),
        consumable=bool(defn.get("consumable") or False),
        quest=bool(defn.get("quest") or False),
        equippable=bool(defn.get("equippable") or False),
        equipped=False,
        extra=extra,
    )


def _validate_item_def(raw: Any, mod_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not isinstance(raw, dict):
        return None, "item entry must be an object"
    iid = raw.get("id")
    if not isinstance(iid, str) or not _ID_RE.match(iid):
        return None, "invalid item id (use lowercase namespaced ids like hello_courier.badge)"
    if iid in _CORE_ITEM_IDS:
        return None, "item id conflicts with core item %r" % iid
    kind = str(raw.get("kind") or "misc")
    if kind not in _ITEM_KINDS:
        return None, "invalid item kind %r" % kind
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        return None, "item needs a non-empty name"
    # Clamp numeric fields
    out = {
        "id": iid,
        "name": name.strip()[:64],
        "glyph": str(raw.get("glyph") or "*")[:2],
        "kind": kind,
        "description": str(raw.get("description") or "")[:400],
        "heal": max(0, min(100, int(raw.get("heal") or 0))),
        "focus_restore": max(0, min(100, int(raw.get("focus_restore") or 0))),
        "attack_bonus": max(0, min(20, int(raw.get("attack_bonus") or 0))),
        "defense_bonus": max(0, min(20, int(raw.get("defense_bonus") or 0))),
        "hack_bonus": max(0, min(20, int(raw.get("hack_bonus") or 0))),
        "ranged_damage": max(0, min(50, int(raw.get("ranged_damage") or 0))),
        "consumable": bool(raw.get("consumable") or False),
        "quest": bool(raw.get("quest") or False),
        "equippable": bool(raw.get("equippable") or False),
        "extra": raw.get("extra") if isinstance(raw.get("extra"), dict) else {},
        "mod_id": mod_id,
    }
    return out, None


def _validate_event_def(raw: Any, mod_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not isinstance(raw, dict):
        return None, "street event must be an object"
    eid = raw.get("id")
    if not isinstance(eid, str) or not _ID_RE.match(eid):
        return None, "invalid street event id"
    kind = str(raw.get("kind") or "broadcast")
    if kind not in _EVENT_KINDS:
        return None, "invalid street event kind %r" % kind
    messages = raw.get("messages") or raw.get("text")
    if isinstance(messages, str):
        messages = [messages]
    if not isinstance(messages, list) or not messages:
        return None, "street event needs messages[]"
    clean_msgs = [str(m).strip()[:240] for m in messages if str(m).strip()]
    if not clean_msgs:
        return None, "street event messages empty after sanitize"
    weight = float(raw.get("weight") or 1.0)
    if weight <= 0 or weight > 100:
        return None, "street event weight out of range"
    return {
        "id": eid,
        "kind": kind,
        "messages": clean_msgs,
        "player_log": str(raw.get("player_log") or "")[:240] or None,
        "weight": weight,
        "mod_id": mod_id,
    }, None


def _validate_journal_arc(raw: Any, mod_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not isinstance(raw, dict):
        return None, "journal arc must be an object"
    aid = raw.get("id")
    if not isinstance(aid, str) or not _ID_RE.match(aid):
        return None, "invalid journal arc id"
    steps_raw = raw.get("steps") or []
    if not isinstance(steps_raw, list) or not steps_raw:
        return None, "journal arc needs steps[]"
    steps: List[Dict[str, Any]] = []
    for s in steps_raw:
        if not isinstance(s, dict):
            return None, "journal step must be an object"
        sid = s.get("id")
        if not isinstance(sid, str) or not sid.strip():
            return None, "journal step needs id"
        text = s.get("text") or s.get("summary")
        if not isinstance(text, str) or not text.strip():
            return None, "journal step needs text"
        steps.append({
            "id": sid.strip()[:64],
            "text": text.strip()[:240],
            "hint": str(s.get("hint") or "")[:160] or None,
        })
    return {
        "id": aid,
        "title": str(raw.get("title") or aid)[:80],
        "auto_offer": bool(raw.get("auto_offer", True)),
        "steps": steps,
        "mod_id": mod_id,
    }, None


def _validate_journal_beat(raw: Any, mod_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not isinstance(raw, dict):
        return None, "journal beat must be an object"
    bid = raw.get("id")
    if not isinstance(bid, str) or not _ID_RE.match(bid):
        return None, "invalid journal beat id"
    text = raw.get("text") or raw.get("summary")
    if not isinstance(text, str) or not text.strip():
        return None, "journal beat needs text"
    trigger = str(raw.get("trigger") or "join").strip().lower()
    if trigger not in _JOURNAL_TRIGGERS:
        return None, "invalid journal beat trigger %r" % trigger
    return {
        "id": bid,
        "text": text.strip()[:240],
        "trigger": trigger,
        "headline": str(raw.get("headline") or "")[:80] or None,
        "mod_id": mod_id,
    }, None


def _validate_streetnet_broadcast(raw: Any, mod_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not isinstance(raw, dict):
        return None, "streetnet broadcast must be an object"
    bid = raw.get("id")
    if not isinstance(bid, str) or not _ID_RE.match(bid):
        return None, "invalid streetnet broadcast id"
    messages = raw.get("messages") or raw.get("text")
    if isinstance(messages, str):
        messages = [messages]
    if not isinstance(messages, list) or not messages:
        return None, "streetnet broadcast needs messages[]"
    clean_msgs = [str(m).strip()[:240] for m in messages if str(m).strip()]
    if not clean_msgs:
        return None, "streetnet messages empty after sanitize"
    weight = float(raw.get("weight") or 1.0)
    if weight <= 0 or weight > 100:
        return None, "streetnet weight out of range"
    return {
        "id": bid,
        "channel": str(raw.get("channel") or "streetnet")[:32],
        "messages": clean_msgs,
        "player_log": str(raw.get("player_log") or "")[:240] or None,
        "weight": weight,
        "fire_on_load": bool(raw.get("fire_on_load") or False),
        "mod_id": mod_id,
    }, None


def _validate_streetnet_command(raw: Any, mod_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Player-typed StreetNet slash command — canned replies + optional allowlisted action."""
    if not isinstance(raw, dict):
        return None, "streetnet command must be an object"
    cid = raw.get("id")
    if not isinstance(cid, str) or not _ID_RE.match(cid):
        return None, "invalid streetnet command id"
    slash = raw.get("slash") or raw.get("cmd") or raw.get("command")
    if not isinstance(slash, str):
        return None, "streetnet command needs slash"
    slash = slash.strip().lower().lstrip("/")
    if not _SLASH_RE.match(slash):
        return None, "invalid streetnet slash %r" % slash
    if slash in _RESERVED_STREETNET_SLASHES:
        return None, "streetnet slash %r is reserved — fail closed" % slash
    replies = raw.get("replies") or raw.get("messages") or raw.get("text")
    if isinstance(replies, str):
        replies = [replies]
    if not isinstance(replies, list) or not replies:
        return None, "streetnet command needs replies[]"
    clean = [str(m).strip()[:240] for m in replies if str(m).strip()]
    if not clean:
        return None, "streetnet command replies empty after sanitize"
    action = raw.get("action")
    arg_s = None
    if action is None or action == "":
        action = None
    else:
        if not isinstance(action, str) or not _UI_ACTION_RE.match(action.strip().lower()):
            return None, "invalid streetnet command action"
        action = action.strip().lower()
        if action not in _ALLOWED_UI_ACTIONS:
            return None, "streetnet command action %r not allowlisted" % action
        arg = raw.get("arg")
        if arg is None or arg == "":
            arg_s = None
        else:
            if not isinstance(arg, (str, int, float)):
                return None, "streetnet command arg must be string/number"
            arg_s = str(arg).strip()
            if not _UI_ARG_RE.match(arg_s):
                return None, "streetnet command arg failed sanitize"
            arg_s = arg_s[:64]
    return {
        "id": cid,
        "slash": slash,
        "help": str(raw.get("help") or "")[:120] or None,
        "replies": clean,
        "player_log": str(raw.get("player_log") or "")[:240] or None,
        "action": action,
        "arg": arg_s,
        "broadcast": bool(raw.get("broadcast") or False),
        "mod_id": mod_id,
    }, None


def _validate_ice_probe(raw: Any, mod_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not isinstance(raw, dict):
        return None, "ice probe must be an object"
    pid = raw.get("id")
    if not isinstance(pid, str) or not _ID_RE.match(pid):
        return None, "invalid ice probe id"
    # Core probes are reserved short names
    if pid in ("stun", "reveal", "scramble"):
        return None, "ice probe id conflicts with core probe %r" % pid
    effect = str(raw.get("effect") or raw.get("kind") or "reveal").strip().lower()
    if effect not in _PROBE_EFFECTS:
        return None, "invalid ice probe effect %r" % effect
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        return None, "ice probe needs a non-empty name"
    return {
        "id": pid,
        "name": name.strip()[:64],
        "desc": str(raw.get("desc") or raw.get("description") or "")[:200],
        "focus_cost": max(1, min(20, int(raw.get("focus_cost") or 3))),
        "cooldown": max(1.0, min(120.0, float(raw.get("cooldown") or 10.0))),
        "radius": max(1, min(24, int(raw.get("radius") or 8))),
        "duration": max(0.5, min(60.0, float(raw.get("duration") or 6.0))),
        "effect": effect,
        "mod_id": mod_id,
    }, None


def _validate_cyber_node(raw: Any, mod_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not isinstance(raw, dict):
        return None, "cyber node must be an object"
    nid = raw.get("id")
    if not isinstance(nid, str) or not _ID_RE.match(nid):
        return None, "invalid cyber node id"
    node_type = str(raw.get("node_type") or raw.get("type") or "maze").strip().lower()
    if node_type not in _NODE_TYPES:
        return None, "invalid cyber node_type %r" % node_type
    weight = float(raw.get("weight") or 1.0)
    if weight <= 0 or weight > 100:
        return None, "cyber node weight out of range"
    grid = raw.get("grid")
    clean_grid: Optional[List[str]] = None
    if grid is not None:
        if not isinstance(grid, list) or not grid:
            return None, "cyber node grid must be a non-empty string list"
        if len(grid) > 24:
            return None, "cyber node grid too tall (max 24)"
        rows = []
        width = None
        for row in grid:
            if not isinstance(row, str) or not row:
                return None, "cyber node grid rows must be non-empty strings"
            if len(row) > 24:
                return None, "cyber node grid too wide (max 24)"
            if width is None:
                width = len(row)
            elif len(row) != width:
                return None, "cyber node grid rows must be equal width"
            # Only allow known glyphs
            for ch in row:
                if ch not in "#.@I*%X":
                    return None, "cyber node grid has invalid glyph %r" % ch
            rows.append(row)
        if "@" not in "".join(rows):
            return None, "cyber node grid needs an @ start"
        if "X" not in "".join(rows):
            return None, "cyber node grid needs an X exit"
        clean_grid = rows
        node_type = "custom"
    return {
        "id": nid,
        "node_type": node_type,
        "weight": weight,
        "hint": str(raw.get("hint") or "")[:200] or None,
        "grid": clean_grid,
        "mod_id": mod_id,
    }, None


def _validate_globe_pin(raw: Any, mod_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not isinstance(raw, dict):
        return None, "globe pin must be an object"
    pid = raw.get("id")
    if not isinstance(pid, str) or not _ID_RE.match(pid):
        return None, "invalid globe pin id"
    try:
        lat = float(raw.get("lat"))
        lon = float(raw.get("lon"))
    except (TypeError, ValueError):
        return None, "globe pin needs numeric lat/lon"
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None, "globe pin lat/lon out of range"
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        return None, "globe pin needs a non-empty name"
    return {
        "id": pid,
        "name": name.strip()[:80],
        "lat": lat,
        "lon": lon,
        "label": str(raw.get("label") or "")[:120],
        "region_id": str(raw.get("region_id") or "")[:64] or None,
        "kind": str(raw.get("kind") or "mod_pin")[:32],
        "mod_id": mod_id,
    }, None


def _validate_globe_region(raw: Any, mod_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not isinstance(raw, dict):
        return None, "globe region must be an object"
    rid = raw.get("id")
    if not isinstance(rid, str) or not _ID_RE.match(rid):
        return None, "invalid globe region id"
    # Protect home / core continent ids from overwrite by requiring namespaced ids
    # (already enforced by _ID_RE needing lowercase; still block known cores without dots)
    if "." not in rid and rid in {
        "fractured_la", "cont_na", "cont_sa", "cont_eu", "cont_af", "cont_me",
        "cont_ca", "cont_as", "cont_oc", "cont_an",
    }:
        return None, "globe region id conflicts with core region %r" % rid
    try:
        lat = float(raw.get("lat"))
        lon = float(raw.get("lon"))
    except (TypeError, ValueError):
        return None, "globe region needs numeric lat/lon"
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None, "globe region lat/lon out of range"
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        return None, "globe region needs a non-empty name"
    kind = str(raw.get("kind") or "poi").strip().lower()
    if kind not in _REGION_KINDS:
        return None, "invalid globe region kind %r" % kind
    metadata_only = bool(raw.get("metadata_only", True))
    shard_seed = raw.get("shard_seed", None)
    if shard_seed is not None and not metadata_only:
        try:
            shard_seed = int(shard_seed)
        except (TypeError, ValueError):
            return None, "globe region shard_seed must be int or null"
    else:
        # Metadata overlays never become teleportable shards in this slice
        shard_seed = None
        metadata_only = True
    return {
        "id": rid,
        "name": name.strip()[:80],
        "kind": kind,
        "continent": str(raw.get("continent") or "na")[:8],
        "lat": lat,
        "lon": lon,
        "label": str(raw.get("label") or "")[:120],
        "home": False,
        "shard_seed": shard_seed,
        "metadata_only": metadata_only,
        "mod_id": mod_id,
    }, None


def _validate_ui_panel(raw: Any, mod_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """CSP-friendly dock panel — title + text/markdown body + allowlisted actions only."""
    if not isinstance(raw, dict):
        return None, "ui panel must be an object"
    pid = raw.get("id")
    if not isinstance(pid, str) or not _ID_RE.match(pid):
        return None, "invalid ui panel id"
    title = raw.get("title") or raw.get("name")
    if not isinstance(title, str) or not title.strip():
        return None, "ui panel needs a non-empty title"
    body = raw.get("body") or raw.get("text") or raw.get("markdown") or ""
    if not isinstance(body, str):
        return None, "ui panel body must be a string"
    body = body.strip()
    if not body:
        return None, "ui panel needs a non-empty body"
    if len(body) > 4000:
        return None, "ui panel body too long (max 4000)"
    fmt = str(raw.get("body_format") or raw.get("format") or "markdown").strip().lower()
    if fmt not in _UI_BODY_FORMATS:
        return None, "invalid ui panel body_format %r" % fmt
    if fmt == "md":
        fmt = "markdown"
    dock = raw.get("dock_label") or raw.get("dock") or raw.get("label")
    if dock is None or dock == "":
        dock = title.strip()[:12]
    else:
        if not isinstance(dock, str) or not _UI_DOCK_RE.match(dock.strip()):
            return None, "invalid ui panel dock_label"
        dock = dock.strip()[:24]
    actions_raw = raw.get("actions") or raw.get("buttons") or []
    if actions_raw is None:
        actions_raw = []
    if not isinstance(actions_raw, list):
        return None, "ui panel actions must be a list"
    if len(actions_raw) > 8:
        return None, "ui panel actions max 8"
    actions: List[Dict[str, Any]] = []
    for a in actions_raw:
        if not isinstance(a, dict):
            return None, "ui panel action must be an object"
        label = a.get("label") or a.get("name") or a.get("text")
        if not isinstance(label, str) or not label.strip():
            return None, "ui panel action needs label"
        action = a.get("action") or a.get("cmd") or a.get("command")
        if not isinstance(action, str) or not _UI_ACTION_RE.match(action.strip().lower()):
            return None, "invalid ui panel action name"
        action = action.strip().lower()
        if action not in _ALLOWED_UI_ACTIONS:
            return None, "ui panel action %r not allowlisted (existing game actions only)" % action
        arg = a.get("arg")
        if arg is None or arg == "":
            arg_s = None
        else:
            if not isinstance(arg, (str, int, float)):
                return None, "ui panel action arg must be string/number"
            arg_s = str(arg).strip()
            if not _UI_ARG_RE.match(arg_s):
                return None, "ui panel action arg failed sanitize"
            arg_s = arg_s[:64]
        actions.append({
            "label": label.strip()[:40],
            "action": action,
            "arg": arg_s,
        })
    return {
        "id": pid,
        "title": title.strip()[:80],
        "dock_label": dock,
        "body": body,
        "body_format": fmt,
        "actions": actions,
        "mod_id": mod_id,
    }, None


def _load_manifest(mod_dir: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[Path]]:
    for name in MANIFEST_NAMES:
        path = mod_dir / name
        if path.is_file():
            try:
                data = _read_json(path)
            except (OSError, json.JSONDecodeError) as exc:
                return None, "manifest read error: %s" % exc, path
            if not isinstance(data, dict):
                return None, "manifest must be a JSON object", path
            return data, None, path
    return None, "no mod.json / manifest.json", None


def discover_mod_dirs(roots: Optional[Sequence[Path]] = None) -> List[Path]:
    roots = list(roots) if roots is not None else default_search_roots()
    found: List[Path] = []
    seen: Set[Path] = set()
    for root in roots:
        if not root.is_dir():
            continue
        try:
            children = sorted(root.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            continue
        for child in children:
            if not child.is_dir() or child.name.startswith("."):
                continue
            # Skip empty placeholder dirs
            if any((child / n).is_file() for n in MANIFEST_NAMES):
                resolved = child.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    found.append(resolved)
    return found


def load_mod(mod_dir: Path, registry: ModRegistry) -> Optional[LoadedMod]:
    """Load one mod directory into *registry*. Fail closed on any hard error."""
    manifest, err, man_path = _load_manifest(mod_dir)
    path_s = str(mod_dir)
    if err or not manifest:
        registry.errors.append(ModLoadError("?", path_s, err or "missing manifest"))
        log.warning("mod skip %s: %s", path_s, err)
        return None

    mid = manifest.get("id")
    if not isinstance(mid, str) or not _ID_RE.match(mid):
        registry.errors.append(
            ModLoadError("?", path_s, "manifest.id invalid (lowercase / namespaced)")
        )
        return None
    if mid in registry.mods:
        registry.errors.append(ModLoadError(mid, path_s, "duplicate mod id"))
        return None

    api_req = str(manifest.get("api_version") or manifest.get("api") or "")
    incompat = api_incompatibility_reason(api_req, registry.api_version)
    if incompat:
        registry.errors.append(ModLoadError(mid, path_s, incompat))
        registry.skipped.append({"id": mid, "reason": incompat})
        log.warning("mod %s: %s", mid, incompat)
        return None

    raw_perms = manifest.get("permissions") or []
    if not isinstance(raw_perms, list):
        registry.errors.append(ModLoadError(mid, path_s, "permissions must be a list"))
        return None
    perms: List[str] = []
    for p in raw_perms:
        if not isinstance(p, str):
            registry.errors.append(ModLoadError(mid, path_s, "permission entries must be strings"))
            return None
        p = p.strip().lower()
        if p in DENIED_PERMISSIONS:
            msg = "denied permission %r — fail closed" % p
            registry.errors.append(ModLoadError(mid, path_s, msg))
            registry.skipped.append({"id": mid, "reason": msg})
            return None
        if p not in KNOWN_PERMISSIONS:
            msg = "unknown permission %r — fail closed" % p
            registry.errors.append(ModLoadError(mid, path_s, msg))
            registry.skipped.append({"id": mid, "reason": msg})
            return None
        perms.append(p)

    entry = manifest.get("entry") or manifest.get("files") or {}
    if entry is None:
        entry = {}
    if not isinstance(entry, dict):
        registry.errors.append(ModLoadError(mid, path_s, "entry must be an object"))
        return None

    loaded = LoadedMod(
        id=mid,
        name=str(manifest.get("name") or mid)[:80],
        version=str(manifest.get("version") or "0.0.0")[:32],
        api_version=api_req,
        description=str(manifest.get("description") or "")[:400],
        author=str(manifest.get("author") or "unknown")[:80],
        license=str(manifest.get("license") or "UNLICENSED")[:64],
        attribution=str(manifest.get("attribution") or "")[:400],
        permissions=perms,
        root=mod_dir,
    )

    # --- items ---
    if "items" in perms:
        items_rel = entry.get("items") or "items.json"
        items_path = _safe_child(mod_dir, str(items_rel))
        if items_path is None or not items_path.is_file():
            registry.errors.append(
                ModLoadError(mid, path_s, "items permission set but items file missing/unsafe")
            )
            return None
        try:
            items_doc = _read_json(items_path)
        except (OSError, json.JSONDecodeError) as exc:
            registry.errors.append(ModLoadError(mid, path_s, "items JSON error: %s" % exc))
            return None
        raw_items = items_doc.get("items") if isinstance(items_doc, dict) else items_doc
        if not isinstance(raw_items, list):
            registry.errors.append(ModLoadError(mid, path_s, "items.json must list items[]"))
            return None
        for raw in raw_items:
            idef, ierr = _validate_item_def(raw, mid)
            if ierr or not idef:
                registry.errors.append(ModLoadError(mid, path_s, "bad item: %s" % ierr))
                return None
            iid = idef["id"]
            if iid in registry.items or iid in loaded.items:
                registry.errors.append(
                    ModLoadError(mid, path_s, "item id collision %r" % iid)
                )
                return None
            loaded.items[iid] = idef
    elif entry.get("items"):
        loaded.warnings.append("items file present but permission 'items' not granted — ignored")

    # --- street events ---
    if "street_events" in perms:
        ev_rel = entry.get("street_events") or "street_events.json"
        ev_path = _safe_child(mod_dir, str(ev_rel))
        if ev_path is None or not ev_path.is_file():
            registry.errors.append(
                ModLoadError(
                    mid, path_s, "street_events permission set but file missing/unsafe"
                )
            )
            return None
        try:
            ev_doc = _read_json(ev_path)
        except (OSError, json.JSONDecodeError) as exc:
            registry.errors.append(ModLoadError(mid, path_s, "street_events JSON error: %s" % exc))
            return None
        raw_ev = ev_doc.get("events") if isinstance(ev_doc, dict) else ev_doc
        if not isinstance(raw_ev, list):
            registry.errors.append(ModLoadError(mid, path_s, "street_events.json must list events[]"))
            return None
        for raw in raw_ev:
            edef, eerr = _validate_event_def(raw, mid)
            if eerr or not edef:
                registry.errors.append(ModLoadError(mid, path_s, "bad street event: %s" % eerr))
                return None
            loaded.street_events.append(edef)
    elif entry.get("street_events"):
        loaded.warnings.append(
            "street_events file present but permission not granted — ignored"
        )

    # --- journal beats / quest steps ---
    if "journal" in perms:
        j_rel = entry.get("journal") or "journal.json"
        j_path = _safe_child(mod_dir, str(j_rel))
        if j_path is None or not j_path.is_file():
            registry.errors.append(
                ModLoadError(mid, path_s, "journal permission set but file missing/unsafe")
            )
            return None
        try:
            j_doc = _read_json(j_path)
        except (OSError, json.JSONDecodeError) as exc:
            registry.errors.append(ModLoadError(mid, path_s, "journal JSON error: %s" % exc))
            return None
        if not isinstance(j_doc, dict):
            registry.errors.append(ModLoadError(mid, path_s, "journal.json must be an object"))
            return None
        for raw in j_doc.get("arcs") or []:
            adef, aerr = _validate_journal_arc(raw, mid)
            if aerr or not adef:
                registry.errors.append(ModLoadError(mid, path_s, "bad journal arc: %s" % aerr))
                return None
            loaded.journal_arcs.append(adef)
        for raw in j_doc.get("beats") or []:
            bdef, berr = _validate_journal_beat(raw, mid)
            if berr or not bdef:
                registry.errors.append(ModLoadError(mid, path_s, "bad journal beat: %s" % berr))
                return None
            loaded.journal_beats.append(bdef)
        if not loaded.journal_arcs and not loaded.journal_beats:
            registry.errors.append(
                ModLoadError(mid, path_s, "journal.json needs arcs[] and/or beats[]")
            )
            return None
    elif entry.get("journal"):
        loaded.warnings.append("journal file present but permission not granted — ignored")

    # --- StreetNet / world broadcasts ---
    if "streetnet" in perms:
        sn_rel = entry.get("streetnet") or "streetnet.json"
        sn_path = _safe_child(mod_dir, str(sn_rel))
        if sn_path is None or not sn_path.is_file():
            registry.errors.append(
                ModLoadError(mid, path_s, "streetnet permission set but file missing/unsafe")
            )
            return None
        try:
            sn_doc = _read_json(sn_path)
        except (OSError, json.JSONDecodeError) as exc:
            registry.errors.append(ModLoadError(mid, path_s, "streetnet JSON error: %s" % exc))
            return None
        if isinstance(sn_doc, dict):
            raw_sn = sn_doc.get("broadcasts") or []
            raw_cmds = sn_doc.get("commands") or []
        else:
            raw_sn = sn_doc
            raw_cmds = []
        if not isinstance(raw_sn, list):
            registry.errors.append(
                ModLoadError(mid, path_s, "streetnet.json must list broadcasts[]")
            )
            return None
        if not isinstance(raw_cmds, list):
            registry.errors.append(
                ModLoadError(mid, path_s, "streetnet.json commands must be a list")
            )
            return None
        for raw in raw_sn:
            bdef, berr = _validate_streetnet_broadcast(raw, mid)
            if berr or not bdef:
                registry.errors.append(
                    ModLoadError(mid, path_s, "bad streetnet broadcast: %s" % berr)
                )
                return None
            loaded.streetnet_broadcasts.append(bdef)
        for raw in raw_cmds:
            cdef, cerr = _validate_streetnet_command(raw, mid)
            if cerr or not cdef:
                registry.errors.append(
                    ModLoadError(mid, path_s, "bad streetnet command: %s" % cerr)
                )
                return None
            slash = cdef["slash"]
            taken = {c.get("slash") for c in registry.streetnet_commands}
            taken.update(c.get("slash") for c in loaded.streetnet_commands)
            if slash in taken:
                registry.errors.append(
                    ModLoadError(mid, path_s, "streetnet slash collision %r" % slash)
                )
                return None
            loaded.streetnet_commands.append(cdef)
        if not loaded.streetnet_broadcasts and not loaded.streetnet_commands:
            registry.errors.append(
                ModLoadError(
                    mid, path_s, "streetnet.json needs broadcasts[] and/or commands[]"
                )
            )
            return None
    elif entry.get("streetnet"):
        loaded.warnings.append("streetnet file present but permission not granted — ignored")

    # --- ICE probes / cyberspace nodes ---
    if "ice_nodes" in perms:
        ice_rel = entry.get("ice_nodes") or "ice_nodes.json"
        ice_path = _safe_child(mod_dir, str(ice_rel))
        if ice_path is None or not ice_path.is_file():
            registry.errors.append(
                ModLoadError(mid, path_s, "ice_nodes permission set but file missing/unsafe")
            )
            return None
        try:
            ice_doc = _read_json(ice_path)
        except (OSError, json.JSONDecodeError) as exc:
            registry.errors.append(ModLoadError(mid, path_s, "ice_nodes JSON error: %s" % exc))
            return None
        if not isinstance(ice_doc, dict):
            registry.errors.append(ModLoadError(mid, path_s, "ice_nodes.json must be an object"))
            return None
        for raw in ice_doc.get("probes") or []:
            pdef, perr = _validate_ice_probe(raw, mid)
            if perr or not pdef:
                registry.errors.append(ModLoadError(mid, path_s, "bad ice probe: %s" % perr))
                return None
            pid = pdef["id"]
            if pid in registry.ice_probes or pid in loaded.ice_probes:
                registry.errors.append(
                    ModLoadError(mid, path_s, "ice probe id collision %r" % pid)
                )
                return None
            loaded.ice_probes[pid] = pdef
        for raw in ice_doc.get("nodes") or []:
            ndef, nerr = _validate_cyber_node(raw, mid)
            if nerr or not ndef:
                registry.errors.append(ModLoadError(mid, path_s, "bad cyber node: %s" % nerr))
                return None
            loaded.cyber_nodes.append(ndef)
        if not loaded.ice_probes and not loaded.cyber_nodes:
            registry.errors.append(
                ModLoadError(mid, path_s, "ice_nodes.json needs probes[] and/or nodes[]")
            )
            return None
    elif entry.get("ice_nodes"):
        loaded.warnings.append("ice_nodes file present but permission not granted — ignored")

    # --- globe pins / region metadata ---
    if "globe_regions" in perms:
        g_rel = entry.get("globe_regions") or "globe_regions.json"
        g_path = _safe_child(mod_dir, str(g_rel))
        if g_path is None or not g_path.is_file():
            registry.errors.append(
                ModLoadError(
                    mid, path_s, "globe_regions permission set but file missing/unsafe"
                )
            )
            return None
        try:
            g_doc = _read_json(g_path)
        except (OSError, json.JSONDecodeError) as exc:
            registry.errors.append(ModLoadError(mid, path_s, "globe_regions JSON error: %s" % exc))
            return None
        if not isinstance(g_doc, dict):
            registry.errors.append(
                ModLoadError(mid, path_s, "globe_regions.json must be an object")
            )
            return None
        for raw in g_doc.get("pins") or []:
            pdef, perr = _validate_globe_pin(raw, mid)
            if perr or not pdef:
                registry.errors.append(ModLoadError(mid, path_s, "bad globe pin: %s" % perr))
                return None
            loaded.globe_pins.append(pdef)
        for raw in g_doc.get("regions") or []:
            rdef, rerr = _validate_globe_region(raw, mid)
            if rerr or not rdef:
                registry.errors.append(ModLoadError(mid, path_s, "bad globe region: %s" % rerr))
                return None
            # Collision with already-loaded core/mod regions
            if any(r.get("id") == rdef["id"] for r in registry.globe_regions):
                registry.errors.append(
                    ModLoadError(mid, path_s, "globe region id collision %r" % rdef["id"])
                )
                return None
            loaded.globe_regions.append(rdef)
        if not loaded.globe_pins and not loaded.globe_regions:
            registry.errors.append(
                ModLoadError(mid, path_s, "globe_regions.json needs pins[] and/or regions[]")
            )
            return None
    elif entry.get("globe_regions"):
        loaded.warnings.append(
            "globe_regions file present but permission not granted — ignored"
        )

    # --- CSP-friendly web UI panels ---
    if "ui_panel" in perms:
        ui_rel = entry.get("ui_panel") or entry.get("ui_panels") or "ui_panel.json"
        ui_path = _safe_child(mod_dir, str(ui_rel))
        if ui_path is None or not ui_path.is_file():
            registry.errors.append(
                ModLoadError(mid, path_s, "ui_panel permission set but file missing/unsafe")
            )
            return None
        try:
            ui_doc = _read_json(ui_path)
        except (OSError, json.JSONDecodeError) as exc:
            registry.errors.append(ModLoadError(mid, path_s, "ui_panel JSON error: %s" % exc))
            return None
        raw_panels = ui_doc.get("panels") if isinstance(ui_doc, dict) else ui_doc
        if not isinstance(raw_panels, list):
            registry.errors.append(
                ModLoadError(mid, path_s, "ui_panel.json must list panels[]")
            )
            return None
        if not raw_panels:
            registry.errors.append(
                ModLoadError(mid, path_s, "ui_panel.json needs at least one panel")
            )
            return None
        for raw in raw_panels:
            pdef, perr = _validate_ui_panel(raw, mid)
            if perr or not pdef:
                registry.errors.append(ModLoadError(mid, path_s, "bad ui panel: %s" % perr))
                return None
            if any(p.get("id") == pdef["id"] for p in registry.ui_panels):
                registry.errors.append(
                    ModLoadError(mid, path_s, "ui panel id collision %r" % pdef["id"])
                )
                return None
            loaded.ui_panels.append(pdef)
    elif entry.get("ui_panel") or entry.get("ui_panels"):
        loaded.warnings.append("ui_panel file present but permission not granted — ignored")

    # Unimplemented permissions: warn, do not fail (forward-compatible).
    for p in perms:
        if p not in IMPLEMENTED_PERMISSIONS:
            loaded.warnings.append(
                "permission %r declared but not hooked in API %s yet" % (p, PLUGIN_API_VERSION)
            )

    # Atomic commit — only after every def validated (no partial apply).
    registry.items.update(loaded.items)
    for iid in loaded.items:
        registry.item_owners[iid] = mid
    registry.street_events.extend(loaded.street_events)
    registry.journal_arcs.extend(loaded.journal_arcs)
    registry.journal_beats.extend(loaded.journal_beats)
    registry.streetnet_broadcasts.extend(loaded.streetnet_broadcasts)
    registry.streetnet_commands.extend(loaded.streetnet_commands)
    registry.ice_probes.update(loaded.ice_probes)
    registry.cyber_nodes.extend(loaded.cyber_nodes)
    registry.globe_pins.extend(loaded.globe_pins)
    registry.globe_regions.extend(loaded.globe_regions)
    registry.ui_panels.extend(loaded.ui_panels)
    registry.mods[mid] = loaded
    log.info(
        "mod loaded %s v%s (%d items, %d street events, %d journal, %d streetnet, "
        "%d cmds, %d probes, %d nodes, %d pins, %d ui panels)",
        mid,
        loaded.version,
        len(loaded.items),
        len(loaded.street_events),
        len(loaded.journal_arcs) + len(loaded.journal_beats),
        len(loaded.streetnet_broadcasts),
        len(loaded.streetnet_commands),
        len(loaded.ice_probes),
        len(loaded.cyber_nodes),
        len(loaded.globe_pins) + len(loaded.globe_regions),
        len(loaded.ui_panels),
    )
    return loaded


def load_all_mods(roots: Optional[Sequence[Path]] = None) -> ModRegistry:
    registry = ModRegistry()
    for mod_dir in discover_mod_dirs(roots):
        load_mod(mod_dir, registry)
    return registry


def _weighted_pick(rng, items: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not items:
        return None
    weights = [float(e.get("weight") or 1.0) for e in items]
    total = sum(weights)
    if total <= 0:
        return None
    r = rng.random() * total
    acc = 0.0
    for ev, w in zip(items, weights):
        acc += w
        if r <= acc:
            return ev
    return items[-1]


class ModdingMixin:
    """Mixed into YearFeaturesMixin — call ``_modding_init()`` from year init."""

    def _modding_bind_registry(self, registry: ModRegistry) -> None:
        self.mod_registry = registry
        self.mod_street_events = list(registry.street_events)
        self.mod_journal_arcs = list(registry.journal_arcs)
        self.mod_journal_beats = list(registry.journal_beats)
        self.mod_streetnet_broadcasts = list(registry.streetnet_broadcasts)
        self.mod_streetnet_commands = list(registry.streetnet_commands)
        self.mod_ice_probes = dict(registry.ice_probes)
        self.mod_cyber_nodes = list(registry.cyber_nodes)
        self.mod_globe_pins = list(registry.globe_pins)
        self.mod_globe_regions = list(registry.globe_regions)
        self.mod_ui_panels = list(registry.ui_panels)
        self._mod_streetnet_fired_on_load = set(
            getattr(self, "_mod_streetnet_fired_on_load", set()) or set()
        )

    def _modding_clear_globe_overlays(self) -> None:
        """Drop previous-load mod overlays so reload does not leave stale pins."""
        if not hasattr(self, "globe_regions") or not isinstance(self.globe_regions, dict):
            return
        stale = [
            rid
            for rid, reg in list(self.globe_regions.items())
            if isinstance(reg, dict) and reg.get("mod_overlay")
        ]
        for rid in stale:
            self.globe_regions.pop(rid, None)
        defs = getattr(self, "globe_defs", None)
        if isinstance(defs, dict):
            defs["regions"] = [
                r
                for r in (defs.get("regions") or [])
                if not (isinstance(r, dict) and r.get("mod_overlay"))
            ]

    def _modding_apply_globe_overlays(self) -> None:
        """Merge metadata-only mod regions into globe_regions (reload-safe)."""
        self._modding_clear_globe_overlays()
        if not hasattr(self, "globe_regions") or not isinstance(self.globe_regions, dict):
            return
        for reg in getattr(self, "mod_globe_regions", None) or []:
            rid = str(reg.get("id") or "")
            if not rid:
                continue
            if rid in self.globe_regions and not (
                isinstance(self.globe_regions.get(rid), dict)
                and self.globe_regions[rid].get("mod_overlay")
            ):
                continue
            if reg.get("metadata_only", True):
                overlay = dict(reg)
                overlay["teleport"] = False
                overlay["mod_overlay"] = True
                self.globe_regions[rid] = overlay
                defs = getattr(self, "globe_defs", None)
                if isinstance(defs, dict):
                    regions = [
                        r
                        for r in (defs.get("regions") or [])
                        if not (isinstance(r, dict) and str(r.get("id")) == rid)
                    ]
                    regions.append(overlay)
                    defs["regions"] = regions

    def _modding_init(self) -> None:
        self._modding_bind_registry(load_all_mods())
        self._modding_apply_globe_overlays()
        if self.mod_registry.mods:
            names = ", ".join(sorted(self.mod_registry.mods))
            self._push_event(
                "mod",
                "Mods online (%d): %s" % (len(self.mod_registry.mods), names),
            )
        for err in self.mod_registry.errors:
            log.warning("mod error [%s] %s: %s", err.mod_id, err.path, err.message)
        self._fire_mod_streetnet_on_load()

    def reload_mods(self) -> Dict[str, Any]:
        """Hot-reload mod defs (aligned with ``/api/reload_defs``). Fail closed per mod."""
        self._mod_streetnet_fired_on_load = set()
        self._modding_bind_registry(load_all_mods())
        self._modding_apply_globe_overlays()
        # Journal offer is idempotent (skips known arc/beat ids).
        for agent in (getattr(self, "players", None) or {}).values():
            self._modding_offer_journal(agent)
        snap = self.mod_registry.snapshot()
        self._push_event(
            "mod",
            "Mods reloaded — %d ok, %d errors."
            % (snap["mod_count"], len(snap["errors"])),
        )
        self._fire_mod_streetnet_on_load()
        return snap

    def _mod_item(self, item_id: str) -> Optional[Item]:
        reg = getattr(self, "mod_registry", None)
        if not reg:
            return None
        defn = reg.items.get(item_id)
        if not defn:
            return None
        return item_from_def(defn)

    def _all_ice_probes(self) -> Dict[str, Dict[str, Any]]:
        """Core ICE probes plus mod probes (mod ids are namespaced)."""
        from .. import constants as C

        out: Dict[str, Dict[str, Any]] = {k: dict(v) for k, v in C.ICE_PROBES.items()}
        for pid, defn in (getattr(self, "mod_ice_probes", None) or {}).items():
            merged = dict(defn)
            merged.setdefault("effect", defn.get("effect") or "reveal")
            out[pid] = merged
        return out
    def _pick_mod_street_event(self) -> Optional[Dict[str, Any]]:
        return _weighted_pick(self.rng, getattr(self, "mod_street_events", None) or [])

    def _fire_mod_street_event(self, living: List[Any]) -> bool:
        ev = self._pick_mod_street_event()
        if not ev:
            return False
        msg = self.rng.choice(list(ev["messages"]))
        kind = str(ev.get("kind") or "broadcast")
        self._push_event(
            kind if kind != "mod" else "broadcast",
            msg,
            mod_id=ev.get("mod_id"),
            event_id=ev.get("id"),
        )
        plog = ev.get("player_log")
        for p in living:
            p.log(plog or ("Mod street event: %s" % msg))
        if kind == "broadcast":
            if hasattr(self, "system_chat"):
                self.system_chat(msg)
        return True

    def _pick_mod_streetnet(self) -> Optional[Dict[str, Any]]:
        return _weighted_pick(
            self.rng, getattr(self, "mod_streetnet_broadcasts", None) or []
        )

    def _fire_mod_streetnet_broadcast(
        self, living: Optional[List[Any]] = None, ev: Optional[Dict[str, Any]] = None
    ) -> bool:
        ev = ev or self._pick_mod_streetnet()
        if not ev:
            return False
        msg = self.rng.choice(list(ev["messages"]))
        channel = str(ev.get("channel") or "streetnet")
        self._push_event(
            "broadcast",
            msg,
            mod_id=ev.get("mod_id"),
            event_id=ev.get("id"),
            channel=channel,
        )
        if hasattr(self, "system_chat"):
            self.system_chat(msg)
        plog = ev.get("player_log")
        for p in living or []:
            p.log(plog or ("StreetNet mod: %s" % msg))
        return True

    def _fire_mod_streetnet_on_load(self) -> None:
        fired = getattr(self, "_mod_streetnet_fired_on_load", None)
        if not isinstance(fired, set):
            fired = set()
            self._mod_streetnet_fired_on_load = fired
        for ev in getattr(self, "mod_streetnet_broadcasts", None) or []:
            if not ev.get("fire_on_load"):
                continue
            eid = str(ev.get("id") or "")
            if not eid or eid in fired:
                continue
            if self._fire_mod_streetnet_broadcast(ev=ev):
                fired.add(eid)

    def _mod_streetnet_help(self) -> str:
        cmds = getattr(self, "mod_streetnet_commands", None) or []
        if not cmds:
            return ""
        bits = []
        for c in cmds[:12]:
            slash = c.get("slash")
            if not slash:
                continue
            help_s = c.get("help") or "mod StreetNet command"
            bits.append("/%s — %s" % (slash, help_s))
        return "Mod cmds: " + " · ".join(bits) if bits else ""

    def _mod_handle_streetnet_command(self, agent, cmd: str, arg1: str = "", rest: str = "") -> bool:
        """Handle a player slash if a loaded mod registered it. Fail closed otherwise."""
        slash = (cmd or "").strip().lower().lstrip("/")
        if not slash:
            return False
        for cdef in getattr(self, "mod_streetnet_commands", None) or []:
            if cdef.get("slash") != slash:
                continue
            replies = list(cdef.get("replies") or [])
            reply = self.rng.choice(replies) if replies else ""
            if reply:
                if hasattr(self, "_irc_notice"):
                    self._irc_notice(agent, reply)
                else:
                    agent.log(reply)
            plog = cdef.get("player_log")
            if plog:
                agent.log(plog)
            action = cdef.get("action")
            if action and hasattr(self, "handle_year_action"):
                try:
                    self.handle_year_action(agent, action, cdef.get("arg") or "")
                except Exception:
                    log.warning("mod streetnet command %s action %s failed", slash, action)
            if cdef.get("broadcast") and reply and hasattr(self, "system_chat"):
                self.system_chat(reply)
            return True
        return False

    def _modding_offer_journal(self, agent) -> None:
        """Attach mod journal arcs / fire join beats for a freshly bootstrapped agent."""
        j = getattr(agent, "journal", None)
        if not isinstance(j, dict):
            return
        arcs = getattr(self, "mod_journal_arcs", None) or []
        if arcs:
            mod_arcs = list(j.get("mod_arcs") or [])
            known = {a.get("id") for a in mod_arcs}
            for arc in arcs:
                if not arc.get("auto_offer", True):
                    continue
                aid = arc.get("id")
                if aid in known:
                    continue
                mod_arcs.append(
                    {
                        "id": aid,
                        "title": arc.get("title") or aid,
                        "step": 0,
                        "steps": [dict(s) for s in (arc.get("steps") or [])],
                        "completed": False,
                        "mod_id": arc.get("mod_id"),
                    }
                )
                known.add(aid)
                agent.log("Journal (mod): %s — offered." % (arc.get("title") or aid))
            j["mod_arcs"] = mod_arcs

        seen = set(j.get("mod_beats_seen") or [])
        for beat in getattr(self, "mod_journal_beats", None) or []:
            if beat.get("trigger") not in ("join", "always"):
                continue
            bid = beat.get("id")
            if not bid or bid in seen:
                continue
            seen.add(bid)
            text = beat.get("text") or ""
            agent.log(text)
            self._push_event(
                "journal",
                text,
                mod_id=beat.get("mod_id"),
                event_id=bid,
            )
        j["mod_beats_seen"] = sorted(seen)
        agent.journal = j
    def _modding_update_journal(self, agent) -> None:
        """Advance simple mod quest arcs (equip/own namespaced items)."""
        j = getattr(agent, "journal", None)
        if not isinstance(j, dict):
            return
        arcs = list(j.get("mod_arcs") or [])
        if arcs:
            inv_ids = {
                getattr(it, "id", None)
                for it in (getattr(agent.actor, "inventory", None) or [])
            }
            changed = False
            for arc in arcs:
                if arc.get("completed"):
                    continue
                steps = list(arc.get("steps") or [])
                step = int(arc.get("step") or 0)
                while step < len(steps):
                    sid = str(steps[step].get("id") or "")
                    matched = sid in inv_ids or any(
                        (iid or "").endswith("." + sid) or iid == sid for iid in inv_ids
                    )
                    if step == 0 and sid in ("accept", "brief", "start"):
                        matched = True
                    if sid in ("done", "complete", "finish", "end"):
                        matched = True
                    if not matched:
                        break
                    step += 1
                    changed = True
                    if step < len(steps):
                        agent.log(
                            "Journal (mod/%s): %s"
                            % (
                                arc.get("id"),
                                steps[step].get("text") or steps[step].get("id"),
                            )
                        )
                arc["step"] = step
                if step >= len(steps) and steps:
                    arc["completed"] = True
                    changed = True
                    agent.log(
                        "Journal (mod): %s complete."
                        % (arc.get("title") or arc.get("id"))
                    )
            if changed:
                j["mod_arcs"] = arcs
                agent.journal = j

        if hasattr(agent, "has_payload") and agent.has_payload():
            seen = set(j.get("mod_beats_seen") or [])
            for beat in getattr(self, "mod_journal_beats", None) or []:
                if beat.get("trigger") != "payload":
                    continue
                bid = beat.get("id")
                if not bid or bid in seen:
                    continue
                seen.add(bid)
                agent.log(beat.get("text") or "")
                self._push_event(
                    "journal",
                    beat.get("text") or "",
                    mod_id=beat.get("mod_id"),
                    event_id=bid,
                )
            j["mod_beats_seen"] = sorted(seen)
            agent.journal = j

    def _pick_mod_cyber_node(self) -> Optional[Dict[str, Any]]:
        return _weighted_pick(self.rng, getattr(self, "mod_cyber_nodes", None) or [])

    def _mod_globe_snapshot_extras(self) -> Dict[str, Any]:
        return {
            "mod_pins": list(getattr(self, "mod_globe_pins", None) or []),
            "mod_regions": [
                r
                for r in (getattr(self, "mod_globe_regions", None) or [])
                if r.get("metadata_only", True)
            ],
        }

    def _modding_snapshot(self, agent=None) -> Dict[str, Any]:
        reg = getattr(self, "mod_registry", None)
        if not reg:
            return {
                "api_version": PLUGIN_API_VERSION,
                "enabled": False,
                "mod_count": 0,
                "mods": [],
                "errors": [],
                "capabilities": host_capability_flags(),
            }
        return reg.snapshot()
