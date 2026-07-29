"""Revocation tears a live stream down -- by both triggers, proven separately."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from scpi_control.server.app import create_app
from scpi_control.server.auth import TokenStore
from scpi_control.server.invitations import InvitationStore
from scpi_control.server.revocation import revoke_identity

CLOSE_IDENTITY_REVOKED = 4403

# Every ws.receive_json() here blocks with no deadline of its own, so a
# revocation that never reaches the socket presents as a HANG rather than a red
# test -- it would wedge CI instead of reporting. A module-level timeout turns
# it back into an ordinary failure, the same reason tests/test_server_stream_ws.py
# carries this mark. 30 s is far above anything here (the slowest backstop poll
# is 10 ms).
pytestmark = pytest.mark.timeout(30)


def _client(tmp_path, interval):
    tokens = TokenStore(str(tmp_path / "tokens.json"))
    invitations = InvitationStore(str(tmp_path / "invitations.json"))
    app = create_app(token_store=tokens, invitation_store=invitations, stream_revocation_interval=interval)
    return app, tokens


def _revoke_on_the_serving_loop(client, tokens, app, name):
    """Run revoke_identity on the loop the app is actually served on.

    Not a harness detail -- it is the constraint the feature is built around,
    and a revocation test that gets it wrong is exercising something the shipped
    code never does. Revocation ends in ``asyncio.Event.set()``
    (StreamRegistry.revoke), which is not thread-safe: called from the pytest
    main thread it reaches ``loop.call_soon`` on a loop owned by another thread,
    which appends the callback to that loop's ``_ready`` deque **without waking
    its selector**. On an otherwise idle loop the callback simply sits there --
    measured: a foreign-thread ``set()`` had not run its waiter a full second
    later, and ran instantly once the loop was poked.

    Under TestClient that is masked, not harmless: ``ws.receive_json()`` is
    itself a portal call, so the client's own next read wakes the loop and the
    revocation lands in milliseconds anyway. A green revocation test therefore
    proves nothing whatever about which thread signalled it -- which is why
    this helper asserts the affinity outright instead of leaving the next
    person to infer it from a passing run, and why every revocation test in
    this file goes through it.

    ``TestClient``'s blocking portal *is* the serving loop, so ``portal.call``
    runs the whole revocation on it: the same thread the shipped admin route
    runs on, where ``Event.set()`` is safe. In production the question does not
    arise -- the panel's route is a coroutine on the one loop that serves both
    apps.
    """
    portal = getattr(client, "portal", None)
    assert portal is not None, "TestClient no longer exposes .portal; find another way onto the serving loop (see this function's docstring)"

    def _revoke():
        # Not decoration: get_running_loop() raises RuntimeError anywhere but
        # the loop thread, so this is the on-loop assertion itself.
        asyncio.get_running_loop()
        return revoke_identity(tokens, app.state.manager, app.state.stream_registry, name)

    return portal.call(_revoke)


def test_the_panel_path_closes_a_live_stream(tmp_path):
    # Interval is 3600s: if this passes, teardown came from the registry walk
    # and not from the backstop, which could not have run.
    app, tokens = _client(tmp_path, interval=3600.0)
    raw = tokens.mint("bob")
    with TestClient(app) as client:
        session_id = client.post("/api/sessions", json={"label": "bench", "mock": True}, headers={"Authorization": "Bearer {0}".format(raw)}).json()["id"]
        with client.websocket_connect("/api/sessions/{0}/stream".format(session_id), subprotocols=["scpi-token.{0}".format(raw), "scpi"]) as ws:
            ws.receive_json()  # initial frame proves the stream is live
            _revoke_on_the_serving_loop(client, tokens, app, "bob")
            with pytest.raises(WebSocketDisconnect) as excinfo:
                for _ in range(50):
                    ws.receive_json()
            assert excinfo.value.code == CLOSE_IDENTITY_REVOKED


def test_the_backstop_closes_a_stream_revoked_by_another_process(tmp_path):
    # No registry involvement: a second TokenStore on the same file is exactly
    # what `scpi-web token revoke` is, and nothing in this process is told.
    app, tokens = _client(tmp_path, interval=0.01)
    raw = tokens.mint("bob")
    with TestClient(app) as client:
        session_id = client.post("/api/sessions", json={"label": "bench", "mock": True}, headers={"Authorization": "Bearer {0}".format(raw)}).json()["id"]
        with client.websocket_connect("/api/sessions/{0}/stream".format(session_id), subprotocols=["scpi-token.{0}".format(raw), "scpi"]) as ws:
            ws.receive_json()
            TokenStore(str(tmp_path / "tokens.json")).revoke("bob")
            with pytest.raises(WebSocketDisconnect) as excinfo:
                for _ in range(50):
                    ws.receive_json()
            assert excinfo.value.code == CLOSE_IDENTITY_REVOKED


def test_a_revoked_stream_stops_blocking_the_claim(tmp_path):
    # The bug that made this whole sub-project necessary: the socket closing is
    # not the point -- releasing owner_watching is. Assert the session is
    # claimable, not merely that the connection died.
    app, tokens = _client(tmp_path, interval=0.01)
    raw = tokens.mint("bob")
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer {0}".format(raw)}
        session_id = client.post("/api/sessions", json={"label": "bench", "mock": True}, headers=headers).json()["id"]
        with client.websocket_connect("/api/sessions/{0}/stream".format(session_id), subprotocols=["scpi-token.{0}".format(raw), "scpi"]) as ws:
            ws.receive_json()
            session = app.state.manager.list()[0]
            assert session.owner_watching() is True
            TokenStore(str(tmp_path / "tokens.json")).revoke("bob")
            with pytest.raises(WebSocketDisconnect) as excinfo:
                for _ in range(50):
                    ws.receive_json()
            assert excinfo.value.code == CLOSE_IDENTITY_REVOKED
        assert session.owner_watching() is False


def test_an_unrelated_identity_keeps_streaming(tmp_path):
    # Over-broad teardown would be worse than none: revoking one person must
    # not drop everyone watching. The mock's frames are deliberately left
    # running here -- the assertion *is* that one still arrives.
    app, tokens = _client(tmp_path, interval=0.01)
    bob = tokens.mint("bob")
    robin = tokens.mint("robin")
    with TestClient(app) as client:
        session_id = client.post("/api/sessions", json={"label": "bench", "mock": True}, headers={"Authorization": "Bearer {0}".format(robin)}).json()["id"]
        with client.websocket_connect("/api/sessions/{0}/stream".format(session_id), subprotocols=["scpi-token.{0}".format(robin), "scpi"]) as ws:
            ws.receive_json()
            _revoke_on_the_serving_loop(client, tokens, app, "bob")
            assert ws.receive_json() is not None
