"""#134 audio inventory — procedural beds + SFX mirror for Godot."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SFX_STATIC = ROOT / "snowcrash" / "static" / "sfx"
SFX_GODOT = ROOT / "godot_client" / "audio" / "sfx"
MUSIC = ROOT / "godot_client" / "audio" / "music"
TRAILER = ROOT / "docs" / "audio" / "trailer-bed-30s.wav"

REQUIRED_SFX = {
    "bump",
    "click",
    "death",
    "door",
    "hurt",
    "kill",
    "melee",
    "pickup",
    "pulse",
    "step",
    "talk",
    "use",
    "win",
    "streetnet_ping",
}


def test_static_sfx_present():
    for name in REQUIRED_SFX - {"streetnet_ping"}:
        assert (SFX_STATIC / f"{name}.wav").is_file(), name


def test_godot_sfx_mirror():
    for name in REQUIRED_SFX:
        p = SFX_GODOT / f"{name}.wav"
        assert p.is_file(), name
        assert p.stat().st_size > 44


def test_music_beds_loopable_length():
    street = MUSIC / "street_ambient.wav"
    ice = MUSIC / "ice_jackin.wav"
    assert street.is_file() and street.stat().st_size > 100_000
    assert ice.is_file() and ice.stat().st_size > 80_000


def test_trailer_bed_15_to_30s():
    import wave

    assert TRAILER.is_file()
    with wave.open(str(TRAILER), "r") as w:
        dur = w.getnframes() / float(w.getframerate())
    assert 15.0 <= dur <= 30.0, dur


def test_bus_layout_and_audio_manager_exist():
    assert (ROOT / "godot_client" / "default_bus_layout.tres").is_file()
    assert (ROOT / "godot_client" / "scripts" / "audio_manager.gd").is_file()
    assert (ROOT / "docs" / "audio.md").is_file()
