# Steam quality bar — survey + gap analysis

Issue **#130** (parent packaging research **#67**; Godot client program **#118** / docks **#127**; demo **#111** / **#126**; Workshop **#72**; mobile/Deck **#75**).

Living doc: competitive survey (Steam / press, Sep 2026), acceptance themes for a **Steam-marketable** Snowcrash, and gap analysis vs current `dev`. Update when comps or our ship posture change.

**Non-goals:** copying any title’s IP/prose/art; treating Slay the Spire 2 sales as a revenue KPI (engine + polish proof only).

---

## North star

Ship adventure-snowcrash as a **Steam-marketable** game that is **best-in-class among Godot-built titles** in its niche — Metaverse courier MMORPG + **3D street** + ICE — **not** a web prototype wrapped for Steam and **not** a text HUD wrapper.

- **Primary SKU** = Godot 4 **3D** desktop client talking to the Python authority over WebSocket (thin client; web / TUI / ASCII remain companions, accessibility, and debug).
- **Presentation goal (#141):** live `/ws` snapshots drive a `Node3D` street (meshes, courier camera, neon Catppuccin). ASCII FPV is overlay/toggle, not the storefront look. See [godot-3d.md](godot-3d.md).
- **Bar to beat** = genre depth (Qud / Cogmind), hacking fantasy (Grey Hack / 868-BACK), Godot commercial polish (StS2 / Brotato-class store + juice), and Godot **look** craft ([Abandoned Spaceship](https://github.com/perfoon/Abandoned-Spaceship-Godot-Demo) + [BLASTRONAUT](https://store.steampowered.com/app/1392650/BLASTRONAUT/) — epic [#163](https://github.com/8r4n/adventure-snowcrash/issues/163)).

---

## Competitive survey

### Traditional / glyph-forward roguelikes (presentation + depth)

| Title | Why it matters |
|-------|----------------|
| **Caves of Qud** | Genre-defining depth + emergent world; critics praise modernized UI/controls vs classic opaque RLs; Steam Deck friendly; “looks simple, plays huge.” |
| **Cogmind** | ASCII-adjacent polish gold standard: readable UI, teaches systems in-game, anti-tedium, high hour retention. |

### Cyberpunk / hacking roguelikes (fantasy + loop)

| Title | Why it matters |
|-------|----------------|
| **868-BACK** | Tight coffee-break cyber-hacking RL; “just one more”; strong identity fantasy. |
| **Into The Grid** | Cyberpunk RL deckbuilder; Very Positive EA; art + tactical clarity praised. |

### Persistent hacking / network multiplayer (online bar)

| Title | Why it matters |
|-------|----------------|
| **Grey Hack** | Always-on MMO hacking sandbox; player agency + consequences. |
| **HackOS / NODE: PROTOCOL / Ghost Network** *(brief)* | Terminal/desktop OS fantasy, co-op/PvP, contracts — players expect *desktop/OS chrome*, not a thin browser HUD. |

### Godot commercial bar (engine + polish)

| Title | Why it matters |
|-------|----------------|
| **Slay the Spire 2** (Godot) | Proof Godot ships mega-hits; Overwhelmingly Positive EA; Steam Deck Verified; native Linux; Workshop on roadmap. |
| **Brotato** | Clear loop, strong store page, audio/VFX polish, Deck support. |
| **Dome Keeper** | Tight fantasy + juice; readable progression in first session. |
| **Cassette Beasts** | Ambitious indie scope with polish that reads “finished product” on Steam. |
| **Until Then** | Narrative/UI craft bar; reminder that Godot ships outside pure action loops too. |

*(Also noted in press/Steam comps: Backpack Battles — consistent Godot indie success pattern.)*

### Godot commercial *look* bar (Abandoned Spaceship–class)

Issue **[#163](https://github.com/8r4n/adventure-snowcrash/issues/163)** (parents **#141** / **#130**). Visual **craft** bar for the Steam 3D SKU — not a loop to clone, not IP to ship.

| Title | Why it matters |
|-------|----------------|
| **[Abandoned Spaceship Godot Demo](https://github.com/perfoon/Abandoned-Spaceship-Godot-Demo)** (Perfoon) | Godot 4 tech-art showcase: trim-sheet recolor shaders, PBR ORM, baked lightmaps, volumetric fog / SSIL / SSAO / TAA, reflection probes, diegetic arcade video. **Look** bar for store screenshots. We cite it; we do **not** copy meshes, textures, or shaders. |
| **[BLASTRONAUT](https://store.steampowered.com/app/1392650/BLASTRONAUT/)** (same author, shipped) | Commercial proof this craft bar sells on Steam — “finished Godot product,” not prototype primitives. |

Biggest remaining Steam-screenshot gaps vs that bar: diegesis (#160). **Materials (#156)**, **kit (#158)**, **camera (#161)**, **lighting (#157)**, and **ground blend (#159)** shipped. Authority / loop stays ours (live Python `/ws` + thin Godot). Assessment table + will/won’t-copy lives in [godot-3d.md — Visual bar](godot-3d.md#visual-bar-163).

**Visual-fidelity checklist** (children of #163 — keep parent epics #163 / #141 open; use `Refs` only):

- [x] [#156](https://github.com/8r4n/adventure-snowcrash/issues/156) Trim-sheet / PBR + Catppuccin recolor shader
- [x] [#157](https://github.com/8r4n/adventure-snowcrash/issues/157) High-preset SSAO/SSIL/TAA/volumetric + probes
- [x] [#158](https://github.com/8r4n/adventure-snowcrash/issues/158) Modular corridor + prop kit (snapshot-placed)
- [x] [#159](https://github.com/8r4n/adventure-snowcrash/issues/159) Ground blend materials
- [ ] [#160](https://github.com/8r4n/adventure-snowcrash/issues/160) Diegetic in-world screens
- [x] [#161](https://github.com/8r4n/adventure-snowcrash/issues/161) Camera juice (cosmetic only; `/ws` grid stays authority)
- [x] [#162](https://github.com/8r4n/adventure-snowcrash/issues/162) Docs: cite this bar here + in [godot-3d.md](godot-3d.md) (this PR)

---

## Quality bar checklist (10 themes)

Treat these as the bar to beat or match in our niche:

| # | Theme | Target | Primary trackers |
|---|--------|--------|------------------|
| 1 | **Primary client = Godot 4 3D** on Steam | Thin WS to Python OK; **3D street** is the presentation; web/ASCII are companions | #141 · #163 · #118 · #127 |
| 2 | **First 10 minutes sell the fantasy** | Tutorial/onboarding; no HUD soup; one clear objective | #133 |
| 3 | **Cogmind-level information design** | Readable glyphs/FPV, tooltips, death/recap clarity | #118 · HUD polish |
| 4 | **Qud-level world density over time** | Regions/globe/news arcs feel alive | #54 · #51 |
| 5 | **Grey Hack–grade persistence fantasy** | Shared world stakes, reputation, player-visible consequences | MMORPG + ecology/empathy systems |
| 6 | **Steam page excellence** | Capsules, trailer, tags, age rating, Deck Verified path | #67 · #126 |
| 7 | **Audio + juice** | SFX/music that match neon Metaverse identity | #134 |
| 8 | **Performance** | Stable on mid PC + Deck; no Chrome-in-a-box as the shipped path | #118 export · #132 |
| 9 | **Mod/Workshop path** | JSON mods now → Workshop later | #72 |
| 10 | **Review hygiene** | Crash-free first hour; Overwhelmingly Positive as the target band | QA #112 · ship checklist |

---

## Gap analysis vs current `dev` (2026-09-13)

Snapshot of adventure-snowcrash on `dev` relative to the bar above.

### What we already have

| Area | State on `dev` |
|------|----------------|
| **Web-first MMORPG** | Feature-complete street layer: WS sync, chat, Payload-Zero, year systems (ICE, globe, Primer, Jaunte, sleeves, ecology, empathy, seasons, mods). Primary play surface today. |
| **ASCII FPV** | Web video→ASCII + TUI raycast; Catppuccin roles. Strong identity for store screenshots *as reference*, not final capsules. |
| **Godot thin client** | `godot_client/`: join/rejoin, intents, HUD, docks, onboarding, audio, **3D street slice (#141)** + ASCII FPV/map toggle. Python `/ws` authority unchanged. |
| **Packaging research** | [#67](https://github.com/8r4n/adventure-snowcrash/issues/67) closed with [steam-packaging.md](steam-packaging.md): Steam Direct, Tauri+sidecar *fastest wrap*, store asset sizes, Deck/Proton notes. **Does not yet re-center Godot as the preferred Steam SKU** (this doc + #118 do). |
| **Mods** | JSON plugin API + local pack contract ([modding.md](modding.md), [modding-workshop.md](modding-workshop.md)); Workshop upload not wired. |
| **Demo / trailer source** | README montage (#111 done); live re-capture still open (#126). |
| **SFX / music** | Procedural WAVs under `snowcrash/static/sfx/` + Godot AudioBus (**#134**): street/ICE beds, mute + volume ConfigFile, trailer bed in [audio.md](audio.md). |
| **Onboarding** | StreetNet Primer (#60) teaches systems *in the web client*. Godot/Steam first-10 beat: [godot-onboarding.md](godot-onboarding.md) (#133). |
| **Mobile / Deck** | PWA research (#75); **Deck Verified checklist** in [steam-deck.md](steam-deck.md) (#132) — **not yet run on hardware**. |

### Gaps vs the 10 themes

| Theme | Gap |
|-------|-----|
| 1 Godot primary SKU | **3D street vertical slice shipped (#141, epic open).** Presentation is still flat primitives vs Abandoned Spaceship–class materials/lighting — **#163** + children **#156–#161**. Remaining also: GodotSteam, sidecar/offline. #67 Tauri wrap of *web* is calendar fallback only. |
| 2 First 10 minutes | **Shipped #133 (Godot):** jack-in brief → name → Payload-Zero beat with dock gate + death/win feedback + skip/remember — see [godot-onboarding.md](godot-onboarding.md). Human ≥3 cold playtest still follow-up. Primer remains deeper post-beat teaching. |
| 3 Info design | Web HUD is dense (“HUD soup” risk); Godot HUD is minimal (good) but lacks Cogmind-grade tooltips / death recap / teach-in-place. |
| 4 World density | Globe (#54) + news arcs (#51) still open; density exists as systems but not as a continuous living world read for new players. |
| 5 Persistence fantasy | Shared world works on hosted `dev`; Steam SKU needs clear offline vs always-online messaging (#67 open questions) and visible reputation/consequence UX in-client. |
| 6 Store page | Asset checklist exists in packaging doc; no final capsules/trailer; #126 is live demo source, not a finished Steam trailer. |
| 7 Audio + juice | **Shipped #134:** Godot Master/SFX/Music buses, original street + ICE loops, juice (confirm/death/uplink/StreetNet), volume sliders, trailer bed — see [audio.md](audio.md). |
| 8 Performance / Deck | Checklist + Linux export stub + InputMap + suspend/reconnect in [steam-deck.md](steam-deck.md) (#132). Device QA **not yet run**; GodotSteam / OSK glyphs still open. #67 Proton risk for webview is another reason Godot export is preferred. |
| 9 Workshop | Local JSON packs only; Steamworks Workshop not started (#72). |
| 10 Review hygiene | QA harness (#112) exists; no “crash-free first hour” Steam checklist or crash reporting wired for a desktop SKU. |

### Packaging posture (update vs #67)

| Path | Role after #130 |
|------|-----------------|
| **Godot 4 + GodotSteam + Python authority** (hosted and/or sidecar) | **Preferred Steam SKU** — matches north star; native overlay/input/Deck. |
| **Tauri/Electron + web** | Emergency / calendar fallback only; weaker “best-in-class Godot product” story. |
| **Web / PWA** | Companion, staging, mobile bridge (#75) — not the storefront hero. |

---

## Recommended priority

Order of investment toward the north star:

1. **Godot 3D Steam SKU** — play loop + docks done; **#141** 3D street slice 1 done (epic open) → **#163** Abandoned Spaceship–class visual bar (#156 materials first) → export + GodotSteam (see [godot-3d.md](godot-3d.md)).
2. **Onboarding / juice** — first-10-minutes fantasy beat (**#133** / [godot-onboarding.md](godot-onboarding.md)) + audio/music pass (**#134** / [audio.md](audio.md)) ✅.
3. **Store page / trailer** — capsules + live trailer source (#126) using the Godot client when ready; asset sizes remain in [steam-packaging.md](steam-packaging.md).
4. **Workshop** — keep JSON mods shipping (#72); Workshop when Steamworks is real.
5. **Deck** — Verified checklist shipped ([steam-deck.md](steam-deck.md) / #132); native Linux depot QA on hardware still outstanding.

Do **not** pay Steam Direct or upload builds without explicit approval (same gate as #67).

---

## Child issues filed from this gap analysis

| Issue | Theme |
|-------|-------|
| [#132](https://github.com/8r4n/adventure-snowcrash/issues/132) Steam Deck Verified checklist | 8 Performance / Deck |
| [#133](https://github.com/8r4n/adventure-snowcrash/issues/133) First 10 minutes onboarding | 2 Onboarding |
| [#134](https://github.com/8r4n/adventure-snowcrash/issues/134) Audio + music pass | 7 Audio + juice |
| [#141](https://github.com/8r4n/adventure-snowcrash/issues/141) Godot 3D Metaverse client | 1 Godot 3D presentation |
| [#163](https://github.com/8r4n/adventure-snowcrash/issues/163) Abandoned Spaceship–class visual fidelity bar | 1 Godot *look* (Steam screenshots) |
| [#156](https://github.com/8r4n/adventure-snowcrash/issues/156)–[#161](https://github.com/8r4n/adventure-snowcrash/issues/161) Materials / lighting / kit / ground / diegesis / camera | #163 children |
| [#162](https://github.com/8r4n/adventure-snowcrash/issues/162) Docs: cite the visual bar | #163 docs (this PR) |

Still covered by existing opens: Godot 3D presentation **#141**, play-loop epic **#118** / **#127**, store/trailer source **#126**, Workshop **#72**, world density **#54** / **#51**, mobile companion **#75**.

---

## Related docs

- [steam-packaging.md](steam-packaging.md) — #67 Direct / depots / store asset sizes
- [steam-deck.md](steam-deck.md) — #132 Steam Deck Verified checklist (Godot Linux export)
- [godot-3d.md](godot-3d.md) — #141 3D street (Steam presentation goal); [Visual bar](godot-3d.md#visual-bar-163) cites #163 / Abandoned Spaceship
- [godot-client.md](godot-client.md) — #109/#118 thin client + slices
- [modding-workshop.md](modding-workshop.md) — #72 Workshop-style packs
- [demo-video.md](demo-video.md) — #126 live re-capture
- [mobile.md](mobile.md) — #75 PWA; not a Steam substitute
- [primer.md](primer.md) — in-world teaching tablet (feeds theme 2)
- [godot-onboarding.md](godot-onboarding.md) — #133 first 10 minutes Godot/Steam beat
- [audio.md](audio.md) — #134 SFX/music attribution, buses, trailer bed
- [qa-automation.md](qa-automation.md) — #112 review-hygiene helper
