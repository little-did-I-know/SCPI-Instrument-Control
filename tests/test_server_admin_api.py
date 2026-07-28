"""The host-only admin app: routes, and the absence of auth."""

import pytest
from fastapi.testclient import TestClient

from scpi_control.server.admin.app import create_admin_app
from scpi_control.server.auth import TokenStore
from scpi_control.server.invitations import InvitationStore


@pytest.fixture
def admin_stores(tmp_path):
    return TokenStore(str(tmp_path / "tokens.json")), InvitationStore(str(tmp_path / "invitations.json"))


@pytest.fixture
def admin(admin_stores):
    tokens, invitations = admin_stores
    app = create_admin_app(token_store=tokens, invitation_store=invitations, base_url="http://192.168.1.50:8765/")
    # base_url is 127.0.0.1, not the httpx default "testserver": TrustedHostMiddleware
    # only allows 127.0.0.1/localhost, and the Host header httpx sends is derived
    # from base_url unless a test overrides it.
    with TestClient(app, base_url="http://127.0.0.1") as client:
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


def test_a_spoofed_host_header_is_rejected(admin):
    # The loopback bind stops non-local sockets, not a browser: a page open
    # on the gateway machine can rebind its own hostname to 127.0.0.1 and
    # become same-origin with this unauthenticated app. TrustedHostMiddleware
    # is the second, independent defence -- it must reject anything that does
    # not present as this host, regardless of what socket it arrived on.
    client, _tokens, _invitations = admin
    response = client.get("/api/identities", headers={"Host": "evil.example"})
    assert response.status_code == 400


def test_localhost_and_loopback_hosts_still_work(admin):
    client, _tokens, _invitations = admin
    assert client.get("/api/identities", headers={"Host": "127.0.0.1"}).status_code == 200
    assert client.get("/api/identities", headers={"Host": "localhost"}).status_code == 200


def test_the_main_app_serves_no_admin_routes(tmp_path):
    # The mirror image of test_the_admin_app_has_no_auth_middleware, and the
    # more important half: that one checks the admin app for auth, which is not
    # where the mistake gets made. The mistake gets made in create_app, as one
    # stray `app.include_router(admin_api.router, prefix="/api")` -- and it
    # passes the entire suite and the CI bundle gate, while handing every LAN
    # token-holder the power to mint invitations for arbitrary names and revoke
    # arbitrary identities. That is a straight escalation from "every token is
    # equal" to admin, so it is asserted in the language it would be written in.
    from scpi_control.server.app import create_app

    tokens = TokenStore(str(tmp_path / "tokens.json"))
    invitations = InvitationStore(str(tmp_path / "invitations.json"))
    app = create_app(token_store=tokens, invitation_store=invitations)
    paths = {route.path for route in app.routes}
    leaked = sorted(path for path in paths if path.startswith("/api/identities") or path.startswith("/api/invitations"))
    assert not leaked, "create_app serves admin routes: {0}".format(leaked)


def test_the_two_apps_never_share_a_static_directory(tmp_path):
    # The second rule in admin/app.py's docstring. The main app's SPA catch-all
    # serves any real file it finds in its own static dir, so pointing the two
    # at one directory would hand the access-management UI to every LAN browser
    # without changing a single route.
    import scpi_control.server.admin.app as admin_app_module
    import scpi_control.server.app as app_module

    assert app_module.STATIC_DIR != admin_app_module.ADMIN_STATIC_DIR
    assert admin_app_module.ADMIN_STATIC_DIR not in app_module.STATIC_DIR.parents


def test_a_foreign_origin_is_rejected_on_a_read(admin):
    # The attack neither the bind nor the Host allowlist touches: a page on any
    # site the admin visits does fetch("http://127.0.0.1:8766/api/identities").
    # The socket is genuinely local and the Host genuinely is 127.0.0.1, so both
    # of the other defences wave it through. Only the Origin gives it away.
    client, tokens, _invitations = admin
    tokens.mint("bob")
    response = client.get("/api/identities", headers={"Origin": "http://evil.example"})
    assert response.status_code == 403
    assert "bob" not in response.text


def test_a_foreign_origin_is_rejected_on_a_write(admin):
    client, _tokens, invitations = admin
    response = client.post("/api/invitations", json={"name": "bob"}, headers={"Origin": "http://evil.example"})
    assert response.status_code == 403
    # The refusal must happen before the handler, not merely hide its output.
    assert invitations.pending() == 0


