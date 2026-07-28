"""Token store: hashing, verification, revocation, persistence."""

import json
from pathlib import Path

import pytest

from scpi_control.server.__main__ import main
from scpi_control.server.auth import DuplicateTokenName, TokenStore


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


def test_duplicate_name_rejected(tmp_path):
    store = TokenStore(str(tmp_path / "tokens.json"))
    store.mint("robin")
    with pytest.raises(DuplicateTokenName):
        store.mint("robin")


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


def test_each_save_publishes_a_new_file_identity(tmp_path):
    # Task 2's reload check keys on (st_ino, st_mtime_ns, st_size). st_ino is
    # the reliable term: an atomic replace always publishes a different file,
    # even when two writes land inside one filesystem timestamp tick and
    # happen to produce the same size.
    path = tmp_path / "tokens.json"
    store = TokenStore(str(path))
    store.mint("aaaa")
    first = path.stat().st_ino
    store.revoke("aaaa")
    store.mint("bbbb")  # same length name -> same file size
    assert path.stat().st_ino != first


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
