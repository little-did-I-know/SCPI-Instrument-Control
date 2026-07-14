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
