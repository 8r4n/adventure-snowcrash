#!/usr/bin/env python3
"""Bake first-person ASCII cutscene packs for Snowcrash (web).

Procedurally renders short cyberpunk "video" frames (stdlib + optional Pillow),
converts each frame to ASCII, and writes JSON packs under
snowcrash/static/cutscenes/. Runtime needs no OpenCV/ffmpeg.

Regenerate:
  python scripts/gen_cutscenes.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "snowcrash" / "static" / "cutscenes"
COLS = 72
ROWS = 22
FPS = 10
ASCII = " .'-:;=~+*#%@"


def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def to_ascii(buf: list[list[float]], cols: int, rows: int) -> str:
    lines = []
    n = len(ASCII) - 1
    for y in range(rows):
        row = []
        for x in range(cols):
            v = clamp01(buf[y][x])
            # gamma-ish so dark stays dark (lo-fi CRT)
            v = v ** 1.35
            row.append(ASCII[int(v * n + 1e-6)])
        lines.append("".join(row))
    return "\n".join(lines)


def blank(cols: int, rows: int, v: float = 0.0) -> list[list[float]]:
    return [[v] * cols for _ in range(rows)]


def add_px(buf: list[list[float]], x: int, y: int, v: float) -> None:
    rows = len(buf)
    cols = len(buf[0])
    if 0 <= x < cols and 0 <= y < rows:
        buf[y][x] = clamp01(buf[y][x] + v)


def draw_rect(buf, x0, y0, x1, y1, v, fill=True):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            if fill or x in (x0, x1) or y in (y0, y1):
                add_px(buf, x, y, v)


def draw_line(buf, x0, y0, x1, y1, v):
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    while True:
        add_px(buf, x, y, v)
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy


def noise(seed: int, x: int, y: int) -> float:
    n = (seed * 374761393 + x * 668265263 + y * 2147483647) & 0x7FFFFFFF
    return (n % 10000) / 10000.0


# ---- Scene generators (t in [0,1]) ----

def scene_jackpoint(t: float, cols: int, rows: int) -> list[list[float]]:
    """Corridor dive into a glowing jack socket."""
    buf = blank(cols, rows, 0.05)
    cx, cy = cols // 2, rows // 2
    # perspective corridor walls
    depth = 0.15 + 0.85 * t
    for y in range(rows):
        for x in range(cols):
            nx = (x - cx) / max(1, cx)
            ny = (y - cy) / max(1, cy)
            # tunnel radius shrinks with depth
            r = math.sqrt(nx * nx + ny * ny * 1.4)
            wall = clamp01((r - (0.95 - 0.55 * depth)) * 4)
            scan = 0.08 * math.sin(y * 1.7 + t * 18)
            buf[y][x] = clamp01(0.08 + wall * 0.55 + scan)
    # vanishing socket
    rad = max(1, int(3 + 10 * (1 - t)))
    for y in range(cy - rad, cy + rad + 1):
        for x in range(cx - rad, cx + rad + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= rad * rad:
                add_px(buf, x, y, 0.55 + 0.4 * t)
    # HUD brackets
    m = 2
    draw_rect(buf, m, m, cols - 1 - m, rows - 1 - m, 0.35, fill=False)
    draw_rect(buf, m + 2, m + 2, cols - 3 - m, rows - 3 - m, 0.2, fill=False)
    # progress bar
    bw = int((cols - 10) * t)
    draw_rect(buf, 5, rows - 3, 5 + bw, rows - 2, 0.7 + 0.2 * math.sin(t * 20))
    # digital snow near end
    if t > 0.7:
        for y in range(rows):
            for x in range(cols):
                if noise(42, x + int(t * 50), y) > 0.92:
                    buf[y][x] = 1.0
    return buf


def scene_uplink(t: float, cols: int, rows: int) -> list[list[float]]:
    """Rising data lattice / Metaverse scrub."""
    buf = blank(cols, rows, 0.04)
    cx = cols // 2
    # rising columns of glyphs-as-brightness
    for x in range(0, cols, 3):
        phase = noise(7, x, 0) * 6.28
        h = int(rows * (0.3 + 0.7 * ((math.sin(t * 8 + phase) + 1) * 0.5)))
        for y in range(rows - h, rows):
            v = 0.25 + 0.55 * ((y - (rows - h)) / max(1, h))
            add_px(buf, x, y, v)
            add_px(buf, x + 1, y, v * 0.6)
    # central uplink diamond
    for i in range(int(4 + 10 * t)):
        draw_line(buf, cx, rows // 2 - i, cx + i, rows // 2, 0.8)
        draw_line(buf, cx, rows // 2 - i, cx - i, rows // 2, 0.8)
        draw_line(buf, cx, rows // 2 + i, cx + i, rows // 2, 0.7)
        draw_line(buf, cx, rows // 2 + i, cx - i, rows // 2, 0.7)
    # horizon wipe
    wipe = int(rows * t)
    for y in range(0, wipe):
        for x in range(cols):
            buf[y][x] = clamp01(buf[y][x] * 0.3 + 0.15)
    draw_rect(buf, 1, 1, cols - 2, rows - 2, 0.25, fill=False)
    return buf


def scene_talk(t: float, cols: int, rows: int) -> list[list[float]]:
    """Close-up avatar mask + subtitle bar."""
    buf = blank(cols, rows, 0.06)
    cx, cy = cols // 2, rows // 2 - 1
    # face oval
    for y in range(rows):
        for x in range(cols):
            nx = (x - cx) / 14.0
            ny = (y - cy) / 9.0
            if nx * nx + ny * ny < 1.0:
                buf[y][x] = 0.25 + 0.15 * math.sin(t * 6)
            if nx * nx + ny * ny < 0.15:
                buf[y][x] = 0.75  # visor glow
    # eyes
    blink = 0.0 if (0.45 < (t % 1.0) < 0.52) else 1.0
    add_px(buf, cx - 5, cy - 1, 0.9 * blink)
    add_px(buf, cx + 5, cy - 1, 0.9 * blink)
    # waveform mouth
    for x in range(cx - 8, cx + 9):
        yy = cy + 3 + int(2 * math.sin(x * 0.7 + t * 22))
        add_px(buf, x, yy, 0.85)
    # subtitle bar
    draw_rect(buf, 4, rows - 5, cols - 5, rows - 2, 0.18)
    draw_rect(buf, 4, rows - 5, cols - 5, rows - 2, 0.45, fill=False)
    # typing cursor
    cur = 4 + int((cols - 12) * min(1.0, t * 1.4))
    draw_rect(buf, 6, rows - 4, cur, rows - 3, 0.7)
    return buf


def scene_payload(t: float, cols: int, rows: int) -> list[list[float]]:
    """Faraday sleeve open / linguistic core pulse."""
    buf = blank(cols, rows, 0.05)
    cx, cy = cols // 2, rows // 2
    # sleeve shell
    open_amt = clamp01(t * 1.3)
    left = cx - int(18 + 8 * open_amt)
    right = cx + int(18 + 8 * open_amt)
    draw_rect(buf, left, cy - 6, cx - int(4 + 10 * open_amt), cy + 6, 0.35, fill=False)
    draw_rect(buf, cx + int(4 + 10 * open_amt), cy - 6, right, cy + 6, 0.35, fill=False)
    # core
    pulse = 0.5 + 0.5 * math.sin(t * 16)
    rad = int(2 + 5 * pulse * clamp01(t * 2))
    for y in range(cy - rad, cy + rad + 1):
        for x in range(cx - rad, cx + rad + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= rad * rad:
                add_px(buf, x, y, 0.55 + 0.4 * pulse)
    # ripple rings
    for k in range(3):
        rr = int(rad + 2 + k * 3 + t * 8)
        for a in range(0, 360, 8):
            ang = math.radians(a)
            add_px(buf, cx + int(rr * math.cos(ang)), cy + int(rr * 0.55 * math.sin(ang)), 0.35)
    # warning ticks
    for x in range(cols):
        if (x + int(t * 30)) % 7 == 0:
            add_px(buf, x, 1, 0.6)
            add_px(buf, x, rows - 2, 0.6)
    return buf


def scene_terminal(t: float, cols: int, rows: int) -> list[list[float]]:
    """Terminal boot / datachip jack."""
    buf = blank(cols, rows, 0.04)
    # CRT bezel
    draw_rect(buf, 2, 1, cols - 3, rows - 2, 0.2, fill=False)
    # scrolling code rain
    for x in range(4, cols - 4, 2):
        offset = int(noise(99, x, 0) * rows + t * rows * 1.5) % rows
        for i in range(6):
            y = (offset + i) % (rows - 2) + 1
            add_px(buf, x, y, 0.25 + i * 0.1)
    # chip insert bar
    chip_x = int(4 + (cols - 16) * clamp01(t * 1.2))
    draw_rect(buf, chip_x, rows // 2 - 1, chip_x + 8, rows // 2 + 1, 0.85)
    draw_rect(buf, cols - 14, rows // 2 - 2, cols - 5, rows // 2 + 2, 0.4, fill=False)
    if t > 0.75:
        for y in range(3, rows - 3):
            for x in range(4, cols - 4):
                if noise(3, x, y + int(t * 40)) > 0.85:
                    buf[y][x] = 1.0
    return buf


def scene_door(t: float, cols: int, rows: int) -> list[list[float]]:
    """Sliding neon door / room transition."""
    buf = blank(cols, rows, 0.07)
    # door panels sliding apart
    gap = int((cols // 2) * clamp01(t * 1.1))
    left_edge = cols // 2 - gap
    right_edge = cols // 2 + gap
    draw_rect(buf, 0, 0, left_edge, rows - 1, 0.28)
    draw_rect(buf, right_edge, 0, cols - 1, rows - 1, 0.28)
    # neon edges
    for y in range(rows):
        add_px(buf, left_edge, y, 0.9)
        add_px(buf, right_edge, y, 0.9)
        if y % 2 == 0:
            add_px(buf, left_edge - 1, y, 0.5)
            add_px(buf, right_edge + 1, y, 0.5)
    # beyond: grid floor
    for y in range(rows // 2, rows):
        for x in range(left_edge + 1, right_edge):
            if (x + int(t * 10)) % 4 == 0 or y % 3 == 0:
                add_px(buf, x, y, 0.35)
    # ceiling lights
    for x in range(left_edge + 2, right_edge, 6):
        add_px(buf, x, 2, 0.8)
    return buf




def scene_briefing(t: float, cols: int, rows: int) -> list[list[float]]:
    """Archive lattice / librarian briefing scroll."""
    buf = blank(cols, rows, 0.04)
    # scrolling archive columns
    for x in range(3, cols - 3, 4):
        offset = int(noise(11, x, 0) * rows + t * rows * 1.2) % rows
        for i in range(8):
            y = (offset + i) % (rows - 2) + 1
            add_px(buf, x, y, 0.2 + i * 0.08)
    # central tome / daemon mask
    cx, cy = cols // 2, rows // 2 - 1
    draw_rect(buf, cx - 10, cy - 5, cx + 10, cy + 5, 0.35, fill=False)
    for y in range(cy - 3, cy + 4):
        for x in range(cx - 7, cx + 8):
            if noise(5, x + int(t * 20), y) > 0.55:
                add_px(buf, x, y, 0.45)
    # subtitle crawl
    bw = int((cols - 8) * clamp01(t * 1.1))
    draw_rect(buf, 4, rows - 4, 4 + bw, rows - 3, 0.7)
    draw_rect(buf, 2, 1, cols - 3, rows - 2, 0.22, fill=False)
    return buf


def scene_club(t: float, cols: int, rows: int) -> list[list[float]]:
    """Black neon dance floor strobe."""
    buf = blank(cols, rows, 0.05)
    pulse = 0.5 + 0.5 * math.sin(t * 22)
    # floor grid
    for y in range(rows // 2, rows):
        for x in range(cols):
            if (x + int(t * 12)) % 5 == 0 or y % 3 == 0:
                add_px(buf, x, y, 0.25 + 0.35 * pulse)
    # strobe bars
    for i in range(6):
        x = int((i + t * 3) * cols / 6) % cols
        draw_rect(buf, x, 2, min(cols - 1, x + 2), rows // 2, 0.55 + 0.4 * pulse)
    # crowd silhouettes
    for k in range(8):
        cx = 6 + k * (cols - 12) // 8
        h = 3 + int(2 * abs(math.sin(t * 10 + k)))
        draw_rect(buf, cx, rows // 2 - h, cx + 2, rows // 2, 0.6)
    draw_rect(buf, 1, 1, cols - 2, rows - 2, 0.3, fill=False)
    return buf


def scene_flotilla(t: float, cols: int, rows: int) -> list[list[float]]:
    """Radio horizon / refugee flotilla signal."""
    buf = blank(cols, rows, 0.04)
    horizon = rows // 2 + int(2 * math.sin(t * 3))
    for y in range(horizon):
        for x in range(cols):
            buf[y][x] = 0.08 + 0.04 * math.sin(x * 0.2 + t)
    # water chop
    for y in range(horizon, rows):
        for x in range(cols):
            v = 0.12 + 0.2 * abs(math.sin(x * 0.35 + t * 6 + y * 0.2))
            buf[y][x] = v
    # hull silhouettes
    for i, ox in enumerate((cols // 4, cols // 2, 3 * cols // 4)):
        w = 6 + i
        draw_rect(buf, ox - w, horizon - 2 - i, ox + w, horizon, 0.55)
        add_px(buf, ox, horizon - 4 - i, 0.85)  # mast light
    # radio rings
    cx, cy = cols // 2, horizon - 1
    for k in range(int(2 + 5 * t)):
        rr = 3 + k * 2
        for a in range(0, 360, 10):
            ang = math.radians(a)
            add_px(buf, cx + int(rr * math.cos(ang)), cy + int(rr * 0.4 * math.sin(ang)), 0.4)
    draw_rect(buf, 2, 1, cols - 3, rows - 2, 0.25, fill=False)
    return buf


def scene_namshub(t: float, cols: int, rows: int) -> list[list[float]]:
    """Counter-incantation / Babel fracture scrub at uplink."""
    buf = blank(cols, rows, 0.05)
    cx, cy = cols // 2, rows // 2
    # fracturing rings
    for k in range(6):
        rr = int(2 + k * 3 + t * 14)
        crack = 0.4 + 0.5 * math.sin(t * 12 + k)
        for a in range(0, 360, 6):
            ang = math.radians(a + t * 40)
            jitter = int(2 * noise(k + 3, int(a), int(t * 10)))
            add_px(buf, cx + int(rr * math.cos(ang)) + jitter, cy + int(rr * 0.55 * math.sin(ang)), crack)
    # glyph shatter columns
    for x in range(4, cols - 4, 3):
        h = int(rows * (0.2 + 0.8 * ((math.sin(t * 9 + x) + 1) * 0.5)))
        for y in range(rows - h, rows):
            add_px(buf, x, y, 0.3 + 0.4 * (y / rows))
    # clean wipe from top
    wipe = int(rows * clamp01(t * 1.05))
    for y in range(0, wipe):
        for x in range(cols):
            buf[y][x] = clamp01(buf[y][x] * 0.25 + 0.12)
    draw_rect(buf, 1, 1, cols - 2, rows - 2, 0.28, fill=False)
    return buf


def scene_victory(t: float, cols: int, rows: int) -> list[list[float]]:
    """Street victory / cleared babel light."""
    buf = blank(cols, rows, 0.06)
    cx, cy = cols // 2, rows // 2
    pulse = 0.5 + 0.5 * math.sin(t * 8)
    # sunrise wash
    for y in range(rows):
        for x in range(cols):
            u = 1.0 - abs(x - cx) / cx
            v = 1.0 - y / rows
            buf[y][x] = clamp01(0.1 + 0.45 * u * v * (0.6 + 0.4 * pulse) * clamp01(t * 1.2))
    # courier glyph
    draw_rect(buf, cx - 2, cy - 3, cx + 2, cy + 3, 0.85)
    add_px(buf, cx, cy - 5, 0.9)
    # confetti noise
    for y in range(rows):
        for x in range(cols):
            if noise(21, x + int(t * 30), y) > 0.93:
                buf[y][x] = 1.0
    draw_rect(buf, 2, 1, cols - 3, rows - 2, 0.35, fill=False)
    return buf


def scene_babel_clear(t: float, cols: int, rows: int) -> list[list[float]]:
    """Babel clear — quiet lattice after scrub."""
    buf = blank(cols, rows, 0.03)
    for x in range(0, cols, 2):
        for y in range(rows):
            phase = math.sin(t * 4 + x * 0.15 + y * 0.1)
            if phase > 0.2:
                add_px(buf, x, y, 0.15 + 0.35 * phase * clamp01(t + 0.2))
    cx, cy = cols // 2, rows // 2
    rad = int(2 + 8 * clamp01(t))
    for y in range(cy - rad, cy + rad + 1):
        for x in range(cx - rad, cx + rad + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= rad * rad:
                add_px(buf, x, y, 0.55)
    draw_rect(buf, 3, 2, cols - 4, rows - 3, 0.25, fill=False)
    return buf


def scene_wish(t: float, cols: int, rows: int) -> list[list[float]]:
    """Wish granted spark / petition ack."""
    buf = blank(cols, rows, 0.05)
    cx, cy = cols // 2, rows // 2
    # star burst
    for a in range(0, 360, 15):
        ang = math.radians(a + t * 60)
        length = int(4 + 12 * t)
        draw_line(
            buf,
            cx,
            cy,
            cx + int(length * math.cos(ang)),
            cy + int(length * 0.6 * math.sin(ang)),
            0.55 + 0.4 * math.sin(t * 10 + a),
        )
    rad = int(2 + 4 * abs(math.sin(t * 14)))
    for y in range(cy - rad, cy + rad + 1):
        for x in range(cx - rad, cx + rad + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= rad * rad:
                add_px(buf, x, y, 0.9)
    # petition bar
    bw = int((cols - 10) * clamp01(t * 1.3))
    draw_rect(buf, 5, rows - 4, 5 + bw, rows - 3, 0.75)
    return buf


SCENES = {
    "jackpoint": {
        "title": "1ST PERSON — JACKING IN",
        "seconds": 2.2,
        "render": scene_jackpoint,
    },
    "uplink": {
        "title": "1ST PERSON — METAVERSE UPLINK",
        "seconds": 2.4,
        "render": scene_uplink,
    },
    "talk": {
        "title": "1ST PERSON — COMM LINK",
        "seconds": 1.6,
        "render": scene_talk,
    },
    "payload": {
        "title": "1ST PERSON — PAYLOAD ACQUIRED",
        "seconds": 2.0,
        "render": scene_payload,
    },
    "terminal": {
        "title": "1ST PERSON — TERMINAL",
        "seconds": 1.8,
        "render": scene_terminal,
    },
    "door": {
        "title": "1ST PERSON — THRESHOLD",
        "seconds": 1.4,
        "render": scene_door,
    },
    "briefing_librarian": {
        "title": "1ST PERSON — ARCHIVE BRIEFING",
        "seconds": 2.4,
        "render": scene_briefing,
    },
    "club_black_neon": {
        "title": "1ST PERSON — BLACK NEON",
        "seconds": 2.0,
        "render": scene_club,
    },
    "flotilla_signal": {
        "title": "1ST PERSON — FLOTILLA SIGNAL",
        "seconds": 2.2,
        "render": scene_flotilla,
    },
    "namshub_counter": {
        "title": "1ST PERSON — BABEL COUNTER",
        "seconds": 2.6,
        "render": scene_namshub,
    },
    "street_victory": {
        "title": "1ST PERSON — STREET VICTORY",
        "seconds": 2.2,
        "render": scene_victory,
    },
    "babel_clear": {
        "title": "1ST PERSON — BABEL CLEAR",
        "seconds": 2.0,
        "render": scene_babel_clear,
    },
    "wish_granted": {
        "title": "1ST PERSON — WISH GRANTED",
        "seconds": 1.6,
        "render": scene_wish,
    },
}


def bake_one(cid: str, meta: dict, cols: int = COLS, rows: int = ROWS, fps: int = FPS) -> Path:
    nframes = max(8, int(meta["seconds"] * fps))
    frames = []
    for i in range(nframes):
        t = i / max(1, nframes - 1)
        buf = meta["render"](t, cols, rows)
        frames.append(to_ascii(buf, cols, rows))
    pack = {
        "id": cid,
        "title": meta["title"],
        "fps": fps,
        "cols": cols,
        "rows": rows,
        "frame_count": len(frames),
        "frames": frames,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{cid}.json"
    path.write_text(json.dumps(pack, separators=(",", ":")), encoding="utf-8")
    return path


def main() -> None:
    print(f"Baking cutscenes → {OUT}")
    index = []
    for cid, meta in SCENES.items():
        path = bake_one(cid, meta)
        size = path.stat().st_size
        print(f"  {cid}.json  {size} bytes  ({meta['seconds']}s @ {FPS}fps)")
        index.append({"id": cid, "title": meta["title"], "file": f"{cid}.json"})
    (OUT / "index.json").write_text(json.dumps({"cutscenes": index}, indent=2), encoding="utf-8")
    print("done")


if __name__ == "__main__":
    main()
