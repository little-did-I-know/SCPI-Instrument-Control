"""Task 2/3: capture-to-report pipeline paths (single-run and batch/comparison).

Empirical finding (also documented in scpi_control/pipeline.py's module
docstring): `DataCollector.batch_capture(channels)` called with no
`timebase_scales`/`voltage_scales` and the default `triggers_per_config=1`
degenerates to exactly one result, whose `"waveforms"` value is produced by
calling `capture_single()` internally -- so the two are not just
shape-equivalent, they are the literal same call. The Task 2 tests below
exercise `_build_single_run_report` directly against `capture_single()`'s
return value; the routing-by-result-count decision itself is Task 4's
concern.

The Task 3 tests exercise `_build_batch_report` against `batch_capture()`'s
(2+ result) output, and prove the auto-constructed `RunSet` is equivalent to
one hand-built the way `examples/batch_report.py` does, per the design doc's
testing requirement.
"""

from datetime import datetime
from pathlib import Path

import pytest

from scpi_control.automation import DataCollector
from scpi_control.connection.mock import MockConnection
from scpi_control.pipeline import (
    REPORT_FORMAT_BOTH,
    REPORT_FORMAT_MARKDOWN,
    REPORT_FORMAT_PDF,
    PipelineResult,
    _build_batch_report,
    _build_single_run_report,
    _to_report_waveform,
    run_capture_pipeline,
)
from scpi_control.report_generator.analysis.comparison_analyzer import ComparisonAnalyzer
from scpi_control.report_generator.comparison_report_builder import build_comparison_report
from scpi_control.report_generator.generators.markdown_generator import MarkdownReportGenerator
from scpi_control.report_generator.models.comparison import MODE_BATCH, MODE_COMPARISON, Run, RunMetadata, RunSet
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


# --------------------------------------------------------------------------
# Task 3: batch/comparison capture-to-report path
# --------------------------------------------------------------------------


def _batch_collector() -> DataCollector:
    """A connected mock-backed DataCollector with distinct per-channel
    signals, so a channel/label mix-up in either construction path would be
    caught by the equivalence check below."""
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
    return dc


def _hand_built_runset(batch_results: list, saved_files: list, mode: str) -> RunSet:
    """Mirrors examples/batch_report.py's manual `Run`/`RunSet` construction
    pattern, using the exact same label/metadata scheme
    `_build_batch_run` (scpi_control/pipeline.py) uses internally -- matching
    labels is what makes this a true equivalence check: `DeltaEntry.run_label`
    and criteria-warning text are keyed by run label, not just channel."""
    runs = []
    for index, (entry, entry_files) in enumerate(zip(batch_results, saved_files)):
        if "error" in entry:
            continue
        config = entry.get("config") or {}
        trigger_num = entry.get("trigger_num")
        condition = ", ".join(f"{k}={v}" for k, v in config.items()) or None
        notes = f"trigger {trigger_num}" if trigger_num is not None else None
        files = [entry_files[ch] for ch in sorted(entry_files)]
        runs.append(Run(label=f"capture_{index:04d}", files=files, metadata=RunMetadata(condition=condition, notes=notes)))
    return RunSet(runs=runs, mode=mode)


def test_batch_report_matches_hand_built_runset_in_mode_batch(tmp_path):
    """The actual equivalence proof: auto-constructing the RunSet from
    `batch_capture()` + `_build_batch_report` must produce the SAME
    `ComparisonResult` a hand-built `RunSet` (examples/batch_report.py's
    pattern) produces for the identical underlying captures."""
    dc = _batch_collector()
    try:
        batch_results = dc.batch_capture([1, 2], triggers_per_config=3)
        assert len(batch_results) == 3

        auto_result, auto_report = _build_batch_report(dc, batch_results, str(tmp_path / "auto"), _metadata(), mode=MODE_BATCH)

        saved_files = dc.save_batch(batch_results, str(tmp_path / "manual"))
        hand_result = ComparisonAnalyzer.analyze(_hand_built_runset(batch_results, saved_files, MODE_BATCH))
        hand_report = build_comparison_report(hand_result, _metadata())
    finally:
        dc.disconnect()

    assert [run.label for run in auto_result.runset.runs] == [run.label for run in hand_result.runset.runs] == ["capture_0000", "capture_0001", "capture_0002"]
    assert auto_result.matched_channels == hand_result.matched_channels == ["1", "2"]
    assert auto_result.aggregates == hand_result.aggregates
    assert auto_result.deltas == hand_result.deltas == {}
    assert auto_result.yield_passed == hand_result.yield_passed
    assert auto_result.yield_total == hand_result.yield_total
    assert auto_result.yield_incomplete == hand_result.yield_incomplete
    assert auto_result.warnings == hand_result.warnings
    assert auto_report.overall_result == hand_report.overall_result


