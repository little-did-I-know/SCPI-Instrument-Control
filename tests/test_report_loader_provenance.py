"""Report-generator loader handles provenance-bearing files and delegates schema paths."""

from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from scpi_control.provenance import AcquisitionProvenance, InstrumentInfo
from scpi_control.report_generator.utils.waveform_loader import WaveformLoader
from scpi_control.waveform import Waveform, WaveformData


def _waveform():
    time = np.linspace(0.0, 1e-3, 80)
    return WaveformData(
        time=time,
        voltage=np.sin(2 * np.pi * 1000 * time),
        channel=1,
        sample_rate=80_000.0,
        provenance=AcquisitionProvenance(instrument=InstrumentInfo(model="SDS824X HD")),
    )


@pytest.mark.parametrize("filename,format", [("wf.npz", None), ("wf.mat", None), ("wf.h5", None), ("wf.csv", "CSV"), ("wf_enh.csv", "CSV_ENHANCED")])
def test_loader_reads_provenance_bearing_files(tmp_path, filename, format):
    if filename.endswith(".mat"):
        pytest.importorskip("scipy")
    if filename.endswith(".h5"):
        pytest.importorskip("h5py")
    out = tmp_path / filename
    Waveform(Mock()).save_waveform(_waveform(), str(out), format=format)
    loaded = WaveformLoader.load(out)
    assert len(loaded) == 1
    assert len(loaded[0].voltage) == 80
    assert loaded[0].sample_rate == pytest.approx(80_000.0)
    assert loaded[0].channel == "1"


def test_loader_preserves_provenance_object(tmp_path):
    out = tmp_path / "wf.npz"
    Waveform(Mock()).save_waveform(_waveform(), str(out))
    loaded = WaveformLoader.load(out)
    assert loaded[0].provenance is not None
    assert loaded[0].provenance.instrument.model == "SDS824X HD"
