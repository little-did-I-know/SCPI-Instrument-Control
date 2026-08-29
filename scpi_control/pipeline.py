"""Capture pipeline: connects live/mock oscilloscope capture (`DataCollector`)
to the report_generator's analysis and reporting stack.

Design: docs/superpowers/specs/2026-08-28-capture-pipeline-design.md
Plan:   docs/superpowers/plans/2026-08-28-capture-pipeline.md

This module closes a gap confirmed by research before this feature started:
`DataCollector` (capture) and `report_generator` (analysis + reporting) had
never been imported into each other anywhere in the codebase.

Task 2 status: the single-run path below is implemented. The batch/comparison
path (Task 3) and the single public entry point that routes between them
(Task 4) do not exist yet -- everything here is intentionally internal
(leading underscore) until both paths exist and can share one public API.

--------------------------------------------------------------------------
Empirical finding: does batch_capture() degenerate to capture_single()?
--------------------------------------------------------------------------
Verified by reading `DataCollector.batch_capture`'s body (automation.py:241)
and then actually running it against a mock-backed `DataCollector`:

    conn = MockConnection(channel_states={1: True}, ...)
    dc = DataCollector("mock", connection=conn); dc.connect()
    single = dc.capture_single([1])                 # -> {1: WaveformData}
    batch = dc.batch_capture([1])                    # no scales, default
                                                       # triggers_per_config=1

Result: `batch_capture([1])` returns a list of length 1. Reading the body
confirms why -- with no `timebase_scales`/`voltage_scales`, `configs` stays
`[{}]` (one config, automation.py:301-307/318); with the default
`triggers_per_config=1`, the inner loop (automation.py:355) runs exactly
once. That single entry's `"waveforms"` value is produced by calling
`self.capture_single(channels)` (automation.py:369) -- the literal same
method `capture_single()` is -- so `batch["waveforms"]` and `single` are not
just equal in shape, they are the result of the identical call.

Conclusion: YES, `batch_capture()` with defaults degenerates to exactly one
result that is the same effective capture `capture_single()` would give.
This is why Task 4's routing can be "by result count" alone (1 result ->
single-run path, 2+ -> batch/comparison path) rather than needing a separate
`capture_single()` code path baked into the router -- though this module's
single-run entry point (below) is still written against the
`Dict[int, WaveformData]` shape both methods produce, so it works either way
callers arrive at it.

--------------------------------------------------------------------------
Type-conversion finding: capture output vs. report_generator's WaveformData
--------------------------------------------------------------------------
`DataCollector.capture_single`/`batch_capture` return
`scpi_control.waveform.WaveformData` instances (confirmed by inspecting a
captured object's `type()` directly). The report_generator package's own
`WaveformData` (`report_generator/models/report_data.py`) is a DIFFERENT,
though related, type: a dataclass subclass of the capture one that adds
report-only fields (`label`, `color`, `statistics`, `signal_type`, `regions`,
...) and an `.analyze()` method. They are not interchangeable -- the report
stack's generators and `WaveformAnalyzer`/`evaluate_measurements` are typed
against the subclass, and only the subclass carries `.statistics`/`.label`.
A conversion step is therefore required; `_to_report_waveform` below copies
the physical-capture fields (time, voltage, channel, sample_rate,
record_length, timebase, voltage_scale, voltage_offset, provenance) across
without recomputing anything. It also pulls `probe_ratio`/`coupling` out of
`provenance.channels[channel]` (a `Dict[int, ChannelSettings]`, see
`scpi_control/provenance.py`) -- these are report-relevant instrument
metadata that the captured `WaveformData` does not carry directly, only via
its provenance snapshot.
"""

import logging
from typing import Dict, List, Optional

from scpi_control.report_generator.analysis.comparison_analyzer import evaluate_measurements
from scpi_control.report_generator.models.criteria import CriteriaSet
from scpi_control.report_generator.models.report_data import (
    MeasurementResult,
    ReportMetadata,
    TestReport,
    TestSection,
)
from scpi_control.report_generator.models.report_data import WaveformData as ReportWaveformData
from scpi_control.waveform import WaveformData as CapturedWaveformData

logger = logging.getLogger(__name__)


