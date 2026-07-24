"""Auth middleware: HTTP bearer, WS subprotocol, exempt paths, identity."""

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from scpi_control.server.app import create_app  # noqa: E402
from scpi_control.server.auth import TokenStore, _route_path  # noqa: E402
from scpi_control.server.sessions import SessionManager  # noqa: E402


@pytest.fixture()
def store(tmp_path):
    return TokenStore(str(tmp_path / "tokens.json"))


@pytest.fixture()
def token(store):
    return store.mint("tester")


@pytest.fixture()
def client(store, token):
    manager = SessionManager()
    app = create_app(manager, token_store=store)
    with TestClient(app) as test_client:
        yield test_client
    manager.close_all()


def auth(token):
    return {"Authorization": "Bearer {0}".format(token)}


def test_anonymous_api_request_is_401(client):
    response = client.get("/api/sessions")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_valid_token_is_accepted(client, token):
    response = client.get("/api/sessions", headers=auth(token))
    assert response.status_code == 200


def test_wrong_token_is_401(client):
    response = client.get("/api/sessions", headers=auth("scpi_bogus"))
    assert response.status_code == 401


def test_malformed_authorization_header_is_401(client, token):
    assert client.get("/api/sessions", headers={"Authorization": token}).status_code == 401
    assert client.get("/api/sessions", headers={"Authorization": "Basic abc"}).status_code == 401


def test_health_is_exempt(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_query_param_token_is_rejected_on_api(client, token):
    response = client.get("/api/sessions?token={0}".format(token))
    assert response.status_code == 401


def test_error_body_keeps_the_shared_shape(client):
    body = client.get("/api/sessions").json()
    assert body["error"] and body["detail"]


def test_identity_is_attached(client, token):
    response = client.get("/api/whoami", headers=auth(token))
    assert response.status_code == 200
    assert response.json()["identity"] == "tester"


def test_websocket_without_subprotocol_is_rejected(client):
    # session id "nope" would 4404 regardless of auth (stream.py:71), so the
    # session must never be reached: assert the specific 1008 the middleware
    # sends on unauthenticated WS scopes, not just "closed somehow".
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/sessions/nope/stream"):
            pass
    assert exc_info.value.code == 1008


def test_websocket_with_a_bad_token_is_rejected(client):
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/sessions/nope/stream", subprotocols=["scpi-token.scpi_bogus", "scpi"]):
            pass
    assert exc_info.value.code == 1008


def test_route_path_matches_starlette_private_helper():
    """``_route_path`` is a deliberate copy of ``starlette._utils.get_route_path``.

    Importing the private name in production code would turn any upstream
    rename into an ImportError at boot, and this project pins no Starlette
    version, so a routine ``pip install -U`` must not be able to brick a
    gateway that has to come up. The tradeoff is silent drift: if upstream
    ever changes its root_path stripping, our copy could quietly diverge and
    the root_path auth-bypass ``_route_path`` exists to close could reopen.

    Import the private helper here, in the test only -- never in
    scpi_control/server/auth.py -- and skip cleanly (not fail) if it
    disappears; the point is a red signal on drift, not a broken suite on a
    routine Starlette upgrade.
    """
    starlette_utils = pytest.importorskip("starlette._utils")
    get_route_path = getattr(starlette_utils, "get_route_path", None)
    if get_route_path is None:
        pytest.skip("starlette._utils.get_route_path no longer exists; drift guard is stale")

    scopes = [
        {"path": "/api/sessions", "root_path": ""},  # no root_path (typical deployment)
        {"path": "/gw/api/sessions", "root_path": "/gw"},  # normal proxy mount
        {"path": "/gw/api/sessions", "root_path": "/gw/"},  # trailing slash on root_path
        {"path": "/gwapi/x", "root_path": "/gw"},  # coincidental prefix, not a path boundary
        {"path": "/gw", "root_path": "/gw"},  # path == root_path
        {"path": "/api/sessions", "root_path": "/other"},  # root_path is not a prefix at all
        {"path": "/gw/gw/api/sessions", "root_path": "/gw"},  # doubled prefix
    ]
    for scope in scopes:
        assert _route_path(scope) == get_route_path(scope), scope
