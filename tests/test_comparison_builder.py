"""Manifest, sign-off, and report assembly for comparison/batch reports."""

import hashlib
from datetime import datetime
from unittest.mock import Mock

import pytest

from scpi_control.provenance import AcquisitionProvenance, InstrumentInfo
from scpi_control.report_generator.comparison_report_builder import build_manifest, build_signoff
from scpi_control.report_generator.models.comparison import Run
from scpi_control.report_generator.utils.waveform_loader import WaveformLoader
from scpi_control.signal_synth import SignalSpec, make_waveform
from scpi_control.waveform import Waveform


def _run_with_file(tmp_path, label="before", name="a.csv"):
    wf = make_waveform(SignalSpec(kind="sine", seed=1), 100_000.0, 500)
    wf.provenance = AcquisitionProvenance(instrument=InstrumentInfo(manufacturer="Siglent", model="SDS824X HD", serial="SN1"), acquired_at="2026-07-22T10:00:00+00:00")
    path = tmp_path / name
    Waveform(Mock()).save_waveform(wf, str(path), format="CSV")
    run = Run(label=label, files=[path])
    run.waveforms = WaveformLoader.load(path)
    return run, path


def test_manifest_entry_has_size_hash_identity(tmp_path):
    run, path = _run_with_file(tmp_path)
    manifest = build_manifest([run])
    entry = manifest.entries[0]
    assert entry.run_label == "before"
    assert entry.file_path == str(path)
    assert entry.size_bytes == path.stat().st_size
    assert entry.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert entry.instrument == "Siglent SDS824X HD (SN1)"
    assert entry.capture_timestamp == "2026-07-22T10:00:00+00:00"


def test_manifest_without_provenance_uses_mtime_and_dash_free_fields(tmp_path):
    wf = make_waveform(SignalSpec(kind="sine", seed=1), 100_000.0, 500)
    path = tmp_path / "bare.csv"
    Waveform(Mock()).save_waveform(wf, str(path), format="CSV", bare=True)
    run = Run(label="r", files=[path])
    run.waveforms = WaveformLoader.load(path)
    entry = build_manifest([run]).entries[0]
    assert entry.instrument is None
    # mtime fallback still yields a parseable ISO timestamp
    datetime.fromisoformat(entry.capture_timestamp)


def test_signoff_roles_with_prefilled_names():
    block = build_signoff(["Tested by", "Approved by"], names={"Tested by": "Robin"})
    assert [r.title for r in block.roles] == ["Tested by", "Approved by"]
    assert block.roles[0].name == "Robin" and block.roles[1].name is None
