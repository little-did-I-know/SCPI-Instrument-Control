"""Session ownership: the creating identity owns the session."""

import threading
import time

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from scpi_control.server.app import create_app  # noqa: E402
from scpi_control.server.auth import TokenStore  # noqa: E402
from scpi_control.server.ownership import WRITE_ROUTES  # noqa: E402
from scpi_control.server.sessions import SessionManager  # noqa: E402
from tests.route_introspection import iter_http_routes  # noqa: E402


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
    ("POST", "/sessions/{session_id}/command"): {"command": "*RST"},
    ("POST", "/sessions/{session_id}/scope/command"): {"command": "*RST"},
    ("PUT", "/sessions/{session_id}/scope/measurements"): [{"channel": 1, "mtype": "PKPK"}],
    ("POST", "/sessions/{session_id}/scope/references"): {"name": "ref", "channel": 1},
    ("POST", "/sessions/{session_id}/owner"): {"name": "carol"},
    ("PATCH", "/sessions/{session_id}/psu/outputs/{n}/enable"): {"enabled": True},
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
    # iter_http_routes is version-robust: Starlette 1.x nests include_router
    # routes so a flat app.routes walk finds almost none (see route_introspection).
    for method, path in iter_http_routes(client.app):
        if (method, path) in write_paths or (method, path) in _OWNERSHIP_CONFLICT_EXEMPT:
            continue
        checked += 1
        url = _concrete(path, sid)
        response = client.request(method, url, headers=bob, json=_BODY_OVERRIDES.get((method, url)), params=_QUERY_OVERRIDES.get(url))
        if response.status_code == 409:
            gated.append("{0} {1} -> {2}".format(method, path, response.status_code))

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


def test_claim_succeeds_once_owner_is_idle(two_users):
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
    response = client.post("/api/sessions/{0}/owner".format(sid), json={"name": "bob"}, headers=owner)
    assert response.status_code == 200
    assert response.json()["owner"] == "bob"
    # Functional check, not just the echoed field: bob can now write, alice cannot.
    assert client.patch("/api/sessions/{0}/scope/timebase".format(sid), json={"timebase": 1e-3}, headers=other).status_code == 200
    assert client.patch("/api/sessions/{0}/scope/timebase".format(sid), json={"timebase": 1e-3}, headers=owner).status_code == 409


def test_non_owner_cannot_hand_off(two_users):
    client, owner, other = two_users
    sid = _make_session(client, owner)["id"]
    assert client.post("/api/sessions/{0}/owner".format(sid), json={"name": "bob"}, headers=other).status_code == 409


def test_hand_off_to_unknown_identity_is_rejected(two_users):
    """name must be a real token-store identity; a typo must not silently
    write-lock the session for everyone until abandon_after elapses.
    """
    client, owner, _other = two_users
    sid = _make_session(client, owner)["id"]
    response = client.post("/api/sessions/{0}/owner".format(sid), json={"name": "carol"}, headers=owner)
    assert response.status_code == 400
    assert client.get("/api/sessions/{0}".format(sid), headers=owner).json()["owner"] == "alice"


def test_hand_off_to_empty_name_releases_ownership(two_users):
    """An empty name is the documented explicit release: it unowns the
    session so it becomes immediately claimable, with no named recipient.
    """
    client, owner, other = two_users
    sid = _make_session(client, owner)["id"]
    response = client.post("/api/sessions/{0}/owner".format(sid), json={"name": ""}, headers=owner)
    assert response.status_code == 200
    assert response.json()["owner"] == ""
    assert client.post("/api/sessions/{0}/claim".format(sid), headers=other).status_code == 200


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
        assert claim(session, "someone", 300.0) is True
        assert session.owner == "someone"
    finally:
        manager.close_all()


