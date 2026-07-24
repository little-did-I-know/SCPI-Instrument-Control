"""Token store: hashing, verification, revocation, persistence."""

import json
from pathlib import Path

import pytest

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
