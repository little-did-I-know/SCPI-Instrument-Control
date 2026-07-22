"""Manifest, sign-off, and report assembly for comparison/batch reports."""

import hashlib
from datetime import datetime
from unittest.mock import Mock

import pytest

from scpi_control.provenance import AcquisitionProvenance, InstrumentInfo
from scpi_control.report_generator.analysis.comparison_analyzer import ComparisonAnalyzer
from scpi_control.report_generator.comparison_report_builder import append_signoff_and_appendix, build_comparison_report, build_manifest, build_signoff
from scpi_control.report_generator.models.comparison import MODE_BATCH, MODE_COMPARISON, Run, RunSet
from scpi_control.report_generator.models.criteria import ComparisonType, CriteriaSet, MeasurementCriteria
from scpi_control.report_generator.models.report_data import SUMMARY_SOURCE_COMPUTED, ReportMetadata, TestReport, TestSection
from scpi_control.report_generator.models.template import ReportTemplate
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


def _metadata():
    return ReportMetadata(title="Comparison", technician="Robin", test_date=datetime(2026, 7, 22, 12, 0, 0))


def _analyzed(tmp_path, mode=MODE_COMPARISON, criteria=None, n=2, amps=(1.0, 1.5, 1.0)):
    runs = [Run(label=f"run{i}", files=[_capture_file(tmp_path, f"r{i}.csv", amps[i])]) for i in range(n)]
    return ComparisonAnalyzer.analyze(RunSet(runs=runs, mode=mode, criteria_set=criteria))


def _capture_file(tmp_path, name, amplitude, channel=1):
    """Write one synthetic sine capture and return its path.

    Provenance is attached so the plain-CSV writer emits the channel header
    line -- see `_capture` in tests/test_comparison_analyzer.py for the same
    adaptation and its rationale.
    """
    wf = make_waveform(SignalSpec(kind="sine", frequency=1_000.0, amplitude=amplitude, seed=7), 100_000.0, 2_000, channel=channel)
    wf.provenance = AcquisitionProvenance(instrument=InstrumentInfo(model="Mock"))
    path = tmp_path / name
    Waveform(Mock()).save_waveform(wf, str(path), format="CSV")
    return path


def test_comparison_report_sections_in_order(tmp_path):
    report = build_comparison_report(_analyzed(tmp_path), _metadata())
    titles = [s.title for s in report.sections]
    assert titles == ["Overview", "Waveform Overlays", "Comparison Results", "Raw Data Appendix", "Sign-Off"]
    assert report.summary_source == SUMMARY_SOURCE_COMPUTED
    assert report.executive_summary


def test_batch_report_has_batch_summary_and_yield(tmp_path):
    cs = CriteriaSet(name="limits")
    cs.add_criteria(MeasurementCriteria(measurement_name="vpp", comparison_type=ComparisonType.RANGE, min_value=1.5, max_value=2.5))
    report = build_comparison_report(_analyzed(tmp_path, mode=MODE_BATCH, criteria=cs, n=3), _metadata())
    titles = [s.title for s in report.sections]
    assert "Batch Summary" in titles and "Comparison Results" not in titles
    assert "2/3" in report.executive_summary
    assert report.overall_result == "FAIL"


def test_overlay_specs_carry_all_runs(tmp_path):
    report = build_comparison_report(_analyzed(tmp_path), _metadata())
    overlays = report.sections[1].overlay_plots
    assert len(overlays) == 1
    assert [t.run_label for t in overlays[0].traces] == ["run0", "run1"]


def test_comparison_table_has_delta_columns(tmp_path):
    report = build_comparison_report(_analyzed(tmp_path), _metadata())
    table = report.sections[2].comparison_table
    assert table.headers[0] == "Measurement"
    assert any("Δ" in h for h in table.headers)
    assert any(cell.text.startswith("vpp") for row in table.rows for cell in row[:1])


def test_signoff_and_appendix_can_be_disabled(tmp_path):
    report = build_comparison_report(_analyzed(tmp_path), _metadata(), include_appendix=False, include_signoff=False)
    titles = [s.title for s in report.sections]
    assert "Raw Data Appendix" not in titles and "Sign-Off" not in titles


