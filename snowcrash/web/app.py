"""FastAPI web frontend — MMORPG Metaverse streets (WebSocket + HTTP)."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional, Set

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ..mmorpg import TICK_HZ, GameWorld
from ..systems.aoi import interested_player_ids

PKG = Path(__file__).resolve().parent.parent
STATIC = PKG / "static"
TEMPLATES_DIR = PKG / "templates"


class ActionBody(BaseModel):
    action: str = "noop"
    arg: Optional[str] = None
    session: str = "default"
    seed: Optional[int] = None
    name: Optional[str] = None


class NewBody(BaseModel):
    session: str = "default"
    seed: Optional[int] = None
    name: Optional[str] = None


def create_app(default_seed: Optional[int] = None, deploy_env: str = "production") -> FastAPI:
    env = (deploy_env or "production").lower()
    if env not in ("production", "dev"):
        env = "production"
    title = (
        "Snowcrash — Fractured LA"
        if env == "production"
        else "Snowcrash MMORPG DEV — Fractured LA"
    )
    app = FastAPI(
        title=("Snowcrash MMORPG" if env == "production" else "Snowcrash MMORPG (DEV)")
    )
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    if STATIC.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

    world = GameWorld(default_seed if default_seed is not None else 42)
    # websocket_id -> player_id
    sockets: Dict[WebSocket, str] = {}
    # player_id -> set of websockets (usually 1)
    player_sockets: Dict[str, Set[WebSocket]] = {}
    lock = asyncio.Lock()
    tick_task: Optional[asyncio.Task] = None

    async def broadcast_snapshots(only: Optional[Set[str]] = None) -> None:
        dead: list[WebSocket] = []
        for ws, pid in list(sockets.items()):
            if only is not None and pid not in only:
                continue
            agent = world.players.get(pid)
            if not agent:
                continue
            try:
                await ws.send_json({"type": "snapshot", "state": world.snapshot(agent)})
            except Exception:
                dead.append(ws)
        for ws in dead:
            await _detach(ws)

    async def _detach(ws: WebSocket) -> None:
        pid = sockets.pop(ws, None)
        if not pid:
            return
        bucket = player_sockets.get(pid)
        if bucket:
            bucket.discard(ws)
            if not bucket:
                player_sockets.pop(pid, None)
                world.leave(pid)
                await broadcast_snapshots()

    async def tick_loop() -> None:
        interval = 1.0 / TICK_HZ
        while True:
            await asyncio.sleep(interval)
            async with lock:
                if any(p.connected for p in world.players.values()):
                    world.enemy_tick()
                    await broadcast_snapshots()

    @app.on_event("startup")
    async def _startup() -> None:
        nonlocal tick_task
        tick_task = asyncio.create_task(tick_loop())

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        if tick_task:
            tick_task.cancel()

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> Any:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "title": title,
                "deploy_env": env,
                "is_dev": env == "dev",
            },
        )

    @app.get("/api/env")
    async def api_env() -> Dict[str, Any]:
        return {"env": env, "mmorpg": True, "seed": world.seed}

    @app.get("/api/state")
    async def api_state(name: str = "Courier") -> JSONResponse:
        # REST bootstrap helper — prefer WebSocket for live play
        async with lock:
            agent = world.join(name)
            return JSONResponse(world.snapshot(agent))

    @app.post("/api/action")
    async def api_action(body: ActionBody) -> JSONResponse:
        async with lock:
            name = body.name or body.session or "Courier"
            agent = world.join(name)
            world.handle_action(agent, body.action, body.arg)
            return JSONResponse(world.snapshot(agent))

    @app.post("/api/new")
    async def api_new(body: NewBody) -> JSONResponse:
        """Join (or rejoin) the shared world — does not wipe other players."""
        async with lock:
            name = body.name or "Courier"
            agent = world.join(name)
            return JSONResponse(world.snapshot(agent))

    @app.get("/api/analytics")
    async def api_analytics(format: str = "json") -> Any:
        async with lock:
            if (format or "").lower() == "csv":
                from fastapi.responses import PlainTextResponse
                return PlainTextResponse(world.analytics_export_csv(), media_type="text/csv")
            return JSONResponse({"events": list(world.analytics_log[-200:])})

    @app.get("/api/replay")
    async def api_replay(limit: int = 200) -> JSONResponse:
        async with lock:
            lim = max(1, min(2000, int(limit)))
            return JSONResponse({"frames": list(world.replay_buffer[-lim:])})

    @app.post("/api/auth/nick")
    async def api_auth_nick(body: dict) -> JSONResponse:
        """Staging auth-nick stub — no real OAuth secrets required (#25)."""
        nick = str((body or {}).get("nick") or "Courier")[:24]
        token = str((body or {}).get("token") or "")
        async with lock:
            if token and token in world.auth_nicks:
                nick = world.auth_nicks[token]
                return JSONResponse({"ok": True, "nick": nick, "token": token, "stub": True})
            import uuid as _uuid
            token = _uuid.uuid4().hex[:12]
            world.auth_nicks[token] = nick
            return JSONResponse({"ok": True, "nick": nick, "token": token, "stub": True})

    @app.post("/api/reload_defs")
    async def api_reload_defs() -> JSONResponse:
        async with lock:
            world.reload_district_defs()
            return JSONResponse({"ok": True, "districts": len(world.district_defs.get("districts", []))})

    @app.get("/health")
    async def health() -> Dict[str, Any]:
        return {
            "status": "ok",
            "mmorpg": True,
            "online": sum(1 for p in world.players.values() if p.connected),
            "seed": world.seed,
            "year_backend": True,
            "weather": getattr(world, "weather_state", {}),
            "aoi": True,
        }

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        player_id: Optional[str] = None
        try:
            # First message should be join
            raw = await asyncio.wait_for(ws.receive_text(), timeout=60.0)
            msg = json.loads(raw)
            if msg.get("type") != "join":
                await ws.send_json({"type": "error", "error": "expected join"})
                await ws.close()
                return
            name = str(msg.get("name") or "Courier")
            reconnect_id = msg.get("id")
            soft_hc = bool(msg.get("soft_hardcore") or msg.get("hardcore"))
            async with lock:
                agent = world.join(name, reconnect_id=reconnect_id, soft_hardcore=soft_hc)
                world.reconnect_parked(agent)
                player_id = agent.id
                sockets[ws] = player_id
                player_sockets.setdefault(player_id, set()).add(ws)
                snap = world.snapshot(agent)
            await ws.send_json({"type": "welcome", "you": player_id, "state": snap})
            await broadcast_snapshots()

            while True:
                raw = await ws.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                mtype = msg.get("type")
                if mtype == "ping":
                    await ws.send_json({"type": "pong", "t": msg.get("t"), "server_t": time.time()})
                    continue
                if mtype == "chat":
                    async with lock:
                        agent = world.players.get(player_id) if player_id else None
                        if not agent:
                            continue
                        err = world.say(agent, str(msg.get("text") or ""))
                        if err == "rate":
                            await ws.send_json({"type": "error", "error": "chat rate limited"})
                        await broadcast_snapshots()
                    continue
                if mtype == "action":
                    async with lock:
                        agent = world.players.get(player_id) if player_id else None
                        if not agent:
                            continue
                        world.handle_action(agent, str(msg.get("action") or "noop"), msg.get("arg"))
                        # AOI interest management (#18) — nearby + social, not full O(n²)
                        interested = interested_player_ids(world, player_id)
                        await broadcast_snapshots(only=interested)
                    continue
                if mtype == "respawn":
                    async with lock:
                        agent = world.players.get(player_id) if player_id else None
                        if agent:
                            world.handle_action(agent, "r")
                            await broadcast_snapshots()
                    continue
        except WebSocketDisconnect:
            pass
        except asyncio.TimeoutError:
            try:
                await ws.close()
            except Exception:
                pass
        except Exception:
            pass
        finally:
            async with lock:
                await _detach(ws)

    return app


app = create_app()
