"""POST /api/join -- the gateway's only unauthenticated write route."""

import pytest
from fastapi.testclient import TestClient

from scpi_control.server.app import create_app
from scpi_control.server.auth import TokenStore
from scpi_control.server.invitations import InvitationStore, format_code


@pytest.fixture
def gateway(tmp_path):
    tokens = TokenStore(str(tmp_path / "tokens.json"))
    invitations = InvitationStore(str(tmp_path / "invitations.json"))
    app = create_app(token_store=tokens, invitation_store=invitations)
    with TestClient(app) as client:
        yield client, tokens, invitations


def test_a_code_joins_and_returns_a_working_token(gateway):
    client, tokens, invitations = gateway
    _link, code = invitations.create("bob")
    response = client.post("/api/join", json={"code": code})
    assert response.status_code == 200
    body = response.json()
    assert body["identity"] == "bob"
    assert tokens.verify(body["token"]) == "bob"


def test_a_spaced_code_joins(gateway):
    client, _tokens, invitations = gateway
    _link, code = invitations.create("bob")
    assert client.post("/api/join", json={"code": format_code(code)}).status_code == 200


def test_a_link_nonce_joins(gateway):
    client, tokens, invitations = gateway
    link, _code = invitations.create("bob")
    response = client.post("/api/join", json={"invite": link})
    assert response.status_code == 200
    assert tokens.verify(response.json()["token"]) == "bob"


def test_join_needs_no_bearer_token(gateway):
    # The route is exempt on purpose: it is how someone with no credential
    # obtains one. Everything else under /api stays fail-closed.
    client, _tokens, invitations = gateway
    _link, code = invitations.create("bob")
    assert client.post("/api/join", json={"code": code}).status_code == 200
    assert client.get("/api/sessions").status_code == 401


def test_joining_twice_with_one_code_fails_the_second_time(gateway):
    client, _tokens, invitations = gateway
    _link, code = invitations.create("bob")
    assert client.post("/api/join", json={"code": code}).status_code == 200
    assert client.post("/api/join", json={"code": code}).status_code == 401


def test_every_failure_looks_identical(gateway):
    # Distinguishing "wrong" from "expired" from "already used" turns this
    # endpoint into an oracle: an attacker could confirm a code's existence
    # without knowing it, or map out when invitations were issued.
    client, _tokens, invitations = gateway
    _link, used = invitations.create("used")
    client.post("/api/join", json={"code": used})
    _link2, expired = invitations.create("stale", ttl=-1.0)

    wrong = client.post("/api/join", json={"code": "000000"})
    already = client.post("/api/join", json={"code": used})
    gone = client.post("/api/join", json={"code": expired})
    missing = client.post("/api/join", json={})

    assert wrong.status_code == already.status_code == gone.status_code == missing.status_code == 401
    assert wrong.content == already.content == gone.content == missing.content


def test_a_unicode_digit_code_is_rejected_like_any_other(gateway):
    # str.isdigit() is True for "²" and "٣"; hmac.compare_digest raises
    # TypeError on a non-ASCII str. Because the comparison only runs when an
    # invitation is live, an unhandled error here reported gateway state to an
    # anonymous caller: 401 with nothing pending, 500 with something pending.
    # The live invitation is the whole point of this test -- without it, it
    # passes even with the bug present.
    client, _tokens, invitations = gateway
    invitations.create("bob")
    plain = client.post("/api/join", json={"code": "000000"})
    unicode_digits = client.post("/api/join", json={"code": "²²²²²²"})
    arabic = client.post("/api/join", json={"code": "٤٥٦٧٨٩"})
    assert plain.status_code == unicode_digits.status_code == arabic.status_code == 401
    assert plain.content == unicode_digits.content == arabic.content


def test_a_corrupt_invitation_store_is_indistinguishable_from_a_wrong_code(gateway, tmp_path):
    # A ValueError out of redeem() used to reach the app-wide handler and come
    # back as 400 {"detail": "invitation store C:\\Users\\...\\invitations.json
    # is unreadable: ..."} -- an absolute path handed to an anonymous caller,
    # and a third distinguishable status on a route whose whole contract is one
    # response. The serve path now refuses to start on a corrupt store, but the
    # file can still be damaged while the gateway is running.
    client, _tokens, _invitations = gateway
    wrong = client.post("/api/join", json={"code": "000000"})
    (tmp_path / "invitations.json").write_text("{ truncated")
    broken = client.post("/api/join", json={"code": "000000"})
    assert broken.status_code == wrong.status_code == 401
    assert broken.content == wrong.content
    assert "invitations.json" not in broken.text


def test_a_failed_join_mints_no_token(gateway):
    client, tokens, _invitations = gateway
    client.post("/api/join", json={"code": "000000"})
    assert tokens.names() == []


def test_the_limiter_stops_a_burst_of_wrong_codes(gateway):
    client, _tokens, _invitations = gateway
    # Pinned exactly, not just "starts 401, ends 429": join.py's comment does
    # the brute-force arithmetic against FAILURE_LIMIT = 10, and a loose
    # assertion passes for any limit from 1 to 11 -- so nothing would have
    # caught someone quietly widening the budget.
    statuses = [client.post("/api/join", json={"code": "000000"}).status_code for _ in range(12)]
    assert statuses == [401] * 10 + [429] * 2


def test_successful_joins_are_not_counted_by_the_limiter(gateway):
    # A success consumes its invitation, so it is self-limiting. Counting
    # successes would let a busy lab lock itself out on a Monday morning.
    client, _tokens, invitations = gateway
    codes = [invitations.create("bob")[1] for _ in range(12)]
    statuses = [client.post("/api/join", json={"code": code}).status_code for code in codes]
    assert statuses == [200] * 12


def test_the_limiter_does_not_block_a_correct_code_after_a_typo(gateway):
    client, _tokens, invitations = gateway
    _link, code = invitations.create("bob")
    client.post("/api/join", json={"code": "000000"})
    client.post("/api/join", json={"code": "000001"})
    assert client.post("/api/join", json={"code": code}).status_code == 200


def test_a_second_join_for_the_same_name_adds_a_device(gateway):
    client, tokens, invitations = gateway
    first = client.post("/api/join", json={"code": invitations.create("bob")[1]}).json()["token"]
    second = client.post("/api/join", json={"code": invitations.create("bob")[1]}).json()["token"]
    assert first != second
    assert tokens.verify(first) == "bob"
    assert tokens.verify(second) == "bob"
    assert tokens.names() == ["bob"]
