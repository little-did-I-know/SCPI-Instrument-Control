"""ComputedAnalyzer: deterministic, LLM-free report population.

Pure CPU over synthesized waveforms. No LLM, no network. Layer 1 (this file's
first tests) populates per-waveform statistics and regions.
"""

from datetime import datetime

import numpy as np

from scpi_control.report_generator.analysis.computed_analyzer import ComputedAnalyzer
from scpi_control.report_generator.models.report_data import (
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
    """A waveform whose analysis raises is skipped, not fatal -- the others still
    get populated."""
    from scpi_control.report_generator.models import report_data

    good = make_square("C1")
    bad = make_square("C2")

    real_analyze = report_data.WaveformData.analyze

    def maybe_raise(self):
        if self.channel == "C2":
            raise RuntimeError("boom")
        return real_analyze(self)

    monkeypatch.setattr(report_data.WaveformData, "analyze", maybe_raise)

    report = make_report(waveforms=[good, bad])
    ComputedAnalyzer().analyze_report(report)  # must not raise

    assert report.get_all_waveforms()[0].statistics is not None  # C1 populated
