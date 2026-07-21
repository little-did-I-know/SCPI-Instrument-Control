"""Regression tests for DataCollector.save_data / save_batch default format.

Bug: both methods defaulted to format="npz" and passed it straight through to
Waveform.save_waveform, which upper-cases the format string and only accepts
CSV, CSV_ENHANCED, NPY, MAT, HDF5 -- "NPZ" is not among them, so the default
(documented) call path raised InvalidParameterError. The fix changes the
default to None so save_waveform's extension-based auto-detect applies.
"""

import numpy as np
import pytest

from scpi_control.automation import DataCollector
from scpi_control.connection.mock import MockConnection
from scpi_control.exceptions import InvalidParameterError
from scpi_control.waveform import WaveformData


@pytest.fixture
def collector():
    mock_connection = MockConnection(
        channel_states={1: True, 2: True},
        sample_rate=1_000.0,
        timebase=1e-3,
    )
    return DataCollector("mock", connection=mock_connection)


def _make_waveform(channel: int) -> WaveformData:
    time = np.linspace(0, 1e-3, 100)
    voltage = np.sin(2 * np.pi * 1000 * time)
    return WaveformData(
        time=time,
        voltage=voltage,
        channel=channel,
        sample_rate=1_000.0,
        timebase=1e-3,
        voltage_scale=1.0,
    )


def test_save_data_default_format_writes_npz_loadable_by_numpy(tmp_path):
    """Regression test: default save_data(...) call must not raise.

    This mirrors the README example: collector.save_data(data, 'measurement.npz').
    """
    mock_connection = MockConnection(channel_states={1: True}, sample_rate=1_000.0, timebase=1e-3)
    collector = DataCollector("mock", connection=mock_connection)
    waveforms = {1: _make_waveform(1)}
    filename = str(tmp_path / "measurement.npz")

    collector.save_data(waveforms, filename)

    saved_path = tmp_path / "measurement_ch1.npz"
    assert saved_path.exists()

    with np.load(saved_path, allow_pickle=True) as npz:
        assert "time" in npz
        assert "voltage" in npz
        assert len(npz["time"]) == 100
        assert len(npz["voltage"]) == 100


def test_save_data_explicit_npy_format_works(tmp_path):
    # Filename intentionally ends in .npz: numpy's np.savez() appends a .npz
    # suffix itself whenever the target name doesn't already end in .npz, so a
    # ".npy" filename here would land on disk as "..._ch1.npy.npz" -- a quirk
    # of numpy, not something this fix changes. Using ".npz" keeps the test
    # focused on the explicit-format contract this fix is pinning.
    mock_connection = MockConnection(channel_states={1: True}, sample_rate=1_000.0, timebase=1e-3)
    collector = DataCollector("mock", connection=mock_connection)
    waveforms = {1: _make_waveform(1)}
    filename = str(tmp_path / "measurement.npz")

    collector.save_data(waveforms, filename, format="NPY")

    saved_path = tmp_path / "measurement_ch1.npz"
    assert saved_path.exists()

    with np.load(saved_path, allow_pickle=True) as npz:
        assert "time" in npz
        assert "voltage" in npz


def test_save_data_explicit_lowercase_npz_still_raises(tmp_path):
    """Pin the contract: save_waveform only accepts the exact tokens it upper-cases
    to CSV/CSV_ENHANCED/NPY/MAT/HDF5. An explicit format="npz" is not one of them
    and must still raise -- only the *default* (None) auto-detects."""
    mock_connection = MockConnection(channel_states={1: True}, sample_rate=1_000.0, timebase=1e-3)
    collector = DataCollector("mock", connection=mock_connection)
    waveforms = {1: _make_waveform(1)}
    filename = str(tmp_path / "measurement.npz")

    with pytest.raises(InvalidParameterError):
        collector.save_data(waveforms, filename, format="npz")


def test_save_batch_default_format_smoke(tmp_path):
    mock_connection = MockConnection(channel_states={1: True, 2: True}, sample_rate=1_000.0, timebase=1e-3)
    collector = DataCollector("mock", connection=mock_connection)

    batch_results = [
        {
            "timestamp": "2026-07-21T00:00:00",
            "config": {"timebase": "1e-3"},
            "waveforms": {1: _make_waveform(1), 2: _make_waveform(2)},
            "trigger_num": 0,
        },
        {
            "timestamp": "2026-07-21T00:00:01",
            "config": {"timebase": "1e-3"},
            "waveforms": {1: _make_waveform(1), 2: _make_waveform(2)},
            "trigger_num": 1,
        },
    ]

    output_dir = tmp_path / "batch_out"
    collector.save_batch(batch_results, str(output_dir))

    saved_files = sorted(output_dir.glob("capture_*.npz"))
    assert len(saved_files) == 4  # 2 captures * 2 channels

    for saved_file in saved_files:
        with np.load(saved_file, allow_pickle=True) as npz:
            assert "time" in npz
            assert "voltage" in npz

    assert (output_dir / "metadata.txt").exists()
