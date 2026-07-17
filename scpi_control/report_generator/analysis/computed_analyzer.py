"""Deterministic, LLM-free analysis that populates a TestReport at build time.

Runs the existing WaveformAnalyzer engine over a report and writes the results
into the report model's own fields -- the same fields both generators already
render, and the same report-level fields the LLM path fills. No LLM, no network.

Two layers:
  * Layer 1 (always): populate each waveform's statistics and detected regions.
  * Layer 2 (fallback): compose an executive summary / findings / recommendations
    only when the LLM produced none (added in a later change).

Mutation is intended -- this is a build-time populate of a fresh report -- but it
is idempotent: Layer 1 clears regions first so a second run does not double-append.
"""

import logging

from scpi_control.report_generator.models.report_data import TestReport
from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer

logger = logging.getLogger(__name__)


class ComputedAnalyzer:
    """Populates a TestReport with deterministic analysis."""

    def analyze_report(self, report: TestReport) -> None:
        """Populate the report in place. Layer 1 (per-waveform) always runs."""
        self._populate_waveforms(report)

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
