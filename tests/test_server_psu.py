"""A PSU session must be a session in exactly the same way a scope session is.

The seam is only real if the shared lifecycle -- worker thread, error state,
close timeout, viewer counting -- behaves identically for a kind that shares
none of the scope's domain. These assertions are deliberately the same ones the
scope session is held to.
"""

import pytest

from scpi_control.connection.mock import MockConnection
from scpi_control.server.sessions import SessionManager

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")  # fastapi.testclient needs it; raises RuntimeError (not ImportError) without it
from fastapi.testclient import TestClient  # noqa: E402

from scpi_control.server.app import create_app  # noqa: E402


def _psu_connection():
    return MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,1.0")


@pytest.fixture
def manager():
    m = SessionManager()
    yield m
    m.close_all()


@pytest.fixture()
def psu_client(gateway_auth):
    """An authenticated HTTP client with one mock PSU session already created,
    exposed on ``.session_id`` -- same pattern as ``client`` in
    tests/test_server_api.py, plus the session bootstrap."""
    store, headers, _raw = gateway_auth
    manager = SessionManager()
    app = create_app(manager, token_store=store)
    with TestClient(app) as test_client:
        test_client.headers.update(headers)
        response = test_client.post("/api/sessions", json={"mock": True, "kind": "psu"})
        assert response.status_code == 201, response.text
        test_client.session_id = response.json()["id"]
        yield test_client
    manager.close_all()


@pytest.fixture()
def scope_client(gateway_auth):
    """Same as psu_client, but a mock scope session -- used to prove PSU
    routes reject a scope session (kind confusion guard)."""
    store, headers, _raw = gateway_auth
    manager = SessionManager()
    app = create_app(manager, token_store=store)
    with TestClient(app) as test_client:
        test_client.headers.update(headers)
        response = test_client.post("/api/sessions", json={"mock": True})
        assert response.status_code == 201, response.text
        test_client.session_id = response.json()["id"]
        yield test_client
    manager.close_all()


def test_a_psu_session_connects_and_reports_its_kind(manager):
    session = manager.create("psu", mock=True, kind="psu", _connection=_psu_connection())
    assert session.kind == "psu"
    assert session.state == "connected"
    assert "SPD3303X" in session.idn


def test_a_psu_session_closes_within_its_timeout(manager):
    """Shared lifecycle: the same close path the scope uses."""
    session = manager.create("psu", mock=True, kind="psu", _connection=_psu_connection())
    session.close(timeout=10.0)
    assert session.state == "closed"


def test_a_psu_session_counts_viewers_like_any_other(manager):
    session = manager.create("psu", mock=True, kind="psu", _connection=_psu_connection())
    assert session.viewers == 0
    unsubscribe = session.subscribe(lambda message: None)
    assert session.viewers == 1
    unsubscribe()
    assert session.viewers == 0


def test_the_default_kind_is_scope(manager):
    """The non-breaking guarantee: an existing caller that passes no kind gets
    exactly what it got before."""
    session = manager.create("scope", mock=True)
    assert session.kind == "scope"
    assert session.num_channels == 4


def test_psu_state_lists_every_output(psu_client):
    session_id = psu_client.session_id
    response = psu_client.get(f"/api/sessions/{session_id}/psu/state")
    assert response.status_code == 200
    outputs = response.json()["outputs"]
    assert outputs and outputs[0]["output"] == 1


def test_setting_voltage_and_current_round_trips(psu_client):
    session_id = psu_client.session_id
    response = psu_client.patch(f"/api/sessions/{session_id}/psu/outputs/1", json={"voltage": 3.3, "current": 0.5})
    assert response.status_code == 200
    state = psu_client.get(f"/api/sessions/{session_id}/psu/state").json()["outputs"][0]
    assert state["voltage"] == pytest.approx(3.3, abs=0.01)
    assert state["current"] == pytest.approx(0.5, abs=0.01)


def test_enabling_an_output_round_trips(psu_client):
    session_id = psu_client.session_id
    assert psu_client.patch(f"/api/sessions/{session_id}/psu/outputs/1/enable", json={"enabled": True}).status_code == 200
    assert psu_client.get(f"/api/sessions/{session_id}/psu/state").json()["outputs"][0]["enabled"] is True


def test_an_unknown_output_is_rejected(psu_client):
    session_id = psu_client.session_id
    response = psu_client.patch(f"/api/sessions/{session_id}/psu/outputs/99", json={"voltage": 1.0})
    assert response.status_code == 400


def test_a_psu_route_rejects_a_scope_session(scope_client):
    """Kind confusion must be an error, not an obscure AttributeError from a
    driver that does not have the method being called."""
    session_id = scope_client.session_id
    response = scope_client.get(f"/api/sessions/{session_id}/psu/state")
    assert response.status_code == 400


def test_a_scope_route_rejects_a_psu_session(psu_client):
    session_id = psu_client.session_id
    response = psu_client.get(f"/api/sessions/{session_id}/scope/state")
    assert response.status_code == 400
