"""scpi-extract CLI: --info, --csv, --json, error exit codes."""

import json
from unittest.mock import Mock

import numpy as np
import pytest

from scpi_control.provenance import AcquisitionProvenance, InstrumentInfo
from scpi_control.scpi_extract import main
from scpi_control.waveform import Waveform, WaveformData


@pytest.fixture
def npz_file(tmp_path):
    time = np.linspace(0.0, 1e-3, 50)
    wf = WaveformData(
        time=time,
        voltage=np.sin(2 * np.pi * 1000 * time),
        channel=1,
        sample_rate=50_000.0,
        provenance=AcquisitionProvenance(instrument=InstrumentInfo(model="SDS824X HD"), acquired_at="2026-07-21T00:00:00+00:00"),
    )
    out = tmp_path / "wf.npz"
    Waveform(Mock()).save_waveform(wf, str(out))
    return out


def test_info_is_default(npz_file, capsys):
    assert main([str(npz_file)]) == 0
    out = capsys.readouterr().out
    assert "SDS824X HD" in out
    assert "50" in out  # sample count


def test_csv_export(npz_file, tmp_path, capsys):
    dest = tmp_path / "out.csv"
    assert main([str(npz_file), "--csv", str(dest)]) == 0
    arr = np.loadtxt(dest, delimiter=",", skiprows=1)
    assert arr.shape == (50, 2)


def test_json_output(npz_file, capsys):
    assert main([str(npz_file), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["provenance"]["instrument"]["model"] == "SDS824X HD"
    assert payload["samples"] == 50


def test_missing_file_exits_nonzero(capsys):
    assert main(["no_such_file.npz"]) == 1
    assert "error" in capsys.readouterr().err.lower()
