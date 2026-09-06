# Jack-in cyberspace puzzle layer

Issue **#47** (parent campaign **#42**). Same courier identity: stand at the street **jackpoint (`J`)**, enter a short ASCII node, solve a maze or ICE-gate puzzle, return with loot — street pad and facing restored exactly. Synergizes with [ICE probes](ice-probes.md) (#46) on ICE-gate nodes. Deep multi-layer vault runs: [ice-heists.md](ice-heists.md) (#56).

Source of truth: `snowcrash/systems/cyberspace.py` (`CyberspaceMixin`), routed from `year_features` / `GameWorld.handle_action` when `agent.mode == "cyberspace"`. Web overlay + Jack dock in `game.js` / `index.html`.

## Enter / exit

### Enter (`jack_in`)

- Must be on **street plane** within Manhattan distance **1** of the jackpoint tile (`JACK_IN_RADIUS`).
- Actions: `jack_in`, `jackin`, `cyberspace`, `enter_jack`, `cyber_in`.
- Optional arg: `maze` or `ice_gate` / `ice` / `gate`. Otherwise node type **alternates** by clears: even `cyber_nodes_cleared` → maze, odd → ice_gate.
- Web: press **`j`** when `cyberspace.can_jack_in` (else `j` is absolute south); dock **Jack** button when enabled.
- On jack-in: street `x/y/z/facing` saved on the session; body gets a long invuln shield (~600s) so the parked sleeve is not flatlined; mode → `cyberspace`; terminal cutscene + pulse SFX.

### Exit (`jack_out`)

- Actions: `jack_out`, `jackout`, `unjack`, `leave_cyber`, `cyber_out`, or **`escape` / Esc / `q`** while jacked.
- Web: **Esc** (mapped to `escape`), **`j`** while in cyberspace, or Jack dock set to exit.
- Restores the exact street pad and facing (no random teleport). Brief exit grace (~3s invuln). Clearing the node jack-outs with reason `cleared`.

Street-only actions (inventory, fire, plane change, etc.) are muted while jacked.

## Node types

Glyphs: `#` wall · `.` floor · `I` ICE · `*` loot · `%` core · `X` exit · `@` you.

| Type | Goal | ICE |
|------|------|-----|
| **maze** | Reach `*` loot, then `X` exit | None |
| **ice_gate** | Reach `%` core, then `X` exit | `I` cells block movement until melted |

Exit port stays locked until loot/core is taken (`g` / step onto tile). Templates are small fixed ASCII maps (`_MAZE_A/B`, `_ICE_GATE_A/B`).

### Movement

Same relative (`forward` / strafe / …) and absolute octile moves as the street layer; turn left/right still work. Bumping `I` logs a hint to use probes.

## ICE synergy (#46)

In-node, only **`stun`** and **`reveal`** apply:

- Same Focus costs and cooldowns as street probes.
- Clears ICE cells near the avatar (stun radius **1**, reveal radius **2**).
- `scramble` logs that it has no street hostiles in the lattice.

Street cameras/drones are irrelevant while jacked; probes spend Focus against the node lattice instead.

## Rewards (on clear)

Granted once per clear (`_cyber_grant_rewards`):

- **Cyberspace Node Key** (`cyber_key` datachip, soft street locks / topology flavor)
- **Node Chip** (maze → “Maze Trace”, ice_gate → “ICE Gate Dump”)
- **+15 credits**, **+3 Focus** (capped at max)
- Quest flags: `cyber_node_cleared`, `cyber_nodes_cleared++`, plus `cyber_maze_cleared` or `cyber_ice_gate_cleared`
- Journal note + side quest `cyber_jack` marked done
- Season XP **+8** when season helpers exist

Manual jack-out without clearing grants no payload.

## Snapshot (`cyberspace`)

Inactive: `{ active, can_jack_in, hint }`.

Active: node `map` rows, `node_type`, position, `loot_taken`, `ice_remaining`, `hint`, parked `street`, legend. While jacked, the MMORPG snapshot **swaps** the ASCII map to the node lattice for GPS/FPV consumers.

## TUI note

Single-player curses TUI does not run `GameWorld` / year cyberspace yet. Use **dev web** to jack in.
