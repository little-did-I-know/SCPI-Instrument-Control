"""Session ownership: the creating identity owns the session."""

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.routing import APIRoute  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from scpi_control.server.app import create_app  # noqa: E402
from scpi_control.server.auth import TokenStore  # noqa: E402
from scpi_control.server.ownership import WRITE_ROUTES  # noqa: E402
from scpi_control.server.sessions import SessionManager  # noqa: E402


@pytest.fixture()
def two_users(tmp_path):
    store = TokenStore(str(tmp_path / "tokens.json"))
    alice = {"Authorization": "Bearer {0}".format(store.mint("alice"))}
    bob = {"Authorization": "Bearer {0}".format(store.mint("bob"))}
    manager = SessionManager()
    app = create_app(manager, token_store=store)
    with TestClient(app) as client:
        yield client, alice, bob
    manager.close_all()


def _make_session(client, headers):
    response = client.post("/api/sessions", json={"label": "s", "mock": True}, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_creator_becomes_owner(two_users):
    client, alice, _bob = two_users
    assert _make_session(client, alice)["owner"] == "alice"


def test_owner_is_visible_in_listing(two_users):
    client, alice, bob = two_users
    _make_session(client, alice)
    listed = client.get("/api/sessions", headers=bob).json()
    assert listed[0]["owner"] == "alice"


def test_non_owner_can_read_state(two_users):
    client, alice, bob = two_users
    sid = _make_session(client, alice)["id"]
    assert client.get("/api/sessions/{0}/scope/state".format(sid), headers=bob).status_code == 200


def test_owner_can_still_write(two_users):
    client, alice, _bob = two_users
    sid = _make_session(client, alice)["id"]
    assert client.patch("/api/sessions/{0}/scope/timebase".format(sid), json={"timebase": 1e-3}, headers=alice).status_code == 200


# --- Bidirectional enumeration over WRITE_ROUTES -----------------------------
#
# WRITE_ROUTES is (method, router-relative path) pairs. Path placeholders are
# filled with values valid enough to clear routing/body validation and reach
# the ownership check, which every gated handler performs before anything
# else -- so the specific placeholder/body values otherwise don't matter.

_PLACEHOLDERS = {"channel": "1", "n": "1", "name": "ref", "op": "run"}

# Bodies for routes whose pydantic model has required fields; FastAPI validates
# the body before the handler runs, so a missing required field (or a missing
# body entirely -- the body *parameter* has no default even when every field
# on its model does) would 422 before ever reaching require_owner. Routes with
# no body parameter tolerate the "{}" default fine, so only the routes that
# need specific required fields get an explicit entry here.
_BODIES = {
    ("PATCH", "/sessions/{session_id}/scope/timebase"): {"timebase": 1e-3},
    ("POST", "/sessions/{session_id}/scope/command"): {"command": "*RST"},
    ("PUT", "/sessions/{session_id}/scope/measurements"): [{"channel": 1, "mtype": "PKPK"}],
    ("POST", "/sessions/{session_id}/scope/references"): {"name": "ref", "channel": 1},
}


def _concrete(path, session_id):
    path = path.replace("{session_id}", session_id)
    for key, value in _PLACEHOLDERS.items():
        path = path.replace("{" + key + "}", value)
    return path


@pytest.mark.parametrize("method,path", sorted(WRITE_ROUTES))
def test_write_route_rejects_non_owner(two_users, method, path):
    client, alice, bob = two_users
    sid = _make_session(client, alice)["id"]
    url = "/api" + _concrete(path, sid)
    response = client.request(method, url, headers=bob, json=_BODIES.get((method, path), {}))
    assert response.status_code == 409
    assert "alice" in response.json()["detail"]


# Query params for non-write routes that would otherwise do something
# expensive or unbounded by default (a real LAN scan for /discover).
_QUERY_OVERRIDES = {"/api/discover": {"cidr": "127.0.0.1/32"}}
_BODY_OVERRIDES = {("POST", "/api/sessions"): {"label": "s2", "mock": True}}


def test_non_write_routes_stay_open_to_non_owner(two_users):
    """Walk the live route table for every (method, path) NOT in WRITE_ROUTES
    and assert a non-owner never gets 409 -- i.e. the read/write split in
    WRITE_ROUTES is exhaustive in both directions, not just for the write side.
    """
    client, alice, bob = two_users
    sid = _make_session(client, alice)["id"]
    write_paths = {(method, "/api" + path) for method, path in WRITE_ROUTES}

    checked = 0
    gated = []
    for route in client.app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/"):
            continue
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            if (method, route.path) in write_paths:
                continue
            checked += 1
            url = _concrete(route.path, sid)
            response = client.request(method, url, headers=bob, json=_BODY_OVERRIDES.get((method, url)), params=_QUERY_OVERRIDES.get(url))
            if response.status_code == 409:
                gated.append("{0} {1} -> {2}".format(method, route.path, response.status_code))

    # A guard on an empty table would pass vacuously; pin a floor so this is
    # verified to be checking real routes, not an accidentally-empty set.
    assert checked >= 15
    assert not gated, "non-owner unexpectedly got 409 on: {0}".format(gated)