def test_template_signoff_roles_flow_through(tmp_path):
    template = ReportTemplate(name="t", include_signoff=True, include_raw_data_appendix=True, signoff_roles=["QA"], signoff_names={"QA": "Robin"})
    report = build_comparison_report(_analyzed(tmp_path), _metadata(), template=template)
    signoff = report.sections[-1].signoff
    assert signoff.roles[0].title == "QA" and signoff.roles[0].name == "Robin"


def test_append_signoff_and_appendix_on_single_run_report(tmp_path):
    path = _capture_file(tmp_path, "single.csv", 1.0)
    section = TestSection(title="Waveforms")
    section.waveforms = WaveformLoader.load(path)
    report = TestReport(metadata=_metadata(), sections=[section])
    template = ReportTemplate(name="t", include_signoff=True, include_raw_data_appendix=True)
    append_signoff_and_appendix(report, template)
    titles = [s.title for s in report.sections]
    assert titles[-2:] == ["Raw Data Appendix", "Sign-Off"]
    assert report.sections[-2].manifest.entries[0].file_path == str(path)


def test_append_signoff_and_appendix_dedupes_one_source_multiple_channels(tmp_path):
    """A single multi-channel file loaded as several waveforms must still
    produce exactly one manifest entry (one representative waveform per
    source file, for provenance -- not one row per channel)."""
    pytest.importorskip("scipy")
    import numpy as np
    from scipy.io import savemat

    path = tmp_path / "multi.mat"
    savemat(str(path), {"time": np.arange(200) / 1e5, "ch1": np.ones(200), "ch2": np.ones(200) * 2.0})
    section = TestSection(title="Waveforms")
    section.waveforms = WaveformLoader.load(path)
    assert len(section.waveforms) == 2  # sanity: two channels from one file
    report = TestReport(metadata=_metadata(), sections=[section])
    template = ReportTemplate(name="t", include_signoff=True, include_raw_data_appendix=True)
    append_signoff_and_appendix(report, template)
    manifest = report.sections[-2].manifest
    assert len(manifest.entries) == 1
    assert manifest.entries[0].file_path == str(path)


def test_appendix_includes_unmatched_channel_with_dash_for_missing_run(tmp_path):
    """The appendix must cover channels present in only some runs (not just
    result.matched_channels), with "—" for runs lacking that channel."""
    run_a = Run(label="dut_a", files=[_capture_file(tmp_path, "a1.csv", 1.0, channel=1)])
    run_b = Run(
        label="dut_b",
        files=[_capture_file(tmp_path, "b1.csv", 1.0, channel=1), _capture_file(tmp_path, "b2.csv", 1.0, channel=2)],
    )
    result = ComparisonAnalyzer.analyze(RunSet(runs=[run_a, run_b], mode=MODE_BATCH))
    assert result.matched_channels == ["1"]  # channel "2" is unmatched

    report = build_comparison_report(result, _metadata())
    appendix = next(s for s in report.sections if s.title == "Raw Data Appendix")
    table = appendix.comparison_table
    assert table.headers == ["Measurement", "dut_a", "dut_b"]

    channel_2_rows = [row for row in table.rows if row[0].text.endswith("(2)")]
    assert channel_2_rows, "channel '2' rows must appear in the appendix even though it's unmatched"
    for row in channel_2_rows:
        assert row[1].text == "—"  # dut_a has no channel 2
        assert row[2].text != "—"  # dut_b does


def test_appendix_measurements_carry_run_label_in_channel(tmp_path):
    cs = CriteriaSet(name="limits")
    cs.add_criteria(MeasurementCriteria(measurement_name="vpp", comparison_type=ComparisonType.RANGE, min_value=0.0, max_value=10.0))
    result = _analyzed(tmp_path, criteria=cs)
    report = build_comparison_report(result, _metadata())
    appendix = next(s for s in report.sections if s.title == "Raw Data Appendix")
    assert appendix.measurements
    for m in appendix.measurements:
        assert " · " in m.channel
        run_label = m.channel.split(" · ")[0]
        assert run_label in ("run0", "run1")
    # the source runs' own measurements must be untouched (no mutation)
    for run in result.runset.runs:
        for m in run.measurements:
            assert " · " not in (m.channel or "")
