"""Revocation tears a live stream down -- by both triggers, proven separately."""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from scpi_control.server.admin.app import create_admin_app
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


def _delete_identity_on_the_panel(client, admin_app, name):
    """DELETE /api/identities/{name} on the admin app, on the gateway's loop.

    A second ``TestClient`` would be the obvious way to reach the panel, and it
    would quietly invalidate the test: each TestClient starts its own portal, so
    the admin route would run on a *second* event loop and set the gateway
    loop's events from a foreign thread -- the harness reintroducing the very
    defect ``_revoke_on_the_serving_loop`` exists to keep out of this file, and
    the opposite of what ships. ``__main__.py`` runs both apps on one loop in
    one process (``_run_servers``); that shared loop is what makes the panel's
    ``Event.set()`` safe on a live socket, so a test of that seam has to
    reproduce it.

    Driving httpx's ASGI transport from inside the gateway client's portal does:
    one loop, the panel's real middleware stack (TrustedHost, same-Origin) and
    the real route, arriving at the same registry the open socket registered
    with. The Host must be 127.0.0.1 because TrustedHostMiddleware allows
    nothing else, and no Origin is sent -- which is what a same-origin fetch
    from the panel's own page looks like.
    """
    async def _request():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=admin_app), base_url="http://127.0.0.1") as http:
            return await http.delete("/api/identities/{0}".format(name))

    return client.portal.call(_request)


def test_the_admin_route_closes_a_live_stream_and_frees_the_session(tmp_path):
    # The seam. Everything either side of it was already covered and the seam
    # itself was not: the route was tested against a synthetic asyncio.Event
    # (tests/test_server_admin_api.py) and the teardown was tested by calling
    # revoke_identity directly (above), so the wiring that joins them -- the
    # panel and the gateway sharing one manager and one registry, as
    # __main__.py arranges -- was exercised only by a CLI test, against stubs.
    # This is the shipped path end to end: click Revoke, socket dies, bench
    # frees up.
    tokens = TokenStore(str(tmp_path / "tokens.json"))
    invitations = InvitationStore(str(tmp_path / "invitations.json"))
    # 3600s, as in the panel-path test above: the backstop cannot be what tore
    # this stream down, so only the route can have.
    gateway = create_app(token_store=tokens, invitation_store=invitations, stream_revocation_interval=3600.0)
    # Precisely __main__.py's wiring: the panel is handed the gateway's own
    # manager and registry. Private copies would give it an empty world and
    # this test would pass while revoking nothing.
    admin_app = create_admin_app(token_store=tokens, invitation_store=invitations, manager=gateway.state.manager, stream_registry=gateway.state.stream_registry)
    raw = tokens.mint("bob")
    with TestClient(gateway) as client:
        headers = {"Authorization": "Bearer {0}".format(raw)}
        session_id = client.post("/api/sessions", json={"label": "bench", "mock": True}, headers=headers).json()["id"]
        with client.websocket_connect("/api/sessions/{0}/stream".format(session_id), subprotocols=["scpi-token.{0}".format(raw), "scpi"]) as ws:
            ws.receive_json()  # initial frame: the socket is real and live
            session = gateway.state.manager.get(session_id)
            assert session.owner_watching() is True
            response = _delete_identity_on_the_panel(client, admin_app, "bob")
            assert response.status_code == 200
            # What the panel tells the operator, from the app that owns the
            # real state rather than a synthetic one: one device, one stream,
            # one session.
            assert response.json() == {"devices": 1, "streams": 1, "sessions": 1}
            with pytest.raises(WebSocketDisconnect) as excinfo:
                for _ in range(50):
                    ws.receive_json()
            assert excinfo.value.code == CLOSE_IDENTITY_REVOKED
        # The point of the whole sub-project: not that the socket closed, but
        # that the bench is usable again. Both halves of "claimable" -- no
        # owner, and nobody watching on that owner's behalf.
        assert session.owner == ""
        assert session.owner_watching() is False


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
