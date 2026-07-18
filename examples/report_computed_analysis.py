"""Deterministic (LLM-free) report analysis.

Builds a synthetic test report and runs ComputedAnalyzer over it. Unlike the AI
path, this needs no local model and no network: it fills the executive summary,
key findings, and recommendations straight from the waveform analysis and sets
summary_source to "computed".

Requirements: SCPI-Instrument-Control[report-generator] (no hardware, no network)
"""

from datetime import datetime

import numpy as np

from scpi_control.report_generator.analysis.computed_analyzer import ComputedAnalyzer
from scpi_control.report_generator.models.report_data import (
    SUMMARY_SOURCE_COMPUTED,
    MeasurementResult,
    ReportMetadata,
    TestReport,
    TestSection,
    WaveformData,
)


def build_report() -> TestReport:
    """A one-channel synthetic report: a 1 kHz sine with light noise."""
    sample_rate = 1e6
    t = np.arange(2000) / sample_rate
    np.random.seed(0)
    v = 3.3 * np.sin(2 * np.pi * 1000 * t) + 0.02 * np.random.randn(t.size)
    waveform = WaveformData(
        channel="C1",
        time=t,
        voltage=v,
        sample_rate=sample_rate,
        record_length=t.size,
        label="1 kHz reference",
    )
    measurements = [
        MeasurementResult(name="Frequency", value=1000.0, unit="Hz", channel="C1", passed=True, criteria_min=990, criteria_max=1010),
        MeasurementResult(name="Peak-to-Peak", value=6.6, unit="V", channel="C1", passed=True, criteria_min=6.0, criteria_max=7.0),
    ]
    report = TestReport(
        metadata=ReportMetadata(title="Computed Analysis Demo", technician="Lab Tech", test_date=datetime.now()),
        sections=[TestSection(title="Captures", waveforms=[waveform], measurements=measurements, order=1)],
    )
    report.overall_result = report.calculate_overall_result()
    return report


def main():
    print("=" * 60)
    print("Deterministic (LLM-free) report analysis")
    print("=" * 60)

    report = build_report()

    print("Running ComputedAnalyzer (no model, no network)...")
    ComputedAnalyzer().analyze_report(report)

    print(f"\nsummary_source: {report.summary_source!r}  (expected {SUMMARY_SOURCE_COMPUTED!r})")
    print("\nExecutive summary:")
    print(f"  {report.executive_summary}")
    print("\nKey findings:")
    for finding in report.key_findings:
        print(f"  - {finding}")
    print("\nRecommendations:")
    for recommendation in report.recommendations:
        print(f"  - {recommendation}")

    print("\n" + "=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
