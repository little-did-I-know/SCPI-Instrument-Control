# tests/test_server_auth_coverage.py
"""Regression coverage for review findings against the auth boundary.

Two things live here that the other auth test modules don't cover:

- Critical 1: a proxy-mounted deployment (``uvicorn --root-path /gw``) must not
  let ``scope["path"]`` still carrying the mount prefix slip an ``/api/*``
  request past the guard.
- Important 2: the OpenAPI schema and HTML doc UIs must sit behind the same
  guard as the rest of the instrument-control surface, not float outside it.
"""

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from scpi_control.server.app import create_app  # noqa: E402
from scpi_control.server.sessions import SessionManager  # noqa: E402


@pytest.fixture()
def client(gateway_auth):
    store, headers, _raw = gateway_auth
    manager = SessionManager()
    app = create_app(manager, token_store=store)
    with TestClient(app) as test_client:
        yield test_client, headers
    manager.close_all()


# --- Critical 1: root_path must be stripped before the /api/* guard check --


def test_root_path_prefixed_api_request_without_credentials_is_401(gateway_auth):
    """Reproduces the bypass: Starlette's router strips ``root_path`` before
    matching routes, so under ``uvicorn --root-path /gw`` a request that
    arrives as scope["path"] == "/gw/api/sessions" is served as
    "/api/sessions". Testing the raw, unstripped path here let it slip past
    the guard entirely -- 200 with the live session list, no credentials.
    """
    store, _headers, _raw = gateway_auth
    manager = SessionManager()
    app = create_app(manager, token_store=store)
    with TestClient(app, root_path="/gw") as client:
        response = client.get("/gw/api/sessions")
        assert response.status_code == 401
    manager.close_all()


def test_root_path_prefixed_api_request_with_credentials_is_served(gateway_auth):
    store, headers, _raw = gateway_auth
    manager = SessionManager()
    app = create_app(manager, token_store=store)
    with TestClient(app, root_path="/gw") as client:
        response = client.get("/gw/api/sessions", headers=headers)
        assert response.status_code == 200
    manager.close_all()


def test_root_path_prefixed_health_check_stays_exempt(gateway_auth):
    store, _headers, _raw = gateway_auth
    manager = SessionManager()
    app = create_app(manager, token_store=store)
    with TestClient(app, root_path="/gw") as client:
        response = client.get("/gw/api/health")
        assert response.status_code == 200
    manager.close_all()


# --- Important 2: API docs must sit behind the guard ------------------------


def _looks_like_openapi_schema(response) -> bool:
    try:
        body = response.json()
    except ValueError:
        return False
    return isinstance(body, dict) and "openapi" in body and "paths" in body


def test_top_level_docs_urls_do_not_expose_the_schema(client):
    test_client, _headers = client
    for path in ("/openapi.json", "/docs", "/redoc"):
        assert not _looks_like_openapi_schema(test_client.get(path))


def test_guarded_openapi_requires_a_token(client):
    test_client, _headers = client
    response = test_client.get("/api/openapi.json")
    assert response.status_code == 401


def test_guarded_openapi_serves_the_schema_with_a_token(client):
    test_client, headers = client
    response = test_client.get("/api/openapi.json", headers=headers)
    assert response.status_code == 200
    assert _looks_like_openapi_schema(response)
