"""load_waveform round-trips every saver format, old files included."""

import logging
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from scpi_control.provenance import AcquisitionProvenance, ChannelSettings, InstrumentInfo
from scpi_control.waveform import Waveform, WaveformData
from scpi_control.waveform_io import LoadedWaveform, load_waveform

FIXTURE = Path(__file__).parent / "fixtures" / "cal_square_sds824x.npz"


def _waveform():
    time = np.linspace(0.0, 1e-3, 100)
    voltage = np.sin(2 * np.pi * 1000 * time)
    prov = AcquisitionProvenance(
        instrument=InstrumentInfo(manufacturer="Siglent Technologies", model="SDS824X HD", serial="S1", firmware="1.0"),
        channels={1: ChannelSettings(channel=1, voltage_scale=0.5)},
        acquired_at="2026-07-21T00:00:00+00:00",
    )
    return WaveformData(time=time, voltage=voltage, channel=1, sample_rate=100_000.0, timebase=1e-4, voltage_scale=0.5, provenance=prov)


@pytest.fixture
def saver():
    return Waveform(Mock())


@pytest.mark.parametrize(
    "filename,format,source_format",
    [
        ("wf.npz", None, "NPZ"),
        ("wf.csv", "CSV", "CSV"),
        ("wf_enh.csv", "CSV_ENHANCED", "CSV"),
        ("wf.mat", None, "MAT"),
        ("wf.h5", None, "HDF5"),
    ],
)
def test_round_trip_every_format(saver, tmp_path, filename, format, source_format):
    if filename.endswith(".mat"):
        pytest.importorskip("scipy")
    if filename.endswith(".h5"):
        pytest.importorskip("h5py")
    wf = _waveform()
    out = tmp_path / filename
    saver.save_waveform(wf, str(out), format=format)

    loaded = load_waveform(out)
    assert isinstance(loaded, LoadedWaveform)
    assert loaded.source_format == source_format
    np.testing.assert_allclose(loaded.time, wf.time, rtol=1e-6)
    np.testing.assert_allclose(loaded.voltage, wf.voltage, rtol=1e-5)
    assert loaded.provenance is not None
    assert loaded.provenance.instrument.model == "SDS824X HD"
    assert loaded.provenance.channels[1].voltage_scale == 0.5
    assert loaded.metadata.get("timebase") == pytest.approx(1e-4)


def test_legacy_fixture_loads_without_provenance():
    loaded = load_waveform(FIXTURE)
    assert loaded.provenance is None
    assert len(loaded.voltage) > 0
    assert loaded.sample_rate and loaded.sample_rate > 0


def test_user_metadata_survives_npz(saver, tmp_path):
    out = tmp_path / "wf.npz"
    saver.save_waveform(_waveform(), str(out), metadata={"operator": "robin", "run": 7})
    loaded = load_waveform(out)
    assert loaded.metadata["operator"] == "robin"
    assert int(loaded.metadata["run"]) == 7


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_waveform(Path("does_not_exist.npz"))


def test_unknown_extension_raises(tmp_path):
    bad = tmp_path / "wf.xyz"
    bad.write_text("nope")
    with pytest.raises(ValueError):
        load_waveform(bad)


def test_to_dataframe(saver, tmp_path):
    pd = pytest.importorskip("pandas")
    out = tmp_path / "wf.npz"
    saver.save_waveform(_waveform(), str(out))
    df = load_waveform(out).to_dataframe()
    assert list(df.columns) == ["time", "voltage"]
    assert df.attrs["provenance"]["instrument"]["model"] == "SDS824X HD"


def test_corrupt_provenance_yields_none_with_warning(tmp_path, caplog):
    from scpi_control import waveform_schema as ws

    out = tmp_path / "wf.npz"
    np.savez(out, **{ws.TIME: np.linspace(0.0, 1.0, 10), ws.VOLTAGE: np.zeros(10), ws.CHANNEL: 1, ws.SAMPLE_RATE: 10.0, ws.PROVENANCE_JSON: "{not valid json"})
    with caplog.at_level(logging.WARNING):
        loaded = load_waveform(out)
    assert loaded.provenance is None
    assert len(loaded.voltage) == 10
    assert any("provenance" in record.message.lower() for record in caplog.records)
