"""Revocation tears a live stream down -- by both triggers, proven separately."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from scpi_control.server.app import create_app
from scpi_control.server.auth import TokenStore
from scpi_control.server.invitations import InvitationStore
from scpi_control.server.revocation import revoke_identity

CLOSE_IDENTITY_REVOKED = 4403


def _client(tmp_path, interval):
    tokens = TokenStore(str(tmp_path / "tokens.json"))
    invitations = InvitationStore(str(tmp_path / "invitations.json"))
    app = create_app(token_store=tokens, invitation_store=invitations, stream_revocation_interval=interval)
    return app, tokens


def test_the_panel_path_closes_a_live_stream(tmp_path):
    # Interval is 3600s: if this passes, teardown came from the registry walk
    # and not from the backstop, which could not have run.
    app, tokens = _client(tmp_path, interval=3600.0)
    raw = tokens.mint("bob")
    with TestClient(app) as client:
        session_id = client.post("/api/sessions", json={"label": "bench", "mock": True}, headers={"Authorization": "Bearer {0}".format(raw)}).json()["id"]
        with client.websocket_connect("/api/sessions/{0}/stream".format(session_id), subprotocols=["scpi-token.{0}".format(raw), "scpi"]) as ws:
            ws.receive_json()  # initial frame proves the stream is live
            revoke_identity(tokens, app.state.manager, app.state.stream_registry, "bob")
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
    # not drop everyone watching.
    app, tokens = _client(tmp_path, interval=0.01)
    bob = tokens.mint("bob")
    robin = tokens.mint("robin")
    with TestClient(app) as client:
        session_id = client.post("/api/sessions", json={"label": "bench", "mock": True}, headers={"Authorization": "Bearer {0}".format(robin)}).json()["id"]
        with client.websocket_connect("/api/sessions/{0}/stream".format(session_id), subprotocols=["scpi-token.{0}".format(robin), "scpi"]) as ws:
            ws.receive_json()
            revoke_identity(tokens, app.state.manager, app.state.stream_registry, "bob")
            assert ws.receive_json() is not None
