# tests/test_server_stream_ws.py
"""WebSocket streaming tests. Skipped when the [web] extra is not installed."""

import asyncio
import time

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")  # fastapi.testclient needs it; raises RuntimeError (not ImportError) without it
from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from scpi_control.server.api.stream import _enqueue  # noqa: E402
from scpi_control.server.app import create_app  # noqa: E402
from scpi_control.server.sessions import SessionManager  # noqa: E402


@pytest.fixture()
def client(gateway_auth):
    store, headers, _raw = gateway_auth
    manager = SessionManager()
    app = create_app(manager, token_store=store)
    with TestClient(app) as test_client:
        test_client.headers.update(headers)
        yield test_client
    manager.close_all()


@pytest.fixture()
def client_manager(gateway_auth):
    """Like ``client`` but also hands back the manager for white-box assertions."""
    store, headers, _raw = gateway_auth
    manager = SessionManager()
    app = create_app(manager, token_store=store)
    with TestClient(app) as test_client:
        test_client.headers.update(headers)
        yield test_client, manager
    manager.close_all()


@pytest.fixture()
def ws_subprotocols(gateway_auth):
    """WebSocket handshakes ignore default client headers; auth via subprotocol."""
    _store, _headers, raw = gateway_auth
    return ["scpi-token.{0}".format(raw), "scpi"]


def _create_mock(client):
    response = client.post("/api/sessions", json={"mock": True})
    assert response.status_code == 201
    return response.json()["id"]


def test_stream_sends_initial_state_then_waveforms(client, ws_subprotocols):
    sid = _create_mock(client)
    with client.websocket_connect("/api/sessions/{0}/stream".format(sid), subprotocols=ws_subprotocols) as ws:
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


def test_stream_relays_state_broadcast_after_mutation(client, ws_subprotocols):
    sid = _create_mock(client)
    with client.websocket_connect("/api/sessions/{0}/stream".format(sid), subprotocols=ws_subprotocols) as ws:
        assert ws.receive_json()["type"] == "state"
        response = client.patch("/api/sessions/{0}/scope/timebase".format(sid), json={"timebase": 0.002})
        assert response.status_code == 200
        for _ in range(20):
            msg = ws.receive_json()
            if msg["type"] == "state" and msg["state"]["timebase"] == 0.002:
                break
        else:
            pytest.fail("no state broadcast observed")


def test_stream_unknown_session_closes(client, ws_subprotocols):
    with pytest.raises(Exception):
        with client.websocket_connect("/api/sessions/nope/stream", subprotocols=ws_subprotocols) as ws:
            ws.receive_json()


# --- Fix 1: bounded outbox with drop-oldest --------------------------------


def test_enqueue_appends_when_not_full():
    q = asyncio.Queue(maxsize=4)
    _enqueue(q, {"type": "state"})
    assert q.qsize() == 1


def test_enqueue_drops_oldest_waveform_when_full():
    q = asyncio.Queue(maxsize=4)
    for i in range(4):
        q.put_nowait({"type": "waveform", "channel": 1, "seq": i})
    _enqueue(q, {"type": "waveform", "channel": 1, "seq": 99})
    items = [q.get_nowait() for _ in range(q.qsize())]
    assert len(items) <= 4
    seqs = [m["seq"] for m in items]
    assert 99 in seqs  # newest frame present
    assert 0 not in seqs  # oldest frame dropped


def test_enqueue_preserves_control_and_drops_incoming_waveform():
    q = asyncio.Queue(maxsize=4)
    for i in range(4):
        q.put_nowait({"type": "state", "n": i})
    _enqueue(q, {"type": "waveform", "channel": 1})
    items = [q.get_nowait() for _ in range(q.qsize())]
    assert len(items) == 4
    assert all(m["type"] == "state" for m in items)  # control frames preserved
    assert [m["n"] for m in items] == [0, 1, 2, 3]  # order intact, waveform dropped


# --- Fix 2: idle sessions still notice client disconnect -------------------


def test_idle_stream_detects_disconnect_and_unsubscribes(client_manager, ws_subprotocols):
    client, manager = client_manager
    sid = _create_mock(client)
    session = manager.get(sid)
    # Disable ch1 -> the session now publishes nothing, so the sender parks.
    assert client.patch("/api/sessions/{0}/scope/channels/1".format(sid), json={"enabled": False}).status_code == 200
    with client.websocket_connect("/api/sessions/{0}/stream".format(sid), subprotocols=ws_subprotocols) as ws:
        assert ws.receive_json()["type"] == "state"
    # Client context exited -> disconnect. The receiver must notice and unsubscribe.
    deadline = time.time() + 5
    while session._subscribers and time.time() < deadline:
        time.sleep(0.05)
    assert session._subscribers == []


# --- Fix 5: deleting a session closes its streams --------------------------


def test_delete_session_closes_stream(client, ws_subprotocols):
    sid = _create_mock(client)
    with client.websocket_connect("/api/sessions/{0}/stream".format(sid), subprotocols=ws_subprotocols) as ws:
        assert ws.receive_json()["type"] == "state"
        assert client.delete("/api/sessions/{0}".format(sid)).status_code == 204
        closed_seen = False
        with pytest.raises(WebSocketDisconnect) as exc_info:
            for _ in range(200):
                msg = ws.receive_json()
                if msg["type"] == "closed":
                    closed_seen = True
        assert closed_seen
        assert exc_info.value.code == 4410
