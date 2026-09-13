"""Hide/show Street GPS overlay (#116) — static shell + persistence hooks."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from snowcrash.web.app import create_app

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "snowcrash" / "static"
TMPL = ROOT / "snowcrash" / "templates" / "index.html"


def test_gps_toggle_assets_on_disk():
    html = TMPL.read_text(encoding="utf-8")
    assert 'id="btn-gps"' in html
    assert 'id="btn-gps-mini"' in html
    assert "Street GPS" in html
    game = (STATIC / "game.js").read_text(encoding="utf-8")
    assert 'GPS_HIDDEN_KEY = "snowcrash_gps_hidden"' in game
    assert "function toggleGpsHidden" in game
    assert "function applyGpsHidden" in game
    assert 'ev.key === "`"' in game or "Backquote" in game
    css = (STATIC / "style.css").read_text(encoding="utf-8")
    assert "gps-hidden" in css
    assert ".btn-gps" in css
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Street GPS" in readme
    assert "snowcrash_gps_hidden" in readme or "localStorage" in readme


def test_index_serves_gps_button():
    app = create_app(default_seed=42, deploy_env="dev")
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert 'id="btn-gps"' in page.text
        assert 'id="minimap-wrap"' in page.text
