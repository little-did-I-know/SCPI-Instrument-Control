"""Session creation refuses disallowed targets and does not reflect peer bytes."""

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from scpi_control.server.app import create_app  # noqa: E402
from scpi_control.server.auth import TokenStore  # noqa: E402
from scpi_control.server.sessions import SessionManager  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    store = TokenStore(str(tmp_path / "tokens.json"))
    headers = {"Authorization": "Bearer {0}".format(store.mint("tester"))}
    manager = SessionManager()
    app = create_app(manager, token_store=store)
    with TestClient(app) as test_client:
        test_client.headers.update(headers)
        yield test_client
    manager.close_all()


def test_loopback_target_is_refused(client):
    response = client.post("/api/sessions", json={"label": "x", "address": "127.0.0.1", "port": 5025})
    assert response.status_code == 400


def test_non_scpi_port_is_refused(client):
    response = client.post("/api/sessions", json={"label": "x", "address": "192.168.99.99", "port": 6379})
    assert response.status_code == 400
    assert "6379" in response.json()["detail"]


def test_port_rejection_response_contains_only_the_synthetic_policy_reason(client):
    # Port 22 is rejected on the port-allowlist check alone (netpolicy.py), before
    # any resolution or connection attempt -- this never reaches Oscilloscope or
    # SocketConnection, so it cannot exercise (or guard) the socket layer. It only
    # confirms the HTTP-level rejection body is exactly netpolicy's synthetic
    # reason text, with nothing else appended. For the guarantee that a real
    # connection failure can't leak peer-read bytes, see
    # tests/test_socket_connection.py::TestSocketConnect::test_connect_failure_does_not_leak_peer_bytes.
    response = client.post("/api/sessions", json={"label": "x", "address": "192.168.99.99", "port": 22})
    assert response.status_code == 400
    assert response.json()["detail"] == "refusing to connect to 192.168.99.99: port 22 is not in the allowed set [5025]"


def test_mock_sessions_bypass_the_policy(client):
    assert client.post("/api/sessions", json={"label": "x", "mock": True}).status_code == 201


def test_create_app_rejects_manager_and_allowed_ports_together(tmp_path):
    # allowed_ports is silently dropped when a manager is also passed in (it only
    # seeds a manager create_app builds itself). A caller who passes both would
    # reasonably assume the two compose, and could end up with no port policy at
    # all instead of the stricter one they asked for. That must fail loudly.
    store = TokenStore(str(tmp_path / "tokens.json"))
    manager = SessionManager()
    try:
        with pytest.raises(ValueError):
            create_app(manager, token_store=store, allowed_ports=frozenset({5025, 1861}))
    finally:
        manager.close_all()
