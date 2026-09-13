# Audio & music — attribution / license

Issue **#134** (parent Steam quality bar **#130**; Godot polish **#118**). Trailer bed also feeds store/demo work **#126**.

## License

All audio under this tree is **original procedural synthesis**, generated in-repo with stdlib Python (`scripts/gen_sfx.py`, `scripts/gen_music.py`). No third-party sample packs, no commercial OSTs, no copyrighted stems.

Same terms as the project **MIT** license ([LICENSE](../LICENSE)): free to use, modify, and redistribute with attribution to the adventure-snowcrash project / 8r4n.

## Inventory

### SFX (`snowcrash/static/sfx/` · mirrored `godot_client/audio/sfx/`)

| Cue | Role |
|-----|------|
| `click` | UI confirm / mute unmute |
| `step` / `bump` / `door` | Locomotion |
| `melee` / `hurt` / `kill` / `pulse` | Combat / hack |
| `pickup` / `use` / `talk` | Interact |
| `death` / `win` | Flatline / Payload-Zero uplink deliver |
| `streetnet_ping` | StreetNet chat / rare RTT juice (**#134**) |

Regenerate: `python scripts/gen_sfx.py` then `python scripts/gen_music.py` (music script re-syncs static → Godot).

### Music beds (`godot_client/audio/music/`)

| File | Role |
|------|------|
| `street_ambient.wav` | ~16s seamless loop — rainy neon street |
| `ice_jackin.wav` | ~12s seamless loop — jack-in / ICE / heist |
| `trailer_bed_24s.wav` | Non-loop 24s street→ICE→resolve (editor mirror) |

### Trailer clip

| File | Role |
|------|------|
| [`docs/audio/trailer-bed-30s.wav`](audio/trailer-bed-30s.wav) | **24s** bed for Steam trailer / #126 store page (under 30s cap) |

## Godot wiring

- **Buses:** Master → SFX, Music (`godot_client/default_bus_layout.tres`)
- **Autoload:** `AudioManager` (`godot_client/scripts/audio_manager.gd`) — PCM WAV loader, mute, volume, juice
- **Persistence:** `user://snowcrash_client.cfg` section `[audio]` (same ConfigFile as onboarding `#133`)
- **UI:** Mute button · **M** key · Audio panel Master/SFX/Music sliders
- **Events:** snapshot `sfx[]`, death/win edges, uplink deliver, StreetNet chat ping, jack-in pulse; music bed swaps on `cyberspace` / `heist`

## Non-goals

Full adaptive score, voice acting, ripping commercial OSTs.
