"""Reference storage moves off pickled metadata onto a JSON string."""

import json

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


def _legacy_and_good(tmp_path, legacy_sorts_last=False):
    """Create one un-migrated legacy file and one valid new-format reference.

    _find_reference_file's fallback scan iterates ``sorted(glob("*.npz"))``,
    so the scan order it actually sees is fixed by filename, not by directory
    iteration order -- faking the latter (e.g. via a patched Path.glob) has no
    effect once sorted() runs over it. To genuinely exercise "the unreadable
    legacy file is encountered before the match" vs. "...after it", the
    legacy file's name is chosen so it sorts before or after the good
    reference's name for real.
    """
    store = ReferenceWaveform(str(tmp_path))
    store.save_reference(_Waveform(), "zzz-good")
    good = next(tmp_path.glob("*.npz"))

    # "zzz-good_<timestamp>.npz" vs "aaa_legacy.npz"/"zzzz_legacy.npz": the
    # 4th character ('-' vs 'z') decides sort order in the latter case, so
    # this reliably lands after the good file regardless of the timestamp.
    legacy_name = "zzzz_legacy.npz" if legacy_sorts_last else "aaa_legacy.npz"
    legacy = tmp_path / legacy_name
    np.savez_compressed(legacy, time=np.arange(4, dtype=float), voltage=np.zeros(4), metadata={"name": "legacy"})
    return store, legacy, good


def test_load_reference_finds_valid_entry_when_legacy_file_sorts_first(tmp_path):
    store, legacy, good = _legacy_and_good(tmp_path, legacy_sorts_last=False)
    assert sorted(tmp_path.glob("*.npz")) == [legacy, good]

    loaded = store.load_reference("zzz-good")
    assert loaded is not None
    assert loaded["metadata"]["name"] == "zzz-good"


def test_load_reference_finds_valid_entry_when_legacy_file_sorts_last(tmp_path):
    store, legacy, good = _legacy_and_good(tmp_path, legacy_sorts_last=True)
    assert sorted(tmp_path.glob("*.npz")) == [good, legacy]

    loaded = store.load_reference("zzz-good")
    assert loaded is not None
    assert loaded["metadata"]["name"] == "zzz-good"


def test_delete_reference_succeeds_despite_legacy_file_in_directory(tmp_path):
    store, legacy, good = _legacy_and_good(tmp_path)

    assert store.delete_reference("zzz-good") is True
    assert not good.exists()
    assert legacy.exists()


def test_rename_reference_succeeds_despite_legacy_file_in_directory(tmp_path):
    store, legacy, good = _legacy_and_good(tmp_path)

    assert store.rename_reference("zzz-good", "renamed") is True
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


def _only_legacy(tmp_path):
    """Create a directory containing nothing but one un-migrated legacy file."""
    legacy = tmp_path / "aaa_legacy.npz"
    np.savez_compressed(legacy, time=np.arange(4, dtype=float), voltage=np.zeros(4), metadata={"name": "legacy"})
    store = ReferenceWaveform(str(tmp_path))
    return store, legacy


def test_delete_reference_on_brand_new_name_returns_false_despite_legacy_file(tmp_path):
    """delete_reference is a 'remove it if present' op: an unreadable legacy
    file elsewhere in the directory is not proof the requested name exists,
    so a name that was never saved must come back False, not raise."""
    store, legacy = _only_legacy(tmp_path)
    assert store.delete_reference("brand-new-name") is False
    assert legacy.exists()


def test_replace_on_save_loop_terminates_despite_legacy_file(tmp_path):
    """Mirrors the server's replace-on-save shape (scope.py's
    `while store.delete_reference(name): pass`) for a name being saved for
    the first time -- it must terminate rather than raise."""
    store, legacy = _only_legacy(tmp_path)
    iterations = 0
    while store.delete_reference("brand-new-name"):
        iterations += 1
        assert iterations < 100  # guard against an infinite loop masking the bug
    assert iterations == 0
    assert legacy.exists()


def test_load_reference_still_raises_despite_delete_fix(tmp_path):
    """The read path keeps its migrate hint: only delete_reference should
    swallow the deferred legacy error, not load_reference."""
    store, legacy = _only_legacy(tmp_path)
    with pytest.raises(LegacyReferenceFormatError) as excinfo:
        store.load_reference("brand-new-name")
    assert "references migrate" in str(excinfo.value)


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
