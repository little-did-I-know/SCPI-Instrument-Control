"""Short-lived invitations: creation, redemption, expiry, single use."""

import json

import pytest

from scpi_control.server.invitations import InvitationStore, format_code


def test_a_code_redeems_to_its_name(tmp_path):
    store = InvitationStore(str(tmp_path / "invitations.json"))
    _link, code = store.create("bob")
    assert store.redeem(code=code) == "bob"


def test_a_link_nonce_redeems_to_its_name(tmp_path):
    store = InvitationStore(str(tmp_path / "invitations.json"))
    link, _code = store.create("bob")
    assert store.redeem(link=link) == "bob"


def test_an_invitation_is_single_use(tmp_path):
    # The whole point of a short-lived credential is that a leaked chat
    # message is worthless. If redemption did not consume the invitation,
    # anyone who saw the link could keep minting tokens until it expired.
    store = InvitationStore(str(tmp_path / "invitations.json"))
    link, code = store.create("bob")
    assert store.redeem(code=code) == "bob"
    assert store.redeem(code=code) is None
    assert store.redeem(link=link) is None


def test_an_expired_invitation_does_not_redeem(tmp_path):
    store = InvitationStore(str(tmp_path / "invitations.json"))
    _link, code = store.create("bob", ttl=-1.0)
    assert store.redeem(code=code) is None


def test_a_wrong_code_redeems_nothing_and_consumes_nothing(tmp_path):
    store = InvitationStore(str(tmp_path / "invitations.json"))
    _link, code = store.create("bob")
    # Derived from the real code rather than hardcoded: a literal "000000"
    # collides with a randomly generated code once in a million runs, and a
    # guard test that flakes that rarely is worse than one that never does.
    wrong = "{0:06d}".format((int(code) + 1) % 1000000)
    assert store.redeem(code=wrong) is None
    assert store.redeem(code=code) == "bob"


def test_codes_are_six_digits_and_links_are_long(tmp_path):
    store = InvitationStore(str(tmp_path / "invitations.json"))
    link, code = store.create("bob")
    # Explicit ASCII rather than code.isdigit(): "²".isdigit() is True, and
    # that idiom in _normalize_code was a live oracle (see the join API tests).
    # Harmless here -- generated codes are ASCII -- but the idiom should not
    # survive anywhere near this file.
    assert len(code) == 6 and all(char in "0123456789" for char in code)
    assert len(link) >= 32


def test_a_code_redeems_however_the_user_spaces_it(tmp_path):
    # It is printed as "417 902" and read out loud, so it comes back typed
    # every which way. Rejecting the format we ourselves display would be a
    # self-inflicted support call.
    store = InvitationStore(str(tmp_path / "invitations.json"))
    _link, code = store.create("bob")
    spaced = format_code(code)
    assert " " in spaced
    assert store.redeem(code=spaced) == "bob"


def test_the_link_nonce_is_not_stored_in_the_clear(tmp_path):
    path = tmp_path / "invitations.json"
    store = InvitationStore(str(path))
    link, _code = store.create("bob")
    assert link not in path.read_text()


def test_the_code_is_stored_in_the_clear_by_design(tmp_path):
    # Documented, not accidental: hashing a secret drawn from 10**6
    # possibilities is theater -- anyone who can read this file can
    # enumerate every hash in under a second. The code's defenses are its
    # ten-minute life, the join limiter, and the file mode. This test exists
    # so nobody "fixes" it into a hash and believes they gained something.
    path = tmp_path / "invitations.json"
    store = InvitationStore(str(path))
    _link, code = store.create("bob")
    assert code in path.read_text()


def test_an_invitation_created_by_another_process_is_seen_without_restart(tmp_path):
    # `scpi-web invite` really does run in a different process from the
    # serving gateway. This is the whole reason invitations live in a file.
    path = str(tmp_path / "invitations.json")
    gateway = InvitationStore(path)
    _link, code = InvitationStore(path).create("bob")
    assert gateway.redeem(code=code) == "bob"


def test_redemption_is_visible_to_another_process(tmp_path):
    path = str(tmp_path / "invitations.json")
    gateway = InvitationStore(path)
    _link, code = gateway.create("bob")
    assert gateway.redeem(code=code) == "bob"
    assert InvitationStore(path).redeem(code=code) is None


def test_expired_invitations_are_pruned_on_write(tmp_path):
    path = tmp_path / "invitations.json"
    store = InvitationStore(str(path))
    store.create("stale", ttl=-1.0)
    store.create("bob")
    assert store.pending() == 1
    assert [entry["name"] for entry in json.loads(path.read_text())["invitations"]] == ["bob"]


def test_create_rejects_an_empty_name(tmp_path):
    # Mirrors TokenStore.mint: an empty identity makes every session it
    # creates unowned, and therefore writable by anyone.
    store = InvitationStore(str(tmp_path / "invitations.json"))
    with pytest.raises(ValueError):
        store.create("  ")


def test_a_corrupt_invitation_file_is_not_silently_empty(tmp_path):
    path = tmp_path / "invitations.json"
    path.write_text("{ not json")
    with pytest.raises(ValueError):
        InvitationStore(str(path))


def test_a_store_corrupted_while_running_keeps_failing(tmp_path):
    # The same ordering guard TokenStore needed: if _load() commits the stat
    # key before the read succeeds, a corrupt file raises loudly exactly once
    # and then matches its own recorded key forever, silently serving stale
    # state. One redeem() call would not catch that -- two do.
    path = tmp_path / "invitations.json"
    store = InvitationStore(str(path))
    _link, code = store.create("bob")
    path.write_text("{ truncated")
    with pytest.raises(ValueError):
        store.redeem(code=code)
    with pytest.raises(ValueError):
        store.redeem(code=code)


def test_redeem_without_a_credential_returns_none(tmp_path):
    store = InvitationStore(str(tmp_path / "invitations.json"))
    store.create("bob")
    assert store.redeem() is None
