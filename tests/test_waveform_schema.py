"""The on-disk waveform contract, shared by the library's savers and the report loader."""

import numpy as np
import pytest

from scpi_control import waveform_schema as ws


def test_core_field_names():
    assert ws.TIME == "time"
    assert ws.VOLTAGE == "voltage"
    assert ws.CHANNEL == "channel"
    assert ws.SAMPLE_RATE == "sample_rate"
    assert ws.TIMESTAMP == "timestamp"
    assert ws.CORE_FIELDS == ("time", "voltage", "channel", "sample_rate", "timestamp")


def test_per_format_metadata_conventions_are_named():
    # The three formats genuinely differ; the schema records that rather than hiding it.
    assert ws.NPZ_META_PREFIX == "meta_"
    assert ws.MAT_META_KEY == "metadata"
    assert ws.HDF5_META_GROUP == "metadata"
    assert ws.HDF5_FILE_ATTRS == ("channel", "sample_rate", "num_samples", "timestamp")
    assert ws.CSV_COMMENT == "#"


def test_npz_saver_writes_exactly_the_schema(tmp_path):
    from scpi_control.waveform import Waveform, WaveformData

    t = np.arange(10) / 1e6
    wf = WaveformData(time=t, voltage=np.zeros(10), channel="C1", sample_rate=1e6, record_length=10)
    p = tmp_path / "a.npz"
    object.__new__(Waveform)._save_npy(wf, str(p), metadata={"dut": "board7"})

    keys = set(np.load(p, allow_pickle=True).files)
    # Every core field is present under its schema name...
    assert ws.CORE_FIELDS[0] in keys and ws.CORE_FIELDS[1] in keys
    assert set(ws.CORE_FIELDS).issubset(keys)
    # ...and user metadata uses the schema's prefix.
    assert f"{ws.NPZ_META_PREFIX}dut" in keys


def test_hdf5_saver_writes_attrs_on_the_file_not_the_dataset(tmp_path):
    h5py = pytest.importorskip("h5py")
    from scpi_control.waveform import Waveform, WaveformData

    t = np.arange(10) / 1e6
    wf = WaveformData(time=t, voltage=np.zeros(10), channel="C1", sample_rate=1e6, record_length=10)
    p = tmp_path / "a.h5"
    object.__new__(Waveform)._save_hdf5(wf, str(p), metadata={"dut": "board7"})

    with h5py.File(p, "r") as f:
        # This is the asymmetry the loader got wrong: attrs live on the FILE.
        assert set(ws.HDF5_FILE_ATTRS).issubset(set(f.attrs.keys()))
        assert ws.TIME in f and ws.VOLTAGE in f
        assert ws.HDF5_META_GROUP in f
