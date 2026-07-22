"""ComparisonAnalyzer: loading, per-run analysis, matching, deltas, aggregates."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from scpi_control.provenance import AcquisitionProvenance, InstrumentInfo
from scpi_control.report_generator.analysis.comparison_analyzer import ComparisonAnalysisError, ComparisonAnalyzer
from scpi_control.report_generator.models.comparison import MODE_BATCH, MODE_COMPARISON, Run, RunSet
from scpi_control.report_generator.models.criteria import ComparisonType, CriteriaSet, MeasurementCriteria
from scpi_control.signal_synth import SignalSpec, make_waveform
from scpi_control.waveform import Waveform


def _capture(tmp_path, name, amplitude=1.0, frequency=1_000.0, channel=1):
    """Write one synthetic sine capture and return its path.

    Provenance is attached so the plain-CSV writer emits the channel header
    line (`save_waveform` only writes it when `waveform.provenance` is set --
    see `scpi_control/waveform.py`); without it every plain CSV round-trips as
    channel "CH1" regardless of the `channel` argument, which collapses the
    channel-matching tests below.
    """
    wf = make_waveform(SignalSpec(kind="sine", frequency=frequency, amplitude=amplitude, seed=42), 100_000.0, 2_000, channel=channel)
    wf.provenance = AcquisitionProvenance(instrument=InstrumentInfo(model="Mock"))
    path = tmp_path / name
    Waveform(Mock()).save_waveform(wf, str(path), format="CSV")
    return path


def _vpp_criteria(vmin, vmax):
    cs = CriteriaSet(name="limits")
    cs.add_criteria(MeasurementCriteria(measurement_name="vpp", comparison_type=ComparisonType.RANGE, min_value=vmin, max_value=vmax))
    return cs


def _two_run_set(tmp_path, mode=MODE_COMPARISON, criteria=None, amp2=1.5):
    return RunSet(
        runs=[
            Run(label="before", files=[_capture(tmp_path, "before.csv", amplitude=1.0)]),
            Run(label="after", files=[_capture(tmp_path, "after.csv", amplitude=amp2)]),
        ],
        mode=mode,
        criteria_set=criteria,
    )


def test_analyze_loads_and_analyzes_each_run(tmp_path):
    result = ComparisonAnalyzer.analyze(_two_run_set(tmp_path))
    for run in result.runset.runs:
        assert len(run.waveforms) == 1
        assert run.waveforms[0].statistics is not None
        assert run.waveforms[0].statistics["vpp"] == pytest.approx(2.0, rel=0.3) or run.label == "after"


def test_matched_channels_found_by_label(tmp_path):
    result = ComparisonAnalyzer.analyze(_two_run_set(tmp_path))
    assert result.matched_channels == ["1"]


def test_unmatched_channel_warns_but_does_not_fail(tmp_path):
    runset = _two_run_set(tmp_path)
    runset.runs[1].files.append(_capture(tmp_path, "extra.csv", channel=2))
    result = ComparisonAnalyzer.analyze(runset)
    assert result.matched_channels == ["1"]
    assert any("2" in w for w in result.warnings)


def test_criteria_set_pass_fail_per_run(tmp_path):
    # vpp ~2.0 for amplitude=1.0 (pass), ~3.0 for amplitude=1.5 (fail)
    result = ComparisonAnalyzer.analyze(_two_run_set(tmp_path, criteria=_vpp_criteria(1.5, 2.5)))
    before, after = result.runset.runs
    assert before.passed is True
    assert after.passed is False
    assert before.measurements[0].name == "vpp" and before.measurements[0].unit == "V"


def test_no_criteria_means_passed_is_none(tmp_path):
    result = ComparisonAnalyzer.analyze(_two_run_set(tmp_path))
    assert all(run.passed is None for run in result.runset.runs)


def test_missing_file_strict_raises_naming_run_and_file(tmp_path):
    runset = _two_run_set(tmp_path)
    runset.runs[1].files = [tmp_path / "missing.csv"]
    with pytest.raises(ComparisonAnalysisError, match="after") as exc:
        ComparisonAnalyzer.analyze(runset)
    assert "missing.csv" in str(exc.value)


def test_skip_bad_runs_drops_run_with_warning(tmp_path):
    runset = RunSet(
        runs=[
            Run(label="a", files=[_capture(tmp_path, "a.csv")]),
            Run(label="b", files=[tmp_path / "missing.csv"]),
            Run(label="c", files=[_capture(tmp_path, "c.csv")]),
        ],
        mode=MODE_BATCH,
    )
    result = ComparisonAnalyzer.analyze(runset, skip_bad_runs=True)
    assert [run.label for run in result.runset.runs] == ["a", "c"]
    assert any("b" in w for w in result.warnings)


def test_skip_bad_runs_still_errors_below_two_survivors(tmp_path):
    runset = _two_run_set(tmp_path)
    runset.runs[0].files = [tmp_path / "gone1.csv"]
    runset.runs[1].files = [tmp_path / "gone2.csv"]
    with pytest.raises(ComparisonAnalysisError, match="at least 2"):
        ComparisonAnalyzer.analyze(runset, skip_bad_runs=True)


def test_dropping_baseline_in_comparison_mode_errors(tmp_path):
    runset = _two_run_set(tmp_path)
    runset.runs[0].files = [tmp_path / "gone.csv"]  # baseline_index == 0
    runset.runs.append(Run(label="third", files=[_capture(tmp_path, "third.csv")]))
    with pytest.raises(ComparisonAnalysisError, match="[Bb]aseline"):
        ComparisonAnalyzer.analyze(runset, skip_bad_runs=True)
