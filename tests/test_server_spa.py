# tests/test_server_spa.py
"""SPA fallback: client routes serve index.html; /api 404s stay JSON."""

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from scpi_control.server import app as app_module  # noqa: E402
from scpi_control.server.app import create_app  # noqa: E402
from scpi_control.server.sessions import SessionManager  # noqa: E402


@pytest.fixture()
def static_client(tmp_path, monkeypatch, gateway_auth):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<!doctype html><title>gateway</title>", encoding="utf-8")
    (static_dir / "app.js").write_text("console.log('x')", encoding="utf-8")
    monkeypatch.setattr(app_module, "STATIC_DIR", static_dir)
    store, headers, _raw = gateway_auth
    manager = SessionManager()
    with TestClient(create_app(manager, token_store=store)) as client:
        client.headers.update(headers)
        yield client
    manager.close_all()


def test_root_serves_index(static_client):
    response = static_client.get("/")
    assert response.status_code == 200
    assert "gateway" in response.text


def test_client_route_falls_back_to_index(static_client):
    response = static_client.get("/sessions/abc123")
    assert response.status_code == 200
    assert "gateway" in response.text


def test_static_asset_is_served(static_client):
    assert static_client.get("/app.js").status_code == 200


def test_unknown_api_path_still_json_404(static_client):
    response = static_client.get("/api/nope")
    assert response.status_code == 404
    assert set(response.json()) == {"error", "detail"}


def test_no_static_build_still_boots(gateway_auth):
    store, headers, _raw = gateway_auth
    manager = SessionManager()
    with TestClient(create_app(manager, token_store=store)) as client:
        assert client.get("/api/sessions", headers=headers).status_code == 200
    manager.close_all()


def test_encoded_traversal_is_contained(tmp_path, monkeypatch, gateway_auth):
    # secret lives OUTSIDE the served static dir
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET", encoding="utf-8")
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<!doctype html><title>gateway</title>", encoding="utf-8")
    monkeypatch.setattr(app_module, "STATIC_DIR", static_dir)
    store, _headers, _raw = gateway_auth
    manager = SessionManager()
    with TestClient(create_app(manager, token_store=store)) as client:
        # Starlette decodes %2e%2e -> .. before the path param reaches the handler
        for payload in ("/%2e%2e/secret.txt", "/../secret.txt", "/%2e%2e%2fsecret.txt"):
            response = client.get(payload)
            assert response.status_code in (200, 404), payload
            assert "TOP SECRET" not in response.text, payload
    manager.close_all()


def test_index_is_never_cached(static_client):
    # index.html names the content-hashed asset files, so it is the one file a
    # rebuild cannot invalidate. Cached, it keeps asking for a bundle that no
    # longer exists and the page appears frozen at the previous build.
    response = static_client.get("/")
    assert response.headers["cache-control"] == "no-store"


def test_the_spa_fallback_is_never_cached(static_client):
    # An unknown path falls back to index.html; that response needs the same
    # treatment or a deep-linked client route caches a stale document.
    response = static_client.get("/sessions/abc123")
    assert response.headers["cache-control"] == "no-store"


def test_hashed_assets_stay_cacheable(static_client):
    # Their names change when their contents do, so making them uncacheable
    # would trade the staleness bug for a slower panel.
    response = static_client.get("/app.js")
    assert response.headers.get("cache-control") != "no-store"
