"""Session ownership: the creating identity owns the session."""

import time

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
    ("POST", "/sessions/{session_id}/owner"): {"name": "carol"},
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

# /claim is deliberately excluded from the scan below: unlike WRITE_ROUTES,
# a non-owner's request is its normal success path, and it 409s only when the
# owner is still active -- a different conflict than "not the owner", so it
# is neither a WRITE_ROUTES entry nor an always-open read route (see the note
# next to WRITE_ROUTES in ownership.py).
_OWNERSHIP_CONFLICT_EXEMPT = {("POST", "/api/sessions/{session_id}/claim")}


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
            if (method, route.path) in write_paths or (method, route.path) in _OWNERSHIP_CONFLICT_EXEMPT:
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


# --- Claim and handoff --------------------------------------------------


def test_claim_is_refused_while_owner_is_active(two_users):
    client, owner, other = two_users
    sid = _make_session(client, owner)["id"]
    response = client.post("/api/sessions/{0}/claim".format(sid), headers=other)
    assert response.status_code == 409
    assert response.json()["detail"]


def test_claim_succeeds_once_owner_is_idle(two_users, monkeypatch):
    client, owner, other = two_users
    sid = _make_session(client, owner)["id"]
    # Make the idle threshold trivially small rather than sleeping.
    client.app.state.abandon_after = 0.0
    response = client.post("/api/sessions/{0}/claim".format(sid), headers=other)
    assert response.status_code == 200
    # two_users mints identities "alice" (owner) / "bob" (other) -- not the
    # local variable names "owner"/"other" used for readability here.
    assert response.json()["owner"] == "bob"
    assert client.patch("/api/sessions/{0}/scope/timebase".format(sid), json={"timebase": 1e-3}, headers=other).status_code == 200


def test_owner_can_hand_off_explicitly(two_users):
    client, owner, other = two_users
    sid = _make_session(client, owner)["id"]
    response = client.post("/api/sessions/{0}/owner".format(sid), json={"name": "other"}, headers=owner)
    assert response.status_code == 200
    assert response.json()["owner"] == "other"


def test_non_owner_cannot_hand_off(two_users):
    client, owner, other = two_users
    sid = _make_session(client, owner)["id"]
    assert client.post("/api/sessions/{0}/owner".format(sid), json={"name": "other"}, headers=other).status_code == 409


def test_claim_succeeds_immediately_on_unowned_session():
    """An unowned session (owner == "") is claimable regardless of
    owner_last_active -- require_owner touches that timer even with no owner
    (see ownership.require_owner), so claim() must not read a fresh
    owner_last_active on an unowned session as "owner activity".
    """
    from scpi_control.server.ownership import claim
    from scpi_control.server.sessions import SessionManager

    manager = SessionManager()
    try:
        session = manager.create("s", mock=True)
        assert session.owner == ""
        session.owner_last_active = time.monotonic()  # as fresh as possible
        assert claim(session, "someone", 300.0) is None
        assert session.owner == "someone"
    finally:
        manager.close_all()


def test_owner_activity_on_read_route_resets_idle_claim_window(two_users):
    """A read route (require_session) must count as owner activity, or a
    watching-but-not-writing owner (the normal case while a capture runs)
    looks idle and can be claimed out from under them.
    """
    client, owner, other = two_users
    sid = _make_session(client, owner)["id"]
    session = client.app.state.manager.get(sid)
    session.owner_last_active -= 1000.0  # simulate a long-idle owner
    client.app.state.abandon_after = 1.0
    assert client.get("/api/sessions/{0}/scope/state".format(sid), headers=owner).status_code == 200
    response = client.post("/api/sessions/{0}/claim".format(sid), headers=other)
    assert response.status_code == 409


@pytest.fixture()
def two_users_ws(tmp_path):
    """Like ``two_users``, but also exposes raw tokens as WS subprotocols.

    WebSocket handshakes ignore default client headers; auth is via
    subprotocol instead (see tests/test_server_stream_ws.py).
    """
    from scpi_control.server.auth import TokenStore

    store = TokenStore(str(tmp_path / "tokens.json"))
    alice_raw = store.mint("alice")
    bob_raw = store.mint("bob")
    alice = {"Authorization": "Bearer {0}".format(alice_raw)}
    bob = {"Authorization": "Bearer {0}".format(bob_raw)}
    alice_ws = ["scpi-token.{0}".format(alice_raw), "scpi"]
    bob_ws = ["scpi-token.{0}".format(bob_raw), "scpi"]
    manager = SessionManager()
    app = create_app(manager, token_store=store)
    with TestClient(app) as client:
        yield client, alice, bob, alice_ws, bob_ws
    manager.close_all()


def test_claim_is_refused_while_owner_is_watching_stream(two_users_ws):
    """The owner-watching flag must block a claim even when the idle
    threshold alone would allow it -- without the flag, this would 200.
    """
    client, alice, bob, alice_ws, _bob_ws = two_users_ws
    sid = _make_session(client, alice)["id"]
    client.app.state.abandon_after = 0.0  # threshold alone would allow the claim
    with client.websocket_connect("/api/sessions/{0}/stream".format(sid), subprotocols=alice_ws) as ws:
        assert ws.receive_json()["type"] == "state"
        response = client.post("/api/sessions/{0}/claim".format(sid), headers=bob)
        assert response.status_code == 409
        assert response.json()["detail"]


def test_claim_succeeds_after_owner_stream_disconnects(two_users_ws):
    """The owner-watching flag must clear on disconnect, or an owner who
    closed their stream tab stays permanently unclaimable.
    """
    client, alice, bob, alice_ws, _bob_ws = two_users_ws
    sid = _make_session(client, alice)["id"]
    client.app.state.abandon_after = 0.0
    with client.websocket_connect("/api/sessions/{0}/stream".format(sid), subprotocols=alice_ws) as ws:
        assert ws.receive_json()["type"] == "state"
    response = client.post("/api/sessions/{0}/claim".format(sid), headers=bob)
    assert response.status_code == 200
