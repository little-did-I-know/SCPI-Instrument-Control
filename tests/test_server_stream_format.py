# tests/test_server_stream_format.py
"""WebSocket stream format negotiation: ?format=binary opts a socket into dense
binary waveform frames; the default stays the JSON contract; two sockets on one
session may differ. Skipped when the [web] extra is not installed."""

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from starlette.websockets import WebSocketDisconnect  # noqa: E402

from scpi_control.server.api import stream as stream_module  # noqa: E402
from scpi_control.server.app import create_app  # noqa: E402
from scpi_control.server.frames import decode_binary  # noqa: E402
from scpi_control.server.sessions import SessionManager  # noqa: E402

pytestmark = pytest.mark.timeout(30)


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
def ws_subprotocols(gateway_auth):
    _store, _headers, raw = gateway_auth
    return ["scpi-token.{0}".format(raw), "scpi"]


def _create_mock(client):
    response = client.post("/api/sessions", json={"mock": True})
    assert response.status_code == 201
    return response.json()["id"]


def _first_waveform_bytes(ws, tries=20):
    """Skip text control frames until a binary frame arrives (or fail)."""
    for _ in range(tries):
        message = ws.receive()
        if "bytes" in message and message["bytes"] is not None:
            return message["bytes"]
        assert message.get("text") is not None, "neither text nor bytes in {0!r}".format(message)
    pytest.fail("no binary frame received")


def test_binary_format_delivers_dense_float32_frames_and_text_control_frames(client, ws_subprotocols):
    sid = _create_mock(client)
    with client.websocket_connect("/api/sessions/{0}/stream?format=binary".format(sid), subprotocols=ws_subprotocols) as ws:
        first = ws.receive_json()  # the opening state frame is text even in binary mode
        assert first["type"] == "state"
        header, samples = decode_binary(_first_waveform_bytes(ws))
        assert header["type"] == "waveform" and header["channel"] == 1 and header["dtype"] == "f32"
        # the default mock is 1 MSa/s x 14 div x 1 ms/div = 14 000 points -- far above the JSON cap
        assert header["n"] == len(samples) == 14_000
        assert "seq" in header


def test_default_format_is_the_unchanged_json_contract(client, ws_subprotocols):
    sid = _create_mock(client)
    with client.websocket_connect("/api/sessions/{0}/stream".format(sid), subprotocols=ws_subprotocols) as ws:
        assert ws.receive_json()["type"] == "state"
        for _ in range(10):
            msg = ws.receive_json()  # a binary frame here would raise: receive_json needs text
            if msg["type"] == "waveform":
                assert set(msg) == {"type", "channel", "t0", "dt", "points"}
                assert 0 < len(msg["points"]) <= 2000
                break
        else:
            pytest.fail("no waveform frame received")


def test_explicit_json_format_behaves_like_the_default(client, ws_subprotocols):
    sid = _create_mock(client)
    with client.websocket_connect("/api/sessions/{0}/stream?format=json".format(sid), subprotocols=ws_subprotocols) as ws:
        assert ws.receive_json()["type"] == "state"
        for _ in range(10):
            msg = ws.receive_json()
            if msg["type"] == "waveform":
                assert "samples" not in msg and "seq" not in msg
                break
        else:
            pytest.fail("no waveform frame received")


def test_two_sockets_on_one_session_each_get_their_own_encoding(client, ws_subprotocols):
    sid = _create_mock(client)
    path = "/api/sessions/{0}/stream".format(sid)
    with client.websocket_connect(path, subprotocols=ws_subprotocols) as text_ws, client.websocket_connect(path + "?format=binary", subprotocols=ws_subprotocols) as bin_ws:
        assert text_ws.receive_json()["type"] == "state"
        assert bin_ws.receive_json()["type"] == "state"
        header, samples = decode_binary(_first_waveform_bytes(bin_ws))
        assert len(samples) == header["n"] > 2000
        for _ in range(10):
            msg = text_ws.receive_json()
            if msg["type"] == "waveform":
                assert len(msg["points"]) <= 2000
                break
        else:
            pytest.fail("no JSON waveform frame on the text socket")


def test_unknown_format_closes_the_socket(client, ws_subprotocols):
    # The socket is accepted, THEN closed with CLOSE_UNKNOWN_FORMAT -- unlike
    # a close-before-accept (e.g. test_stream_unknown_session_closes), which a
    # client only ever sees as a failed handshake. Accepting first is what
    # makes the 4400 code actually observable: receive_json() raises
    # WebSocketDisconnect carrying it.
    sid = _create_mock(client)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/sessions/{0}/stream?format=msgpack".format(sid), subprotocols=ws_subprotocols) as ws:
            ws.receive_json()
    assert exc_info.value.code == stream_module.CLOSE_UNKNOWN_FORMAT


def test_the_unknown_format_close_code_is_distinct():
    assert stream_module.CLOSE_UNKNOWN_FORMAT == 4400
    assert stream_module.CLOSE_UNKNOWN_FORMAT not in (4404, 4410, 4403, 4500)


def test_outbox_is_sized_for_dense_frames():
    # 256 x ~400 kB per slow client was the old bound; dense frames need a
    # tighter one, and eviction of the oldest waveform keeps a slow client current.
    assert stream_module.OUTBOX_MAXSIZE == 32


def test_encode_helper_routes_by_format():
    import numpy as np

    from scpi_control.server.frames import waveform_message

    msg = waveform_message(1, np.arange(3) * 1e-6, [0.0, 1.0, 2.0], seq=1)
    assert isinstance(stream_module._encode(msg, binary=True), bytes)
    assert stream_module._encode(msg, binary=False)["points"] == [0.0, 1.0, 2.0]
    state = {"type": "state", "state": {}}
    assert stream_module._encode(state, binary=True) is state  # control frames stay JSON in both modes
