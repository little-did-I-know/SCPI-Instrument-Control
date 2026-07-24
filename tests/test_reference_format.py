"""Reference storage moves off pickled metadata onto a JSON string."""

import json
from pathlib import Path

import numpy as np
import pytest

from scpi_control.reference_waveform import CorruptReferenceError, LegacyReferenceFormatError, REFERENCE_META_KEY, ReferenceWaveform


class _Waveform:
    def __init__(self):
        self.time = np.linspace(0, 1, 16)
        self.voltage = np.sin(self.time)
        self.channel = 1


def test_saved_reference_has_no_object_array(tmp_path):
    store = ReferenceWaveform(str(tmp_path))
    store.save_reference(_Waveform(), "base")
    saved = list(tmp_path.glob("*.npz"))[0]
    with np.load(saved, allow_pickle=False) as data:
        assert "meta_json" in data.files
        assert "metadata" not in data.files
        assert json.loads(str(data["meta_json"]))["name"] == "base"


def test_new_format_round_trips(tmp_path):
    store = ReferenceWaveform(str(tmp_path))
    store.save_reference(_Waveform(), "base")
    loaded = store.load_reference("base")
    assert loaded is not None
    assert loaded["metadata"]["name"] == "base"
    assert len(loaded["time"]) == 16


def test_legacy_pickled_file_raises_with_migrate_hint(tmp_path):
    legacy = tmp_path / "ref_legacy.npz"
    np.savez_compressed(legacy, time=np.arange(4, dtype=float), voltage=np.zeros(4), metadata={"name": "legacy"})
    store = ReferenceWaveform(str(tmp_path))
    with pytest.raises(LegacyReferenceFormatError) as excinfo:
        store.load_reference("legacy")
    assert "references migrate" in str(excinfo.value)


def test_listing_does_not_unpickle_legacy_files(tmp_path):
    legacy = tmp_path / "ref_legacy.npz"
    np.savez_compressed(legacy, time=np.arange(4, dtype=float), voltage=np.zeros(4), metadata={"name": "legacy"})
    store = ReferenceWaveform(str(tmp_path))
    store.save_reference(_Waveform(), "good")
    listed = store.list_references()
    assert [entry["name"] for entry in listed] == ["good"]


def _force_glob_order(monkeypatch, storage_dir, ordered_paths):
    """Make storage_dir.glob("*.npz") yield ordered_paths regardless of filesystem order.

    _find_reference_file's fallback scan is glob-order dependent, so tests that
    pin "a match is found regardless of where the legacy file sorts" need
    deterministic control over that order rather than relying on incidental
    filesystem/OS behaviour (which is exactly the kind of luck this bug hid
    behind).
    """
    real_glob = Path.glob

    def fake_glob(self, pattern, *args, **kwargs):
        if self == storage_dir and pattern == "*.npz":
            return iter(ordered_paths)
        return real_glob(self, pattern, *args, **kwargs)

    monkeypatch.setattr(Path, "glob", fake_glob)


def _legacy_and_good(tmp_path):
    """Create one un-migrated legacy file and one valid new-format reference."""
    legacy = tmp_path / "aaa_legacy.npz"
    np.savez_compressed(legacy, time=np.arange(4, dtype=float), voltage=np.zeros(4), metadata={"name": "legacy"})
    store = ReferenceWaveform(str(tmp_path))
    store.save_reference(_Waveform(), "zzz-good")
    good = next(p for p in tmp_path.glob("*.npz") if p != legacy)
    return store, legacy, good


def test_load_reference_finds_valid_entry_when_legacy_file_sorts_first(tmp_path, monkeypatch):
    store, legacy, good = _legacy_and_good(tmp_path)
    _force_glob_order(monkeypatch, store.storage_dir, [legacy, good])

    loaded = store.load_reference("zzz-good")
    assert loaded is not None
    assert loaded["metadata"]["name"] == "zzz-good"


def test_load_reference_finds_valid_entry_when_legacy_file_sorts_last(tmp_path, monkeypatch):
    store, legacy, good = _legacy_and_good(tmp_path)
    _force_glob_order(monkeypatch, store.storage_dir, [good, legacy])

    loaded = store.load_reference("zzz-good")
    assert loaded is not None
    assert loaded["metadata"]["name"] == "zzz-good"


def test_delete_reference_succeeds_despite_legacy_file_in_directory(tmp_path, monkeypatch):
    store, legacy, good = _legacy_and_good(tmp_path)
    _force_glob_order(monkeypatch, store.storage_dir, [legacy, good])

    assert store.delete_reference("zzz-good") is True
    assert not good.exists()
    assert legacy.exists()


def test_rename_reference_succeeds_despite_legacy_file_in_directory(tmp_path, monkeypatch):
    store, legacy, good = _legacy_and_good(tmp_path)
    _force_glob_order(monkeypatch, store.storage_dir, [legacy, good])

    assert store.rename_reference("zzz-good", "renamed") is True
    # rename_reference wrote a new file our forced ordering doesn't know about;
    # revert to real directory order to look it up (legacy is still present, so
    # this still exercises the mixed-directory lookup, just without a pinned order).
    monkeypatch.undo()
    assert store.load_reference("renamed") is not None


def test_lookup_still_raises_when_only_legacy_files_match_no_valid_entry(tmp_path):
    """No-match-found case still surfaces the deferred error (unchanged from before)."""
    legacy = tmp_path / "aaa_legacy.npz"
    np.savez_compressed(legacy, time=np.arange(4, dtype=float), voltage=np.zeros(4), metadata={"name": "legacy"})
    store = ReferenceWaveform(str(tmp_path))
    with pytest.raises(LegacyReferenceFormatError):
        store.load_reference("legacy")


def test_non_dict_json_metadata_raises_corrupt_reference_error(tmp_path):
    bad = tmp_path / "badmeta.npz"
    np.savez_compressed(bad, time=np.arange(4, dtype=float), voltage=np.zeros(4), **{REFERENCE_META_KEY: json.dumps([1, 2, 3])})
    store = ReferenceWaveform(str(tmp_path))
    with pytest.raises(CorruptReferenceError):
        store.load_reference("badmeta")


def test_non_serializable_array_metadata_raises_type_error_not_io_error(tmp_path):
    store = ReferenceWaveform(str(tmp_path))
    with pytest.raises(TypeError):
        store.save_reference(_Waveform(), "bad-meta", metadata={"cal": np.arange(3)})


def test_numpy_int64_metadata_value_raises_type_error_not_io_error(tmp_path):
    store = ReferenceWaveform(str(tmp_path))
    with pytest.raises(TypeError):
        store.save_reference(_Waveform(), "int64-meta", metadata={"count": np.int64(5)})


def test_corrupt_json_metadata_chains_original_exception(tmp_path):
    bad = tmp_path / "badjson.npz"
    np.savez_compressed(bad, time=np.arange(4, dtype=float), voltage=np.zeros(4), **{REFERENCE_META_KEY: "{not valid json"})
    store = ReferenceWaveform(str(tmp_path))
    with pytest.raises(CorruptReferenceError) as excinfo:
        store.load_reference("badjson")
    assert excinfo.value.__cause__ is not None
