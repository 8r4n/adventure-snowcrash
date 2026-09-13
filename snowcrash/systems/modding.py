"""Modder / plugin framework (#72) — data-driven JSON mods, fail-closed.

Loads manifests from ``mods/`` and ``examples/plugins/`` and registers
JSON-defined items, street events, journal beats, StreetNet broadcasts,
ICE probes / light cyberspace nodes, and globe pins. No arbitrary Python/WASM exec.
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
PLUGIN_API_VERSION = "1.1.0"

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


def _parse_semver(v: str) -> Optional[Tuple[int, int, int]]:
    if not isinstance(v, str):
        return None
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$", v.strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def api_compatible(required: str, provided: str = PLUGIN_API_VERSION) -> bool:
    """True if *required* major matches and minor/patch <= *provided* (same major)."""
    req = _parse_semver(required)
    got = _parse_semver(provided)
    if req is None or got is None:
        return False
    if req[0] != got[0]:
        return False
    # Mod asks for API <= host API within the same major.
    return req <= got


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


def _safe_child(base: Path, rel: str) -> Optional[Path]:
    """Resolve *rel* under *base*; reject absolute / traversal."""
    if not rel or not isinstance(rel, str):
        return None
    if os.path.isabs(rel) or ".." in Path(rel).parts:
        return None
    try:
        base_r = base.resolve()
        target = (base / rel).resolve()
    except OSError:
        return None
    try:
        target.relative_to(base_r)
    except ValueError:
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
    ice_probes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    cyber_nodes: List[Dict[str, Any]] = field(default_factory=list)
    globe_pins: List[Dict[str, Any]] = field(default_factory=list)
    globe_regions: List[Dict[str, Any]] = field(default_factory=list)
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
            "ice_probes": sorted(self.ice_probes.keys()),
            "cyber_nodes": [n.get("id") for n in self.cyber_nodes],
            "globe_pins": [p.get("id") for p in self.globe_pins],
            "globe_regions": [r.get("id") for r in self.globe_regions],
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
    ice_probes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    cyber_nodes: List[Dict[str, Any]] = field(default_factory=list)
    globe_pins: List[Dict[str, Any]] = field(default_factory=list)
    globe_regions: List[Dict[str, Any]] = field(default_factory=list)
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
        self.ice_probes.clear()
        self.cyber_nodes.clear()
        self.globe_pins.clear()
        self.globe_regions.clear()
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
            "ice_probe_count": len(self.ice_probes),
            "cyber_node_count": len(self.cyber_nodes),
            "globe_pin_count": len(self.globe_pins),
            "globe_region_count": len(self.globe_regions),
            "mods": [m.summary() for m in self.mods.values()],
            "errors": [
                {"mod_id": e.mod_id, "path": e.path, "message": e.message}
                for e in self.errors
            ],
            "skipped": list(self.skipped),
            "implemented_permissions": sorted(IMPLEMENTED_PERMISSIONS),
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
    if not api_compatible(api_req, registry.api_version):
        msg = "incompatible api_version %r (host %s) — fail closed" % (
            api_req,
            registry.api_version,
        )
        registry.errors.append(ModLoadError(mid, path_s, msg))
        registry.skipped.append({"id": mid, "reason": msg})
        log.warning("mod %s: %s", mid, msg)
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
            if iid in registry.items:
                registry.errors.append(
                    ModLoadError(mid, path_s, "item id collision %r" % iid)
                )
                return None
            loaded.items[iid] = idef
            registry.items[iid] = idef
            registry.item_owners[iid] = mid
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
            registry.street_events.append(edef)
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
            registry.journal_arcs.append(adef)
        for raw in j_doc.get("beats") or []:
            bdef, berr = _validate_journal_beat(raw, mid)
            if berr or not bdef:
                registry.errors.append(ModLoadError(mid, path_s, "bad journal beat: %s" % berr))
                return None
            loaded.journal_beats.append(bdef)
            registry.journal_beats.append(bdef)
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
        raw_sn = sn_doc.get("broadcasts") if isinstance(sn_doc, dict) else sn_doc
        if not isinstance(raw_sn, list):
            registry.errors.append(
                ModLoadError(mid, path_s, "streetnet.json must list broadcasts[]")
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
            registry.streetnet_broadcasts.append(bdef)
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
            if pid in registry.ice_probes:
                registry.errors.append(
                    ModLoadError(mid, path_s, "ice probe id collision %r" % pid)
                )
                return None
            loaded.ice_probes[pid] = pdef
            registry.ice_probes[pid] = pdef
        for raw in ice_doc.get("nodes") or []:
            ndef, nerr = _validate_cyber_node(raw, mid)
            if nerr or not ndef:
                registry.errors.append(ModLoadError(mid, path_s, "bad cyber node: %s" % nerr))
                return None
            loaded.cyber_nodes.append(ndef)
            registry.cyber_nodes.append(ndef)
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
            registry.globe_pins.append(pdef)
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
            registry.globe_regions.append(rdef)
        if not loaded.globe_pins and not loaded.globe_regions:
            registry.errors.append(
                ModLoadError(mid, path_s, "globe_regions.json needs pins[] and/or regions[]")
            )
            return None
    elif entry.get("globe_regions"):
        loaded.warnings.append(
            "globe_regions file present but permission not granted — ignored"
        )

    # Unimplemented permissions: warn, do not fail (forward-compatible).
    for p in perms:
        if p not in IMPLEMENTED_PERMISSIONS:
            loaded.warnings.append(
                "permission %r declared but not hooked in API %s yet" % (p, PLUGIN_API_VERSION)
            )

    registry.mods[mid] = loaded
    log.info(
        "mod loaded %s v%s (%d items, %d street events, %d journal, %d streetnet, "
        "%d probes, %d nodes, %d pins)",
        mid,
        loaded.version,
        len(loaded.items),
        len(loaded.street_events),
        len(loaded.journal_arcs) + len(loaded.journal_beats),
        len(loaded.streetnet_broadcasts),
        len(loaded.ice_probes),
        len(loaded.cyber_nodes),
        len(loaded.globe_pins) + len(loaded.globe_regions),
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
        self.mod_ice_probes = dict(registry.ice_probes)
        self.mod_cyber_nodes = list(registry.cyber_nodes)
        self.mod_globe_pins = list(registry.globe_pins)
        self.mod_globe_regions = list(registry.globe_regions)
        self._mod_streetnet_fired_on_load = set(
            getattr(self, "_mod_streetnet_fired_on_load", set()) or set()
        )

    def _modding_apply_globe_overlays(self) -> None:
        """Merge metadata-only mod regions into globe_regions (non-destructive)."""
        if not hasattr(self, "globe_regions") or not isinstance(self.globe_regions, dict):
            return
        for reg in getattr(self, "mod_globe_regions", None) or []:
            rid = str(reg.get("id") or "")
            if not rid or rid in self.globe_regions:
                continue
            if reg.get("metadata_only", True):
                overlay = dict(reg)
                overlay["teleport"] = False
                overlay["mod_overlay"] = True
                self.globe_regions[rid] = overlay
                defs = getattr(self, "globe_defs", None)
                if isinstance(defs, dict):
                    regions = list(defs.get("regions") or [])
                    if not any(str(r.get("id")) == rid for r in regions):
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
            }
        return reg.snapshot()
