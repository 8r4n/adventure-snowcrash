# Migration stub — year backend (2026)

**Status:** stub only. World state is process memory.

## Intended future schema
- `players(id, nick_auth, xp, level, credits, skills_json, loadout_json, season_json, …)`
- `crews(id, name, stash_json)`
- `housing(player_id, stash_json)`
- `analytics_events(t, kind, player_id, payload_json)`

## Roll-forward
1. Export `/api/analytics?format=csv` before restart if needed.
2. No SQL to apply yet — deploying this branch is additive Python only.
3. District JSON hot-reload does not migrate player positions.

## Roll-back
Revert to prior `dev` tip; no persistent store to undo.
