"""Mobile playability (#75) — static shell, join helpers, slice 4 HUD/chords."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from snowcrash.web.app import create_app

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "snowcrash" / "static"


def test_qr_and_sw_assets_on_disk():
    qr = (STATIC / "qrcode.min.js").read_text(encoding="utf-8")
    assert "qrcode-generator" in qr
    assert "function" in qr
    sw = (STATIC / "sw.js").read_text(encoding="utf-8")
    assert "snowcrash-shell-v3" in sw
    assert "/static/qrcode.min.js" in sw
    game = (STATIC / "game.js").read_text(encoding="utf-8")
    assert "function idleFrameMs" in game
    assert "function buildJoinUrl" in game
    assert "function paintJoinQr" in game
    assert "function scenePlan" in game
    assert "window.prompt" not in game
    assert "jaunte-region" in game
    html = (ROOT / "snowcrash" / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'id="btn-show-qr"' in html
    assert 'id="join-qr"' in html
    assert "/static/qrcode.min.js" in html


def test_index_and_sw_served():
    app = create_app(default_seed=42, deploy_env="dev")
    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        body = page.text
        assert 'id="btn-show-qr"' in body
        assert "/static/qrcode.min.js" in body
        sw = client.get("/sw.js")
        assert sw.status_code == 200
        assert "snowcrash-shell-v3" in sw.text
        qr = client.get("/static/qrcode.min.js")
        assert qr.status_code == 200
        assert len(qr.content) > 1000


def test_slice4_chord_and_nested_scroll_markers():
    html = (ROOT / "snowcrash" / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'data-chord-layout="onehand-v4"' in html
    assert 'data-act="look"' in html
    assert 'data-act="."' in html
    assert "LOOK" in html and "WAIT" in html
    assert "chord-primary" in html
    # plane pad removed from mobile chords (keyboard still available)
    assert 'data-act="plane_up"' not in html
    css = (STATIC / "style.css").read_text(encoding="utf-8")
    assert "Mobile slice 4 (#75)" in css
    assert "max-height: none !important" in css
    assert "is-pressed" in css
    assert "safe-area-inset-top" in css
    game = (STATIC / "game.js").read_text(encoding="utf-8")
    assert 'classList.add("is-pressed")' in game
    assert "nestedScrollBound" in game
    doc = (ROOT / "docs" / "mobile.md").read_text(encoding="utf-8")
    assert "Slice 4" in doc
    assert "LOOK/WAIT" in doc or "LOOK / WAIT" in doc