def test_batch_report_mode_comparison_produces_deltas_vs_baseline(tmp_path):
    dc = _batch_collector()
    try:
        batch_results = dc.batch_capture([1, 2], triggers_per_config=2)
        assert len(batch_results) == 2

        result, report = _build_batch_report(dc, batch_results, str(tmp_path / "cmp"), _metadata(), mode=MODE_COMPARISON)
    finally:
        dc.disconnect()

    assert result.runset.mode == MODE_COMPARISON
    assert result.aggregates == {}
    assert result.deltas, "MODE_COMPARISON should populate deltas vs. the baseline run"
    for channel_deltas in result.deltas.values():
        for entries in channel_deltas.values():
            # baseline run (index 0) is excluded from its own delta list.
            assert len(entries) == len(result.runset.runs) - 1
    assert report.overall_result in {"PASS", "FAIL", "INCONCLUSIVE"}


def test_batch_report_excludes_error_entries_with_a_logged_warning(tmp_path, caplog):
    """A failed capture within an otherwise-successful batch (an entry
    carrying `"error"`) must not be silently included as if it had
    succeeded. Chosen handling: skip it from the RunSet and log a warning
    naming the entry and its capture error."""
    dc = _batch_collector()
    try:
        batch_results = dc.batch_capture([1, 2], triggers_per_config=3)
        assert len(batch_results) == 3
        batch_results[1]["error"] = "simulated capture timeout"
        batch_results[1]["waveforms"] = {}

        with caplog.at_level("WARNING", logger="scpi_control.pipeline"):
            result, _report = _build_batch_report(dc, batch_results, str(tmp_path / "err"), _metadata(), mode=MODE_BATCH)
    finally:
        dc.disconnect()

    assert [run.label for run in result.runset.runs] == ["capture_0000", "capture_0002"]
    assert any("excluded from the RunSet" in msg and "simulated capture timeout" in msg for msg in caplog.messages)


def test_batch_report_raises_when_too_few_runs_survive_errors(tmp_path):
    """Every entry failing must not silently produce a degenerate/empty
    report, nor surface only `RunSet.validate()`'s generic "needs at least
    2 runs, got 0" -- that message has no link back to WHY, and the real
    cause (batch_capture() failures) otherwise lives only in logs a caller
    may not have visibility into. `_build_batch_report` must raise its own
    actionable `ValueError` naming the total entry count, how many failed,
    a sample of the actual failure text, and how many runs would survive."""
    dc = _batch_collector()
    try:
        batch_results = dc.batch_capture([1, 2], triggers_per_config=3)
        assert len(batch_results) == 3
        for entry in batch_results:
            entry["error"] = "simulated capture timeout"
            entry["waveforms"] = {}

        with pytest.raises(ValueError) as excinfo:
            _build_batch_report(dc, batch_results, str(tmp_path / "allfail"), _metadata(), mode=MODE_BATCH)
    finally:
        dc.disconnect()

    message = str(excinfo.value)
    # This is the crux of the regression this test guards against: the
    # generic RunSet.validate() message alone ("needs at least 2 runs, got
    # 0") would satisfy pytest.raises(ValueError) but say nothing about why.
    assert "needs at least 2 runs, got 0" not in message
    assert "simulated capture timeout" in message
    assert "3" in message  # total entries
    assert "0" in message  # runs that would survive


