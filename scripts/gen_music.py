#!/usr/bin/env python3
"""Generate original loopable music beds + StreetNet ping for Snowcrash (#134).

Neon Metaverse identity — procedural synth only (stdlib wave/struct/math).
MIT-compatible; no copyrighted OSTs or third-party samples.

Writes:
  godot_client/audio/music/street_ambient.wav   (~16s seamless loop)
  godot_client/audio/music/ice_jackin.wav       (~12s seamless loop)
  godot_client/audio/sfx/streetnet_ping.wav     (short juice cue)
  docs/audio/trailer-bed-30s.wav                (15–30s trailer bed for #126)
"""

from __future__ import annotations

import math
import shutil
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MUSIC_OUT = ROOT / "godot_client" / "audio" / "music"
SFX_OUT = ROOT / "godot_client" / "audio" / "sfx"
STATIC_SFX = ROOT / "snowcrash" / "static" / "sfx"
DOCS_AUDIO = ROOT / "docs" / "audio"
RATE = 22050


def _clamp(x: float) -> float:
    return max(-1.0, min(1.0, x))


def write_wav(path: Path, samples: list[float], rate: int = RATE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(
            struct.pack("<h", int(_clamp(s) * 32767)) for s in samples
        )
        w.writeframes(frames)
    return path


def _lcg(seed: int) -> int:
    return (1103515245 * seed + 12345) & 0x7FFFFFFF


def soft_noise(n: int, seed: int, band: float = 0.15) -> list[float]:
    out: list[float] = []
    prev = 0.0
    s = seed
    for _ in range(n):
        s = _lcg(s)
        nval = (s / 0x7FFFFFFF) * 2.0 - 1.0
        prev = prev * (1.0 - band) + nval * band
        out.append(prev)
    return out


def sine_at(i: int, freq: float, rate: int = RATE) -> float:
    return math.sin(2.0 * math.pi * freq * i / rate)


def tri_at(i: int, freq: float, rate: int = RATE) -> float:
    p = (freq * i / rate) % 1.0
    return 2.0 * abs(2.0 * p - 1.0) - 1.0


def saw_at(i: int, freq: float, rate: int = RATE) -> float:
    p = (freq * i / rate) % 1.0
    return p * 2.0 - 1.0


def normalize(samples: list[float], peak: float = 0.88) -> list[float]:
    m = max((abs(x) for x in samples), default=1.0) or 1.0
    scale = peak / m
    return [x * scale for x in samples]


def crossfade_loop(samples: list[float], fade_ms: float = 80.0) -> list[float]:
    """Make a clip loop-friendly by crossfading ends."""
    n = len(samples)
    fade = min(n // 4, max(1, int(RATE * fade_ms / 1000.0)))
    out = list(samples)
    for i in range(fade):
        t = i / fade
        a = out[i]
        b = out[n - fade + i]
        out[i] = a * t + b * (1.0 - t)
        out[n - fade + i] = b * t + a * (1.0 - t)
    return out


def street_ambient(dur: float = 16.0) -> list[float]:
    """Rainy neon street bed — low drone + soft pulse + sparse arpeggio."""
    n = int(RATE * dur)
    noise = soft_noise(n, 0x51EE7, band=0.08)
    # A minor-ish: A2, E3, C4, G3 — cyber dusk
    root, fifth, third, seventh = 110.0, 164.81, 261.63, 196.0
    bpm = 72.0
    beat = RATE * 60.0 / bpm
    out = [0.0] * n
    for i in range(n):
        t = i / RATE
        # slow LFO for breath
        lfo = 0.55 + 0.45 * math.sin(2.0 * math.pi * 0.07 * t)
        drone = (
            0.22 * sine_at(i, root)
            + 0.12 * sine_at(i, root * 2.01)
            + 0.08 * tri_at(i, fifth * 0.5)
        )
        # soft sidechain pulse every beat
        pulse_env = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(2.0 * math.pi * i / beat))
        pad = 0.10 * sine_at(i, third * 0.5) * lfo
        # sparse high pluck on 2 & 4
        bar = (i / beat) % 4.0
        pluck = 0.0
        if 1.0 <= bar < 1.12 or 3.0 <= bar < 3.1:
            local = (bar % 1.0)
            env = math.exp(-local * 18.0)
            pluck = 0.14 * sine_at(i, seventh * 2) * env
        rain = 0.04 * noise[i]
        out[i] = (drone * pulse_env + pad + pluck + rain) * 0.85
    return crossfade_loop(normalize(out, 0.72))


def ice_jackin(dur: float = 12.0) -> list[float]:
    """Jack-in / ICE bed — colder, faster digital grit."""
    n = int(RATE * dur)
    noise = soft_noise(n, 0x1CE, band=0.35)
    # colder fifths: D3 / A3 / F#4
    f1, f2, f3 = 146.83, 220.0, 369.99
    bpm = 96.0
    beat = RATE * 60.0 / bpm
    out = [0.0] * n
    for i in range(n):
        t = i / RATE
        lfo = 0.5 + 0.5 * math.sin(2.0 * math.pi * 0.11 * t)
        grit = 0.06 * noise[i]
        # detuned saw pad
        pad = (
            0.16 * saw_at(i, f1)
            + 0.12 * saw_at(i, f1 * 1.005)
            + 0.10 * sine_at(i, f2)
        ) * (0.6 + 0.4 * lfo)
        # ICE alarm chirp every 2 beats
        bar = (i / beat) % 2.0
        chirp = 0.0
        if bar < 0.18:
            env = math.exp(-bar * 14.0)
            chirp = 0.18 * sine_at(i, f3 + 80.0 * bar) * env
        # data tick 16ths
        tick = 0.0
        sixteenth = beat / 4.0
        if (i % int(sixteenth)) < int(RATE * 0.012):
            tick = 0.05 * sine_at(i, 880.0)
        out[i] = pad * 0.9 + grit + chirp + tick
    return crossfade_loop(normalize(out, 0.78))


def streetnet_ping() -> list[float]:
    """Soft dual-tone ping for StreetNet / RTT juice."""
    n = int(RATE * 0.14)
    out: list[float] = []
    for i in range(n):
        t = i / RATE
        env = math.exp(-t * 22.0)
        v = 0.28 * sine_at(i, 740.0) + 0.18 * sine_at(i, 1110.0)
        out.append(v * env)
    return normalize(out, 0.7)


def trailer_bed(dur: float = 24.0) -> list[float]:
    """15–30s non-loop store/trailer bed — street → ICE swell → resolve."""
    n = int(RATE * dur)
    street = street_ambient(dur)
    ice = ice_jackin(dur)
    # morph: street first third, blend middle, ice last third, soft resolve
    out = [0.0] * n
    for i in range(n):
        u = i / max(1, n - 1)
        if u < 0.35:
            w = 0.0
        elif u < 0.55:
            w = (u - 0.35) / 0.20
        elif u < 0.82:
            w = 1.0
        else:
            # resolve back toward street drone + fade
            w = 1.0 - (u - 0.82) / 0.18
        fade = 1.0
        if u < 0.04:
            fade = u / 0.04
        elif u > 0.92:
            fade = (1.0 - u) / 0.08
        out[i] = (street[i] * (1.0 - w) + ice[i] * w) * fade
        # end chime (win-ish)
        if u > 0.88:
            local = (u - 0.88) / 0.12
            env = math.exp(-local * 4.0) * (0.3 + 0.7 * (1.0 - local))
            out[i] += 0.2 * sine_at(i, 392.0) * env
            out[i] += 0.15 * sine_at(i, 587.0) * env
    return normalize(out, 0.8)


def sync_static_sfx() -> None:
    """Mirror web procedural SFX into Godot audio tree."""
    SFX_OUT.mkdir(parents=True, exist_ok=True)
    if not STATIC_SFX.is_dir():
        return
    for src in sorted(STATIC_SFX.glob("*.wav")):
        dst = SFX_OUT / src.name
        shutil.copy2(src, dst)
        print(f"  sync sfx {src.name}")


def main() -> None:
    print("Syncing static SFX → godot_client/audio/sfx/")
    sync_static_sfx()

    print(f"Writing music to {MUSIC_OUT}")
    street = street_ambient(16.0)
    ice = ice_jackin(12.0)
    p_street = write_wav(MUSIC_OUT / "street_ambient.wav", street)
    p_ice = write_wav(MUSIC_OUT / "ice_jackin.wav", ice)
    print(f"  {p_street.name}  {p_street.stat().st_size} bytes  ({len(street)/RATE:.1f}s)")
    print(f"  {p_ice.name}  {p_ice.stat().st_size} bytes  ({len(ice)/RATE:.1f}s)")

    ping = streetnet_ping()
    p_ping = write_wav(SFX_OUT / "streetnet_ping.wav", ping)
    print(f"  {p_ping.name}  {p_ping.stat().st_size} bytes  ({len(ping)/RATE*1000:.0f} ms)")

    print(f"Writing trailer bed to {DOCS_AUDIO}")
    bed = trailer_bed(24.0)
    p_bed = write_wav(DOCS_AUDIO / "trailer-bed-30s.wav", bed)
    # also mirror under godot_client for editor convenience / #126
    p_bed2 = write_wav(MUSIC_OUT / "trailer_bed_24s.wav", bed)
    print(f"  {p_bed.name}  {p_bed.stat().st_size} bytes  ({len(bed)/RATE:.1f}s)")
    print(f"  {p_bed2.name}  (mirror)")
    print("done — original MIT procedural audio (#134)")


if __name__ == "__main__":
    main()
