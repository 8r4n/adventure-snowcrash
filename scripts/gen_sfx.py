#!/usr/bin/env python3
"""Generate short original procedural SFX (WAV) for Snowcrash.

Cyberpunk / lo-fi digital blips — stdlib only (wave, struct, math).
Writes into snowcrash/static/sfx/.
"""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "snowcrash" / "static" / "sfx"
RATE = 22050


def _clamp(x: float) -> float:
    return max(-1.0, min(1.0, x))


def write_wav(name: str, samples: list[float], rate: int = RATE) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.wav"
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(
            struct.pack("<h", int(_clamp(s) * 32767)) for s in samples
        )
        w.writeframes(frames)
    return path


def env_adsr(
    i: int,
    n: int,
    a: float = 0.02,
    d: float = 0.08,
    s_level: float = 0.55,
    r: float = 0.25,
) -> float:
    t = i / max(1, n - 1)
    if t < a:
        return t / a
    if t < a + d:
        return 1.0 - (1.0 - s_level) * ((t - a) / d)
    if t < 1.0 - r:
        return s_level
    return s_level * max(0.0, (1.0 - t) / r)


def tone(
    dur: float,
    freq: float,
    amp: float = 0.45,
    wave_kind: str = "sine",
    slide: float = 0.0,
    noise: float = 0.0,
    a: float = 0.02,
    d: float = 0.1,
    s_level: float = 0.5,
    r: float = 0.35,
) -> list[float]:
    n = max(1, int(RATE * dur))
    out: list[float] = []
    phase = 0.0
    # simple LCG for reproducible noise (no random import needed for consistency)
    seed = int(freq * 1000 + dur * 10000) & 0x7FFFFFFF
    for i in range(n):
        t = i / RATE
        f = freq + slide * (i / n)
        phase += 2 * math.pi * f / RATE
        if wave_kind == "square":
            v = 1.0 if math.sin(phase) >= 0 else -1.0
        elif wave_kind == "saw":
            v = ((phase / (2 * math.pi)) % 1.0) * 2.0 - 1.0
        elif wave_kind == "tri":
            v = 2.0 * abs(((phase / (2 * math.pi)) % 1.0) * 2.0 - 1.0) - 1.0
        else:
            v = math.sin(phase)
        if noise > 0:
            seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
            nval = (seed / 0x7FFFFFFF) * 2.0 - 1.0
            v = v * (1.0 - noise) + nval * noise
        e = env_adsr(i, n, a=a, d=d, s_level=s_level, r=r)
        # soft high-freq roll via simple one-pole feel: attenuate late samples slightly
        out.append(amp * e * v * (0.85 + 0.15 * math.sin(t * 40)))
    return out


def noise_burst(
    dur: float,
    amp: float = 0.35,
    band: float = 0.55,
    a: float = 0.01,
    r: float = 0.55,
) -> list[float]:
    n = max(1, int(RATE * dur))
    out: list[float] = []
    seed = 0xC0FFEE ^ int(dur * 1e6)
    prev = 0.0
    for i in range(n):
        seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
        nval = (seed / 0x7FFFFFFF) * 2.0 - 1.0
        # cheap lowpass for softer digital grit
        prev = prev * (1.0 - band) + nval * band
        e = env_adsr(i, n, a=a, d=0.05, s_level=0.4, r=r)
        out.append(amp * e * prev)
    return out


def mix(*parts: list[float]) -> list[float]:
    if not parts:
        return []
    n = max(len(p) for p in parts)
    out = [0.0] * n
    for p in parts:
        for i, v in enumerate(p):
            out[i] += v
    peak = max((abs(x) for x in out), default=1.0) or 1.0
    if peak > 0.95:
        scale = 0.95 / peak
        out = [x * scale for x in out]
    return out