def test_batch_report_raises_names_partial_failures_too_few_to_reach_minimum(tmp_path):
    """A batch where SOME entries survive, but not enough to reach the
    RunSet minimum of 2, must still name the failure(s) that caused it --
    not just the count that failed."""
    dc = _batch_collector()
    try:
        batch_results = dc.batch_capture([1, 2], triggers_per_config=3)
        assert len(batch_results) == 3
        batch_results[0]["error"] = "instrument busy"
        batch_results[0]["waveforms"] = {}
        batch_results[1]["error"] = "simulated capture timeout"
        batch_results[1]["waveforms"] = {}

        with pytest.raises(ValueError) as excinfo:
            _build_batch_report(dc, batch_results, str(tmp_path / "partial"), _metadata(), mode=MODE_BATCH)
    finally:
        dc.disconnect()

    message = str(excinfo.value)
    assert "instrument busy" in message
    assert "simulated capture timeout" in message
    assert "3" in message  # total entries
    assert "2" in message  # failed count
    assert "1" in message  # runs that would survive


# --------------------------------------------------------------------------
# Task 4: report generation wiring + the single public entry point
# --------------------------------------------------------------------------


def _single_run_collector() -> DataCollector:
    """Mirrors `_capture_square_waves`'s signal, but returns the connected
    `DataCollector` itself (not a captured dict) -- `run_capture_pipeline`
    owns calling `batch_capture()` internally."""
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
    return dc


def _reportlab_available() -> bool:
    try:
        import reportlab  # noqa: F401
    except ImportError:
        return False
    return True


def test_run_capture_pipeline_routes_plain_call_to_single_run_path(tmp_path):
    """A caller who passes no sweep parameters at all -- just channels, an
    output dir, and metadata -- must land on the single-run path
    automatically, with no `ComparisonResult` and exactly one `TestReport`
    section per channel."""
    dc = _single_run_collector()
    try:
        result = run_capture_pipeline(dc, [1, 2], str(tmp_path), _metadata())
    finally:
        dc.disconnect()

    assert isinstance(result, PipelineResult)
    assert result.comparison is None
    assert len(result.report.sections) == 2
    assert {s.title for s in result.report.sections} == {"Channel 1", "Channel 2"}
    assert result.report_paths.keys() == {REPORT_FORMAT_MARKDOWN}

    md_path = result.report_paths[REPORT_FORMAT_MARKDOWN]
    assert md_path.exists()
    assert md_path.stat().st_size > 0


def test_run_capture_pipeline_single_run_passing_criteria(tmp_path):
    dc = _single_run_collector()
    try:
        result = run_capture_pipeline(dc, [1, 2], str(tmp_path), _metadata(), criteria_set=_passing_vpp_criteria())
    finally:
        dc.disconnect()

    assert result.comparison is None
    assert result.report.overall_result == "PASS"
    assert result.report_paths[REPORT_FORMAT_MARKDOWN].exists()


def test_run_capture_pipeline_single_run_failing_criteria(tmp_path):
    dc = _single_run_collector()
    try:
        result = run_capture_pipeline(dc, [1, 2], str(tmp_path), _metadata(), criteria_set=_failing_frequency_criteria())
    finally:
        dc.disconnect()

    assert result.comparison is None
    assert result.report.overall_result == "FAIL"
    assert result.report_paths[REPORT_FORMAT_MARKDOWN].exists()


def test_run_capture_pipeline_single_run_generates_pdf_when_reportlab_available(tmp_path):
    if not _reportlab_available():
        pytest.skip("reportlab not installed")

    dc = _single_run_collector()
    try:
        result = run_capture_pipeline(dc, [1, 2], str(tmp_path), _metadata(), report_format=REPORT_FORMAT_BOTH)
    finally:
        dc.disconnect()

    assert result.report_paths.keys() == {REPORT_FORMAT_MARKDOWN, REPORT_FORMAT_PDF}
    pdf_path = result.report_paths[REPORT_FORMAT_PDF]
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0


