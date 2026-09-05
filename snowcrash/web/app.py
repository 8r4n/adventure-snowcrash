"""FastAPI web frontend — HTML tile grid + keyboard."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ..engine import GameState, handle_action, new_game, snapshot

PKG = Path(__file__).resolve().parent.parent
STATIC = PKG / "static"
TEMPLATES_DIR = PKG / "templates"

# Single-player in-memory session (demo)
_sessions: Dict[str, GameState] = {}


class ActionBody(BaseModel):
    action: str = "noop"
    arg: Optional[str] = None
    session: str = "default"
    seed: Optional[int] = None


class NewBody(BaseModel):
    session: str = "default"
    seed: Optional[int] = None


def create_app(default_seed: Optional[int] = None) -> FastAPI:
    app = FastAPI(title="Snowcrash Rogue")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    if STATIC.is_dir():
        app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

    def get_gs(session: str = "default", seed: Optional[int] = None) -> GameState:
        if session not in _sessions:
            _sessions[session] = new_game(seed if seed is not None else default_seed)
        return _sessions[session]

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> Any:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"title": "Snowcrash — Fractured LA"},
        )

    @app.get("/api/state")
    async def api_state(session: str = "default") -> JSONResponse:
        gs = get_gs(session)
        return JSONResponse(snapshot(gs))

    @app.post("/api/action")
    async def api_action(body: ActionBody) -> JSONResponse:
        gs = get_gs(body.session, body.seed)
        result = handle_action(gs, body.action, body.arg)
        return JSONResponse(result)

    @app.post("/api/new")
    async def api_new(body: NewBody) -> JSONResponse:
        _sessions[body.session] = new_game(body.seed if body.seed is not None else default_seed)
        return JSONResponse(snapshot(_sessions[body.session]))

    @app.get("/health")
    async def health() -> Dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
