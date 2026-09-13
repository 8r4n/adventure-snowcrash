# Godot / Steam — first 10 minutes onboarding

Issue **#133** (parent Steam quality bar **#130** · Godot client **#118** · Primer teaching **#60** · related docks **#127**).

Cold Steam traffic must feel the Metaverse courier fantasy in **≤10 minutes**: one clear objective, no dock overload, readable FPV. The web StreetNet Primer (#60) teaches systems deeply but is HUD-heavy for a first-session product beat — this doc is the **Godot SKU** beat.

**Prose rule:** original Metaverse fiction only. Reuse Payload-Zero / Primer *teaching ideas*; do not invent or copy copyrighted novel text.

---

## Scripted beat (acceptance)

| Step | Player sees | Notes |
|------|-------------|--------|
| 1. Jack-in brief | 3 short chapters (Metaverse → Payload-Zero → controls) | Text overlay; **Skip intro** for returning players |
| 2. Name | Courier handle + “remember name / skip intro next time” | Persisted in Godot `user://snowcrash_client.cfg` (web analogue: `localStorage`) |
| 3. Street objective | **Payload-Zero**: jackpoint `(J)` → sleeve → uplink `(U)` → scrub | Server objective / compass already in snapshot (`objective.text`) |
| 4. Feedback | Win overlay on personal quest clear; death recap on early death | Clear cause + last objective + `R` respawn |
| 5. Anti–HUD soup | Year docks + StreetNet **gated** until beat completes or skip | Coach strip explains the lock |

Optional **Skip beat · unlock docks** at name / beat / death — marks intro+beat complete so the next launch skips straight to play.

---

## Godot implementation

| Path | Role |
|------|------|
| `godot_client/scripts/onboarding.gd` | Phase machine, ConfigFile, coach / death / win overlays |
| `godot_client/scripts/main.gd` | Wires beat ↔ net join / respawn; formats `objective` dict; log death recap when not in beat |
| `godot_client/scripts/year_docks.gd` | `set_secondary_gated(bool)` hides dock bar + StreetNet |
| `godot_client/scenes/main.tscn` | `OnboardingBeat` CanvasLayer |

No server rewrite required. Light client-only gating; Payload-Zero remains the existing personal MMORPG quest.

### Persistence keys (`[onboarding]` in `user://snowcrash_client.cfg`)

| Key | Meaning |
|-----|---------|
| `remembered_name` | Last courier name |
| `skip_intro` | Skip chapter brief on next launch |
| `beat_complete` | Skip entire onboarding (returning player) |

---

## Playtest acceptance (follow-up)

**Target:** ≥3 cold players hit the fantasy sell **without a human guide**.

This box cannot literally run three humans. Track as a follow-up checklist on #133 / Steam QA:

### Intended test script

1. Wipe client config (`user://snowcrash_client.cfg`) or use a fresh OS user — simulate cold install.
2. Start `./scripts/run_dev.sh`, open Godot `godot_client/`, Run Project.
3. **Do not coach.** Note whether the player:
   - Understands they are a Metaverse courier within ~2 minutes
   - Enters a name and jacks in without asking what to click
   - States the objective as “get Payload-Zero to the uplink” (or equivalent) within ~5 minutes
   - Does **not** open year docks / StreetNet before the beat ends (or understands they are locked)
   - On intentional early death: can explain *why* they died and how to continue (`R`)
4. Second launch: confirm remembered name + skip intro / beat.
5. Pass bar: **3/3** cold players complete or clearly articulate the beat objective inside 10 minutes.

Record notes under issue #133 comments or QA fixtures when humans are available.

---

## Diegetic screens vs dock gate

#160 jack terminal / StreetNet billboards are **presentation only** — they never call `set_secondary_gated(false)` or open docks.

## Related

- [steam-quality-bar.md](steam-quality-bar.md) — theme 2 tracker
- [primer.md](primer.md) — deeper teaching tablet (post-beat)
- [godot-client.md](godot-client.md) — thin client architecture
- [godot_client/README.md](../godot_client/README.md) — how to run
