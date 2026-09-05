#!/usr/bin/env python3
"""Generate original procedural cyberpunk intro MP4 for Snowcrash.

No copyrighted footage — synthetic neon grids, city silhouettes, glitch, rain.
Requires Pillow + ffmpeg. Writes snowcrash/static/cutscenes/intro/montage.mp4
"""

from __future__ import annotations

import math
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    print("Pillow required: pip install pillow", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "snowcrash" / "static" / "cutscenes" / "intro"
OUT_MP4 = OUT_DIR / "montage.mp4"

W, H = 960, 540
FPS = 15
DURATION = 26.0  # seconds
N_FRAMES = int(DURATION * FPS)


def clamp(v, lo=0, hi=255):
    return max(lo, min(hi, int(v)))


def neon(r, g, b, a=255):
    return (clamp(r), clamp(g), clamp(b), clamp(a))


def lerp(a, b, t):
    return a + (b - a) * t


def scene_id(t: float) -> int:
    # 0 grid rain, 1 skyline, 2 datastream, 3 tunnel glitch, 4 title pulse
    if t < 5.5:
        return 0
    if t < 11.0:
        return 1
    if t < 16.5:
        return 2
    if t < 21.5:
        return 3
    return 4


def draw_noise(img: Image.Image, amount: float, rng: random.Random):
    px = img.load()
    n = int(W * H * amount)
    for _ in range(n):
        x = rng.randrange(W)
        y = rng.randrange(H)
        v = rng.randint(0, 80)
        r, g, b, a = px[x, y]
        px[x, y] = (clamp(r + v), clamp(g + v // 2), clamp(b + v), a)


def draw_scanlines(draw: ImageDraw.ImageDraw, t: float):
    for y in range(0, H, 3):
        a = 18 + int(8 * math.sin(y * 0.08 + t * 6))
        draw.line([(0, y), (W, y)], fill=neon(0, 0, 0, a), width=1)


def draw_grid(draw: ImageDraw.ImageDraw, t: float, vanishing=(W // 2, int(H * 0.42))):
    vx, vy = vanishing
    # horizon
    draw.rectangle([0, 0, W, vy], fill=neon(8, 12, 28, 255))
    draw.rectangle([0, vy, W, H], fill=neon(4, 6, 14, 255))
    # perspective floor grid
    for i in range(1, 18):
        y = vy + int((H - vy) * (i / 18) ** 1.6)
        pulse = 0.5 + 0.5 * math.sin(t * 3 + i * 0.4)
        col = neon(20 + 60 * pulse, 180 * pulse, 200, 200)
        draw.line([(0, y), (W, y)], fill=col, width=1)
    for i in range(-20, 21):
        x0 = vx + i * 28
        col = neon(255, 40, 120, 90 + abs(i) % 40)
        draw.line([(x0, H), (vx, vy)], fill=col, width=1)
    # vertical neon pillars
    for i in range(-6, 7):
        x = vx + i * 70 + int(12 * math.sin(t * 2 + i))
        h = 40 + abs(i) * 8
        draw.rectangle([x - 2, vy - h, x + 2, vy], fill=neon(57, 220, 230, 180))


def draw_rain(draw: ImageDraw.ImageDraw, t: float, rng: random.Random):
    for i in range(120):
        x = (i * 97 + int(t * 180)) % W
        y = (i * 53 + int(t * 420 + i * 13)) % H
        length = 8 + (i % 7)
        draw.line([(x, y), (x - 2, y + length)], fill=neon(120, 200, 255, 70), width=1)


def draw_skyline(draw: ImageDraw.ImageDraw, t: float):
    # sky gradient baked as bands
    for y in range(H):
        u = y / H
        r = lerp(6, 40, u)
        g = lerp(4, 10, u)
        b = lerp(18, 50, u)
        if u < 0.35:
            r = lerp(10, 80, u / 0.35)
            g = lerp(5, 20, u / 0.35)
            b = lerp(30, 60, u / 0.35)
        draw.line([(0, y), (W, y)], fill=neon(r, g, b, 255))
    # buildings
    rng = random.Random(42)
    x = 0
    while x < W:
        bw = rng.randint(28, 70)
        bh = rng.randint(80, 320)
        base = H - 40
        top = base - bh
        draw.rectangle([x, top, x + bw, base], fill=neon(8, 10, 18, 255))
        # windows
        for wy in range(top + 8, base - 8, 14):
            for wx in range(x + 4, x + bw - 4, 10):
                if rng.random() < 0.55:
                    flicker = 0.6 + 0.4 * math.sin(t * 5 + wx * 0.1 + wy * 0.05)
                    if (wx + wy) % 3 == 0:
                        c = neon(255 * flicker, 40, 140, 220)
                    else:
                        c = neon(40, 200 * flicker, 220, 200)
                    draw.rectangle([wx, wy, wx + 5, wy + 7], fill=c)
        # neon sign strip
        if rng.random() < 0.4:
            draw.rectangle(
                [x + 4, top + 20, x + bw - 4, top + 28],
                fill=neon(255, 30 + 40 * math.sin(t * 4), 100, 230),
            )
        x += bw + rng.randint(2, 10)
    # ground reflection
    draw.rectangle([0, H - 40, W, H], fill=neon(5, 8, 16, 255))
    for i in range(0, W, 6):
        draw.line(
            [(i, H - 40), (i + int(10 * math.sin(t + i * 0.05)), H)],
            fill=neon(40, 160, 180, 40),
            width=1,
        )


def draw_datastream(img: Image.Image, draw: ImageDraw.ImageDraw, t: float, rng: random.Random):
    draw.rectangle([0, 0, W, H], fill=neon(4, 6, 12, 255))
    # cascading glyphs as bright blocks
    glyphs = "01アイウエカキクケコ∑∂∞≈≠≤≥#@$%&*"
    for col in range(0, W, 14):
        speed = 40 + (col * 7) % 90
        offset = int(t * speed + col * 3) % (H + 80)
        for k in range(18):
            y = (offset + k * 16) % (H + 40) - 20
            bright = max(0.15, 1.0 - k / 18)
            ch_i = (col // 14 + k + int(t * 10)) % len(glyphs)
            # draw as colored rect "glyph stand-in"
            g = glyphs[ch_i]
            if (col // 14 + k) % 5 == 0:
                c = neon(255 * bright, 50 * bright, 160 * bright, 255)
            else:
                c = neon(30 * bright, 220 * bright, 200 * bright, 255)
            draw.rectangle([col, y, col + 10, y + 12], fill=c)
            # tiny accent
            if k == 0:
                draw.rectangle([col, y, col + 10, y + 12], fill=neon(220, 255, 255, 255))
    # glitch bars
    for _ in range(4):
        y = rng.randint(0, H - 12)
        h = rng.randint(2, 14)
        shift = rng.randint(-40, 40)
        region = img.crop((0, y, W, y + h))
        img.paste(region, (shift, y))


def draw_tunnel(draw: ImageDraw.ImageDraw, t: float):
    draw.rectangle([0, 0, W, H], fill=neon(2, 2, 6, 255))
    cx, cy = W // 2, H // 2
    max_r = int(math.hypot(cx, cy))
    for i in range(28, 0, -1):
        r = int(max_r * (i / 28) * (0.55 + 0.45 * ((t * 1.8) % 1)))
        pulse = (i + int(t * 12)) % 5
        if pulse == 0:
            c = neon(255, 40, 120, 200)
        elif pulse == 1:
            c = neon(40, 220, 230, 180)
        else:
            c = neon(10 + i * 2, 14, 30 + i, 255)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=c, width=2)
    # center payload core
    core = 18 + int(10 * math.sin(t * 8))
    draw.ellipse([cx - core, cy - core, cx + core, cy + core], fill=neon(255, 60, 140, 255))
    draw.ellipse(
        [cx - core // 2, cy - core // 2, cx + core // 2, cy + core // 2],
        fill=neon(240, 240, 255, 255),
    )


def draw_title_pulse(draw: ImageDraw.ImageDraw, t: float):
    draw.rectangle([0, 0, W, H], fill=neon(5, 8, 14, 255))
    # radial burst
    cx, cy = W // 2, H // 2
    for i in range(40):
        ang = i * (math.pi * 2 / 40) + t * 1.5
        r = 80 + 200 * (0.5 + 0.5 * math.sin(t * 3 + i))
        x2 = cx + int(math.cos(ang) * r)
        y2 = cy + int(math.sin(ang) * r)
        c = neon(40, 200, 220, 100) if i % 2 == 0 else neon(255, 40, 120, 100)
        draw.line([(cx, cy), (x2, y2)], fill=c, width=2)
    # big block letters as rectangles (SNOWCRASH silhouette)
    letters = [
        (0.12, 0.38, 0.08, 0.24),  # S-ish
        (0.22, 0.38, 0.08, 0.24),
        (0.32, 0.38, 0.08, 0.24),
        (0.42, 0.38, 0.08, 0.24),
        (0.52, 0.38, 0.08, 0.24),
        (0.62, 0.38, 0.08, 0.24),
        (0.72, 0.38, 0.08, 0.24),
        (0.82, 0.38, 0.08, 0.24),
    ]
    pulse = 0.7 + 0.3 * math.sin(t * 6)
    for lx, ly, lw, lh in letters:
        x0, y0 = int(lx * W), int(ly * H)
        x1, y1 = int((lx + lw) * W), int((ly + lh) * H)
        draw.rectangle(
            [x0, y0, x1, y1],
            fill=neon(40 * pulse, 220 * pulse, 230 * pulse, 255),
            outline=neon(255, 50, 140, 255),
            width=2,
        )
    # floor glow
    draw.ellipse(
        [cx - 200, H - 80, cx + 200, H - 10],
        fill=neon(20, 80, 100, 80),
    )


def render_frame(i: int) -> Image.Image:
    t = i / FPS
    rng = random.Random(i * 9973 + 13)
    img = Image.new("RGBA", (W, H), neon(4, 6, 12, 255))
    draw = ImageDraw.Draw(img, "RGBA")
    sid = scene_id(t)

    if sid == 0:
        draw_grid(draw, t)
        draw_rain(draw, t, rng)
    elif sid == 1:
        draw_skyline(draw, t)
        draw_rain(draw, t, rng)
    elif sid == 2:
        draw_datastream(img, draw, t, rng)
    elif sid == 3:
        draw_tunnel(draw, t)
        if rng.random() < 0.35:
            # chromatic tear
            y = rng.randint(0, H - 20)
            draw.rectangle([0, y, W, y + rng.randint(4, 18)], fill=neon(255, 0, 80, 60))
    else:
        draw_title_pulse(draw, t)

    draw_scanlines(draw, t)
    draw_noise(img, 0.004, rng)

    # vignette
    vig = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vig)
    for r in range(0, 180, 8):
        a = int(r * 0.7)
        vd.rectangle([r, r, W - r, H - r], outline=(0, 0, 0, a))
    img = Image.alpha_composite(img, vig)

    # slight blur on fast motion scenes
    if sid in (2, 3):
        img = img.filter(ImageFilter.GaussianBlur(radius=0.6))

    return img.convert("RGB")


def main():
    if not shutil.which("ffmpeg"):
        print("ffmpeg not found on PATH", file=sys.stderr)
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="snowcrash-intro-") as tmp:
        tmp_path = Path(tmp)
        print(f"Rendering {N_FRAMES} frames @ {FPS}fps ({W}x{H})…")
        for i in range(N_FRAMES):
            frame = render_frame(i)
            frame.save(tmp_path / f"frame_{i:05d}.png", optimize=True)
            if i % 30 == 0:
                print(f"  frame {i}/{N_FRAMES}")

        cmd = [
            "ffmpeg",
            "-y",
            "-framerate",
            str(FPS),
            "-i",
            str(tmp_path / "frame_%05d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-profile:v",
            "baseline",
            "-level",
            "3.0",
            "-crf",
            "23",
            "-movflags",
            "+faststart",
            "-an",
            str(OUT_MP4),
        ]
        print("Encoding", OUT_MP4, "…")
        subprocess.check_call(cmd)
        size = OUT_MP4.stat().st_size
        print(f"Wrote {OUT_MP4} ({size // 1024} KiB)")

    # tiny manifest for the web client
    manifest = OUT_DIR / "manifest.json"
    manifest.write_text(
        '{\n  "montage": "montage.mp4",\n  "duration": %.1f,\n  "fps": %d,\n  "note": "Original procedural cyberpunk footage — no copyrighted media."\n}\n'
        % (DURATION, FPS),
        encoding="utf-8",
    )
    print("Wrote", manifest)


if __name__ == "__main__":
    main()