def test_a_rebound_origin_on_the_panels_own_port_is_rejected(admin):
    # The rebinding variant: the attacker's page reaches the panel on the right
    # port, so its Origin carries the panel's port but the attacker's hostname.
    client, _tokens, invitations = admin
    assert client.post("/api/invitations", json={"name": "bob"}, headers={"Origin": "http://evil.example:8766"}).status_code == 403
    assert invitations.pending() == 0


def test_the_panels_own_origin_is_accepted(admin):
    # Both spellings TrustedHostMiddleware allows: the banner opens 127.0.0.1,
    # an SSH port-forward reaches the same panel as localhost.
    client, _tokens, _invitations = admin
    for origin in ("http://127.0.0.1:8766", "http://localhost:8766"):
        assert client.get("/api/identities", headers={"Origin": origin}).status_code == 200, origin
        assert client.post("/api/invitations", json={"name": "bob"}, headers={"Origin": origin}).status_code == 200, origin


def test_a_request_with_no_origin_is_accepted(admin):
    # curl, scripts, and same-origin browser fetches that omit the header. An
    # Origin is what a *cross*-origin request is obliged to carry; refusing its
    # absence would break the panel itself.
    client, _tokens, invitations = admin
    assert client.get("/api/identities").status_code == 200
    assert client.post("/api/invitations", json={"name": "bob"}).status_code == 200
    assert invitations.pending() == 1


def test_the_origin_allowlist_follows_the_configured_admin_port(admin_stores):
    # The port is not hardcoded: run the panel on --admin-port 9001 and 9001 is
    # what its own Origin must be, while the default 8766 becomes foreign.
    tokens, invitations = admin_stores
    app = create_admin_app(token_store=tokens, invitation_store=invitations, admin_port=9001)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.get("/api/identities", headers={"Origin": "http://127.0.0.1:9001"}).status_code == 200
        assert client.get("/api/identities", headers={"Origin": "http://127.0.0.1:8766"}).status_code == 403


def test_a_safelisted_content_type_cannot_create_an_invitation(admin):
    # The third defence's other half, pinned so it stops being accidental. A
    # form/text body is what a cross-origin page can send with no preflight at
    # all; FastAPI's JSON-only body parsing is what refuses it. If someone
    # teaches this endpoint to read form bodies, this test fails before the
    # Origin check is the only thing left standing.
    client, _tokens, invitations = admin
    for content_type in ("text/plain;charset=UTF-8", "application/x-www-form-urlencoded", "multipart/form-data; boundary=x"):
        response = client.post("/api/invitations", content=b'{"name": "bob"}', headers={"Content-Type": content_type})
        assert response.status_code != 200, content_type
    assert invitations.pending() == 0


def test_admin_spa_traversal_is_contained(tmp_path):
    # admin/static/ does not exist yet (no bundle has been built), so the
    # SPA route -- including its path-traversal guard -- has never actually
    # run in this test file. Build a throwaway static dir and monkeypatch it
    # in, mirroring tests/test_server_spa.py::test_encoded_traversal_is_contained
    # for the main app, so the admin app's own wiring gets the same proof.
    import scpi_control.server.admin.app as admin_app_module

    secret = tmp_path / "outside" / "secret.txt"
    secret.parent.mkdir()
    secret.write_text("TOP SECRET", encoding="utf-8")
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<!doctype html><title>admin</title>", encoding="utf-8")

    original = admin_app_module.ADMIN_STATIC_DIR
    admin_app_module.ADMIN_STATIC_DIR = static_dir
    try:
        tokens = TokenStore(str(tmp_path / "tokens.json"))
        invitations = InvitationStore(str(tmp_path / "invitations.json"))
        app = admin_app_module.create_admin_app(token_store=tokens, invitation_store=invitations)
        with TestClient(app, base_url="http://127.0.0.1") as client:
            for payload in ("/%2e%2e/outside/secret.txt", "/../outside/secret.txt", "/%2e%2e%2foutside/secret.txt"):
                response = client.get(payload)
                assert response.status_code in (200, 404), payload
                assert "TOP SECRET" not in response.text, payload
    finally:
        admin_app_module.ADMIN_STATIC_DIR = original
