"""A PSU session must be a session in exactly the same way a scope session is.

The seam is only real if the shared lifecycle -- worker thread, error state,
close timeout, viewer counting -- behaves identically for a kind that shares
none of the scope's domain. These assertions are deliberately the same ones the
scope session is held to.
"""

import time

import pytest

from scpi_control.connection.mock import MockConnection
from scpi_control.server.sessions import SessionError, SessionManager

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")  # fastapi.testclient needs it; raises RuntimeError (not ImportError) without it
from fastapi.testclient import TestClient  # noqa: E402

from scpi_control.server.app import create_app  # noqa: E402


def _psu_connection():
    return MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,1.0")


class KillablePsuConnection(MockConnection):
    """A PSU mock whose wire can be pulled mid-session (mirrors the scope's
    KillableMock in tests/test_server_sessions.py)."""

    def kill(self):
        self._connected = False


def _wait_for(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


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
    """Shared lifecycle: the same close path the scope uses.

    Asserting ``state == "closed"`` alone proves nothing: close() sets that
    unconditionally *after* join(timeout=...), so a worker that ignored _STOP
    and outlived the join would still satisfy it. The thread and the job queue
    are what actually have to be dead.
    """
    session = manager.create("psu", mock=True, kind="psu", _connection=_psu_connection())
    session.close(timeout=10.0)
    assert session._thread.is_alive() is False, "close() returned but the worker thread is still running"
    assert session.state == "closed"
    with pytest.raises(SessionError):
        session.submit(lambda psu: psu.identify())


def test_a_psu_session_enters_the_error_state_when_the_wire_drops(manager):
    """The spec's dropped-wire case, for the PSU. The file's premise is that a
    PSU session is held to the same assertions as a scope session, and the
    scope has ``test_idle_poll_detects_dropped_connection``; without the PSU
    equivalent, the shared error path is only ever proven on one kind."""
    conn = KillablePsuConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,1.0")
    session = manager.create("psu", mock=True, kind="psu", _connection=conn)
    errors = []
    # _poll_tick returns early with no subscribers, so the drop is only ever
    # noticed while something is watching -- exactly as for a scope.
    unsubscribe = session.subscribe(errors.append)
    try:
        conn.kill()
        assert _wait_for(lambda: session.state == "error"), "poll tick never noticed the dropped PSU connection"
        assert any(m.get("type") == "error" for m in errors), "the drop must be announced on the stream, not only in session.state"
        with pytest.raises(SessionError):
            session.submit(lambda psu: psu.identify())
    finally:
        unsubscribe()


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
