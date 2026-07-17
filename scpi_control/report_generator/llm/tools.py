"""Callable tools the local model invokes to inspect a loaded report.

Every public method of ReportTools is a tool. `ollama` builds each tool's JSON
schema from its SIGNATURE and its Google-style DOCSTRING, so both are wire
contract rather than documentation:

  * Type-hint every parameter. An unhinted parameter is silently typed "string".
  * Spell every optional `Optional[X] = None`. A plain default (`x: float = 3.0`)
    is marked REQUIRED in the schema despite having a default.
  * Keep the `Args:` block accurate -- it is the model's only description of each
    parameter.

Numeric bounds do NOT survive into the schema: ollama's Tool model keeps only
type/items/description/enum and drops minimum, maximum, default and
additionalProperties. State bounds in the docstring and enforce them here.

Everything in this module is pure CPU over in-memory arrays: no I/O, no
instrument, and no knowledge of the LLM.
"""

from typing import Callable, List, Optional, Tuple

from scpi_control.report_generator.models.report_data import TestReport, WaveformData
from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer

# detect_transients is unbounded by default in WaveformAnalyzer, so a noisy
# capture really can yield hundreds and blow the context. This is the real
# backstop: the analyzer is called with no limit so the TRUE total is known, and
# the truncation to MAX_TRANSIENTS is reported rather than hidden -- "400 found,
# showing first 10" instead of a bare "10 found", which would teach the model the
# signal is cleaner than it is.
MAX_TRANSIENTS = 10

_SENSITIVITY_DEFAULT = 3.0
_SENSITIVITY_MIN = 1.0
_SENSITIVITY_MAX = 10.0


class ReportTools:
    """Read-only tools over one loaded report."""

    def __init__(self, report: TestReport):
        self.report = report

    def functions(self) -> List[Callable]:
        """The bound tool methods, for LLMClient.chat_with_tools."""
        return [
            self.list_waveforms,
            self.analyze_waveform,
            self.detect_transients,
            self.list_measurements,
        ]

    # -- internals (not tools) --

    def _waveforms(self) -> List[Tuple[WaveformData, str]]:
        """Every waveform paired with the section title it was captured under.

        The title travels with the waveform because a channel is only unique
        within a section: two sections can each capture C1, and a caller that
        drops the title cannot say which one it got.
        """
        return [(wf, section.title) for section in self.report.sections for wf in section.waveforms]

    def _find(self, channel: str) -> Tuple[WaveformData, str]:
        for waveform, section_title in self._waveforms():
            if waveform.channel == channel or waveform.label == channel:
                return waveform, section_title
        available = ", ".join(f"{wf.channel} [{title}]" for wf, title in self._waveforms()) or "none"
        raise ValueError(f"no waveform for channel {channel!r}. Available: {available}")

    # -- tools --

    def list_waveforms(self) -> str:
        """List the captured waveforms available in this report.

        Call this first to discover which channels exist before asking about one.
        """
        waveforms = self._waveforms()
        if not waveforms:
            return "This report contains no waveforms."
        return "\n".join(f"{wf.channel}: label={wf.label!r}, {wf.record_length} samples at {wf.sample_rate / 1e6:.2f} MSa/s  [{section_title}]" for wf, section_title in waveforms)

    def analyze_waveform(self, channel: str) -> str:
        """Analyze one captured waveform and report its measured characteristics.

        Reports the detected signal type and confidence, amplitude, frequency,
        timing and quality statistics, and total harmonic distortion for periodic
        signals.

        If two sections captured the same channel, this analyzes the first and
        names the section it used; report that section alongside your answer.

        Args:
            channel: Channel to analyze, e.g. "C1". Must be one listed by list_waveforms.
        """
        waveform, section_title = self._find(channel)
        stats = WaveformAnalyzer.analyze(waveform)
        lines = [f"analyze_waveform(channel={channel}) [{section_title}]:"]
        lines.extend(f"  {name}: {WaveformAnalyzer.format_stat_value(name, value)}" for name, value in stats.items())
        return "\n".join(lines)

    def detect_transients(self, channel: str, sensitivity: Optional[float] = None) -> str:
        """Find sudden anomalies (glitches, spikes) in one captured waveform.

        Use this to judge whether a signal is clean. Reports where each transient
        starts and ends, in microseconds.

        If two sections captured the same channel, this inspects the first and
        names the section it used; report that section alongside your answer.

        Args:
            channel: Channel to inspect, e.g. "C1". Must be one listed by list_waveforms.
            sensitivity: Detection threshold in standard deviations; lower finds more.
                Must be between 1.0 and 10.0. Defaults to 3.0.
        """
        if sensitivity is None:
            sensitivity = _SENSITIVITY_DEFAULT
        if not _SENSITIVITY_MIN <= sensitivity <= _SENSITIVITY_MAX:
            raise ValueError(f"sensitivity must be between {_SENSITIVITY_MIN} and {_SENSITIVITY_MAX}, got {sensitivity}")

        waveform, section_title = self._find(channel)
        regions = WaveformAnalyzer.detect_transients(waveform, sensitivity=sensitivity)
        head = f"detect_transients(channel={channel}, sensitivity={sensitivity}) [{section_title}]:"
        if not regions:
            return f"{head} none found."

        shown = regions[:MAX_TRANSIENTS]
        summary = f"{head} {len(regions)} found"
        if len(regions) > len(shown):
            summary += f", showing first {len(shown)}"
        lines = [summary]
        lines.extend(f"  {r.label}: {r.start_time * 1e6:.2f} to {r.end_time * 1e6:.2f} µs" for r in shown)
        return "\n".join(lines)

    def list_measurements(self) -> str:
        """List the measurements recorded in this report, with pass/fail status.

        Use this to judge whether the test passed.
        """
        rows = [(m, section.title) for section in self.report.sections for m in section.measurements]
        if not rows:
            return "This report contains no measurements."
        lines = []
        for measurement, section_title in rows:
            status = "" if measurement.passed is None else ("  PASS" if measurement.passed else "  FAIL")
            channel = f" on {measurement.channel}" if measurement.channel else ""
            lines.append(f"{measurement.name}{channel}: {measurement.value:.4g} {measurement.unit}{status}  [{section_title}]")
        return "\n".join(lines)
