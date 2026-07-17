"""Deterministic, LLM-free analysis that populates a TestReport at build time.

Runs the existing WaveformAnalyzer engine over a report and writes the results
into the report model's own fields -- the same fields both generators already
render, and the same report-level fields the LLM path fills. No LLM, no network.

Two layers:
  * Layer 1 (always): populate each waveform's statistics and detected regions.
  * Layer 2 (fallback): compose an executive summary / findings / recommendations
    only when the LLM produced none.

Mutation is intended -- this is a build-time populate of a fresh report -- but it
is idempotent: Layer 1 clears regions first so a second run does not double-append.
Layer 2 only ever writes when the LLM-authored fields are all empty, so re-running
after an LLM has already written content is a no-op for those fields.
"""

import logging

from scpi_control.report_generator.models.report_data import SUMMARY_SOURCE_COMPUTED, TestReport
from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer

logger = logging.getLogger(__name__)


class ComputedAnalyzer:
    """Populates a TestReport with deterministic analysis."""

    MAX_FINDINGS = 8
    MAX_RECOMMENDATIONS = 8

    def analyze_report(self, report: TestReport) -> None:
        """Populate the report in place. Layer 1 (per-waveform) always runs;
        Layer 2 (report-level prose) runs only when the LLM produced none."""
        self._populate_waveforms(report)
        if not report.executive_summary and not report.key_findings and not report.recommendations:
            self._write_report_level(report)

    def _populate_waveforms(self, report: TestReport) -> None:
        for waveform in report.get_all_waveforms():
            try:
                waveform.clear_regions()  # idempotency: no double-append on re-run
                waveform.analyze()
                WaveformAnalyzer.detect_regions(
                    waveform,
                    auto_detect_plateaus=True,
                    auto_detect_edges=True,
                    auto_detect_transients=True,
                )
                WaveformAnalyzer.analyze_all_regions(waveform)
            except Exception:
                logger.warning(
                    f"Computed analysis skipped for waveform {waveform.channel!r}",
                    exc_info=True,
                )

    def _write_report_level(self, report: TestReport) -> None:
        report.executive_summary = self._executive_summary(report)
        report.key_findings = self._key_findings(report)
        report.recommendations = self._recommendations(report)
        report.summary_source = SUMMARY_SOURCE_COMPUTED

    def _executive_summary(self, report: TestReport) -> str:
        waveforms = report.get_all_waveforms()
        measurements = report.get_all_measurements()
        parts = [f"This report covers {len(waveforms)} capture(s) across {len(report.sections)} section(s)."]
        graded = [m for m in measurements if m.passed is not None]
        if graded:
            passed = sum(1 for m in graded if m.passed)
            parts.append(f"Overall result: {report.calculate_overall_result()} ({passed} of {len(graded)} measurements passed).")
        for waveform in waveforms:
            parts.append(self._describe_waveform(waveform))
        return " ".join(parts)

    def _describe_waveform(self, waveform) -> str:
        if not waveform.statistics:
            return f"{waveform.channel}: analysis unavailable."
        signal = waveform.format_statistic("signal_type")
        freq = waveform.format_statistic("frequency")
        vpp = waveform.format_statistic("vpp")
        text = f"{waveform.channel}: {signal}, {freq}, Vpp {vpp}"
        if waveform.get_statistic("thd") is not None:
            text += f", THD {waveform.format_statistic('thd')}"
        return text + "."

    def _key_findings(self, report: TestReport):
        findings = []
        for measurement in report.get_all_measurements():
            if measurement.passed is False:
                findings.append(f"{self._measurement_str(measurement)} -- FAIL (limits {self._limits_str(measurement)})")
        for waveform in report.get_all_waveforms():
            findings.append(self._describe_waveform(waveform).rstrip("."))
        for waveform in report.get_all_waveforms():
            count = len(waveform.get_regions_by_type("transient"))
            if count:
                findings.append(f"{waveform.channel}: {count} transient(s) detected")
        return self._cap(findings, self.MAX_FINDINGS)

    def _recommendations(self, report: TestReport):
        recommendations = []
        for measurement in report.get_all_measurements():
            if measurement.passed is False:
                recommendations.append(
                    f"Investigate {measurement.name}{self._on(measurement)}: measured {measurement.value:.4g} {measurement.unit}, outside the limits {self._limits_str(measurement)}."
                )
        for waveform in report.get_all_waveforms():
            for region in waveform.regions:
                note = region.calibration_recommendation
                if note and not note.startswith("✓"):  # skip the "good" note
                    recommendations.append(f"{waveform.channel}: {note}")
        for waveform in report.get_all_waveforms():
            count = len(waveform.get_regions_by_type("transient"))
            if count:
                recommendations.append(f"Review {count} transient(s) on {waveform.channel}.")
        if not recommendations:
            recommendations.append("All measurements within limits; no anomalies detected.")
        return self._cap(recommendations, self.MAX_RECOMMENDATIONS)

    @staticmethod
    def _measurement_str(measurement) -> str:
        return f"{measurement.name}{ComputedAnalyzer._on(measurement)}: {measurement.value:.4g} {measurement.unit}"

    @staticmethod
    def _limits_str(measurement) -> str:
        low = "-inf" if measurement.criteria_min is None else f"{measurement.criteria_min:.4g}"
        high = "+inf" if measurement.criteria_max is None else f"{measurement.criteria_max:.4g}"
        return f"[{low}, {high}] {measurement.unit}"

    @staticmethod
    def _on(measurement) -> str:
        return f" on {measurement.channel}" if measurement.channel else ""

    @staticmethod
    def _cap(items, limit):
        if len(items) <= limit:
            return items
        return items[:limit] + [f"... and {len(items) - limit} more"]