def test_run_capture_pipeline_pdf_only_skips_gracefully_without_reportlab(tmp_path, caplog):
    """When `reportlab` genuinely is not installed, requesting PDF must not
    raise -- it should log a clear warning and simply omit "pdf" from
    `report_paths`, matching this repo's optional-dependency convention."""
    if _reportlab_available():
        pytest.skip("reportlab is installed in this environment; this test needs it absent")

    dc = _single_run_collector()
    try:
        with caplog.at_level("WARNING", logger="scpi_control.pipeline"):
            result = run_capture_pipeline(dc, [1, 2], str(tmp_path), _metadata(), report_format=REPORT_FORMAT_PDF)
    finally:
        dc.disconnect()

    assert REPORT_FORMAT_PDF not in result.report_paths
    assert any("reportlab" in msg.lower() for msg in caplog.messages)


def test_run_capture_pipeline_routes_sweep_call_to_batch_path(tmp_path):
    """A caller who passes `triggers_per_config=3` (2+ expected results)
    must land on the batch/comparison path automatically: a populated
    `ComparisonResult` is returned alongside the `TestReport`, and it
    matches what calling the internal batch path directly would produce for
    the identical underlying captures."""
    dc = _batch_collector()
    try:
        result = run_capture_pipeline(dc, [1, 2], str(tmp_path / "auto"), _metadata(), triggers_per_config=3, mode=MODE_BATCH)
    finally:
        dc.disconnect()

    assert isinstance(result, PipelineResult)
    assert result.comparison is not None
    assert [run.label for run in result.comparison.runset.runs] == ["capture_0000", "capture_0001", "capture_0002"]
    assert result.comparison.matched_channels == ["1", "2"]
    assert result.report.overall_result == build_comparison_report(result.comparison, _metadata()).overall_result
    assert result.report_paths[REPORT_FORMAT_MARKDOWN].exists()
    assert result.report_paths[REPORT_FORMAT_MARKDOWN].stat().st_size > 0


def test_run_capture_pipeline_batch_mode_comparison(tmp_path):
    dc = _batch_collector()
    try:
        result = run_capture_pipeline(dc, [1, 2], str(tmp_path), _metadata(), triggers_per_config=2, mode=MODE_COMPARISON)
    finally:
        dc.disconnect()

    assert result.comparison is not None
    assert result.comparison.runset.mode == MODE_COMPARISON
    assert result.comparison.deltas, "MODE_COMPARISON should populate deltas vs. the baseline run"
    assert result.report_paths[REPORT_FORMAT_MARKDOWN].exists()


def test_run_capture_pipeline_rejects_unknown_report_format(tmp_path):
    dc = _single_run_collector()
    try:
        with pytest.raises(ValueError, match="report_format"):
            run_capture_pipeline(dc, [1, 2], str(tmp_path), _metadata(), report_format="xml")
    finally:
        dc.disconnect()


def test_run_capture_pipeline_rejects_unknown_mode(tmp_path):
    dc = _single_run_collector()
    try:
        with pytest.raises(ValueError, match="mode"):
            run_capture_pipeline(dc, [1, 2], str(tmp_path), _metadata(), mode="not-a-real-mode")
    finally:
        dc.disconnect()


def test_run_capture_pipeline_single_capture_error_raises_instead_of_empty_report(tmp_path, monkeypatch):
    """An exactly-one-result batch whose sole entry failed (an `"error"`
    key) must raise rather than silently producing a zero-section
    `TestReport` that would look like a trivial pass."""
    dc = _single_run_collector()

    def _failing_batch_capture(channels, **kwargs):
        return [{"waveforms": {}, "config": {}, "trigger_num": 0, "error": "simulated capture timeout"}]

    monkeypatch.setattr(dc, "batch_capture", _failing_batch_capture)

    try:
        with pytest.raises(RuntimeError, match="simulated capture timeout"):
            run_capture_pipeline(dc, [1, 2], str(tmp_path), _metadata())
    finally:
        dc.disconnect()
