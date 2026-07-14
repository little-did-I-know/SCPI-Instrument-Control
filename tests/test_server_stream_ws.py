# tests/test_server_stream_ws.py
"""WebSocket streaming tests. Skipped when the [web] extra is not installed."""

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from scpi_control.server.app import create_app  # noqa: E402
from scpi_control.server.sessions import SessionManager  # noqa: E402


@pytest.fixture()
def client():
    manager = SessionManager()
    app = create_app(manager)
    with TestClient(app) as test_client:
        yield test_client
    manager.close_all()


def _create_mock(client):
    response = client.post("/api/sessions", json={"mock": True})
    assert response.status_code == 201
    return response.json()["id"]


def test_stream_sends_initial_state_then_waveforms(client):
    sid = _create_mock(client)
    with client.websocket_connect("/api/sessions/{0}/stream".format(sid)) as ws:
        first = ws.receive_json()
        assert first["type"] == "state"
        assert first["state"]["channels"]["1"]["enabled"] is True
        # channel 1 is enabled on the default mock -> waveform frames flow
        for _ in range(10):
            msg = ws.receive_json()
            if msg["type"] == "waveform":
                assert msg["channel"] == 1
                assert 0 < len(msg["points"]) <= 2000
                break
        else:
            pytest.fail("no waveform frame received")


def test_stream_relays_state_broadcast_after_mutation(client):
    sid = _create_mock(client)
    with client.websocket_connect("/api/sessions/{0}/stream".format(sid)) as ws:
        assert ws.receive_json()["type"] == "state"
        response = client.patch("/api/sessions/{0}/scope/timebase".format(sid), json={"timebase": 0.002})
        assert response.status_code == 200
        for _ in range(20):
            msg = ws.receive_json()
            if msg["type"] == "state" and msg["state"]["timebase"] == 0.002:
                break
        else:
            pytest.fail("no state broadcast observed")


def test_stream_unknown_session_closes(client):
    with pytest.raises(Exception):
        with client.websocket_connect("/api/sessions/nope/stream") as ws:
            ws.receive_json()
