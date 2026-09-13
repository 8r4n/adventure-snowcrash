# Godot thin client (play loop + docks)

**Godot 4.3+** project that talks to the existing Snowcrash Python MMORPG server over WebSocket. It does **not** simulate the street.

- Research / architecture: [`docs/godot-client.md`](../docs/godot-client.md)
- Implementation epic: GitHub **#118**
- Slice 1 play loop: **#118** · Slice 2 StreetNet + year docks: **#127**
- First 10 minutes onboarding: **#133** — see [`docs/godot-onboarding.md`](../docs/godot-onboarding.md)
- Steam north star: **#130** (Godot is the preferred Steam SKU)
- Steam Deck Verified path: **#132** — see [`docs/steam-deck.md`](../docs/steam-deck.md)

The Godot **editor/binary is not required in this repo**. These files are a valid project — open them in a local Godot 4.x editor.

## Open in Godot Editor

1. Install [Godot 4.3 or newer](https://godotengine.org/download) (4.4.1+ if you later add GodotSteam).
2. Start the **dev** MMORPG server (shared world, port **8766**):

   ```bash
   cd /path/to/adventure-snowcrash   # or the adventure-dev worktree
   source .venv/bin/activate
   ./scripts/run_dev.sh              # → http://127.0.0.1:8766/  and  ws://127.0.0.1:8766/ws
   ```

3. Launch Godot → **Import** → select `godot_client/project.godot`.
4. Press **F5** (Run Project). Main scene is `scenes/main.tscn`.
5. Leave the URL as `ws://127.0.0.1:8766/ws`, enter a courier name, **Jack in**.
6. Status should go `connecting…` → `ONLINE · <player id> · …ms · N online`.
7. Click the view (or anywhere that is not a LineEdit), then play. Use the **dock bar** for year panels; **StreetNet** chat is on the right.

Production server default is port **8765** — change the URL if you point at that process.

## Controls (play loop)

| Input | Intent (same strings as web) |
|-------|------------------------------|
| WASD / arrows | forward / strafe / back (chords → diagonal relative moves) |
| Q / E or ← / → | turn_left / turn_right |
| G | get / pickup |
| F | fire / hack |
| `.` | look (log position) |
| Space | wait (`.`) |
| I | open inventory mode |
| 0–9 | `inv_select` (multi-digit, 420ms commit like web) |
| U / Enter (in inv) | use selected |
| Esc | close inventory / escape |
| R | respawn |
| V | toggle FPV ASCII ↔ overhead map crop |
| Disconnect | stop reconnect loop |

### Gamepad / Steam Deck (#132)

| Input | Intent |
|-------|--------|
| Left stick / D-pad | relative move (8-way) |
| L1 / R1 | turn_left / turn_right |
| A (South) | get (`g`) |
| X (West) | fire (`f`) |
| B (East) | look |
| Y (North) | inventory |
| L2 | use (`u`) |
| R2 | respawn (`r`) — confirm on device |
| Select | FPV ↔ map |
| Start | cycle year docks |

Default viewport **1280×800** (`keep` aspect). Linux export preset: `export_presets.cfg.example`. Suspend/resume nudges WS reconnect in `net_client.gd`. **Device QA not yet run on hardware.**

## StreetNet + year docks (#127)

| Surface | Snapshot fields | Core actions |
|---------|-----------------|--------------|
| StreetNet chat | `chat`, `irc` (channel, channels, topics, nicks) | `type: chat` · `/join #chan` |
| Journal | `journal` | `journal_track` |
| ICE | `ice` (probes, nearby, focus) | `ice_probe` stun/reveal/scramble/list · Jack in/out |
| Globe | `globe` (regions, cooldown, hop cost) | `globe`, `globe_zoom`, `globe_search`, `globe_filter`, `teleport`, `globe_recall` |
| Primer | `primer` | `primer`, `primer_start`, `primer_close` |
| Jaunte | `jaunte` | `jaunte_*`, `jaunte_globe` |
| Sleeves | `sleeves` | `sleeves`, `sleeve`, `sleeve_rent`, `house`, `sleeve_status` |
| Forecast | `forecast` | `forecast`, `forecast_nudge`, `forecast_status`, `forecast_close` |
| Ecology | `ecology` | `ecology_*`, `ecology_claim`, `ecology_raid` |
| Empathy | `empathy` | `empathy_*`, `empathy_answer`, `bounty_*` |
| Hello Courier / mod `ui_panel` | `mods.panels` | allowlisted `action` (+ optional `arg`) from panel JSON |

Dock bar is accordion-style (one panel open). Opening Globe/Primer/Jaunte/Sleeves/Forecast/Ecology/Empathy sends the same refresh action as web. Catppuccin Mocha colors via `scripts/catppuccin.gd`.

## Onboarding (#133)

Cold launch shows a short jack-in brief → name gate → **Payload-Zero** street beat. Year docks + StreetNet stay gated until the beat wins or the player skips. Returning players: `user://snowcrash_client.cfg` remembers name / skip intro.

Death during the beat opens a recap (cause + last objective + respawn). Details: [`docs/godot-onboarding.md`](../docs/godot-onboarding.md).

## HUD

- Connection status + RTT + online count
- HP / Focus / XP / level / credits / tile / facing / mode
- Objective (peach; green on win, red on death)
- Inventory `ItemList` (click select, double-click use)
- Scrolling log from `state.messages`
- **FPV** text view (TUI-style raycast from snapshot map) or cropped ASCII overhead with facing glyph
- Year dock body + StreetNet channel list / nick list / chat log

## Layout

| Path | Role |
|------|------|
| `project.godot` | Godot 4.3+ config, GL Compatibility, 1280×800, Deck InputMap |
| `export_presets.cfg.example` | Linux/X11 + Windows export stub (#132) |
| `scenes/main.tscn` | Name gate, HUD, FPV/map, inventory, log, docks, StreetNet |
| `scripts/net_client.gd` | `WebSocketPeer` — join/rejoin by id, action, chat, ping, backoff reconnect |
| `scripts/main.gd` | UI + hold-to-move + inventory digits + docks wiring |
| `scripts/year_docks.gd` | StreetNet + year dock paint/actions (#127); secondary gate for #133 |
| `scripts/onboarding.gd` | First-10 fantasy beat overlays + ConfigFile (#133) |
| `scripts/audio_manager.gd` | AudioBus Master/SFX/Music, juice, volume ConfigFile (#134) |
| `default_bus_layout.tres` | Master → SFX / Music |
| `audio/sfx/` | Mirrored procedural WAVs (+ streetnet_ping) |
| `audio/music/` | street_ambient + ice_jackin loops + trailer bed |
| `scripts/fpv_ascii.gd` | Snapshot → FPV ASCII / map crop |
| `scripts/catppuccin.gd` | Mocha palette tokens |
| `icon.svg` | Placeholder Catppuccin icon |

`.godot/` is generated by the editor — gitignored.

## Protocol check (no Godot)

```bash
source .venv/bin/activate
PYTHONPATH=. pytest -q tests/test_godot_ws_protocol.py
# or against a live server:
python scripts/godot_ws_harness.py --url ws://127.0.0.1:8766/ws
```

Harness covers play-loop envelopes plus dock/chat actions (`globe`, `ice_probe`, `primer`, `jaunte`, `sleeves`, `forecast`, `ecology`, `empathy`, StreetNet chat).

## Audio (#134)

- **Mute** button / **M** key; **Audio** panel with Master / SFX / Music sliders (persist `user://snowcrash_client.cfg`).
- Snapshot `sfx[]` + death / win / uplink / StreetNet ping juice.
- Music: street bed on the Street; ICE bed while `cyberspace` / `heist`.
- Regenerate: `python scripts/gen_sfx.py && python scripts/gen_music.py`
- Attribution: [docs/audio.md](../docs/audio.md)

## Out of scope (later #118 slices)

GPS minimap (#116), party/crew/shop/craft surfaces, desktop export, full Theme resource, Steam packaging (#67 / #130). Onboarding #133 + audio/music #134 are in-tree.
