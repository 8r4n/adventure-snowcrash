# QA automation (#112)

Env-gated playtest harness so bots/CI can drive the same server protocol the web client uses — no brittle UI scraping.

**Off by default.** Set `ADVENTURE_QA=1` (also accepts `true` / `yes` / `on`) only on trusted local/CI hosts. Do **not** enable on public Cloudflare tunnels.

## Quick start (dev :8766)

```bash
# terminal A — deterministic seed 42 is the run_dev.sh default
ADVENTURE_QA=1 ./scripts/run_dev.sh
# → http://127.0.0.1:8766/

# terminal B — stdlib smoke
python scripts/qa_smoke.py

# or in-process pytest (no server required)
ADVENTURE_QA=1 PYTHONPATH=. pytest -q tests/test_qa_112.py
```

`SEED` still controls the world (`SEED=42` by default in `scripts/run_dev.sh`). Same seed → same street layout for reproducible assertions.

## Surfaces

### Prefer WebSocket `/ws` (protocol-level)

Same frames as the browser / Godot client ([docs/godot-client.md](godot-client.md)):

| Client → server | Notes |
|-----------------|--------|
| `{type:"join", name, id?}` | First message; rejoin with `id` |
| `{type:"action", action, arg?}` | Same intents as web (`forward`, `turn_left`, `get`, year verbs…) |
| `{type:"chat", text}` | StreetNet |
| `{type:"qa_snapshot"}` | **QA only** — lean structured snapshot |
| `{type:"qa_events", limit?}` | **QA only** — recent event log |

When `ADVENTURE_QA=1`, `welcome` includes `"qa": true`. Closing the socket parks the courier (normal leave).

### HTTP `/qa/*` (QA only — 404 when flag unset)

| Method | Path | Body / query | Result |
|--------|------|--------------|--------|
| GET | `/qa/status` | — | `{ok, qa, seed, tick, online, …}` |
| POST | `/qa/join` | `{name}` | `{ok, you, state}` lean snapshot |
| POST | `/qa/action` | `{name\|id, action, arg?}` | apply intent → lean snapshot |
| GET | `/qa/snapshot` | `?name=` or `?id=` | lean snapshot |
| GET | `/qa/events` | `?limit=` | event ring buffer |
| POST | `/qa/leave` | `{name\|id}` | park courier / detach sockets |

`/api/env` and `/health` report `"qa": true|false` so sidecars can detect the flag without probing `/qa/status`.

Legacy REST (`POST /api/action`, `POST /api/new`, `GET /api/state`) still exists for bootstrap; live playtests should use `/ws` or `/qa/*`.

### Lean snapshot fields

```json
{
  "qa": true,
  "seed": 42,
  "tick": 12,
  "you": "…",
  "player": {"name", "x", "y", "z", "hp", "max_hp", "focus", "facing_name", "plane", …},
  "inventory": [{"id", "name", "kind", "equipped"}],
  "map_summary": {"size", "origin", "rows", "glyph_at_player", "width", "height"},
  "docks": {"globe", "primer", "sleeves", "jaunte", "empathy", "forecast", "ice_dock", "cyberspace", "heist", "mod_panels"},
  "messages": ["…"],
  "errors": ["…"],
  "events": [{"t", "kind", "name", "action?", …}],
  "objective": "…",
  "jackpoint": [x, y],
  "uplink": [x, y]
}
```

Full paint snapshots continue on `/ws` as `{type:"snapshot", state}` (unchanged).

### Secondary: `window.__QA__`

Only when the page was served with QA enabled (`meta[name=snowcrash-qa]=1`). Exposes `state()`, `action()`, `chat()`, `requestQaSnapshot()`, etc. Prefer server `/qa` or `/ws` for CI; the bridge is for manual browser console playtests.

## Example (HTTP)

```bash
curl -s http://127.0.0.1:8766/qa/status | jq .
curl -s -X POST http://127.0.0.1:8766/qa/join \
  -H 'content-type: application/json' \
  -d '{"name":"QaCourier"}' | jq '.state.player'
curl -s -X POST http://127.0.0.1:8766/qa/action \
  -H 'content-type: application/json' \
  -d '{"name":"QaCourier","action":"forward"}' | jq '.state.player,.state.map_summary.glyph_at_player'
curl -s -X POST http://127.0.0.1:8766/qa/leave \
  -H 'content-type: application/json' \
  -d '{"name":"QaCourier"}' | jq .
```

## Safety

- Flag unset → `/qa/*` returns **404**; WS ignores `qa_*` message types; no `window.__QA__`.
- Normal play path is unchanged.
- Event log is in-memory only (cap 200) and only allocated when QA is on.

## Related

- Issue [#112](https://github.com/8r4n/adventure-snowcrash/issues/112)
- WebSocket notes: [godot-client.md](godot-client.md)
- Year action verbs: [year_backend_actions.md](year_backend_actions.md)
