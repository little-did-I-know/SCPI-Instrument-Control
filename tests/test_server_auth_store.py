"""Token store: hashing, verification, revocation, persistence."""

import json
from pathlib import Path

import pytest

from scpi_control.server.__main__ import main
from scpi_control.server.auth import TokenStore


def test_minted_token_verifies_to_its_name(tmp_path):
    store = TokenStore(str(tmp_path / "tokens.json"))
    raw = store.mint("robin")
    assert raw.startswith("scpi_")
    assert store.verify(raw) == "robin"


def test_raw_token_is_not_stored(tmp_path):
    path = tmp_path / "tokens.json"
    store = TokenStore(str(path))
    raw = store.mint("robin")
    assert raw not in path.read_text()


def test_unknown_token_does_not_verify(tmp_path):
    store = TokenStore(str(tmp_path / "tokens.json"))
    store.mint("robin")
    assert store.verify("scpi_nope") is None
    assert store.verify("") is None


def test_revoked_token_stops_verifying(tmp_path):
    store = TokenStore(str(tmp_path / "tokens.json"))
    raw = store.mint("robin")
    assert store.revoke("robin") is True
    assert store.verify(raw) is None
    assert store.revoke("robin") is False


def test_mint_rejects_empty_name(tmp_path):
    # An empty name mints a token whose identity is "" -- and require_owner()
    # in ownership.py treats owner == "" as unowned, so every session that
    # token creates is writable by any authenticated identity. Reject it here
    # rather than let that degenerate identity into existence.
    store = TokenStore(str(tmp_path / "tokens.json"))
    with pytest.raises(ValueError):
        store.mint("")


def test_mint_rejects_whitespace_only_name(tmp_path):
    store = TokenStore(str(tmp_path / "tokens.json"))
    with pytest.raises(ValueError):
        store.mint("   ")


def test_mint_still_accepts_a_normal_name(tmp_path):
    # Guard against over-rejecting: a real name must still mint cleanly.
    store = TokenStore(str(tmp_path / "tokens.json"))
    raw = store.mint("robin")
    assert store.verify(raw) == "robin"


