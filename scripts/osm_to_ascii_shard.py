#!/usr/bin/env python3
"""OSM (XML) → Snowcrash ASCII shard spike (#83).

Offline-first: defaults to scripts/fixtures/tiny_downtown.osm.xml.
Optional live Overpass fetch via --bbox (disabled in CI; needs network).

Emits:
  - ASCII grid preview on stdout (or --preview-only)
  - JSON chunk (snowcrash_ascii_shard_v1) compatible with future mapgen ingest
  - Optional .txt grid dump

Glyph language matches snowcrash.constants (WALL #, STREET =, FLOOR ., etc.).
Does not paste copyrighted map tiles. Real OSM extracts remain ODbL —
attribute © OpenStreetMap contributors (https://www.openstreetmap.org/copyright).

Usage:
  python scripts/osm_to_ascii_shard.py
  python scripts/osm_to_ascii_shard.py --input scripts/fixtures/tiny_downtown.osm.xml \\
      --out /tmp/shard.json --width 64 --height 40
  python scripts/osm_to_ascii_shard.py --bbox -118.252,34.048,-118.246,34.052  # live
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Glyphs aligned with snowcrash.constants
WALL = "#"
FLOOR = "."
STREET = "="
GRASS = ","
WATER = "~"
JACKPOINT = "J"
UPLINK = "U"
NPC = "&"
EMPTY = " "

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "tiny_downtown.osm.xml"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# highway=* → street weight (wider paint for primary)
HIGHWAY_WIDTH = {
    "motorway": 3,
    "trunk": 3,
    "primary": 2,
    "secondary": 2,
    "tertiary": 2,
    "residential": 1,
    "living_street": 1,
    "service": 1,
    "unclassified": 1,
    "pedestrian": 1,
    "footway": 1,
    "path": 1,
    "cycleway": 1,
    "alley": 1,
}

JACK_AMENITIES = frozenset({"internet_cafe", "telecommunication", "telephone"})
UPLINK_AMENITIES = frozenset({"bureau_de_change", "bank", "atm"})
VENDOR_KEYS = frozenset({"shop", "amenity", "tourism"})


def _tags(elem: ET.Element) -> Dict[str, str]:
    return {t.get("k", ""): t.get("v", "") for t in elem.findall("tag") if t.get("k")}


def parse_osm_xml(data: str | bytes) -> Tuple[
    Dict[int, Tuple[float, float]],
    List[dict],
    List[dict],
    Optional[Tuple[float, float, float, float]],
]:
    """Return nodes{id:(lat,lon)}, ways[], poi_nodes[], optional bounds(minlon,minlat,maxlon,maxlat)."""
    root = ET.fromstring(data)
    nodes: Dict[int, Tuple[float, float]] = {}
    for n in root.findall("node"):
        nid = int(n.get("id"))
        nodes[nid] = (float(n.get("lat")), float(n.get("lon")))
    ways: List[dict] = []
    for w in root.findall("way"):
        refs = [int(nd.get("ref")) for nd in w.findall("nd")]
        ways.append({"id": int(w.get("id")), "refs": refs, "tags": _tags(w)})
    pois: List[dict] = []
    for n in root.findall("node"):
        tags = _tags(n)
        if tags:
            pois.append(
                {
                    "id": int(n.get("id")),
                    "lat": float(n.get("lat")),
                    "lon": float(n.get("lon")),
                    "tags": tags,
                }
            )
    bounds = None
    b = root.find("bounds")
    if b is not None:
        bounds = (
            float(b.get("minlon")),
            float(b.get("minlat")),
            float(b.get("maxlon")),
            float(b.get("maxlat")),
        )
    return nodes, ways, pois, bounds


def fetch_overpass(bbox: Tuple[float, float, float, float], timeout: float = 60.0) -> bytes:
    """bbox = (minlon, minlat, maxlon, maxlat). Small extracts only — see Overpass etiquette."""
    minlon, minlat, maxlon, maxlat = bbox
    # Keep query tiny: highways, buildings, water, parks, a few amenities
    query = f"""
    [out:xml][timeout:25];
    (
      way["highway"]({minlat},{minlon},{maxlat},{maxlon});
      way["building"]({minlat},{minlon},{maxlat},{maxlon});
      way["natural"="water"]({minlat},{minlon},{maxlat},{maxlon});
      way["waterway"]({minlat},{minlon},{maxlat},{maxlon});
      way["leisure"="park"]({minlat},{minlon},{maxlat},{maxlon});
      way["landuse"="industrial"]({minlat},{minlon},{maxlat},{maxlon});
      node["amenity"]({minlat},{minlon},{maxlat},{maxlon});
      node["shop"]({minlat},{minlon},{maxlat},{maxlon});
    );
    (._;>;);
    out body;
    """
    req = urllib.request.Request(
        OVERPASS_URL,
        data=urllib.parse.urlencode({"data": query}).encode("utf-8"),
        headers={"User-Agent": "adventure-snowcrash-osm-spike/0.1 (#83 research)"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def infer_bounds(
    nodes: Dict[int, Tuple[float, float]],
    explicit: Optional[Tuple[float, float, float, float]],
) -> Tuple[float, float, float, float]:
    if explicit:
        return explicit
    if not nodes:
        raise SystemExit("no nodes to bound")
    lats = [lat for lat, _ in nodes.values()]
    lons = [lon for _, lon in nodes.values()]
    pad_lat = (max(lats) - min(lats)) * 0.05 or 0.0001
    pad_lon = (max(lons) - min(lons)) * 0.05 or 0.0001
    return (
        min(lons) - pad_lon,
        min(lats) - pad_lat,
        max(lons) + pad_lon,
        max(lats) + pad_lat,
    )


def project(
    lat: float,
    lon: float,
    bounds: Tuple[float, float, float, float],
    width: int,
    height: int,
) -> Tuple[int, int]:
    minlon, minlat, maxlon, maxlat = bounds
    # y increases southward on screen
    if maxlon == minlon or maxlat == minlat:
        return 0, 0
    x = int((lon - minlon) / (maxlon - minlon) * (width - 1))
    y = int((maxlat - lat) / (maxlat - minlat) * (height - 1))
    return max(0, min(width - 1, x)), max(0, min(height - 1, y))


def _bresenham(x0: int, y0: int, x1: int, y1: int) -> Iterable[Tuple[int, int]]:
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        yield x, y
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


def _paint_disk(grid: List[List[str]], cx: int, cy: int, r: int, ch: str, w: int, h: int) -> None:
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r:
                x, y = cx + dx, cy + dy
                if 0 <= x < w and 0 <= y < h:
                    grid[y][x] = ch


def _fill_polygon(grid: List[List[str]], pts: Sequence[Tuple[int, int]], ch: str, w: int, h: int) -> None:
    if len(pts) < 3:
        return
    min_y = max(0, min(p[1] for p in pts))
    max_y = min(h - 1, max(p[1] for p in pts))
    for y in range(min_y, max_y + 1):
        xs: List[int] = []
        n = len(pts)
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            if y0 == y1:
                continue
            if (y0 <= y < y1) or (y1 <= y < y0):
                t = (y - y0) / (y1 - y0)
                xs.append(int(x0 + t * (x1 - x0)))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            for x in range(max(0, xs[i]), min(w - 1, xs[i + 1]) + 1):
                grid[y][x] = ch


def rasterize(
    nodes: Dict[int, Tuple[float, float]],
    ways: List[dict],
    pois: List[dict],
    bounds: Tuple[float, float, float, float],
    width: int,
    height: int,
) -> Tuple[List[List[str]], Dict[str, Tuple[int, int]]]:
    """Paint order: grass base → parks → water → buildings → streets → POIs.

    Streets use thin strokes so a dense downtown fixture still shows blocks.
    """
    grid = [[GRASS for _ in range(width)] for _ in range(height)]
    landmarks: Dict[str, Tuple[int, int]] = {}

    def way_pts(way: dict) -> List[Tuple[int, int]]:
        return [project(*nodes[r], bounds, width, height) for r in way["refs"] if r in nodes]

    # 1) Named parks
    for way in ways:
        tags = way["tags"]
        if tags.get("leisure") == "park" or tags.get("landuse") in ("grass", "recreation_ground"):
            _fill_polygon(grid, way_pts(way), GRASS, width, height)

    # 2) Water (polygons or thin canals)
    for way in ways:
        tags = way["tags"]
        if not (
            tags.get("natural") == "water"
            or tags.get("waterway")
            or tags.get("landuse") == "basin"
        ):
            continue
        pts = way_pts(way)
        if tags.get("waterway") and len(pts) >= 2:
            for i in range(len(pts) - 1):
                for x, y in _bresenham(*pts[i], *pts[i + 1]):
                    if 0 <= x < width and 0 <= y < height:
                        grid[y][x] = WATER
        else:
            _fill_polygon(grid, pts, WATER, width, height)

    # 3) Buildings → floor fill + wall ring
    for way in ways:
        tags = way["tags"]
        if not tags.get("building"):
            continue
        pts = way_pts(way)
        if len(pts) < 3:
            continue
        _fill_polygon(grid, pts, FLOOR, width, height)
        for i in range(len(pts) - 1):
            for x, y in _bresenham(*pts[i], *pts[i + 1]):
                if 0 <= x < width and 0 <= y < height:
                    grid[y][x] = WALL

    # 4) Highways → streets (overwrite grass/floor; keep building walls where possible)
    for way in ways:
        tags = way["tags"]
        hw = tags.get("highway")
        if not hw:
            continue
        # Cap paint radius so small grids stay readable
        radius = 1 if HIGHWAY_WIDTH.get(hw, 1) >= 2 else 0
        pts = way_pts(way)
        for i in range(len(pts) - 1):
            for x, y in _bresenham(*pts[i], *pts[i + 1]):
                if radius == 0:
                    if 0 <= x < width and 0 <= y < height and grid[y][x] != WATER:
                        grid[y][x] = STREET
                else:
                    for dy in range(-radius, radius + 1):
                        for dx in range(-radius, radius + 1):
                            xx, yy = x + dx, y + dy
                            if 0 <= xx < width and 0 <= yy < height and grid[yy][xx] != WATER:
                                # Do not erase solid building outlines aggressively
                                if grid[yy][xx] == WALL and (dx, dy) != (0, 0):
                                    continue
                                grid[yy][xx] = STREET

    # 5) POIs / landmarks (last)
    for poi in pois:
        tags = poi["tags"]
        x, y = project(poi["lat"], poi["lon"], bounds, width, height)
        amenity = tags.get("amenity", "")
        name = (tags.get("name") or "").lower()
        if amenity in JACK_AMENITIES or "jack" in name:
            grid[y][x] = JACKPOINT
            landmarks["jackpoint"] = (x, y)
        elif amenity in UPLINK_AMENITIES or "uplink" in name or "metaverse" in name:
            grid[y][x] = UPLINK
            landmarks["uplink"] = (x, y)
        elif amenity in ("bar", "nightclub", "pub") or "club" in name:
            grid[y][x] = NPC
            landmarks.setdefault("club", (x, y))
        elif "shop" in tags or amenity in ("marketplace", "restaurant", "cafe"):
            if grid[y][x] not in (WATER, JACKPOINT, UPLINK):
                grid[y][x] = NPC
            landmarks.setdefault("vendor", (x, y))
        elif tags.get("landuse") == "industrial" or "faraday" in name:
            landmarks.setdefault("faraday", (x, y))
            if grid[y][x] not in (WATER, JACKPOINT, UPLINK):
                grid[y][x] = FLOOR

    return grid, landmarks


def shard_seed_hint(bounds: Tuple[float, float, float, float], grid: List[List[str]]) -> int:
    """Stable int seed derived from geometry — usable as regions.json shard_seed."""
    blob = f"{bounds}|{len(grid)}x{len(grid[0])}|{''.join(''.join(r) for r in grid[:8])}"
    return int(hashlib.sha256(blob.encode()).hexdigest()[:8], 16)


def grid_to_lines(grid: List[List[str]]) -> List[str]:
    return ["".join(row) for row in grid]


def build_chunk(
    grid: List[List[str]],
    landmarks: Dict[str, Tuple[int, int]],
    bounds: Tuple[float, float, float, float],
    source: str,
    real_osm: bool,
) -> dict:
    lines = grid_to_lines(grid)
    h, w = len(grid), len(grid[0]) if grid else 0
    seed = shard_seed_hint(bounds, grid)
    attribution = None
    if real_osm:
        attribution = {
            "text": "© OpenStreetMap contributors",
            "url": "https://www.openstreetmap.org/copyright",
            "license": "ODbL-1.0",
            "note": (
                "Map data from OpenStreetMap. Produced ASCII shard is a Produced Work; "
                "substantial extracts redistributed as databases remain under ODbL share-alike."
            ),
        }
    else:
        attribution = {
            "text": "Synthetic OSM-schema fixture (not live OSM data)",
            "license": "same as adventure-snowcrash (MIT) for this fixture only",
            "note": "Replace with live OSM extracts before shipping geo-faithful shards; then apply ODbL attribution.",
        }
    return {
        "format": "snowcrash_ascii_shard_v1",
        "issue": 83,
        "width": w,
        "height": h,
        "tiles": lines,
        "glyphs": {
            "wall": WALL,
            "floor": FLOOR,
            "street": STREET,
            "grass": GRASS,
            "water": WATER,
            "jackpoint": JACKPOINT,
            "uplink": UPLINK,
            "npc": NPC,
        },
        "landmarks": {k: {"x": v[0], "y": v[1]} for k, v in landmarks.items()},
        "bbox": {
            "minlon": bounds[0],
            "minlat": bounds[1],
            "maxlon": bounds[2],
            "maxlat": bounds[3],
        },
        "shard_seed": seed,
        "source": source,
        "attribution": attribution,
        "mapgen_hook": (
            "Future: load tiles into GameMap or seed generate_world(shard_seed). "
            "Globe teleport (#54) can point regions.json shard_seed at this value."
        ),
    }


def parse_bbox(s: str) -> Tuple[float, float, float, float]:
    parts = [float(p.strip()) for p in s.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox must be minlon,minlat,maxlon,maxlat")
    return parts[0], parts[1], parts[2], parts[3]


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="OSM → ASCII Metaverse shard spike (#83)")
    ap.add_argument(
        "--input",
        "-i",
        type=Path,
        default=DEFAULT_FIXTURE,
        help="OSM XML path (default: bundled tiny downtown fixture)",
    )
    ap.add_argument(
        "--bbox",
        type=parse_bbox,
        default=None,
        help="Live Overpass bbox minlon,minlat,maxlon,maxlat (network; not for CI)",
    )
    ap.add_argument("--width", type=int, default=64, help="Grid width (default 64)")
    ap.add_argument("--height", type=int, default=40, help="Grid height (default 40)")
    ap.add_argument("--out", "-o", type=Path, default=None, help="Write JSON chunk path")
    ap.add_argument("--txt", type=Path, default=None, help="Also write plain ASCII .txt grid")
    ap.add_argument("--preview-only", action="store_true", help="Print grid only, no JSON file")
    args = ap.parse_args(argv)

    real_osm = False
    if args.bbox is not None:
        try:
            raw = fetch_overpass(args.bbox)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            print(f"Overpass fetch failed: {e}", file=sys.stderr)
            print("Falling back to bundled fixture.", file=sys.stderr)
            raw = args.input.read_bytes()
            source = str(args.input)
        else:
            real_osm = True
            source = f"overpass:{args.bbox}"
    else:
        if not args.input.is_file():
            print(f"Missing input: {args.input}", file=sys.stderr)
            return 1
        raw = args.input.read_bytes()
        source = str(args.input.relative_to(REPO_ROOT) if args.input.is_relative_to(REPO_ROOT) else args.input)

    nodes, ways, pois, xml_bounds = parse_osm_xml(raw)
    bounds = infer_bounds(nodes, xml_bounds if args.bbox is None else args.bbox)
    # If live bbox given, prefer that envelope even if XML has its own
    if args.bbox is not None and real_osm:
        bounds = args.bbox

    grid, landmarks = rasterize(nodes, ways, pois, bounds, args.width, args.height)
    chunk = build_chunk(grid, landmarks, bounds, source, real_osm)
    lines = chunk["tiles"]

    print(f"# OSM→ASCII shard  {chunk['width']}x{chunk['height']}  seed={chunk['shard_seed']}")
    print(f"# source={chunk['source']}")
    print(f"# landmarks={chunk['landmarks']}")
    print(f"# attribution: {chunk['attribution']['text']}")
    print()
    for row in lines:
        print(row)

    if args.preview_only:
        return 0

    out = args.out
    if out is None:
        out = Path("/tmp") / f"osm_shard_{chunk['shard_seed']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(chunk, indent=2) + "\n", encoding="utf-8")
    print(f"\n# wrote {out}", file=sys.stderr)

    if args.txt:
        args.txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"# wrote {args.txt}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
