"""Token store: hashing, verification, revocation, persistence."""

import json

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


def test_names_lists_without_secrets(tmp_path):
    store = TokenStore(str(tmp_path / "tokens.json"))
    store.mint("robin")
    store.mint("bench-laptop")
    assert sorted(store.names()) == ["bench-laptop", "robin"]
    assert json.loads((tmp_path / "tokens.json").read_text())["tokens"][0]["name"]
