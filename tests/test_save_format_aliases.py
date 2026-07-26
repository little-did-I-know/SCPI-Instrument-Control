"""Every format name the docs promise must actually save.

save_waveform accepted CSV/CSV_ENHANCED/NPY/MAT/HDF5 but the docstrings around
it -- and four shipped examples -- use 'npz' and 'h5', which raised. 'npz' was
also start_continuous_capture's DEFAULT, so an overnight run with default
arguments wrote nothing and only logged it.

Note the asymmetry that caused this: save_waveform's own auto-detect branch maps
.npz -> NPY and .h5 -> HDF5, so the same spelling was valid as a file extension
and invalid as an argument.
"""

import numpy as np
import pytest

from scpi_control import exceptions
from scpi_control.waveform import Waveform, WaveformData


@pytest.fixture
def waveform():
    return WaveformData(time=np.arange(10) / 1e3, voltage=np.zeros(10), channel=1, sample_rate=1e3)


@pytest.fixture
def manager():
    return Waveform.__new__(Waveform)


@pytest.mark.parametrize("fmt", ["npz", "NPZ", "npy", "NPY", "csv", "CSV", "csv_enhanced", "mat", "MAT"])
def test_documented_format_names_save(manager, waveform, tmp_path, fmt):
    target = tmp_path / "capture.out"
    manager.save_waveform(waveform, str(target), format=fmt)
    assert list(tmp_path.iterdir()), f"format={fmt!r} wrote no file"


@pytest.mark.parametrize("fmt", ["h5", "H5", "hdf5", "HDF5"])
def test_hdf5_format_names_save(manager, waveform, tmp_path, fmt):
    pytest.importorskip("h5py")  # CI installs .[dev,web] only -- no h5py
    target = tmp_path / "capture.out"
    manager.save_waveform(waveform, str(target), format=fmt)
    assert list(tmp_path.iterdir()), f"format={fmt!r} wrote no file"


def test_an_unknown_format_still_raises_and_lists_the_canonical_names(manager, waveform, tmp_path):
    """The aliases must not turn the guard into a no-op."""
    with pytest.raises(exceptions.InvalidParameterError) as excinfo:
        manager.save_waveform(waveform, str(tmp_path / "x.out"), format="parquet")
    assert "CSV, CSV_ENHANCED, NPY, MAT, HDF5" in str(excinfo.value)


def test_the_alias_and_the_extension_agree(manager, waveform, tmp_path):
    """An explicit format and the auto-detected one must resolve identically for
    the same spelling -- the inconsistency that produced this bug."""
    explicit = tmp_path / "explicit.npz"
    detected = tmp_path / "detected.npz"
    manager.save_waveform(waveform, str(explicit), format="npz")
    manager.save_waveform(waveform, str(detected), format=None)
    assert explicit.exists() and detected.exists()
