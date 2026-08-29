"""Task 2: single-run capture-to-report pipeline path.

Empirical finding (also documented in scpi_control/pipeline.py's module
docstring): `DataCollector.batch_capture(channels)` called with no
`timebase_scales`/`voltage_scales` and the default `triggers_per_config=1`
degenerates to exactly one result, whose `"waveforms"` value is produced by
calling `capture_single()` internally -- so the two are not just
shape-equivalent, they are the literal same call. These tests exercise
`_build_single_run_report` directly against `capture_single()`'s return
value; the routing-by-result-count decision itself is Task 4's concern.
"""

from datetime import datetime
from pathlib import Path

import pytest

from scpi_control.automation import DataCollector
from scpi_control.connection.mock import MockConnection
from scpi_control.pipeline import _build_single_run_report, _to_report_waveform
from scpi_control.report_generator.generators.markdown_generator import MarkdownReportGenerator
from scpi_control.report_generator.models.criteria import ComparisonType, CriteriaSet, MeasurementCriteria
from scpi_control.report_generator.models.report_data import ReportMetadata
from scpi_control.signal_synth import SignalSpec

_FREQUENCY_HZ = 1_000.0
_AMPLITUDE_V = 1.0  # square wave -> vpp = 2 * amplitude = 2.0 V


def _capture_square_waves() -> dict:
    """Capture a known 1 kHz, 2 Vpp square wave on channels 1 and 2 (mock scope)."""
    conn = MockConnection(
        channel_states={1: True, 2: True},
        sample_rate=100_000.0,
        timebase=1e-3,
        signals={
            1: SignalSpec(kind="square", frequency=_FREQUENCY_HZ, amplitude=_AMPLITUDE_V, noise_rms=0.0, seed=7),
            2: SignalSpec(kind="square", frequency=_FREQUENCY_HZ, amplitude=_AMPLITUDE_V, noise_rms=0.0, seed=8),
        },
    )
    dc = DataCollector("mock", connection=conn)
    dc.connect()
    try:
        return dc.capture_single([1, 2])
    finally:
        dc.disconnect()


def _metadata() -> ReportMetadata:
    return ReportMetadata(title="Pipeline Test", technician="tester", test_date=datetime(2026, 8, 28))


def _passing_vpp_criteria() -> CriteriaSet:
    """vpp ~2.0 V comfortably inside [1.5, 2.5] -- the known signal PASSES."""
    cs = CriteriaSet(name="passing-vpp")
    cs.add_criteria(
        MeasurementCriteria(
            measurement_name="vpp",
            comparison_type=ComparisonType.RANGE,
            min_value=1.5,
            max_value=2.5,
            severity="critical",
        )
    )
    return cs


def _failing_frequency_criteria() -> CriteriaSet:
    """An absurdly tight frequency window the known 1 kHz signal FAILS."""
    cs = CriteriaSet(name="failing-frequency")
    cs.add_criteria(
        MeasurementCriteria(
            measurement_name="frequency",
            comparison_type=ComparisonType.RANGE,
            min_value=999_999.0,
            max_value=1_000_001.0,
            severity="critical",
        )
    )
    return cs


def test_one_section_per_captured_channel_with_expected_statistics():
    waveforms = _capture_square_waves()

    report = _build_single_run_report(waveforms, _metadata())

    assert len(report.sections) == 2
    assert {s.title for s in report.sections} == {"Channel 1", "Channel 2"}
    for section in report.sections:
        assert len(section.waveforms) == 1
        stats = section.waveforms[0].statistics
        assert stats is not None
        assert stats["vpp"] == pytest.approx(2.0 * _AMPLITUDE_V, rel=0.2)
        assert stats["frequency"] == pytest.approx(_FREQUENCY_HZ, rel=0.2)


