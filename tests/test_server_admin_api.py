"""The host-only admin app: routes, and the absence of auth."""

import pytest
from fastapi.testclient import TestClient

from scpi_control.server.admin.app import create_admin_app
from scpi_control.server.auth import TokenStore
from scpi_control.server.invitations import InvitationStore


@pytest.fixture
def admin(tmp_path):
    tokens = TokenStore(str(tmp_path / "tokens.json"))
    invitations = InvitationStore(str(tmp_path / "invitations.json"))
    app = create_admin_app(token_store=tokens, invitation_store=invitations, base_url="http://192.168.1.50:8765/")
    with TestClient(app) as client:
        yield client, tokens, invitations


def test_identities_are_listed_with_device_counts(admin):
    client, tokens, _invitations = admin
    tokens.mint("bob")
    tokens.mint("bob")
    tokens.mint("robin")
    rows = {row["name"]: row for row in client.get("/api/identities").json()}
    assert rows["bob"]["devices"] == 2
    assert rows["robin"]["devices"] == 1


def test_identities_never_expose_hashes(admin):
    client, tokens, _invitations = admin
    tokens.mint("bob")
    assert "hash" not in client.get("/api/identities").text


def test_creating_an_invitation_returns_a_link_and_a_code(admin):
    client, _tokens, invitations = admin
    body = client.post("/api/invitations", json={"name": "bob"}).json()
    assert body["name"] == "bob"
    assert body["code"].isdigit() and len(body["code"]) == 6
    assert body["link"].startswith("http://192.168.1.50:8765/?invite=")
    assert invitations.pending() == 1


def test_a_created_invitation_actually_redeems(admin):
    # The panel's whole job is handing out working access. A link that looks
    # right but does not redeem would be worse than no panel.
    client, _tokens, invitations = admin
    body = client.post("/api/invitations", json={"name": "bob"}).json()
    nonce = body["link"].split("?invite=")[1]
    assert invitations.redeem(link=nonce) == "bob"


def test_an_empty_name_is_rejected(admin):
    client, _tokens, invitations = admin
    assert client.post("/api/invitations", json={"name": "   "}).status_code == 400
    assert invitations.pending() == 0


def test_pending_invitations_are_listed_without_a_link(admin):
    # pending_list stores only the nonce's hash, so a listed invitation cannot
    # carry a reconstructable link. Asserting it is absent stops someone
    # "helpfully" inventing one from the id later.
    client, _tokens, _invitations = admin
    client.post("/api/invitations", json={"name": "bob"})
    row = client.get("/api/invitations").json()[0]
    assert row["name"] == "bob"
    assert row["code"].isdigit()
    assert row.get("link") in (None, "")


def test_cancelling_an_invitation_stops_it_redeeming(admin):
    client, _tokens, invitations = admin
    code = client.post("/api/invitations", json={"name": "bob"}).json()["code"]
    invitation_id = client.get("/api/invitations").json()[0]["id"]
    assert client.delete("/api/invitations/{0}".format(invitation_id)).status_code == 204
    assert invitations.redeem(code=code) is None


def test_cancelling_an_unknown_invitation_is_404(admin):
    client, _tokens, _invitations = admin
    assert client.delete("/api/invitations/deadbeef").status_code == 404


def test_revoking_an_identity_removes_every_device(admin):
    client, tokens, _invitations = admin
    laptop = tokens.mint("bob")
    tablet = tokens.mint("bob")
    assert client.delete("/api/identities/bob").status_code == 204
    assert tokens.verify(laptop) is None
    assert tokens.verify(tablet) is None


def test_revoking_an_unknown_identity_is_404(admin):
    client, _tokens, _invitations = admin
    assert client.delete("/api/identities/ghost").status_code == 404


def test_the_admin_app_has_no_auth_middleware(admin):
    # The boundary is the loopback bind, not a credential. If AuthMiddleware
    # ever appears here it means someone mounted the admin app under the main
    # one, which would also make it reachable from the LAN.
    from scpi_control.server.auth import AuthMiddleware

    client, _tokens, _invitations = admin
    installed = [middleware.cls for middleware in client.app.user_middleware]
    assert AuthMiddleware not in installed


def test_every_route_answers_without_a_token(admin):
    client, tokens, _invitations = admin
    tokens.mint("bob")
    assert client.get("/api/identities").status_code == 200
    assert client.get("/api/invitations").status_code == 200
