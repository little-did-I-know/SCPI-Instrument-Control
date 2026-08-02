"""CSV export: a readable table behind a header that explains it."""

import csv

import numpy as np
import pytest

from scpi_control.frequency_response.model import FrequencyResponse, ResponsePoint, SweepSettings
from scpi_control.provenance import AcquisitionProvenance, InstrumentInfo


def _result():
    settings = SweepSettings(reference_channel=1, response_channel=2, awg_channel=1, frequencies=(100.0, 1000.0), amplitude_vpp=2.0, settle_s=0.05, autorange=True)
    points = [
        ResponsePoint(frequency_hz=100.0, gain_db=-0.04, phase_deg=-5.7, reference_vpp=2.0, response_vpp=1.99, cycles_in_window=1.4, samples_per_cycle=10000.0, volts_per_div=0.5),
        ResponsePoint(frequency_hz=1000.0, gain_db=None, phase_deg=None, excluded_reason="response clipped"),
    ]
    provenance = AcquisitionProvenance(
        instrument=InstrumentInfo(manufacturer="Siglent", model="SDS824X HD", serial="SDS1234", firmware="3.8.12"), library_version="6.0.0", acquired_at="2026-08-02T12:00:00Z", dialect="modern"
    )
    return FrequencyResponse(settings=settings, points=points, provenance=provenance)


def test_csv_header_lines_are_all_commented(tmp_path):
    path = tmp_path / "sweep.csv"
    _result().to_csv(path)

    lines = path.read_text().splitlines()
    header = [line for line in lines if line.startswith("#")]
    assert len(header) >= 5
    assert lines.index("frequency_hz,gain_db,phase_deg,reference_vpp,response_vpp,cycles_in_window,samples_per_cycle,volts_per_div,excluded_reason") == len(header)


def test_csv_header_records_the_instrument_and_the_settings(tmp_path):
    path = tmp_path / "sweep.csv"
    _result().to_csv(path)

    header = "\n".join(line for line in path.read_text().splitlines() if line.startswith("#"))
    assert "SDS824X HD" in header
    assert "3.8.12" in header
    assert "amplitude_vpp: 2.0" in header
    assert "settle_s: 0.05" in header
    assert "autorange: True" in header


def test_csv_rows_round_trip_through_a_plain_reader(tmp_path):
    path = tmp_path / "sweep.csv"
    _result().to_csv(path)

    with open(path, newline="") as handle:
        rows = list(csv.DictReader(line for line in handle if not line.startswith("#")))

    assert [row["frequency_hz"] for row in rows] == ["100.0", "1000.0"]
    assert rows[0]["gain_db"] == "-0.04"
    assert rows[1]["gain_db"] == ""
    assert rows[1]["excluded_reason"] == "response clipped"


def test_numpy_reads_the_measured_columns(tmp_path):
    # genfromtxt's names=True consumes the FIRST line as the header, comment or
    # not, so the metadata block has to be dropped before it. Measured on numpy
    # 2.4.0, and true even for a single comment line. pandas.read_csv(comment="#")
    # does handle it unaided; numpy needs this one line of help.
    path = tmp_path / "sweep.csv"
    _result().to_csv(path)

    with open(path) as handle:
        data = np.genfromtxt((line for line in handle if not line.startswith("#")), delimiter=",", names=True)

    assert data["frequency_hz"].tolist() == [100.0, 1000.0]
    assert np.isnan(data["gain_db"][1])  # an empty field reads as NaN, never a sentinel


def test_csv_survives_missing_provenance(tmp_path):
    result = _result()
    result.provenance = None
    path = tmp_path / "sweep.csv"
    result.to_csv(path)
    assert "# instrument: unknown" in path.read_text()
