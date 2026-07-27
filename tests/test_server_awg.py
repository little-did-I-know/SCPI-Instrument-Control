"""An AWG session must be a session in exactly the same way the others are.

The seam is only real if the shared lifecycle -- worker thread, error state,
close timeout, viewer counting -- behaves identically for a third kind that
shares neither the scope's nor the PSU's domain. These assertions are
deliberately the same ones both existing kinds are held to.
"""

import pytest

from scpi_control.connection.mock import MockConnection
from scpi_control.server.sessions import SessionManager

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")  # fastapi.testclient needs it; raises RuntimeError (not ImportError) without it
from fastapi.testclient import TestClient  # noqa: E402

from scpi_control.server.app import create_app  # noqa: E402


def _awg_connection():
    return MockConnection("mock", awg_mode=True, awg_idn="Siglent Technologies,SDG1032X,SDG1XXXXX,2.01.01.37R1")


@pytest.fixture
def manager():
    m = SessionManager()
    yield m
    m.close_all()


def test_an_awg_session_connects_and_reports_its_kind(manager):
    session = manager.create("awg", mock=True, kind="awg", _connection=_awg_connection())
    assert session.kind == "awg"
    assert session.state == "connected"
    assert "SDG1032X" in session.idn


def test_an_awg_session_closes_within_its_timeout(manager):
    session = manager.create("awg", mock=True, kind="awg", _connection=_awg_connection())
    session.close(timeout=10.0)
    assert session.state == "closed"


def test_an_awg_session_counts_viewers_like_any_other(manager):
    session = manager.create("awg", mock=True, kind="awg", _connection=_awg_connection())
    assert session.viewers == 0
    unsubscribe = session.subscribe(lambda message: None)
    assert session.viewers == 1
    unsubscribe()
    assert session.viewers == 0


@pytest.fixture()
def awg_client(gateway_auth):
    """An authenticated HTTP client with one mock AWG session already created,
    exposed on ``.session_id`` -- same pattern as psu_client in
    tests/test_server_psu.py."""
    store, headers, _raw = gateway_auth
    manager = SessionManager()
    app = create_app(manager, token_store=store)
    with TestClient(app) as test_client:
        test_client.headers.update(headers)
        response = test_client.post("/api/sessions", json={"mock": True, "kind": "awg"})
        assert response.status_code == 201, response.text
        test_client.session_id = response.json()["id"]
        yield test_client
    manager.close_all()


@pytest.fixture()
def scope_client(gateway_auth):
    """A mock scope session -- used to prove the AWG routes refuse another kind."""
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


def test_awg_state_lists_every_channel(awg_client):
    response = awg_client.get("/api/sessions/{0}/awg/state".format(awg_client.session_id))
    assert response.status_code == 200, response.text
    channels = response.json()["channels"]
    assert channels and channels[0]["channel"] == 1


def test_setting_waveform_parameters_round_trips(awg_client):
    session_id = awg_client.session_id
    response = awg_client.patch(
        "/api/sessions/{0}/awg/channels/1".format(session_id),
        json={"function": "SINE", "frequency": 2000.0, "amplitude": 1.5, "offset": 0.25},
    )
    assert response.status_code == 200, response.text
    state = awg_client.get("/api/sessions/{0}/awg/state".format(session_id)).json()["channels"][0]
    assert state["function"] == "SINE"
    assert state["frequency"] == pytest.approx(2000.0, rel=1e-3)
    assert state["amplitude"] == pytest.approx(1.5, rel=1e-3)
    assert state["offset"] == pytest.approx(0.25, abs=0.01)


def test_setting_the_function_to_pulse_exposes_its_duty_cycle(awg_client):
    """The conditional read is part of the wire contract, not just an
    optimisation: a client renders the duty field off the presence of a value."""
    session_id = awg_client.session_id
    assert awg_client.patch("/api/sessions/{0}/awg/channels/1".format(session_id), json={"function": "PULSE"}).status_code == 200
    state = awg_client.get("/api/sessions/{0}/awg/state".format(session_id)).json()["channels"][0]
    assert state["duty_cycle"] is not None
    assert state["symmetry"] is None


