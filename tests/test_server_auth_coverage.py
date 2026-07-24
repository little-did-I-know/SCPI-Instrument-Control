# tests/test_server_auth_coverage.py
"""Regression coverage for review findings against the auth boundary.

Three things live here that the other auth test modules don't cover:

- Critical 1: a proxy-mounted deployment (``uvicorn --root-path /gw``) must not
  let ``scope["path"]`` still carrying the mount prefix slip an ``/api/*``
  request past the guard.
- Important 2: the OpenAPI schema and HTML doc UIs must sit behind the same
  guard as the rest of the instrument-control surface, not float outside it.
- Critical 3: this is the load-bearing test of the whole sub-project. It walks
  the *real* route table -- rather than a hand-maintained list -- so a new
  router mounted under /api/ is covered by this guard the day it is added,
  instead of silently slipping through anonymous. Note that /api/openapi.json
  is registered by FastAPI as a plain ``starlette.routing.Route``, not an
  ``APIRoute`` (it is added via ``add_route``, not a decorator), so the
  enumeration below never sees it -- that path is exercised separately by
  ``test_guarded_openapi_requires_a_token`` above.
"""

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from scpi_control.server.app import create_app  # noqa: E402
from scpi_control.server.auth import TokenStore  # noqa: E402
from scpi_control.server.sessions import SessionManager  # noqa: E402
from tests.route_introspection import iter_http_routes, iter_ws_routes  # noqa: E402


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


# --- Critical 3: every route in the real table rejects anonymous access ----

PLACEHOLDERS = {"session_id": "nope", "channel": "1", "n": "1", "name": "ref", "op": "run"}


def _concrete(path):
    for key, value in PLACEHOLDERS.items():
        path = path.replace("{" + key + "}", value)
    return path


# Enumeration is version-robust (see tests/route_introspection.py): Starlette 1.x
# nests include_router routes so walking app.routes flat finds almost none.
def _http_routes(app):
    return iter_http_routes(app)


def _ws_routes(app):
    return iter_ws_routes(app)


@pytest.fixture(scope="module")
def enumerated_app(tmp_path_factory):
    store = TokenStore(str(tmp_path_factory.mktemp("cfg") / "tokens.json"))
    store.mint("tester")
    manager = SessionManager()
    application = create_app(manager, token_store=store)
    yield application
    manager.close_all()


def test_route_table_is_not_empty(enumerated_app):
    # A guard on an empty table would pass vacuously; pin a floor so the
    # enumeration itself is verified to be finding real routes.
    assert len(list(_http_routes(enumerated_app))) >= 30
    assert len(list(_ws_routes(enumerated_app))) >= 1


def test_every_api_route_rejects_anonymous(enumerated_app):
    with TestClient(enumerated_app) as test_client:
        unguarded = []
        for method, path in _http_routes(enumerated_app):
            response = test_client.request(method, _concrete(path))
            if response.status_code != 401:
                unguarded.append("{0} {1} -> {2}".format(method, path, response.status_code))
        assert not unguarded, "unauthenticated access reached: {0}".format(unguarded)


def test_every_ws_route_rejects_anonymous(enumerated_app):
    # Assert the 1008 policy-violation code specifically. A bare
    # pytest.raises(Exception) passes vacuously here: an unknown session id
    # closes with 4404 regardless of auth, so the test would stay green with
    # the WebSocket guard entirely removed.
    with TestClient(enumerated_app) as test_client:
        for path in _ws_routes(enumerated_app):
            with pytest.raises(WebSocketDisconnect) as excinfo:
                with test_client.websocket_connect(_concrete(path)):
                    pass
            assert excinfo.value.code == 1008, "{0} closed {1}, not a policy violation".format(path, excinfo.value.code)
