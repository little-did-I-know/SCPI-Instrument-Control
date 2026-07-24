"""Reference storage moves off pickled metadata onto a JSON string."""

import json

import numpy as np
import pytest

from scpi_control.reference_waveform import LegacyReferenceFormatError, ReferenceWaveform


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
