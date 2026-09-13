# Godot 3D Metaverse presentation

Issue **#141** (parent play loop **#118** · quality bar **#130** · Deck **#132** · onboarding **#133** · audio **#134**).

**Steam presentation goal:** the shipped desktop SKU is a **true 3D street** (Godot `Node3D` world + courier camera), not a text HUD wrapper. Python `/ws` stays game authority. ASCII FPV / overhead map remain as overlay, accessibility, and debug — they are **not** deleted.

Godot **may be missing** on this box. Files under [`godot_client/`](../godot_client/) are valid Godot **4.3+** scenes (open locally).

---

## Architecture (unchanged authority)

```
┌──────────────────────────────────────────────┐
│  Godot 4 presentation                        │
│  Street3D (meshes / camera / VFX / lights)   │
│  Control HUD · docks · StreetNet · ASCII     │
│  WebSocketPeer  →  ws(s)://host:port/ws      │
└──────────────────┬───────────────────────────┘
                   │ JSON snapshots + intents
┌──────────────────▼───────────────────────────┐
│  snowcrash.web  GameWorld (Python)           │
└──────────────────────────────────────────────┘
```

Thin-client rule still holds: **Godot never simulates the street.** It paints `snapshot.state.map` / `player` / `entities` / `players` / `jackpoint` / `uplink` and sends the same named intents as web (`forward`, `turn_left`, …).

---

## How to open the 3D view

1. Start the **dev** server: `./scripts/run_dev.sh` → `ws://127.0.0.1:8766/ws`
2. Godot 4.3+ → Import `godot_client/project.godot` → **F5**
3. Enter a courier name → **Jack in**
4. Default viewport is **3D street** (neon corridor from the live snapshot)
5. **V** / Select / View button cycles **3D → FPV ASCII → overhead map → 3D**
6. **C** / Cam button / R3 toggles **close 3rd-person ↔ first-person**
7. Move/look: WASD + Q/E, left stick, L1/R1, **right stick X → turn** (same WS intents)

HUD, inventory, year docks, and StreetNet stay as Control overlay. ASCII path is `fpv_ascii.gd` (unchanged).

---

## Glyph → mesh catalog (slice 1)

| Glyph | Role | 3D mesh | Catppuccin |
|-------|------|---------|------------|
| `#` | wall | box, 2.55 m | Teal / Sky emission (checker) |
| `.` | floor | thin slab | Surface 0 |
| `=` | street | slab + neon tick | Mantle + Yellow |
| `,` | grass | slab | Green darkened |
| `~` | water | translucent slab | Sapphire-ish Sky |
| `+` | door | yellow frame | Yellow emission |
| `o` | manhole | disc | Overlay 0 |
| `<` `>` | stairs | stepped box | Lavender |
| `J` | jackpoint | tall plinth + pillar + crown + pulse Omni + Label3D | Sky |
| `U` | uplink | taller peach beacon + ring + pulse Omni + Label3D | Peach |
| `$` | vendor | emissive kiosk + canopy + `$` billboard (from `landmarks`) | Yellow / Peach |
| `@` | self | teal capsule + head + facing chevron (hidden in 1st) | Teal |
| letter / `players` | other couriers | tall blue capsule + head + sky facing chevron + nameplate | Blue / Sky |
| `&` | NPC | short lavender capsule + larger head | Lavender |
| `i` | infected | hunched green box + offset head | Green |
| `t` | thug | wide peach slab + disc head | Peach |
| `d` | drone | hovering mauve sphere + torus ring | Mauve |
| `B` | boss | oversized red capsule + ring | Red |
| `c` | street cam | red box on prop pole | Red |
| `*` | loot / pickup | yellow spark + disc (map `*` + signal-key landmarks) | Yellow |
| ` ` | void / fog | skipped | — |

Landmarks **J** / **U** spawn from `state.jackpoint` / `state.uplink`. **Vendors** and signal-key loot also read `state.landmarks` (`glyph` `$` / `*`). Other `state.entities` / `state.players` use pooled multi-part meshes + `Label3D` billboards. **Facing chevrons** use snapshot `facing` for self + other couriers (agents).

Map rebuild is **AOI-cropped** (`BUILD_RADIUS` 18) and hashed so a 200×120 city does not instantiate every tile. Entities are **pooled** (cap `MAX_POOLED_ENTITIES` 48) with shared `PrimitiveMesh` + materials — no per-snap alloc, no per-vendor Omni (Deck light budget stays courier + J + U).

---

## Camera + input

| Mode | Rig |
|------|-----|
| **3rd** (default) | Close over-shoulder, courier capsule visible |
| **1st** | Eye-height, mesh hidden |

