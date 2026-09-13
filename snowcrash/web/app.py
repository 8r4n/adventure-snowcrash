"""FastAPI web frontend — MMORPG Metaverse streets (WebSocket + HTTP)."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Set

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ..mmorpg import TICK_HZ, GameWorld
from ..systems.aoi import interested_player_ids
from ..systems import qa as qa_mod
from ..theme import resolve_theme_name

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


class QaJoinBody(BaseModel):
    name: str = "QaCourier"
    soft_hardcore: bool = False


class QaActionBody(BaseModel):
    action: str = "noop"
    arg: Optional[str] = None
    name: Optional[str] = None
    id: Optional[str] = None


class QaLeaveBody(BaseModel):
    name: Optional[str] = None
    id: Optional[str] = None


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
    qa_on = qa_mod.qa_enabled()
    if qa_on:
        qa_mod.ensure_event_log(world)
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
                "qa_enabled": qa_on,
                "default_theme": resolve_theme_name(os.environ.get("SNOWCRASH_THEME")),
            },
        )

    @app.get("/sw.js")
    async def service_worker() -> FileResponse:
        """Root-scoped light offline shell worker (#75)."""
        return FileResponse(
            STATIC / "sw.js",
            media_type="application/javascript; charset=utf-8",
            headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
        )

    @app.get("/manifest.webmanifest")
    async def web_manifest() -> FileResponse:
        return FileResponse(
            STATIC / "manifest.webmanifest",
            media_type="application/manifest+json",
        )

    @app.get("/api/env")
    async def api_env() -> Dict[str, Any]:
        return {
            "env": env,
            "mmorpg": True,
            "seed": world.seed,
            "qa": qa_on,
            "qa_env": qa_mod.QA_ENV_VAR if qa_on else None,
        }

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
            mods = getattr(world, "mod_registry", None)
            mod_snap = mods.snapshot() if mods is not None else {
                "mod_count": 0, "errors": [], "api_version": None,
            }
            return JSONResponse({
                "ok": True,
                "districts": len(world.district_defs.get("districts", [])),
                "mods": mod_snap,
                "reload": {
                    "districts": True,
                    "recipes": True,
                    "season": True,
                    "mods": True,
                    "api_version": mod_snap.get("api_version"),
                    "fail_closed": True,
                    "note": "JSON mods remapped from mods/ + examples/plugins/; "
                            "broken packs skipped (see mods.errors / mods.skipped).",
                },
            })

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
            "qa": qa_on,
        }

    # ---- QA automation surface (#112) — only when ADVENTURE_QA is truthy ----
    def _qa_off() -> JSONResponse:
        return JSONResponse(
            {"ok": False, "error": "QA automation disabled", "hint": "export ADVENTURE_QA=1"},
            status_code=404,
        )

    @app.get("/qa/status")
    async def qa_status() -> Any:
        if not qa_on:
            return _qa_off()
        return {
            "ok": True,
            "qa": True,
            "seed": world.seed,
            "tick": world.tick,
            "online": sum(1 for p in world.players.values() if p.connected),
            "events": len(getattr(world, "qa_events", []) or []),
            "env": env,
        }

    @app.post("/qa/join")
    async def qa_join(body: QaJoinBody) -> Any:
        if not qa_on:
            return _qa_off()
        async with lock:
            agent = world.join(body.name, soft_hardcore=bool(body.soft_hardcore))
            world.reconnect_parked(agent)
            agent.connected = True
            qa_mod.record_event(world, "join", agent)
            snap = qa_mod.structured_snapshot(world, agent)
        return JSONResponse({"ok": True, "you": agent.id, "state": snap})

    @app.post("/qa/action")
    async def qa_action(body: QaActionBody) -> Any:
        if not qa_on:
            return _qa_off()
        async with lock:
            agent = qa_mod.find_agent(world, name=body.name, player_id=body.id)
            if not agent:
                name = body.name or "QaCourier"
                agent = world.join(name)
                world.reconnect_parked(agent)
                agent.connected = True
                qa_mod.record_event(world, "join", agent, via="action")
            world.handle_action(agent, str(body.action or "noop"), body.arg)
            qa_mod.record_event(
                world, "action", agent, action=str(body.action or "noop"), arg=body.arg
            )
            snap = qa_mod.structured_snapshot(world, agent)
        return JSONResponse({"ok": True, "you": agent.id, "state": snap})

    @app.get("/qa/snapshot")
    async def qa_snapshot(name: str = "QaCourier", id: Optional[str] = None) -> Any:
        if not qa_on:
            return _qa_off()
        async with lock:
            agent = qa_mod.find_agent(world, name=name, player_id=id)
            if not agent:
                return JSONResponse(
                    {"ok": False, "error": "courier not found — POST /qa/join first"},
                    status_code=404,
                )
            snap = qa_mod.structured_snapshot(world, agent)
        return JSONResponse({"ok": True, "you": agent.id, "state": snap})

    @app.get("/qa/events")
    async def qa_events(limit: int = 50) -> Any:
        if not qa_on:
            return _qa_off()
        lim = max(1, min(200, int(limit)))
        events = list(getattr(world, "qa_events", []) or [])[-lim:]
        return JSONResponse({"ok": True, "events": events, "seed": world.seed})

    @app.post("/qa/leave")
    async def qa_leave(body: QaLeaveBody) -> Any:
        if not qa_on:
            return _qa_off()
        async with lock:
            agent = qa_mod.find_agent(world, name=body.name, player_id=body.id)
            if not agent:
                return JSONResponse({"ok": False, "error": "courier not found"}, status_code=404)
            pid = agent.id
            qa_mod.record_event(world, "leave", agent)
            # Drop any live sockets for this player, then park the body
            for ws, sid in list(sockets.items()):
                if sid == pid:
                    await _detach(ws)
            if pid in world.players and world.players[pid].connected:
                world.leave(pid)
        return JSONResponse({"ok": True, "left": pid})

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
                if qa_on:
                    qa_mod.record_event(world, "join", agent, via="ws")
            welcome: Dict[str, Any] = {"type": "welcome", "you": player_id, "state": snap}
            if qa_on:
                welcome["qa"] = True
            await ws.send_json(welcome)
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
                        act = str(msg.get("action") or "noop")
                        world.handle_action(agent, act, msg.get("arg"))
                        if qa_on:
                            qa_mod.record_event(world, "action", agent, action=act, arg=msg.get("arg"), via="ws")
                        # AOI interest management (#18) — nearby + social, not full O(n²)
                        interested = interested_player_ids(world, player_id)
                        await broadcast_snapshots(only=interested)
                    continue
                if qa_on and mtype == "qa_snapshot":
                    async with lock:
                        agent = world.players.get(player_id) if player_id else None
                        if not agent:
                            continue
                        qsnap = qa_mod.structured_snapshot(world, agent)
                    await ws.send_json({"type": "qa_snapshot", "state": qsnap})
                    continue
                if qa_on and mtype == "qa_events":
                    lim = max(1, min(200, int(msg.get("limit") or 50)))
                    events = list(getattr(world, "qa_events", []) or [])[-lim:]
                    await ws.send_json({"type": "qa_events", "events": events, "seed": world.seed})
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