def test_non_owner_read_does_not_refresh_owner_last_active(two_users):
    """require_session only touches owner_last_active for the owner's own
    reads. A non-owner polling a read route (e.g. GET /scope/state during a
    capture) must never extend the owner's claim-protection window, or an
    authenticated non-owner could keep a session permanently unclaimable
    just by reading it -- defeating the claim mechanism entirely.
    """
    client, owner, other = two_users
    sid = _make_session(client, owner)["id"]
    session = client.app.state.manager.get(sid)
    session.owner_last_active -= 1000.0
    stale = session.owner_last_active
    assert client.get("/api/sessions/{0}/scope/state".format(sid), headers=other).status_code == 200
    assert session.owner_last_active == stale


def test_owner_read_refreshes_owner_last_active(two_users):
    """Paired with the non-owner test above: the owner's own read must still
    count as activity, or a watching-but-not-writing owner looks idle.
    """
    client, owner, _other = two_users
    sid = _make_session(client, owner)["id"]
    session = client.app.state.manager.get(sid)
    session.owner_last_active -= 1000.0
    stale = session.owner_last_active
    assert client.get("/api/sessions/{0}/scope/state".format(sid), headers=owner).status_code == 200
    assert session.owner_last_active > stale


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


# --- Owner-watching must track identity, not a connect-time snapshot -------


def test_claim_while_watching_protects_new_owner_from_reclaim(two_users_ws):
    """Bob opens the stream while alice still owns the session, then claims
    it -- the natural "Claim" button flow in a UI that already has the
    stream open. A boolean snapshot computed at connect time (before bob
    was owner) never flips true for him, so alice could reclaim mid-capture.
    Watching must be evaluated against the *current* owner at claim time.
    """
    client, alice, bob, _alice_ws, bob_ws = two_users_ws
    sid = _make_session(client, alice)["id"]
    client.app.state.abandon_after = 0.0  # idle threshold alone would allow either claim
    with client.websocket_connect("/api/sessions/{0}/stream".format(sid), subprotocols=bob_ws) as ws:
        assert ws.receive_json()["type"] == "state"
        response = client.post("/api/sessions/{0}/claim".format(sid), headers=bob)
        assert response.status_code == 200
        assert response.json()["owner"] == "bob"
        # bob is now owner and already watching -- alice must not be able to
        # reclaim out from under him.
        response = client.post("/api/sessions/{0}/claim".format(sid), headers=alice)
        assert response.status_code == 409


def test_handoff_with_stale_watcher_stays_claimable(two_users_ws):
    """Alice watches, then explicitly hands off to bob. Alice's browser tab
    stays open (a stale watcher). owner_watching() must key off bob -- the
    current owner -- not alice's lingering socket, or the session becomes
    permanently unclaimable despite bob (the actual owner) never watching.
    """
    client, alice, bob, alice_ws, _bob_ws = two_users_ws
    sid = _make_session(client, alice)["id"]
    client.app.state.abandon_after = 0.0
    with client.websocket_connect("/api/sessions/{0}/stream".format(sid), subprotocols=alice_ws) as ws:
        assert ws.receive_json()["type"] == "state"
        response = client.post("/api/sessions/{0}/owner".format(sid), json={"name": "bob"}, headers=alice)
        assert response.status_code == 200
        assert response.json()["owner"] == "bob"
        # bob (the current owner) isn't watching -- alice's stale socket must
        # not block a claim.
        response = client.post("/api/sessions/{0}/claim".format(sid), headers=alice)
        assert response.status_code == 200