Facing is server `player.facing` (N/E/S/W). Position lerps toward tile centers — no client prediction, no new server APIs.

Right stick X is mapped to `look_left` / `look_right` and sent as **`turn_left` / `turn_right`** (existing intents). Keyboard Q/E and L1/R1 unchanged.

---

## Renderer + Deck perf budget

| Surface | Renderer | Why |
|---------|----------|-----|
| **Desktop Steam** | **Forward+** (`project.godot` `rendering_method=forward_plus`) | Clustered Omni lights, glow/bloom on neon materials |
| **Deck / Android** | **Mobile** (`rendering_method.mobile=mobile`) | Same scenes; cheaper clustered lights; glow still works |
| Fallback | GL Compatibility | Glow ignored; meshes still playable if someone force-switches |

**Targets (slice 1, not device-QA’d yet):**

| Device | Goal | Budget knobs |
|--------|------|----------------|
| Mid PC (1080p) | **60 fps** comfortable, **30 fps** floor | MSAA 2x on the street SubViewport; Forward+ glow on |
| Steam Deck (800p) | **30 fps** floor | Mobile renderer; `BUILD_RADIUS` 18; **shadows off**; max ~3 Omni (courier + J + U); entity pool ≤48; vendor emissive-only (no Omni); SubViewport `UPDATE_WHEN_VISIBLE`; no per-tile lights |
| Low | 30 fps | Drop MSAA; shrink radius to 14; disable glow in a later quality setting |

Honesty: **no Deck hardware pass yet** (same gate as [steam-deck.md](steam-deck.md)). Do not claim Verified from this slice.

Quality toggles (later polish slice): radius, MSAA, glow, landmark lights.

---

## Slice progress

| # | Slice | Status |
|---|-------|--------|
| 1 | **3D street vertical slice** — glyphs → meshes, courier camera, WS intents, J/U, ASCII toggle | Done (#142) |
| 2 | **Entities polish** — distinct silhouettes, facing chevrons, vendors `$`, pickups, landmark billboards | **This PR** |
| 3 | Cyberspace / ICE — distinct 3D visual language for jack-in layers | Open |
| 4 | Globe — 3D Earth / region picker or hybrid UI | Open |
| 5 | Polish — lighting, particles, materials, Deck device QA | Open |
| 6 | Optional ASCII overlay (hybrid look on top of 3D) | Open |

**#141 stays OPEN** until the Steam-ready 3D loop (acceptance on the issue). This PR is `Refs #141` only (do not close the epic).

### Slice 1 acceptance (partial)

- [x] Playable 3D street driven by live `/ws` snapshots (no server rewrite)
- [x] Courier move + facing via existing intents + gamepad map
- [x] J / U landmark readability
- [x] `docs/godot-3d.md` design + progress
- [x] `docs/godot-client.md` + [steam-quality-bar.md](steam-quality-bar.md) state **3D is the Steam presentation goal**
- [ ] 30 fps+ mid-PC / Deck **measured** (documented budget only)
- [ ] Landmark / vendor pass without any HUD soup (onboarding still uses Control chrome)

### Slice 2 acceptance (this PR)

- [x] Other players / NPCs / enemies as **distinct** multi-part meshes (silhouette + Catppuccin), not identical boxes
- [x] Vendors (`$`), jackpoint **J**, uplink **U** as readable emissive landmarks + billboards
- [x] Items / pickups when map or `landmarks` expose `*`
- [x] Facing indicators for agents (self + other couriers from snapshot `facing`)
- [x] Deck-conscious pooling / shared meshes; no extra Omni lights for vendors
- [x] `docs/godot-3d.md` slice 2 progress updated

---

## Files

| Path | Role |
|------|------|
| `godot_client/scenes/street.tscn` | `Node3D` world, environment, courier rig |
| `godot_client/scripts/street_3d.gd` | Snapshot → meshes / pooled entities / landmarks / facing / camera |
| `godot_client/scenes/main.tscn` | Street SubViewport inside the view pane + HUD overlay |
| `godot_client/scripts/main.gd` | View cycle, cam toggle, right-stick look |
| `godot_client/scripts/fpv_ascii.gd` | ASCII FPV / map (kept) |

---

## Non-goals (v1)

- Rewriting simulation in GDScript
- Photoreal AAA fidelity
- Dropping web / TUI / ASCII
- Closing #141 from this slice

## Related

- [godot-client.md](godot-client.md) — thin-client program + #118 slices
- [steam-quality-bar.md](steam-quality-bar.md) — #130; 3D is the Steam presentation goal
- [steam-deck.md](steam-deck.md) — #132 Deck checklist
- [theme-catppuccin.md](theme-catppuccin.md) — palette attribution