def gen_all() -> dict[str, Path]:
    specs: dict[str, list[float]] = {}

    # soft footstep blip
    specs["step"] = mix(
        tone(0.06, 180, amp=0.22, wave_kind="tri", a=0.01, r=0.5),
        noise_burst(0.05, amp=0.12, band=0.7, r=0.6),
    )

    # wall bump — dull thud + click
    specs["bump"] = mix(
        tone(0.08, 90, amp=0.35, wave_kind="sine", slide=-40, a=0.005, r=0.55),
        tone(0.04, 420, amp=0.18, wave_kind="square", a=0.005, r=0.7),
    )

    # melee — short noise slap + mid blip
    specs["melee"] = mix(
        noise_burst(0.07, amp=0.4, band=0.85, a=0.002, r=0.55),
        tone(0.09, 220, amp=0.28, wave_kind="saw", slide=-120, a=0.005, r=0.5),
    )

    # enemy hurt — descending soft buzz
    specs["hurt"] = tone(
        0.12, 380, amp=0.32, wave_kind="square", slide=-180, noise=0.15, a=0.01, r=0.45
    )

    # enemy kill — digital dissolve
    specs["kill"] = mix(
        tone(0.18, 520, amp=0.3, wave_kind="saw", slide=-400, noise=0.2, a=0.01, r=0.5),
        noise_burst(0.15, amp=0.22, band=0.5, r=0.65),
        tone(0.1, 140, amp=0.2, wave_kind="sine", slide=-60, a=0.02, r=0.5),
    )

    # ranged / hack pulse — neon chirp
    specs["pulse"] = mix(
        tone(0.1, 660, amp=0.35, wave_kind="sine", slide=280, a=0.005, r=0.4),
        tone(0.08, 990, amp=0.18, wave_kind="square", slide=-100, a=0.01, r=0.5, noise=0.05),
    )

    # pickup — bright ascending blip
    specs["pickup"] = mix(
        tone(0.07, 520, amp=0.28, wave_kind="sine", a=0.01, r=0.4),
        tone(0.09, 780, amp=0.22, wave_kind="tri", a=0.04, r=0.45),
    )

    # use / heal — soft upward wash
    specs["use"] = mix(
        tone(0.16, 300, amp=0.28, wave_kind="sine", slide=160, a=0.05, r=0.4),
        tone(0.14, 450, amp=0.15, wave_kind="tri", slide=80, a=0.08, r=0.45),
    )

    # talk / NPC — two soft data chirps
    specs["talk"] = mix(
        tone(0.05, 440, amp=0.22, wave_kind="sine", a=0.01, r=0.5),
        [0.0] * int(RATE * 0.04)
        + tone(0.06, 550, amp=0.2, wave_kind="tri", a=0.01, r=0.5),
    )

    # door — servo hiss + click
    specs["door"] = mix(
        noise_burst(0.1, amp=0.2, band=0.35, a=0.02, r=0.5),
        tone(0.06, 160, amp=0.25, wave_kind="square", slide=40, a=0.01, r=0.5),
        tone(0.04, 720, amp=0.12, wave_kind="sine", a=0.3, r=0.4),
    )

    # win — short major-ish arpeggio
    specs["win"] = mix(
        tone(0.12, 392, amp=0.28, wave_kind="sine", a=0.02, r=0.35),
        [0.0] * int(RATE * 0.08)
        + tone(0.12, 494, amp=0.26, wave_kind="sine", a=0.02, r=0.35),
        [0.0] * int(RATE * 0.16)
        + tone(0.2, 587, amp=0.3, wave_kind="tri", a=0.02, r=0.4),
    )

    # death — descending noise crash
    specs["death"] = mix(
        tone(0.35, 280, amp=0.35, wave_kind="saw", slide=-220, noise=0.35, a=0.02, r=0.55),
        noise_burst(0.3, amp=0.28, band=0.6, a=0.01, r=0.7),
        tone(0.25, 80, amp=0.3, wave_kind="sine", slide=-30, a=0.05, r=0.5),
    )

    # UI click
    specs["click"] = tone(
        0.035, 880, amp=0.22, wave_kind="sine", a=0.005, r=0.55
    )

    paths = {}
    for name, samples in specs.items():
        paths[name] = write_wav(name, samples)
        size = paths[name].stat().st_size
        print(f"  {name}.wav  {size} bytes  ({len(samples)/RATE*1000:.0f} ms)")
    return paths


if __name__ == "__main__":
    print(f"Writing SFX to {OUT}")
    gen_all()
    print("done")
