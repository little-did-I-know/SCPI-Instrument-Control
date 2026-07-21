"""Savers embed provenance additively; legacy output stays byte-identical."""

import json

import numpy as np
import pytest

from scpi_control import waveform_schema as ws
from scpi_control.provenance import AcquisitionProvenance, ChannelSettings, InstrumentInfo
from scpi_control.waveform import Waveform, WaveformData


def _waveform(with_provenance=True):
    time = np.linspace(0.0, 1e-3, 100)
    voltage = np.sin(2 * np.pi * 1000 * time)
    prov = None
    if with_provenance:
        prov = AcquisitionProvenance(
            instrument=InstrumentInfo(manufacturer="Siglent Technologies", model="SDS824X HD", serial="S1", firmware="1.0"),
            channels={1: ChannelSettings(channel=1, voltage_scale=0.5, probe_ratio=10.0)},
            acquired_at="2026-07-21T00:00:00+00:00",
        )
    return WaveformData(time=time, voltage=voltage, channel=1, sample_rate=100_000.0, timebase=1e-4, voltage_scale=0.5, voltage_offset=0.1, provenance=prov)


@pytest.fixture
def saver():
    from unittest.mock import Mock

    return Waveform(Mock())


def test_npz_embeds_provenance_and_scales(saver, tmp_path):
    out = tmp_path / "wf.npz"
    saver.save_waveform(_waveform(), str(out))
    data = np.load(out, allow_pickle=True)
    prov = AcquisitionProvenance.from_json(str(data[ws.PROVENANCE_JSON]))
    assert prov.instrument.model == "SDS824X HD"
    assert float(data[ws.TIMEBASE]) == 1e-4
    assert float(data[ws.VOLTAGE_SCALE]) == 0.5
    assert float(data[ws.VOLTAGE_OFFSET]) == 0.1
    for key in ws.CORE_FIELDS:  # legacy keys untouched
        assert key in data.files


def test_npz_without_provenance_has_no_provenance_key(saver, tmp_path):
    out = tmp_path / "wf.npz"
    saver.save_waveform(_waveform(with_provenance=False), str(out))
    assert ws.PROVENANCE_JSON not in np.load(out).files


def test_mat_embeds_provenance(saver, tmp_path):
    scipy = pytest.importorskip("scipy")
    from scipy.io import loadmat

    out = tmp_path / "wf.mat"
    saver.save_waveform(_waveform(), str(out))
    mat = loadmat(str(out), squeeze_me=True)
    prov = AcquisitionProvenance.from_json(str(mat[ws.PROVENANCE_JSON]))
    assert prov.channels[1].probe_ratio == 10.0
    assert float(np.asarray(mat[ws.TIMEBASE])) == 1e-4


def test_hdf5_embeds_provenance(saver, tmp_path):
    h5py = pytest.importorskip("h5py")

    out = tmp_path / "wf.h5"
    saver.save_waveform(_waveform(), str(out))
    with h5py.File(out, "r") as f:
        prov = AcquisitionProvenance.from_json(str(f.attrs[ws.PROVENANCE_JSON]))
        assert prov.instrument.serial == "S1"
        assert float(f.attrs[ws.TIMEBASE]) == 1e-4


def test_plain_csv_gains_commented_header(saver, tmp_path):
    out = tmp_path / "wf.csv"
    saver.save_waveform(_waveform(), str(out), format="CSV")
    text = out.read_text()
    assert text.startswith(ws.CSV_COMMENT)
    json_line = [ln for ln in text.splitlines() if ws.CSV_HEADER_PROVENANCE in ln][0]
    payload = json_line.split(":", 1)[1].strip()
    assert json.loads(payload)["instrument"]["model"] == "SDS824X HD"
    # numpy still reads it out of the box
    arr = np.loadtxt(out, delimiter=",", comments=ws.CSV_COMMENT, skiprows=len([ln for ln in text.splitlines() if ln.startswith(ws.CSV_COMMENT)]) + 1)
    assert arr.shape == (100, 2)


def test_plain_csv_bare_is_byte_identical_to_legacy(saver, tmp_path):
    bare = tmp_path / "bare.csv"
    legacy = tmp_path / "legacy.csv"
    saver.save_waveform(_waveform(), str(bare), format="CSV", bare=True)
    saver.save_waveform(_waveform(with_provenance=False), str(legacy), format="CSV")
    assert bare.read_bytes() == legacy.read_bytes()
    assert not bare.read_text().startswith(ws.CSV_COMMENT)


def test_enhanced_csv_appends_provenance_lines(saver, tmp_path):
    out = tmp_path / "wf.csv"
    saver.save_waveform(_waveform(), str(out), format="CSV_ENHANCED", metadata={"operator": "robin"})
    text = out.read_text()
    assert f"{ws.CSV_HEADER_CHANNEL}: 1" in text  # legacy lines intact
    assert "operator: robin" in text
    assert ws.CSV_HEADER_TIMEBASE in text
    assert ws.CSV_HEADER_PROVENANCE in text


def test_binary_formats_write_scales_even_without_provenance(saver, tmp_path):
    out = tmp_path / "wf.npz"
    saver.save_waveform(_waveform(with_provenance=False), str(out))
    data = np.load(out)
    assert float(data[ws.TIMEBASE]) == 1e-4
    assert float(data[ws.VOLTAGE_SCALE]) == 0.5
    assert float(data[ws.VOLTAGE_OFFSET]) == 0.1


def test_plain_csv_without_provenance_stays_headerless(saver, tmp_path):
    """Documented contract: plain CSV carries scale fields only inside the
    provenance header; a provenance-less save is byte-identical legacy output."""
    out = tmp_path / "wf.csv"
    saver.save_waveform(_waveform(with_provenance=False), str(out), format="CSV")
    assert not out.read_text().startswith(ws.CSV_COMMENT)