def test_watcher_released_on_abnormal_disconnect(two_users_ws, monkeypatch):
    """The finally block in the stream route must release the watcher slot
    even when the connection tears down abnormally -- the handler raises
    before ever sending a frame -- rather than via a clean client close.
    """
    from scpi_control.server.adapters import ScopeAdapter

    client, alice, bob, alice_ws, _bob_ws = two_users_ws
    sid = _make_session(client, alice)["id"]
    client.app.state.abandon_after = 0.0

    raised = []
    reached = threading.Event()

    def _boom(_self, _scope):
        # Recording the call is inside the same body as the raise, so if a
        # future edit swaps this helper for a non-raising stand-in (e.g.
        # ``return {}``), the whole body -- including this append -- goes
        # with it, and the assertion below catches the decay into a
        # duplicate of the clean-close test.
        raised.append(True)
        reached.set()
        raise RuntimeError("simulated mid-stream failure")

    # The stream handler now asks the session's *adapter* for its opening
    # frame (adapter.initial_frame), so that is the seam to break.
    monkeypatch.setattr(ScopeAdapter, "initial_frame", _boom)
    # No receive_json for a *state* frame here: the handler never gets one.
    #
    # But we cannot just close immediately either. The handler reaches
    # initial_frame via ``session.submit(...)`` onto the session's worker
    # thread, so it runs asynchronously relative to the handshake -- closing
    # the socket right away races that dispatch, and the job may never run.
    # That race made this test fail intermittently in CI on whichever
    # interpreter happened to lose it (3.10 on one run, 3.11 on the next, each
    # time passing on the others). Waiting for the helper to actually fire
    # removes the timing dependency; the timeout keeps a genuine regression
    # from hanging the suite.
    with client.websocket_connect("/api/sessions/{0}/stream".format(sid), subprotocols=alice_ws):
        assert reached.wait(timeout=10.0), "handler never reached initial_frame within 10s"

    assert raised, "abnormal path never exercised -- initial_frame must raise, not return"

    # If the watcher slot leaked, alice would still read as "watching" and
    # this claim (owner idle, threshold 0) would be wrongly refused.
    response = client.post("/api/sessions/{0}/claim".format(sid), headers=bob)
    assert response.status_code == 200


# --- A Counter, not a set: same identity, two tabs --------------------------


def test_owner_watching_survives_one_of_two_tabs_closing(two_users_ws):
    """The owner opens the live stream in two tabs. Closing one tab must not
    clear the watching flag while the other is still open -- this is the
    exact scenario a Counter was chosen over a set to handle: a plain
    membership set would drop the identity on the first close even though a
    second tab from the same identity is still live.
    """
    client, alice, bob, alice_ws, _bob_ws = two_users_ws
    sid = _make_session(client, alice)["id"]
    client.app.state.abandon_after = 0.0  # idle threshold alone would allow the claim
    with client.websocket_connect("/api/sessions/{0}/stream".format(sid), subprotocols=alice_ws) as ws1:
        assert ws1.receive_json()["type"] == "state"
        with client.websocket_connect("/api/sessions/{0}/stream".format(sid), subprotocols=alice_ws) as ws2:
            assert ws2.receive_json()["type"] == "state"
        # ws2 (second tab) just closed; ws1 (same identity) is still open,
        # so the owner must still read as watching.
        response = client.post("/api/sessions/{0}/claim".format(sid), headers=bob)
        assert response.status_code == 409
    # Both tabs are now closed -- no longer watching.
    response = client.post("/api/sessions/{0}/claim".format(sid), headers=bob)
    assert response.status_code == 200


def test_release_owner_watching_callback_is_idempotent():
    """The unmark callback returned by mark_owner_watching must decrement at
    most once even if invoked twice (e.g. a duplicate release on some
    disconnect path). Without the idempotency latch, a second call on one
    tab's callback would wrongly clear a still-live second tab from the same
    identity, and the per-identity count would be able to go negative.
    """
    from scpi_control.server.sessions import SessionManager

    manager = SessionManager()
    try:
        session = manager.create("s", mock=True)
        session.owner = "alice"
        unmark_tab1 = session.mark_owner_watching("alice")
        unmark_tab2 = session.mark_owner_watching("alice")  # a second open tab
        assert session._watchers["alice"] == 2

        unmark_tab1()
        assert session._watchers["alice"] == 1
        unmark_tab1()  # duplicate release of the same tab's callback
        assert session._watchers["alice"] >= 0
        assert session._watchers["alice"] == 1  # unchanged: idempotent, tab2 still live
        # tab2 never released its slot -- the owner must still read as watching.
        assert session.owner_watching() is True

        unmark_tab2()
        assert session._watchers["alice"] >= 0
        assert session.owner_watching() is False
    finally:
        manager.close_all()