def _to_report_waveform(waveform: CapturedWaveformData) -> ReportWaveformData:
    """Convert a captured `scpi_control.waveform.WaveformData` into the
    report package's `WaveformData` subclass (see the type-conversion note
    in this module's docstring for why the two are not the same type).

    Copies the physical-capture fields already present on the source, plus
    `probe_ratio`/`coupling` recovered from `waveform.provenance.channels`
    (keyed by the ORIGINAL int channel number -- looked up here, before the
    report `WaveformData.__post_init__` stringifies `channel`). Provenance,
    or that channel's entry within it, may legitimately be absent (e.g. a
    capture made with `provenance=False`, or a snapshot that failed --
    `Waveform.acquire` logs a warning and returns provenance=None rather
    than raising, per its own docstring); this conversion is no stricter
    than that and simply leaves `probe_ratio`/`coupling` at their `None`
    defaults in that case.

    Remaining report-only fields (`label`, `statistics`, `signal_type`, ...)
    are left at their dataclass defaults for the caller to populate via
    `.analyze()`.
    """
    channel_settings = waveform.provenance.channels.get(waveform.channel) if waveform.provenance is not None else None

    return ReportWaveformData(
        time=waveform.time,
        voltage=waveform.voltage,
        channel=waveform.channel,
        sample_rate=waveform.sample_rate,
        record_length=waveform.record_length,
        timebase=waveform.timebase,
        voltage_scale=waveform.voltage_scale,
        voltage_offset=waveform.voltage_offset,
        provenance=waveform.provenance,
        probe_ratio=channel_settings.probe_ratio if channel_settings is not None else None,
        coupling=channel_settings.coupling if channel_settings is not None else None,
    )


def _build_single_run_report(
    waveforms: Dict[int, CapturedWaveformData],
    metadata: ReportMetadata,
    criteria_set: Optional[CriteriaSet] = None,
) -> TestReport:
    """Turn one capture (`capture_single`'s or a degenerate `batch_capture`'s
    return value -- see this module's docstring) into a `TestReport`.

    Mirrors `examples/report_generation_example.py`'s hand-built pattern --
    one `TestSection` per channel, `overall_result` computed at the end --
    but built from a real (or mock) capture rather than synthesized data.

    Args:
        waveforms: Channel number -> captured waveform, exactly the shape
            `DataCollector.capture_single()` returns (and a single
            `batch_capture()` result's `"waveforms"` entry matches).
        metadata: Report metadata (title, technician, test date, ...).
        criteria_set: Optional pass/fail criteria. None (the default) skips
            criteria evaluation entirely -- each waveform's `.statistics`
            is still populated, but no `MeasurementResult`s are produced
            and `overall_result` comes back "INCONCLUSIVE" (matching
            `TestReport.calculate_overall_result()`'s no-measurements case
            and `evaluate_measurements`'s `criteria_set=None` behavior).

    Returns:
        A `TestReport` with one section per channel (sorted by channel
        number for deterministic ordering) and `overall_result` set.
    """
    report = TestReport(metadata=metadata)

    report_waveforms: List[ReportWaveformData] = []
    for channel in sorted(waveforms):
        wf = _to_report_waveform(waveforms[channel])
        # wf.analyze() delegates to WaveformAnalyzer.analyze(wf) and stores
        # the result on wf.statistics/wf.signal_type -- this is the same
        # call ComparisonAnalyzer.analyze() makes on each loaded run's
        # waveforms (comparison_analyzer.py:94-95), and deliberately NOT
        # DataCollector.analyze_waveform(), a separate, weaker duplicate
        # this feature does not use (see the design doc's "Problem").
        wf.analyze()
        report_waveforms.append(wf)

    # evaluate_measurements is the shared helper extracted from
    # ComparisonAnalyzer._apply_criteria (Task 1) -- using it here, rather
    # than a second reimplementation, is what guarantees this single-run
    # path and the batch/comparison path apply criteria identically.
    criteria_warnings: List[str] = []
    measurements, _passed, _incomplete = evaluate_measurements(
        report_waveforms,
        criteria_set,
        criteria_warnings,
        label="Single-run capture",
    )
    for message in criteria_warnings:
        logger.warning(message)

    for order, wf in enumerate(report_waveforms, start=1):
        section_measurements: List[MeasurementResult] = [m for m in measurements if m.channel == wf.label]
        report.add_section(
            TestSection(
                title=f"Channel {wf.label}",
                waveforms=[wf],
                measurements=section_measurements,
                order=order,
            )
        )

    report.overall_result = report.calculate_overall_result()
    return report
