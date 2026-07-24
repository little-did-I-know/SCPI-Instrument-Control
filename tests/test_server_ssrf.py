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


def test_refusal_does_not_echo_peer_bytes(client):
    response = client.post("/api/sessions", json={"label": "x", "address": "192.168.99.99", "port": 22})
    assert response.status_code == 400
    assert "SSH" not in response.text and "OpenSSH" not in response.text


def test_mock_sessions_bypass_the_policy(client):
    assert client.post("/api/sessions", json={"label": "x", "mock": True}).status_code == 201
