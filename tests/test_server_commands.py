"""The SCPI console is not a scope feature.

Sending a raw command needs nothing kind-specific: both Oscilloscope and
PowerSupply expose write() and query(). It lived under /scope/ only because the
scope was the only kind, and once PR #125 put require_kind on those routes, a
PSU session's terminal would have 400'd rather than merely been hidden.

The old route keeps working, unchanged, because it is public API.
"""

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")  # fastapi.testclient needs it; raises RuntimeError (not ImportError) without it
from fastapi.testclient import TestClient  # noqa: E402

from scpi_control.server.app import create_app  # noqa: E402
from scpi_control.server.sessions import SessionManager  # noqa: E402


def _client(gateway_auth, body):
    store, headers, _raw = gateway_auth
    manager = SessionManager()
    app = create_app(manager, token_store=store)
    with TestClient(app) as test_client:
        test_client.headers.update(headers)
        response = test_client.post("/api/sessions", json=body)
        assert response.status_code == 201, response.text
        test_client.session_id = response.json()["id"]
        yield test_client
    manager.close_all()


@pytest.fixture()
def psu_client(gateway_auth):
    for client in _client(gateway_auth, {"mock": True, "kind": "psu"}):
        yield client


@pytest.fixture()
def scope_client(gateway_auth):
    for client in _client(gateway_auth, {"mock": True}):
        yield client


def test_a_psu_session_can_send_a_scpi_command(psu_client):
    """The whole point: this path 400s today because the only command route
    lives under /scope/ behind require_kind."""
    response = psu_client.post("/api/sessions/{0}/command".format(psu_client.session_id), json={"command": "*IDN?"})
    assert response.status_code == 200, response.text
    assert "SPD3303X" in response.json()["response"]


def test_a_scope_session_can_send_a_scpi_command(scope_client):
    response = scope_client.post("/api/sessions/{0}/command".format(scope_client.session_id), json={"command": "*IDN?"})
    assert response.status_code == 200, response.text
    assert response.json()["command"] == "*IDN?"
    assert response.json()["response"]


def test_a_write_command_returns_a_null_response(scope_client):
    """A command with no trailing '?' is a write: there is nothing to read back,
    and inventing a response would be a lie about the instrument."""
    response = scope_client.post("/api/sessions/{0}/command".format(scope_client.session_id), json={"command": "*RST"})
    assert response.status_code == 200, response.text
    assert response.json()["response"] is None


def test_an_empty_command_is_rejected(scope_client):
    response = scope_client.post("/api/sessions/{0}/command".format(scope_client.session_id), json={"command": "   "})
    assert response.status_code == 400


def test_an_unknown_session_is_404(scope_client):
    response = scope_client.post("/api/sessions/nope/command", json={"command": "*IDN?"})
    assert response.status_code == 404


def test_the_scope_command_route_is_unchanged(scope_client):
    """Public API: /scope/command keeps working exactly as it did."""
    response = scope_client.post("/api/sessions/{0}/scope/command".format(scope_client.session_id), json={"command": "*IDN?"})
    assert response.status_code == 200, response.text
    assert response.json()["response"]


def test_the_scope_command_route_still_refuses_a_psu_session(psu_client):
    """require_kind stays on the old route. Only the new one is kind-agnostic."""
    response = psu_client.post("/api/sessions/{0}/scope/command".format(psu_client.session_id), json={"command": "*IDN?"})
    assert response.status_code == 400
