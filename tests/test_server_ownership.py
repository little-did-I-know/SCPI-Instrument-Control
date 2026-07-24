"""Session ownership: the creating identity owns the session."""

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402

from scpi_control.server.app import create_app  # noqa: E402
from scpi_control.server.auth import TokenStore  # noqa: E402
from scpi_control.server.sessions import SessionManager  # noqa: E402


@pytest.fixture()
def two_users(tmp_path):
    store = TokenStore(str(tmp_path / "tokens.json"))
    owner = {"Authorization": "Bearer {0}".format(store.mint("owner"))}
    other = {"Authorization": "Bearer {0}".format(store.mint("other"))}
    manager = SessionManager()
    app = create_app(manager, token_store=store)
    with TestClient(app) as client:
        yield client, owner, other
    manager.close_all()


def _make_session(client, headers):
    response = client.post("/api/sessions", json={"label": "s", "mock": True}, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_creator_becomes_owner(two_users):
    client, owner, _ = two_users
    assert _make_session(client, owner)["owner"] == "owner"


def test_owner_is_visible_in_listing(two_users):
    client, owner, other = two_users
    _make_session(client, owner)
    listed = client.get("/api/sessions", headers=other).json()
    assert listed[0]["owner"] == "owner"


def test_non_owner_cannot_patch_timebase(two_users):
    client, owner, other = two_users
    sid = _make_session(client, owner)["id"]
    response = client.patch("/api/sessions/{0}/scope/timebase".format(sid), json={"timebase": 1e-3}, headers=other)
    assert response.status_code == 409
    assert "owner" in response.json()["detail"]


def test_non_owner_cannot_send_raw_commands(two_users):
    client, owner, other = two_users
    sid = _make_session(client, owner)["id"]
    response = client.post("/api/sessions/{0}/scope/command".format(sid), json={"command": "*RST"}, headers=other)
    assert response.status_code == 409


def test_non_owner_cannot_delete_the_session(two_users):
    client, owner, other = two_users
    sid = _make_session(client, owner)["id"]
    assert client.delete("/api/sessions/{0}".format(sid), headers=other).status_code == 409


def test_non_owner_can_read_state(two_users):
    client, owner, other = two_users
    sid = _make_session(client, owner)["id"]
    assert client.get("/api/sessions/{0}/scope/state".format(sid), headers=other).status_code == 200


def test_owner_can_still_write(two_users):
    client, owner, _ = two_users
    sid = _make_session(client, owner)["id"]
    assert client.patch("/api/sessions/{0}/scope/timebase".format(sid), json={"timebase": 1e-3}, headers=owner).status_code == 200
