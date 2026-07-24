"""Characterization tests: current observable behaviour of ReferenceWaveform.

Written BEFORE the storage format changes, asserting only on the public API so
they stay valid across the migration. If one of these fails, the behaviour
changed -- that is the signal they exist to give.
"""

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

import scpi_control.reference_waveform as reference_waveform_module
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


def test_save_none_waveform_raises_value_error(store):
    with pytest.raises(ValueError):
        store.save_reference(None, "baseline")


def test_save_empty_name_raises_value_error(store):
    with pytest.raises(ValueError):
        store.save_reference(_Waveform(), "")


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


def test_caller_supplied_metadata_survives_round_trip_alongside_derived_fields(store):
    store.save_reference(_Waveform(), "with-extra", metadata={"custom_key": "custom_value", "author": "tester"})
    metadata = store.load_reference("with-extra")["metadata"]

    # Caller-supplied keys survive.
    assert metadata["custom_key"] == "custom_value"
    assert metadata["author"] == "tester"

    # Derived keys are still present alongside them.
    assert metadata["name"] == "with-extra"
    assert metadata["num_samples"] == 32
    assert metadata["channel"] == 1


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


def test_list_references_sorted_by_timestamp_descending(store, monkeypatch):
    """list_references() documents sorting by timestamp, descending.

    Timestamps come from datetime.now().isoformat() at save time, so two real
    saves in a fast test run can land in the same resolution tick and make a
    strict-ordering assertion flaky. To pin the sort behaviour deterministically
    without touching production code, the `datetime` name imported into
    reference_waveform.py is monkeypatched with a stand-in whose now() always
    advances, guaranteeing each save gets a strictly later timestamp than the
    last -- everything else (real datetime instances, fromtimestamp) is left
    untouched.
    """

    class _StepDatetime:
        _current = [datetime(2024, 1, 1, 0, 0, 0)]

        @classmethod
        def now(cls):
            cls._current[0] += timedelta(seconds=1)
            return cls._current[0]

        @staticmethod
        def fromtimestamp(*args, **kwargs):
            return datetime.fromtimestamp(*args, **kwargs)

    monkeypatch.setattr(reference_waveform_module, "datetime", _StepDatetime)

    store.save_reference(_Waveform(), "first")
    store.save_reference(_Waveform(), "second")
    store.save_reference(_Waveform(), "third")

    listed = store.list_references()
    assert [entry["name"] for entry in listed] == ["third", "second", "first"]


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