def test_cli_token_add_empty_name_exits_nonzero_and_writes_nothing(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        main(["token", "add", "", "--config-dir", str(tmp_path)])
    assert excinfo.value.code != 0
    assert TokenStore(str(tmp_path / "tokens.json")).names() == []


def test_store_reloads_from_disk(tmp_path):
    path = str(tmp_path / "tokens.json")
    raw = TokenStore(path).mint("robin")
    assert TokenStore(path).verify(raw) == "robin"


def test_is_empty_tracks_contents(tmp_path):
    store = TokenStore(str(tmp_path / "tokens.json"))
    assert store.is_empty() is True
    store.mint("robin")
    assert store.is_empty() is False


def test_corrupt_store_is_not_silently_empty(tmp_path):
    path = tmp_path / "tokens.json"
    path.write_text("{ this is not json")
    with pytest.raises(ValueError):
        TokenStore(str(path))


def test_top_level_array_is_rejected(tmp_path):
    path = tmp_path / "tokens.json"
    path.write_text(json.dumps([{"name": "robin", "hash": "deadbeef"}]))
    with pytest.raises(ValueError):
        TokenStore(str(path))


def test_tokens_as_string_is_rejected(tmp_path):
    path = tmp_path / "tokens.json"
    path.write_text(json.dumps({"tokens": "robin"}))
    with pytest.raises(ValueError):
        TokenStore(str(path))


def test_entry_missing_hash_is_rejected(tmp_path):
    path = tmp_path / "tokens.json"
    path.write_text(json.dumps({"tokens": [{"name": "robin"}]}))
    with pytest.raises(ValueError):
        TokenStore(str(path))


def test_verify_does_not_write_to_disk(tmp_path):
    # last_used is audit-flavoured metadata, updated in memory only: a
    # synchronous rewrite of tokens.json (plus chmod) on every authenticated
    # request would put blocking disk I/O, and an unsynchronized
    # read-modify-write race, on the hot path of every API call.
    path = tmp_path / "tokens.json"
    store = TokenStore(str(path))
    raw = store.mint("robin")
    before_mtime = path.stat().st_mtime_ns
    before_contents = path.read_bytes()
    assert store.verify(raw) == "robin"
    assert path.stat().st_mtime_ns == before_mtime
    assert path.read_bytes() == before_contents


def test_names_lists_without_secrets(tmp_path):
    store = TokenStore(str(tmp_path / "tokens.json"))
    store.mint("robin")
    store.mint("bench-laptop")
    assert sorted(store.names()) == ["bench-laptop", "robin"]
    assert json.loads((tmp_path / "tokens.json").read_text())["tokens"][0]["name"]


def test_no_argument_defaults_never_touch_the_real_home(tmp_path):
    """Proves the autouse `_no_real_home` guard in conftest.py actually works.

    TokenStore() and ReferenceWaveform() with no arguments both fall back to
    a path derived from the real home directory unless something redirects
    them. This is the regression that already bit this branch once (a CLI
    test minted a live token into the developer's real ~/.siglent/tokens.json).
    If this assertion ever starts failing, the guard fixture has broken and
    every other test in the suite is one missed `--config-dir`/`storage_dir`
    away from writing outside the sandbox again.
    """
    import os

    from scpi_control.reference_waveform import ReferenceWaveform
    from scpi_control.server.auth import TokenStore as UnpinnedTokenStore

    # os.path.expanduser bypasses pathlib entirely, so it still reports the
    # genuine home directory even though this test's autouse fixture has
    # monkeypatched Path.home() for the duration of the test. Note this can't
    # be asserted as "not an ancestor of the resolved path" -- on this
    # machine tmp_path itself lives under the real home (...\AppData\Local\
    # Temp\...), so that relationship would hold true even when the guard is
    # broken. Compare against the exact real-default path instead.
    real_home = Path(os.path.expanduser("~"))
    real_default_token_path = real_home / ".siglent" / "tokens.json"
    real_default_reference_dir = real_home / ".siglent" / "references"

    store = UnpinnedTokenStore()
    assert tmp_path in store.path.parents
    assert store.path != real_default_token_path

    reference = ReferenceWaveform()
    assert tmp_path in reference.storage_dir.parents
    assert reference.storage_dir != real_default_reference_dir


def test_save_never_leaves_a_truncated_store(tmp_path, monkeypatch):
    # The failure this guards: _save() used to truncate tokens.json before
    # writing it. Once a second process reads the file live (hot reload), a
    # read landing in that window sees invalid JSON -- and __init__ treats
    # that as a hard refusal to start. Simulate a crash at the moment of
    # publication and assert the previous store survived intact.
    path = tmp_path / "tokens.json"
    store = TokenStore(str(path))
    raw = store.mint("robin")
    good = path.read_bytes()

    def boom(src, dst):
        raise OSError("simulated crash during publish")

    monkeypatch.setattr("os.replace", boom)
    with pytest.raises(OSError):
        store.mint("bench-laptop")
    assert path.read_bytes() == good
    assert TokenStore(str(path)).verify(raw) == "robin"


def test_save_leaves_no_temp_file_behind(tmp_path):
    path = tmp_path / "tokens.json"
    TokenStore(str(path)).mint("robin")
    # tmp_path also holds the autouse `_no_real_home` fixture's "fake-home"
    # directory (see conftest.py) -- unrelated to this store. Filter it out;
    # the point of this test is that _save() leaves no leftover temp file
    # alongside tokens.json.
    assert [p.name for p in tmp_path.iterdir() if p.name != "fake-home"] == ["tokens.json"]


# A test asserting that every save changes st_ino used to live here. It was
# wrong, and CI on Linux proved it: os.replace frees the old inode and the next
# mkstemp in the same directory reuses the number, so a revoke followed by a
# same-length mint produced an identical st_ino and an identical st_size. It
# passed only on Windows, where the file index does change.
#
# It was not rewritten to assert the whole _stat_key tuple instead, because that
# would be flaky by construction: with the inode reused and the size equal,
# detection rests on st_mtime_ns alone, and Linux's coarse clock granularity
# (~1-4ms) lets two rapid saves share a timestamp legitimately.
#
# What the reload mechanism actually has to do is covered behaviourally by the
# four cross-process tests below, which is the right altitude for it. See
# _stat_key's docstring for which term carries detection on which platform, and
# for the residual this leaves.


def test_revocation_by_another_process_takes_effect_without_restart(tmp_path):
    # Two TokenStore instances on one path stand in for the serving gateway
    # and the CLI, which really are separate processes. Before hot reload, the
    # gateway kept honouring a revoked token until someone restarted it --
    # which made the documented remedy for a leaked credential a no-op.
    path = str(tmp_path / "tokens.json")
    gateway = TokenStore(path)
    raw = gateway.mint("robin")
    assert gateway.verify(raw) == "robin"

    cli = TokenStore(path)
    assert cli.revoke("robin") is True

    assert gateway.verify(raw) is None


def test_a_token_minted_by_another_process_verifies_without_restart(tmp_path):
    path = str(tmp_path / "tokens.json")
    gateway = TokenStore(path)
    gateway.mint("robin")

    raw = TokenStore(path).mint("bob")

    assert gateway.verify(raw) == "bob"


def test_reload_still_does_not_write_on_the_verify_path(tmp_path):
    path = tmp_path / "tokens.json"
    store = TokenStore(str(path))
    raw = store.mint("robin")
    TokenStore(str(path)).mint("bob")  # force a reload on the next verify
    before = path.read_bytes()
    assert store.verify(raw) == "robin"
    assert path.read_bytes() == before


def test_a_store_whose_file_vanishes_verifies_nothing(tmp_path):
    # Deleting tokens.json must fail closed, not freeze the last known good
    # set in memory.
    path = tmp_path / "tokens.json"
    store = TokenStore(str(path))
    raw = store.mint("robin")
    path.unlink()
    assert store.verify(raw) is None


def test_a_store_corrupted_while_running_fails_closed_and_loudly(tmp_path):
    # verify() could not raise before hot reload; now it can, because the
    # file it re-reads may have been damaged since startup. That is the
    # correct behaviour and must stay: __init__ already treats a corrupt
    # store as a hard error precisely because "no tokens" is
    # indistinguishable from a fresh install and would open the gateway.
    # Catching this inside verify() and returning None would look like
    # failing closed while actually turning a loud, fixable problem into
    # every request mysteriously returning 401.
    path = tmp_path / "tokens.json"
    store = TokenStore(str(path))
    raw = store.mint("robin")
    path.write_text("{ truncated")
    with pytest.raises(ValueError):
        store.verify(raw)
    # And again: a corrupt store must keep failing loudly, not fail once and
    # then silently resume serving the stale pre-corruption token list. The
    # first version of this test called verify() only once, which is exactly
    # how that bug survived the suite.
    with pytest.raises(ValueError):
        store.verify(raw)


def test_a_name_can_hold_several_device_tokens(tmp_path):
    # Bob has a laptop and a bench tablet. Both are Bob.
    store = TokenStore(str(tmp_path / "tokens.json"))
    laptop = store.mint("bob")
    tablet = store.mint("bob")
    assert laptop != tablet
    assert store.verify(laptop) == "bob"
    assert store.verify(tablet) == "bob"


def test_revoking_a_name_cuts_off_every_device(tmp_path):
    store = TokenStore(str(tmp_path / "tokens.json"))
    laptop = store.mint("bob")
    tablet = store.mint("bob")
    assert store.revoke("bob") is True
    assert store.verify(laptop) is None
    assert store.verify(tablet) is None


def test_names_are_unique_and_sorted(tmp_path):
    # api/sessions.py's ownership handoff tests membership in names(); a name
    # repeated once per device would also make `token list` misleading.
    store = TokenStore(str(tmp_path / "tokens.json"))
    store.mint("robin")
    store.mint("bob")
    store.mint("bob")
    assert store.names() == ["bob", "robin"]


def test_summary_counts_devices_without_revealing_secrets(tmp_path):
    store = TokenStore(str(tmp_path / "tokens.json"))
    raw = store.mint("bob")
    store.mint("bob")
    store.mint("robin")
    store.verify(raw)
    rows = {row["name"]: row for row in store.summary()}
    assert rows["bob"]["devices"] == 2
    assert rows["robin"]["devices"] == 1
    assert rows["bob"]["last_used"] is not None
    assert "hash" not in rows["bob"]


def test_summary_sees_a_token_minted_by_another_process(tmp_path):
    # summary() used to read self._tokens directly, with no reload -- fine
    # while only the CLI called it, but the admin app's GET /api/identities
    # is the first caller living inside the same running server process that
    # a second process (the CLI minting/revoking) writes past. Without a
    # reload here, the admin panel would render a roster missing tokens
    # minted after this process started.
    path = str(tmp_path / "tokens.json")
    gateway = TokenStore(path)
    gateway.mint("robin")

    TokenStore(path).mint("bob")

    names = {row["name"] for row in gateway.summary()}
    assert names == {"robin", "bob"}


def test_revoke_does_not_resurrect_a_token_minted_by_another_process(tmp_path):
    # revoke() used to read and rewrite self._tokens with no reload first.
    # Instance A revoking "robin" while stale would _save() its own outdated
    # in-memory list -- silently erasing the token instance B minted for
    # "bob" in between, even though this revoke has nothing to do with bob.
    path = str(tmp_path / "tokens.json")
    instance_a = TokenStore(path)
    raw_robin = instance_a.mint("robin")

    instance_b = TokenStore(path)
    raw_bob = instance_b.mint("bob")

    assert instance_a.revoke("robin") is True

    # bob's token, minted by instance_b after instance_a's snapshot, must
    # still verify -- instance_a's revoke() must not have overwritten it.
    fresh = TokenStore(path)
    assert fresh.verify(raw_bob) == "bob"
    assert fresh.verify(raw_robin) is None


def test_names_sees_an_identity_minted_by_another_process(tmp_path):
    # names() was the one public reader that never reloaded. That was harmless
    # while its only caller ran after verify() had already reloaded in the same
    # request -- identity_is_live() is the first caller for which it is not.
    path = str(tmp_path / "tokens.json")
    gateway = TokenStore(path)
    gateway.mint("robin")
    TokenStore(path).mint("bob")
    assert gateway.names() == ["bob", "robin"]


def test_names_stops_seeing_an_identity_revoked_by_another_process(tmp_path):
    path = str(tmp_path / "tokens.json")
    gateway = TokenStore(path)
    gateway.mint("bob")
    TokenStore(path).revoke("bob")
    assert gateway.names() == []
