#!/usr/bin/env python3
"""Generate short procedural jack-in MP4s for Snowcrash cutscenes.

Each clip is original neon/cyberpunk motion — sampled by VideoAsciiCanvas
like the intro. Falls back to JSON packs if ffmpeg/Pillow missing at build time.
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
    from PIL import Image, ImageDraw
except ImportError:
    print("Pillow required: pip install pillow", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "snowcrash" / "static" / "cutscenes"

W, H = 640, 360
FPS = 12
DURATION = 1.8
N_FRAMES = int(DURATION * FPS)

SCENES = {
    "jackpoint": {"hue": (40, 200, 220), "accent": (255, 42, 109), "label": "JACK"},
    "uplink": {"hue": (61, 214, 140), "accent": (57, 197, 207), "label": "UPLINK"},
    "talk": {"hue": (210, 168, 255), "accent": (57, 197, 207), "label": "COMM"},
    "payload": {"hue": (240, 180, 41), "accent": (255, 42, 109), "label": "PAYLOAD"},
    "terminal": {"hue": (57, 197, 207), "accent": (240, 180, 41), "label": "TERM"},
    "door": {"hue": (240, 180, 41), "accent": (57, 197, 207), "label": "DOOR"},
}


def clamp(v, lo=0, hi=255):
    return max(lo, min(hi, int(v)))


def render_frame(scene: dict, i: int) -> Image.Image:
    t = i / FPS
    rng = random.Random(i * 7919 + hash(scene["label"]) % 9973)
    img = Image.new("RGB", (W, H), (5, 8, 12))
    draw = ImageDraw.Draw(img)
    hr, hg, hb = scene["hue"]
    ar, ag, ab = scene["accent"]

    # tunnel / iris
    cx, cy = W // 2, H // 2
    for r in range(220, 20, -8):
        pulse = 0.6 + 0.4 * math.sin(t * 8 + r * 0.05)
        col = (
            clamp(hr * pulse * (r / 220)),
            clamp(hg * pulse * (r / 220)),
            clamp(hb * pulse * (r / 220)),
        )
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=2)

    # converging grid
    for k in range(-8, 9):
        x = cx + int(k * 18 * (1 + 0.3 * math.sin(t * 4)))
        draw.line([(x, 0), (cx, cy)], fill=(hr // 3, hg // 3, hb // 3), width=1)
        draw.line([(x, H), (cx, cy)], fill=(hr // 3, hg // 3, hb // 3), width=1)

    # data bars
    for b in range(12):
        bh = 10 + int(40 * abs(math.sin(t * 6 + b)))
        x0 = 20 + b * (W - 40) // 12
        draw.rectangle(
            [x0, H - 30 - bh, x0 + 18, H - 20],
            fill=(clamp(ar * 0.8), clamp(ag * 0.8), clamp(ab * 0.8)),
        )

    # center glyph block
    label = scene["label"]
    block_w = 18 * len(label)
    x0 = cx - block_w // 2
    y0 = cy - 18
    for li, ch in enumerate(label):
        draw.rectangle(
            [x0 + li * 18, y0, x0 + li * 18 + 14, y0 + 28],
            fill=(ar, ag, ab),
            outline=(hr, hg, hb),
            width=1,
        )

    # scanlines
    for y in range(0, H, 3):
        a = 30 + int(10 * math.sin(y * 0.1 + t * 5))
        draw.line([(0, y), (W, y)], fill=(0, 0, 0), width=1)

    # noise
    px = img.load()
    for _ in range(int(W * H * 0.004)):
        x = rng.randrange(W)
        y = rng.randrange(H)
        v = rng.randint(0, 60)
        r, g, b = px[x, y]
        px[x, y] = (clamp(r + v), clamp(g + v // 2), clamp(b + v))

    return img


def encode(id_: str, scene: dict) -> Path:
    out = OUT_DIR / f"{id_}.mp4"
    with tempfile.TemporaryDirectory(prefix=f"sc-cut-{id_}-") as tmp:
        tmp_path = Path(tmp)
        for i in range(N_FRAMES):
            render_frame(scene, i).save(tmp_path / f"frame_{i:04d}.png")
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(FPS),
            "-i", str(tmp_path / "frame_%04d.png"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "28",
            "-movflags", "+faststart",
            str(out),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
    return out


def main():
    if not shutil.which("ffmpeg"):
        print("ffmpeg not found", file=sys.stderr)
        sys.exit(1)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for id_, scene in SCENES.items():
        print(f"Rendering {id_}…")
        path = encode(id_, scene)
        print(f"  → {path} ({path.stat().st_size} bytes)")
    print("Done.")


if __name__ == "__main__":
    main()
