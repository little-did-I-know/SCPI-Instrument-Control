"""Characterization tests: current observable behaviour of ReferenceWaveform.

Written BEFORE the storage format changes, asserting only on the public API so
they stay valid across the migration. If one of these fails, the behaviour
changed -- that is the signal they exist to give.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

from scpi_control.reference_waveform import ReferenceWaveform


class _Waveform:
    def __init__(self, channel=1, samples=32):
        self.time = np.linspace(0, 1e-3, samples)
        self.voltage = np.sin(2 * np.pi * 1000 * self.time)
        self.channel = channel


@pytest.fixture()
def store(tmp_path):
    return ReferenceWaveform(str(tmp_path))


def test_storage_dir_is_created(tmp_path):
    target = tmp_path / "nested" / "refs"
    ReferenceWaveform(str(target))
    assert target.is_dir()


def test_save_returns_a_path_that_exists(store):
    saved = store.save_reference(_Waveform(), "baseline")
    assert saved
    assert Path(saved).exists()


def test_round_trip_preserves_samples(store):
    waveform = _Waveform()
    store.save_reference(waveform, "baseline")
    loaded = store.load_reference("baseline")
    assert loaded is not None
    assert np.allclose(loaded["time"], waveform.time)
    assert np.allclose(loaded["voltage"], waveform.voltage)


def test_metadata_carries_name_and_derived_stats(store):
    store.save_reference(_Waveform(), "baseline")
    metadata = store.load_reference("baseline")["metadata"]
    assert metadata["name"] == "baseline"
    assert metadata["num_samples"] == 32
    assert metadata["channel"] == 1
    for key in ("min_voltage", "max_voltage", "mean_voltage", "std_voltage", "time_span", "timestamp"):
        assert key in metadata


def test_unknown_name_loads_as_none(store):
    assert store.load_reference("never-saved") is None


def test_list_references_reports_saved_entries(store):
    store.save_reference(_Waveform(), "one")
    store.save_reference(_Waveform(channel=2), "two")
    listed = store.list_references()
    assert sorted(entry["name"] for entry in listed) == ["one", "two"]
    for entry in listed:
        for key in ("name", "channel", "timestamp", "num_samples", "time_span"):
            assert key in entry


def test_list_is_empty_for_a_fresh_store(store):
    assert store.list_references() == []


def test_delete_removes_the_reference(store):
    store.save_reference(_Waveform(), "doomed")
    assert store.delete_reference("doomed") is True
    assert store.load_reference("doomed") is None


def test_deleting_an_unknown_reference_reports_false(store):
    assert store.delete_reference("ghost") is False


def test_storage_size_grows_after_a_save(store):
    before = store.get_storage_size()
    store.save_reference(_Waveform(), "sized")
    assert store.get_storage_size() > before


def test_names_with_path_characters_are_sanitized(store):
    store.save_reference(_Waveform(), "weird/name:with*chars")
    for saved in Path(store.storage_dir).glob("*.npz"):
        assert "/" not in saved.name and ":" not in saved.name and "*" not in saved.name


# --- Additional characterization coverage: other storage-affecting public methods ---
# rename_reference and clear_all_references are part of the same public surface
# (they go through _find_reference_file / the npz metadata just like save/load/
# list/delete) but were not in the brief's test list. Pinning them here too so
# the coming format/path-resolution migration has to prove them unchanged as well.


@pytest.mark.xfail(
    condition=sys.platform.startswith("win"),
    reason=(
        "Pre-existing bug (not introduced by this test suite): rename_reference() keeps the "
        "np.load() NpzFile from the source file alive (never closes it) while it still holds "
        "time/voltage/metadata references, then calls old_filepath.unlink() on that same file. "
        "Windows refuses to unlink a file with an open handle, so this raises WinError 32 and "
        "rename_reference returns False instead of True. Likely POSIX-safe, since unlinking an "
        "open file is permitted there. rename_reference has no other callers in the codebase. "
        "strict=True so this starts failing loudly (XPASS) if a future change fixes it, as a "
        "reminder to drop the xfail."
    ),
    strict=True,
)
def test_rename_reference_moves_data_to_the_new_name(store):
    waveform = _Waveform()
    store.save_reference(waveform, "old-name")
    assert store.rename_reference("old-name", "new-name") is True

    assert store.load_reference("old-name") is None
    loaded = store.load_reference("new-name")
    assert loaded is not None
    assert loaded["metadata"]["name"] == "new-name"
    assert np.allclose(loaded["voltage"], waveform.voltage)


def test_renaming_an_unknown_reference_reports_false(store):
    assert store.rename_reference("ghost", "whatever") is False


def test_clear_all_references_removes_everything_and_reports_count(store):
    store.save_reference(_Waveform(), "one")
    store.save_reference(_Waveform(), "two")
    assert store.clear_all_references() == 2
    assert store.list_references() == []
    assert store.get_storage_size() == 0


def test_clear_all_references_on_empty_store_reports_zero(store):
    assert store.clear_all_references() == 0
