"""The admin app's view of live sessions: list, release, and close.

Unauthenticated by design -- see admin/app.py -- so the listing test asserts
reachability with no credential explicitly rather than leaving it implied.
"""

import pytest
from fastapi.testclient import TestClient

from scpi_control.server.admin.app import create_admin_app
from scpi_control.server.auth import TokenStore
from scpi_control.server.invitations import InvitationStore
from scpi_control.server.revocation import StreamRegistry
from scpi_control.server.sessions import SessionManager


@pytest.fixture
def admin_sessions(tmp_path):
    tokens = TokenStore(str(tmp_path / "tokens.json"))
    invitations = InvitationStore(str(tmp_path / "invitations.json"))
    manager = SessionManager()
    registry = StreamRegistry()
    app = create_admin_app(token_store=tokens, invitation_store=invitations, manager=manager, stream_registry=registry)
    # base_url is 127.0.0.1, not the httpx default "testserver": TrustedHostMiddleware
    # only allows 127.0.0.1/localhost, mirroring tests/test_server_admin_api.py.
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client, manager


def test_the_listing_reports_owner_viewers_and_idle_seconds(admin_sessions):
    client, manager = admin_sessions
    manager.create("bench-1", mock=True, owner="bob")
    rows = client.get("/api/sessions").json()
    assert len(rows) == 1
    row = rows[0]
    assert row["owner"] == "bob"
    assert row["viewers"] == 0
    assert isinstance(row["idle_seconds"], (int, float))


def test_the_listing_is_reachable_with_no_credential(admin_sessions):
    # The point of this app: no auth middleware, no token required. See
    # admin/app.py's module docstring for what stands in for a credential
    # instead.
    client, manager = admin_sessions
    manager.create("bench-1", mock=True, owner="bob")
    response = client.get("/api/sessions")
    assert response.status_code == 200
    assert response.json()[0]["owner"] == "bob"


def test_releasing_a_session_clears_its_owner(admin_sessions):
    client, manager = admin_sessions
    session = manager.create("bench-1", mock=True, owner="bob")
    response = client.post("/api/sessions/{0}/release".format(session.id))
    assert response.status_code == 204
    assert manager.get(session.id).owner == ""


def test_releasing_an_unknown_session_is_404(admin_sessions):
    client, _manager = admin_sessions
    assert client.post("/api/sessions/ghost/release").status_code == 404


def test_deleting_a_session_closes_it_and_removes_it(admin_sessions):
    client, manager = admin_sessions
    session = manager.create("bench-1", mock=True, owner="bob")
    response = client.delete("/api/sessions/{0}".format(session.id))
    assert response.status_code == 204
    assert session.state == "closed"
    assert session.id not in {s.id for s in manager.list()}


def test_deleting_an_unknown_session_is_404(admin_sessions):
    client, _manager = admin_sessions
    assert client.delete("/api/sessions/ghost").status_code == 404
