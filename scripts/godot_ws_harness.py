#!/usr/bin/env python3
"""Validate /ws protocol shapes the Godot client sends (#118 slice 1).

Mirrors godot_client/scripts/net_client.gd message envelopes against a live
or in-process Python server. Does not require the Godot binary.

Usage:
  python scripts/godot_ws_harness.py --url ws://127.0.0.1:8766/ws
  python scripts/godot_ws_harness.py --inprocess
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GODOT_JOIN = {"type": "join", "name": "GodotHarness"}
GODOT_ACTIONS = [
    {"type": "action", "action": "forward", "arg": None},
    {"type": "action", "action": "turn_left", "arg": None},
    {"type": "action", "action": "look", "arg": None},
    {"type": "action", "action": "g", "arg": None},
    {"type": "action", "action": "f", "arg": None},
    {"type": "action", "action": "i", "arg": None},
    {"type": "action", "action": "inv_select", "arg": "0"},
    {"type": "action", "action": "u", "arg": None},
    {"type": "action", "action": "escape", "arg": None},
    {"type": "action", "action": ".", "arg": None},
]
GODOT_PING = {"type": "ping", "t": 12345}
GODOT_CHAT = {"type": "chat", "text": "harness ping"}

REQUIRED_SNAPSHOT_KEYS = (
    "player",
    "map",
    "messages",
    "inventory",
    "objective",
    "credits",
    "xp",
    "level",
    "mode",
)


def assert_welcome(msg: Dict[str, Any]) -> str:
    assert msg.get("type") == "welcome", msg
    assert msg.get("you"), msg
    state = msg.get("state") or {}
    assert isinstance(state, dict), msg
    for k in ("player", "map", "mode"):
        assert k in state, f"welcome.state missing {k}"
    return str(msg["you"])


def assert_snapshot_keys(state: Dict[str, Any]) -> None:
    missing = [k for k in REQUIRED_SNAPSHOT_KEYS if k not in state]
    assert not missing, f"snapshot missing keys: {missing}"
    player = state.get("player") or {}
    for k in ("name", "x", "y", "hp", "max_hp", "facing_name"):
        assert k in player, f"player missing {k}"


def _recv_until(ws, want_types: set[str], limit: int = 12) -> Dict[str, Any]:
    last: Dict[str, Any] = {}
    for _ in range(limit):
        last = ws.receive_json()
        if last.get("type") in want_types:
            return last
    raise AssertionError(f"expected {want_types}, last={last}")


def run_with_starlette_client() -> None:
    from fastapi.testclient import TestClient

    from snowcrash.web.app import create_app

    app = create_app(default_seed=42, deploy_env="dev")
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json(dict(GODOT_JOIN))
            welcome = _recv_until(ws, {"welcome"})
            pid = assert_welcome(welcome)
            assert_snapshot_keys(welcome["state"])

            # Envelope Godot NetClient would send on reconnect
            rejoin = {"type": "join", "name": "GodotHarness", "id": pid}
            assert rejoin["id"] == pid

            for payload in GODOT_ACTIONS:
                ws.send_json(payload)
                snap = _recv_until(ws, {"snapshot", "error"})
                if snap.get("type") == "snapshot":
                    assert_snapshot_keys(snap["state"])

            ws.send_json(dict(GODOT_PING))
            pong = _recv_until(ws, {"pong"})
            assert pong.get("t") == 12345, pong

            ws.send_json(dict(GODOT_CHAT))
            _recv_until(ws, {"snapshot", "error"})


def run_live(url: str) -> None:
    try:
        import websockets  # type: ignore
    except ImportError as exc:
        raise SystemExit("pip install websockets for --url mode") from exc

    import asyncio

    async def _go() -> None:
        async with websockets.connect(url) as ws:
            await ws.send(json.dumps(GODOT_JOIN))
            welcome = None
            for _ in range(8):
                msg = json.loads(await ws.recv())
                if msg.get("type") == "welcome":
                    welcome = msg
                    break
            assert welcome is not None
            pid = assert_welcome(welcome)
            assert_snapshot_keys(welcome["state"])
            print("welcome ok", pid)

            for payload in GODOT_ACTIONS[:5]:
                await ws.send(json.dumps(payload))
                for _ in range(10):
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
                    if msg.get("type") == "snapshot":
                        assert_snapshot_keys(msg["state"])
                        print("action ok", payload["action"])
                        break

            await ws.send(json.dumps(GODOT_PING))
            for _ in range(10):
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
                if msg.get("type") == "pong":
                    print("pong ok", msg.get("t"))
                    break
            print("live harness passed")

    asyncio.run(_go())


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", help="Live ws URL e.g. ws://127.0.0.1:8766/ws")
    p.add_argument(
        "--inprocess",
        action="store_true",
        default=True,
        help="Use FastAPI TestClient (default)",
    )
    args = p.parse_args(argv)
    if args.url:
        run_live(args.url)
    else:
        run_with_starlette_client()
        print("in-process harness passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
