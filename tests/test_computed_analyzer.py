"""ComputedAnalyzer: deterministic, LLM-free report population.

Pure CPU over synthesized waveforms. No LLM, no network. Layer 1 (this file's
first tests) populates per-waveform statistics and regions.
"""

from datetime import datetime

import numpy as np

from scpi_control.report_generator.analysis.computed_analyzer import ComputedAnalyzer
from scpi_control.report_generator.models.report_data import (
    SUMMARY_SOURCE_AI,
    SUMMARY_SOURCE_COMPUTED,
    MeasurementResult,
    ReportMetadata,
    TestReport,
    TestSection,
    WaveformData,
)


def make_square(channel="C1", n=4000, rate=1e6, freq=500.1):
    t = np.arange(n) / rate
    v = np.where(np.sin(2 * np.pi * freq * t) >= 0, 1.0, -1.0)
    return WaveformData(channel=channel, time=t, voltage=v, sample_rate=rate, record_length=n)


def make_report(waveforms=None, measurements=None):
    section = TestSection(
        title="Captures",
        waveforms=[make_square()] if waveforms is None else list(waveforms),
        measurements=[] if measurements is None else list(measurements),
    )
    return TestReport(
        metadata=ReportMetadata(title="Bench", technician="robin", test_date=datetime(2026, 7, 17)),
        sections=[section],
    )


def test_layer1_populates_statistics_and_regions():
    report = make_report()
    ComputedAnalyzer().analyze_report(report)
    wf = report.get_all_waveforms()[0]
    assert wf.statistics is not None
    assert wf.regions  # a square wave yields plateaus/edges
    assert any(r.slope is not None for r in wf.regions)  # analyze_all_regions ran


def test_layer1_is_idempotent():
    """Running twice must not double-append regions -- clear_regions guards it."""
    report = make_report()
    analyzer = ComputedAnalyzer()
    analyzer.analyze_report(report)
    first = len(report.get_all_waveforms()[0].regions)
    analyzer.analyze_report(report)
    assert len(report.get_all_waveforms()[0].regions) == first


def test_layer1_is_non_fatal_on_one_bad_waveform(monkeypatch):
    """A waveform whose analysis raises is skipped, not fatal -- and a LATER
    waveform still gets populated, proving the loop CONTINUES past the failure
    (not merely that analyze_report didn't raise)."""
    from scpi_control.report_generator.models import report_data

    bad = make_square("C2")
    good = make_square("C1")

    real_analyze = report_data.WaveformData.analyze

    def maybe_raise(self):
        if self.channel == "C2":
            raise RuntimeError("boom")
        return real_analyze(self)

    monkeypatch.setattr(report_data.WaveformData, "analyze", maybe_raise)

    report = make_report(waveforms=[bad, good])  # the bad one is processed FIRST
    ComputedAnalyzer().analyze_report(report)  # must not raise

    waveforms = report.get_all_waveforms()
    assert waveforms[0].statistics is None  # C2 raised -> skipped, left unpopulated
    assert waveforms[1].statistics is not None  # C1, processed AFTER, still populated


def measurement(name, value, unit, passed=None, lo=None, hi=None, channel="C1"):
    return MeasurementResult(name=name, value=value, unit=unit, channel=channel, passed=passed, criteria_min=lo, criteria_max=hi)


def test_layer2_writes_summary_findings_and_recommendations_when_empty():
    ms = [
        measurement("Rise Time", 2.4e-9, "s", passed=False, hi=2.0e-9),
        measurement("Overshoot", 5.0, "%", passed=True, hi=10.0),
    ]
    report = make_report(measurements=ms)
    ComputedAnalyzer().analyze_report(report)

    assert report.summary_source == SUMMARY_SOURCE_COMPUTED
    assert "FAIL" in report.executive_summary or "1 of 2" in report.executive_summary
    assert any("Rise Time" in f for f in report.key_findings)  # the failure is a finding
    assert any("Rise Time" in r for r in report.recommendations)  # and a recommendation


def test_layer2_stands_down_when_the_llm_already_wrote_content():
    report = make_report(measurements=[measurement("V", 1.0, "V", passed=True, hi=5.0)])
    report.executive_summary = "LLM summary."
    report.summary_source = SUMMARY_SOURCE_AI
    ComputedAnalyzer().analyze_report(report)

    assert report.executive_summary == "LLM summary."  # untouched
    assert report.summary_source == SUMMARY_SOURCE_AI  # untouched
    assert report.get_all_waveforms()[0].statistics is not None  # Layer 1 still ran


def test_layer2_is_deterministic():
    ms = [measurement("Rise Time", 2.4e-9, "s", passed=False, hi=2.0e-9)]
    a = make_report(measurements=ms)
    b = make_report(measurements=ms)
    ComputedAnalyzer().analyze_report(a)
    ComputedAnalyzer().analyze_report(b)
    assert a.executive_summary == b.executive_summary
    assert a.key_findings == b.key_findings
    assert a.recommendations == b.recommendations


def test_layer2_caps_findings_and_states_the_remainder():
    ms = [measurement(f"M{i}", float(i), "V", passed=False, hi=0.0) for i in range(12)]
    report = make_report(measurements=ms)
    ComputedAnalyzer().analyze_report(report)
    assert len(report.key_findings) <= ComputedAnalyzer.MAX_FINDINGS + 1  # +1 for the "... and N more" line
    assert any("more" in f for f in report.key_findings)


def test_layer2_clean_report_recommends_nothing_to_do():
    report = make_report(measurements=[measurement("V", 1.0, "V", passed=True, hi=5.0)])
    # A fast (50 kHz) sine reliably yields NO plateaus (arcs shorter than the 1%
    # min-duration) and NO transients (smooth) -- so no miscompensation notes and
    # nothing to review. (Verified in the predecessor sub-project's make_flatless.)
    t = np.arange(2000) / 1e6
    report.sections[0].waveforms = [WaveformData(channel="C1", time=t, voltage=np.sin(2 * np.pi * 50_000 * t), sample_rate=1e6, record_length=2000)]
    ComputedAnalyzer().analyze_report(report)
    assert any("within limits" in r.lower() or "no anomalies" in r.lower() for r in report.recommendations)
