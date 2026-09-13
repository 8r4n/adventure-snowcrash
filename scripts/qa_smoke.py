#!/usr/bin/env python3
"""Smoke playtest against a running dev server (#112).

Usage:
  ADVENTURE_QA=1 ./scripts/run_dev.sh   # terminal A
  python scripts/qa_smoke.py            # terminal B (default http://127.0.0.1:8766)

Requires the stdlib only (urllib). Prefer pytest tests/test_qa_112.py for CI.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("QA_BASE", "http://127.0.0.1:8766").rstrip("/")


def call(method: str, path: str, body: dict | None = None) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    try:
        status = call("GET", "/qa/status")
    except urllib.error.HTTPError as e:
        print("QA disabled or server down:", e, file=sys.stderr)
        print("Start with: ADVENTURE_QA=1 ./scripts/run_dev.sh", file=sys.stderr)
        return 1
    print("status:", status)
    join = call("POST", "/qa/join", {"name": "SmokeCourier"})
    print("join you=", join.get("you"), "hp=", join["state"]["player"]["hp"],
          "pos=", join["state"]["player"]["x"], join["state"]["player"]["y"])
    act = call("POST", "/qa/action", {"name": "SmokeCourier", "action": "forward"})
    p = act["state"]["player"]
    print("after forward: pos=", p["x"], p["y"], "hp=", p["hp"])
    assert p["hp"] is not None
    assert act["state"]["map_summary"]["rows"]
    leave = call("POST", "/qa/leave", {"name": "SmokeCourier"})
    print("leave:", leave)
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
