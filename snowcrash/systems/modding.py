"""Modder / plugin framework (#72) — data-driven JSON mods, fail-closed.

v1 loads manifests from ``mods/`` and ``examples/plugins/`` and registers
JSON-defined items + street events only. No arbitrary Python/WASM exec.
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
PLUGIN_API_VERSION = "1.0.0"

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
IMPLEMENTED_PERMISSIONS: Set[str] = {"items", "street_events"}

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
    errors: List[ModLoadError] = field(default_factory=list)
    skipped: List[Dict[str, str]] = field(default_factory=list)

    def clear(self) -> None:
        self.mods.clear()
        self.items.clear()
        self.item_owners.clear()
        self.street_events.clear()
        self.errors.clear()
        self.skipped.clear()

    def snapshot(self) -> Dict[str, Any]:
        return {
            "api_version": self.api_version,
            "enabled": True,
            "mod_count": len(self.mods),
            "item_count": len(self.items),
            "street_event_count": len(self.street_events),
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

    # Unimplemented permissions: warn, do not fail (forward-compatible).
    for p in perms:
        if p not in IMPLEMENTED_PERMISSIONS:
            loaded.warnings.append(
                "permission %r declared but not hooked in API %s yet" % (p, PLUGIN_API_VERSION)
            )

    registry.mods[mid] = loaded
    log.info(
        "mod loaded %s v%s (%d items, %d street events)",
        mid,
        loaded.version,
        len(loaded.items),
        len(loaded.street_events),
    )
    return loaded


def load_all_mods(roots: Optional[Sequence[Path]] = None) -> ModRegistry:
    registry = ModRegistry()
    for mod_dir in discover_mod_dirs(roots):
        load_mod(mod_dir, registry)
    return registry


class ModdingMixin:
    """Mixed into YearFeaturesMixin — call ``_modding_init()`` from year init."""

    def _modding_init(self) -> None:
        self.mod_registry = load_all_mods()
        self.mod_street_events = list(self.mod_registry.street_events)
        if self.mod_registry.mods:
            names = ", ".join(sorted(self.mod_registry.mods))
            self._push_event(
                "mod",
                "Mods online (%d): %s" % (len(self.mod_registry.mods), names),
            )
        for err in self.mod_registry.errors:
            log.warning("mod error [%s] %s: %s", err.mod_id, err.path, err.message)

    def reload_mods(self) -> Dict[str, Any]:
        """Hot-reload mod defs (aligned with ``/api/reload_defs``). Fail closed per mod."""
        self.mod_registry = load_all_mods()
        self.mod_street_events = list(self.mod_registry.street_events)
        snap = self.mod_registry.snapshot()
        self._push_event(
            "mod",
            "Mods reloaded — %d ok, %d errors."
            % (snap["mod_count"], len(snap["errors"])),
        )
        return snap

    def _mod_item(self, item_id: str) -> Optional[Item]:
        reg = getattr(self, "mod_registry", None)
        if not reg:
            return None
        defn = reg.items.get(item_id)
        if not defn:
            return None
        return item_from_def(defn)

    def _pick_mod_street_event(self) -> Optional[Dict[str, Any]]:
        events = getattr(self, "mod_street_events", None) or []
        if not events:
            return None
        # Weighted choice
        weights = [float(e.get("weight") or 1.0) for e in events]
        total = sum(weights)
        if total <= 0:
            return None
        r = self.rng.random() * total
        acc = 0.0
        for ev, w in zip(events, weights):
            acc += w
            if r <= acc:
                return ev
        return events[-1]

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
