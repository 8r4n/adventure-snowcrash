# StreetNet Empathy Audit + Synth Bounty Contracts

Issue **#63** (parent campaign **#42** · related **#27** **#28**). Optional **empathy audit** dialogue mini-game and a **rogue synth bounty board** with at least two contract types. Mechanics inspired by empathy-test / bounty-hunter tropes — prose is **original Metaverse fiction only** (no copyrighted names or quotes).

Source of truth: `snowcrash/systems/empathy.py` (`EmpathyMixin`), mixed into `YearFeaturesMixin` / `GameWorld`. Web dock **Empathy** · **Shift+E**.

## Empathy audit (optional)

Three StreetNet scenarios. Pick **a / b / c** each time. Empathic picks score positive; cold picks score zero or negative.

| Outcome | Threshold | Effects |
|---------|-----------|---------|
| **PASS** | ≥2 empathic answers and score ≥2 | **+8 reputation**, **−4 heat**, unlocks “warm lattice” (better **Reclaim** payouts) |
| **FAIL** | Below threshold | **−6 reputation**, **+10 moral heat** (corp audit pressure) |

Cooldown ~**45s** between full audits. Start anytime from the dock — not required for street play.

### Controls

| Input | Effect |
|-------|--------|
| Dock **Empathy** · **Shift+E** | Open panel |
| `empathy` / `bounty_board` | Open status + board |
| `empathy_audit` / `audit` | Start dialogue test |
| `empathy_answer a` (or `b` / `c`) | Answer current scenario |
| `empathy_status` | Pass/fail + board summary |

## Synth bounty board (≥2 types)

Marked targets use glyph **`σ`** (rogue synth). One active bounty at a time.

| Type | Goal | Rewards (base) | Heat |
|------|------|----------------|------|
| **Retire** | Flatline the marked synth, then turn in | +45 cr · +3 rep | **+8** on turn-in (wetwork noticed) |
| **Reclaim** | Stand adjacent → **Bind** (non-lethal), then turn in | +35 cr · +12 rep | **−6** on turn-in (rehab preferred) |

Notes:

- Killing a **Reclaim** target voids the contract (−rep, +heat).
- Reclaim without a prior audit **pass** halves rep and softens heat shed.
- Abandon despawns the target (**+2 heat**).
- Turn-in grants a bit of season XP; a fresh available contract of that type re-posts.

### Controls

| Input | Effect |
|-------|--------|
| `bounty_accept retire` / `reclaim` | Spawn + accept |
| `bounty_reclaim` / Empathy **Bind** | Non-lethal adjacent capture |
| `bounty_turnin [type]` | Collect rewards when **ready** |
| `bounty_abandon` | Cancel active hunt |
| `bounty_list` | Board statuses |

## Snapshot (`empathy`)

| Field | Meaning |
|-------|---------|
| `audit_active` / `question` | Live dialogue prompt + choices |
| `last_result` / `passed_once` | pass \| fail \| null · warm lattice flag |
| `pass_count` / `fail_count` | Counters |
| `cooldown` | Seconds until re-audit |
| `bounties[]` | Board rows (`type`, `status`, `dist`, rewards) |
| `types[]` | Catalog for UI |
| `last_feedback` | `{kind, text, t}` for toasts |
| `synth_glyph` | `σ` |

## Web UI

Dock **Empathy** · audit buttons for a/b/c · bounty Accept / Bind / Turn in / Abandon · toasts on pass/fail/bounty · **Shift+E**.

## Design notes

- Call it **StreetNet Empathy Lattice** / **Empathy Audit** — never third-party trademarked test names.
- Moral heat reuses corp patrol heat (`_add_heat`) so failed audits and wet Retire jobs feed the same pressure loop (#50).
- Reputation is the existing year `agent.reputation` field (#27 contracts family).