def test_enabling_an_output_round_trips(awg_client):
    session_id = awg_client.session_id
    assert awg_client.patch("/api/sessions/{0}/awg/channels/1/enable".format(session_id), json={"enabled": True}).status_code == 200
    assert awg_client.get("/api/sessions/{0}/awg/state".format(session_id)).json()["channels"][0]["enabled"] is True


def test_all_outputs_off_turns_every_channel_off(awg_client):
    """A signal generator drives a real circuit. One action must kill every
    output, rather than N toggles raced against each other."""
    session_id = awg_client.session_id
    for n in (1, 2):
        awg_client.patch("/api/sessions/{0}/awg/channels/{1}/enable".format(session_id, n), json={"enabled": True})
    response = awg_client.post("/api/sessions/{0}/awg/outputs/off".format(session_id))
    assert response.status_code == 200, response.text
    for channel in awg_client.get("/api/sessions/{0}/awg/state".format(session_id)).json()["channels"]:
        assert channel["enabled"] is False, "channel {0} stayed on".format(channel["channel"])


def test_an_unknown_channel_is_rejected(awg_client):
    response = awg_client.patch("/api/sessions/{0}/awg/channels/99".format(awg_client.session_id), json={"frequency": 1000.0})
    assert response.status_code == 400


def test_an_unsupported_function_is_rejected(awg_client):
    """A bad function must be a named 400, not an obscure failure deep inside
    the worker thread."""
    response = awg_client.patch("/api/sessions/{0}/awg/channels/1".format(awg_client.session_id), json={"function": "TRIANGLE"})
    assert response.status_code == 400
    assert "TRIANGLE" in response.json()["detail"]


def test_an_awg_route_rejects_a_scope_session(scope_client):
    response = scope_client.get("/api/sessions/{0}/awg/state".format(scope_client.session_id))
    assert response.status_code == 400


def test_a_scope_route_rejects_an_awg_session(awg_client):
    response = awg_client.get("/api/sessions/{0}/scope/state".format(awg_client.session_id))
    assert response.status_code == 400


def test_patching_function_and_duty_cycle_together_writes_the_function_first(gateway_auth):
    """apply() in awg.py sets ``function`` before ``duty_cycle``/``symmetry`` on
    purpose: duty belongs to PULSE and symmetry to RAMP, so the shape
    parameter must land on the wire only after the function that makes it
    meaningful. A state round-trip can't tell the two orders apart -- the mock
    stores pulse_duty unconditionally either way -- but MockConnection records
    every write, so the order actually placed on the wire is directly
    observable. Built with an explicit _connection so the connection object
    (and its .writes log) is held here rather than built anonymously inside
    the adapter.
    """
    store, headers, _raw = gateway_auth
    manager = SessionManager()
    conn = _awg_connection()
    session = manager.create("awg", mock=True, kind="awg", _connection=conn)
    app = create_app(manager, token_store=store)
    try:
        with TestClient(app) as test_client:
            test_client.headers.update(headers)
            response = test_client.patch(
                "/api/sessions/{0}/awg/channels/1".format(session.id),
                json={"function": "PULSE", "duty_cycle": 25.0},
            )
            assert response.status_code == 200, response.text
    finally:
        manager.close_all()

    function_writes = [i for i, w in enumerate(conn.writes) if w.startswith("C1:BSWV WVTP,PULSE")]
    duty_writes = [i for i, w in enumerate(conn.writes) if w.startswith("C1:BSWV DUTY,")]
    assert function_writes, "the function write never reached the wire: {0}".format(conn.writes)
    assert duty_writes, "the duty_cycle write never reached the wire: {0}".format(conn.writes)
    assert function_writes[0] < duty_writes[0], "function must be written before duty_cycle: {0}".format(conn.writes)
