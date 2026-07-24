"""End-to-end: mint a token, drive a session, hit every boundary."""

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from scpi_control.server.app import create_app  # noqa: E402
from scpi_control.server.auth import TokenStore  # noqa: E402
from scpi_control.server.sessions import SessionManager  # noqa: E402


def test_full_authenticated_lifecycle(tmp_path):
    store = TokenStore(str(tmp_path / "tokens.json"))
    owner_raw = store.mint("owner")
    other_raw = store.mint("other")
    manager = SessionManager()
    app = create_app(manager, token_store=store, references_dir=str(tmp_path / "refs"))

    with TestClient(app) as client:
        owner = {"Authorization": "Bearer {0}".format(owner_raw)}
        other = {"Authorization": "Bearer {0}".format(other_raw)}

        assert client.get("/api/health").status_code == 200
        assert client.get("/api/sessions").status_code == 401

        created = client.post("/api/sessions", json={"label": "bench", "mock": True}, headers=owner)
        assert created.status_code == 201
        sid = created.json()["id"]
        assert created.json()["owner"] == "owner"

        assert client.get("/api/sessions/{0}/scope/state".format(sid), headers=other).status_code == 200
        assert client.post("/api/sessions/{0}/scope/command".format(sid), json={"command": "*RST"}, headers=other).status_code == 409
        assert client.post("/api/sessions/{0}/scope/command".format(sid), json={"command": "*RST"}, headers=owner).status_code == 200

        with client.websocket_connect("/api/sessions/{0}/stream".format(sid), subprotocols=["scpi-token.{0}".format(owner_raw), "scpi"]) as socket:
            assert socket.receive_json()["type"]

        # Same, real session id, but no subprotocol offered at all: the
        # rejection must come from AuthMiddleware, not from stream.py's own
        # unknown-session 4404 (which a bogus id like "nope" would give either
        # way and would prove nothing about the auth boundary specifically).
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/api/sessions/{0}/stream".format(sid)):
                pass
        assert exc_info.value.code == 1008

        revoked = store.revoke("other")
        assert revoked is True
        assert client.get("/api/sessions", headers=other).status_code == 401

        assert client.delete("/api/sessions/{0}".format(sid), headers=owner).status_code == 204

    manager.close_all()