def test_passing_criteria_marks_measurements_passed_and_overall_pass():
    waveforms = _capture_square_waves()

    report = _build_single_run_report(waveforms, _metadata(), criteria_set=_passing_vpp_criteria())

    measurements = report.get_all_measurements()
    assert measurements, "the vpp criterion should produce a MeasurementResult per channel"
    assert all(m.passed for m in measurements)
    assert report.overall_result == "PASS"


def test_failing_criteria_marks_measurements_failed_and_overall_fail():
    waveforms = _capture_square_waves()

    report = _build_single_run_report(waveforms, _metadata(), criteria_set=_failing_frequency_criteria())

    measurements = report.get_all_measurements()
    assert measurements, "the frequency criterion should produce a MeasurementResult per channel"
    assert any(m.passed is False for m in measurements)
    assert report.overall_result == "FAIL"


def test_no_criteria_set_still_populates_statistics_but_no_verdict():
    """Matches evaluate_measurements's criteria_set=None behavior: measurements
    come back empty (nothing to evaluate against), but .statistics is still
    populated from WaveformAnalyzer.analyze(), and overall_result is
    INCONCLUSIVE rather than a fabricated PASS/FAIL."""
    waveforms = _capture_square_waves()

    report = _build_single_run_report(waveforms, _metadata(), criteria_set=None)

    for section in report.sections:
        assert section.waveforms[0].statistics is not None
        assert section.waveforms[0].statistics["vpp"] == pytest.approx(2.0 * _AMPLITUDE_V, rel=0.2)
        assert section.measurements == []
    assert report.get_all_measurements() == []
    assert report.overall_result == "INCONCLUSIVE"


def test_to_report_waveform_carries_probe_ratio_and_coupling_from_provenance():
    """`_to_report_waveform` must pull `probe_ratio`/`coupling` out of the
    captured waveform's `provenance.channels` (keyed by the original int
    channel number) -- these are silently dropped otherwise, even though
    `markdown_generator.py` renders a "Probe Ratio" row from them and
    `examples/report_generation_example.py` sets both fields deliberately."""
    conn = MockConnection(
        channel_states={1: True},
        sample_rate=100_000.0,
        timebase=1e-3,
        signals={1: SignalSpec(kind="square", frequency=_FREQUENCY_HZ, amplitude=_AMPLITUDE_V, noise_rms=0.0, seed=7)},
    )
    dc = DataCollector("mock", connection=conn)
    dc.connect()
    try:
        dc.scope.channel1.probe_ratio = 10.0
        dc.scope.channel1.coupling = "AC"
        waveforms = dc.capture_single([1])
    finally:
        dc.disconnect()

    captured = waveforms[1]
    assert captured.provenance is not None
    assert captured.provenance.channels[1].probe_ratio == 10.0
    assert captured.provenance.channels[1].coupling == "AC"

    report_waveform = _to_report_waveform(captured)

    assert report_waveform.probe_ratio == 10.0
    assert report_waveform.coupling == "AC"
    # channel is stringified by ReportWaveformData.__post_init__ -- the
    # provenance lookup inside _to_report_waveform must happen against the
    # ORIGINAL int channel, before that stringification.
    assert report_waveform.channel == "1"

    report_waveform.analyze()
    rendered = MarkdownReportGenerator(include_plots=False)._generate_waveform_info(report_waveform, Path("."), "waveform")
    assert "Probe Ratio" in rendered
    assert "10.0:1" in rendered


def test_to_report_waveform_defaults_probe_ratio_and_coupling_when_provenance_missing():
    """A capture without provenance (or without that channel's entry) is a
    real, valid case elsewhere (`Waveform.acquire(provenance=False)`, or a
    failed snapshot that logs a warning and leaves `.provenance = None`) --
    this conversion must not be stricter than that: it should fall back to
    the field's own `None` default rather than raising."""
    waveforms = _capture_square_waves()
    captured = waveforms[1]
    captured.provenance = None

    report_waveform = _to_report_waveform(captured)

    assert report_waveform.probe_ratio is None
    assert report_waveform.coupling is None
