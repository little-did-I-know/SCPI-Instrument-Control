"""REST API tests. Skipped entirely when the [web] extra is not installed."""

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


def test_lists_no_sessions_initially(client):
    response = client.get("/api/sessions")
    assert response.status_code == 200
    assert response.json() == []


def test_unknown_session_is_404(client):
    response = client.get("/api/sessions/deadbeef")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] and body["detail"]


def test_unmatched_route_404_shares_error_shape(client):
    response = client.get("/api/definitely-not-a-route")
    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"error", "detail"}


def test_wrong_method_405_shares_error_shape(client):
    response = client.delete("/api/sessions")  # only GET/POST exist on this path
    assert response.status_code == 405
    body = response.json()
    assert set(body) == {"error", "detail"}


def create_mock_session(client, model=None):
    payload = {"mock": True}
    if model:
        payload["model"] = model
    response = client.post("/api/sessions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


class TestSessionEndpoints:
    def test_create_mock_session_returns_info(self, client):
        body = create_mock_session(client)
        assert body["state"] == "connected"
        assert body["mock"] is True
        assert body["model"] == "SDS1104X-E"
        assert body["dialect"] == "legacy"
        assert body["num_channels"] == 4

    def test_create_modern_mock_by_model(self, client):
        body = create_mock_session(client, model="SDS824X HD")
        assert body["model"] == "SDS824X HD"
        assert body["dialect"] == "modern"

    def test_create_real_session_requires_address(self, client):
        response = client.post("/api/sessions", json={"mock": False})
        assert response.status_code == 400

    def test_delete_session(self, client):
        body = create_mock_session(client)
        assert client.delete("/api/sessions/" + body["id"]).status_code == 204
        assert client.delete("/api/sessions/" + body["id"]).status_code == 404
        assert client.get("/api/sessions").json() == []


def test_models_endpoint_lists_registry(client):
    response = client.get("/api/models")
    assert response.status_code == 200
    models = response.json()
    names = [m["model_name"] for m in models]
    assert "SDS1104X-E" in names and "SDS824X HD" in names
    assert names == sorted(names)
    assert {"model_name", "series", "num_channels", "bandwidth_mhz", "dialect"} <= set(models[0])
