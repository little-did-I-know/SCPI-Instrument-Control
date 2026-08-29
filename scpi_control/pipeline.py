"""Capture pipeline: connects live/mock oscilloscope capture (`DataCollector`)
to the report_generator's analysis and reporting stack.

Design: docs/superpowers/specs/2026-08-28-capture-pipeline-design.md
Plan:   docs/superpowers/plans/2026-08-28-capture-pipeline.md

This module closes a gap confirmed by research before this feature started:
`DataCollector` (capture) and `report_generator` (analysis + reporting) had
never been imported into each other anywhere in the codebase.

Task 2/3 status: both the single-run path (`_build_single_run_report`) and
the batch/comparison path (`_build_batch_report`) are implemented. The single
public entry point that routes between them by result count (Task 4) does
not exist yet -- everything here is intentionally internal (leading
underscore) until both paths exist and can share one public API.

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
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scpi_control.automation import DataCollector
from scpi_control.report_generator.analysis.comparison_analyzer import ComparisonAnalyzer, evaluate_measurements
from scpi_control.report_generator.comparison_report_builder import build_comparison_report
from scpi_control.report_generator.models.comparison import (
    MODE_BATCH,
    ComparisonResult,
    Run,
    RunMetadata,
    RunSet,
)
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


# --------------------------------------------------------------------------
# Task 3: batch/comparison capture-to-report path
# --------------------------------------------------------------------------
#
# `save_batch`'s return-value question (see the design doc's "Batch/comparison
# path" subsection and the plan's Task 3): does `DataCollector.save_batch`
# need to start RETURNING the paths it wrote, so this module can build
# `Run.files` from that return value instead of independently reconstructing
# `save_batch`'s filename convention (`capture_{i:04d}_ch{ch}_{config_str}_
# trig{trigger_num}.{ext}`, automation.py:652 at the time of writing) and
# risking drift from it?
#
# Decision: YES, changed `save_batch` to return `List[Dict[int, Path]]` (one
# dict per `batch_results` entry, channel -> saved Path; empty dict for an
# entry with no waveforms, e.g. a failed/"error" capture). This was a clean,
# small change -- one new local list, one append per channel already being
# saved, one `return` -- and it is backward compatible: `save_batch` returned
# `None` before, every existing call site (`examples/batch_capture.py`,
# `docs/examples/intermediate.md`, `tests/test_automation_save.py`) ignores
# the return value and is unaffected by a function that now returns something
# where it returned nothing. The alternative (reconstructing the filename
# convention here) would require this module to duplicate five moving parts
# --i.e. the index, `config_str`'s join/replace logic, `trigger_num`, `ch`,
# and the extension-selection rule -- any one of which drifting out of sync
# with `save_batch` would silently point `Run.files` at nonexistent paths.
# Preferring the return-value approach, per the design doc's stated
# preference, avoids that entirely.


def _build_batch_run(index: int, entry: Dict[str, Any], saved_files: Dict[int, Path]) -> Run:
    """Build one `Run` for one `batch_capture()` entry that was saved to disk.

    Label: `capture_{index:04d}`, matching `save_batch`'s own per-entry file
    numbering (`automation.py`'s `capture_{i:04d}_ch{ch}_..."` convention) so
    a Run's label and its saved filenames correlate directly -- useful for a
    human matching a report row back to a file on disk, and also what makes
    the equivalence test in `tests/test_pipeline.py` able to hand-build an
    identical `RunSet` using the exact same scheme.

    `RunMetadata`: `condition` and `notes` are derived from the entry's
    `"config"` (the batch_capture configuration dict -- timebase/voltage-scale
    overrides, empty for a plain multi-trigger batch) and `"trigger_num"`;
    `dut_id`/`operator` are left `None` -- `batch_capture()` output carries no
    per-DUT or per-operator identity to draw them from (unlike
    `examples/batch_report.py`'s synthetic DUTs, which invent one). A caller
    with real DUT identities should set `run.metadata.dut_id` after this
    function returns, or bypass it and hand-build `Run`s directly.
    """
    config = entry.get("config") or {}
    trigger_num = entry.get("trigger_num")

    condition = ", ".join(f"{k}={v}" for k, v in config.items()) or None
    notes = f"trigger {trigger_num}" if trigger_num is not None else None

    timestamp: Optional[datetime] = None
    raw_timestamp = entry.get("timestamp")
    if raw_timestamp:
        try:
            timestamp = datetime.fromisoformat(raw_timestamp)
        except ValueError:
            # Malformed/foreign timestamp string: leave it unset rather than
            # fail the whole run over a cosmetic metadata field.
            logger.warning(f"Batch entry {index}: could not parse timestamp {raw_timestamp!r}")

    files = [saved_files[ch] for ch in sorted(saved_files)]
    return Run(
        label=f"capture_{index:04d}",
        files=files,
        metadata=RunMetadata(condition=condition, notes=notes, timestamp=timestamp),
    )


def _build_batch_report(
    collector: DataCollector,
    batch_results: List[Dict[str, Any]],
    output_dir: str,
    metadata: ReportMetadata,
    *,
    mode: str = MODE_BATCH,
    criteria_set: Optional[CriteriaSet] = None,
    format: Optional[str] = None,
) -> Tuple[ComparisonResult, TestReport]:
    """Turn `batch_capture()`'s output (2+ results) into a comparison/batch
    report, auto-constructing `Run`/`RunSet` rather than requiring the caller
    to hand-build them (see this module's docstring and the design doc's
    "Batch/comparison path" subsection).

    Saves every entry via `collector.save_batch()` first -- `ComparisonAnalyzer`
    only accepts file-based `Run`s (`_load_run` calls `WaveformLoader.load`
    per `run.files` entry; there is no in-memory path), so writing to disk is
    a genuine prerequisite here, not an incidental step.

    Entries carrying an `"error"` key (a failed capture within the batch,
    see `DataCollector.batch_capture`) are SKIPPED -- not included as if they
    had succeeded, and not silently dropped either: each is logged as a
    warning naming its index and the capture error, and `save_batch` still
    writes whatever that entry's (empty) `"waveforms"` dict contains, i.e.
    nothing, so no stray file is created for it. `RunSet.validate()` (called
    below) then still enforces the >=2-runs structural minimum against
    whatever survives.

    Args:
        collector: The (connected) `DataCollector` that produced
            `batch_results` -- reused to call `save_batch`, which needs the
            instrument's `save_waveform` to serialize each channel.
        batch_results: `DataCollector.batch_capture()`'s return value, with
            2 or more entries (see this module's docstring for why exactly-1
            routes to `_build_single_run_report` instead).
        output_dir: Where `save_batch` writes the per-run capture files.
        metadata: Report metadata (title, technician, test date, ...).
        mode: `MODE_BATCH` (default, cross-run aggregates) or
            `MODE_COMPARISON` (deltas vs. `runset.baseline`, run index 0).
        criteria_set: Optional pass/fail criteria, applied identically to
            both this path and `_build_single_run_report` via the shared
            `evaluate_measurements` helper (Task 1) -- through
            `ComparisonAnalyzer.analyze` here, since that's the analyzer this
            path already uses, unmodified.
        format: Passed through to `save_batch` (file format override).

    Returns:
        `(result, report)`: the `ComparisonResult` (deltas/aggregates/yield,
        useful for direct programmatic inspection or an equivalence check
        against a hand-built `RunSet`) and the `TestReport` built from it via
        `build_comparison_report` -- both, since Task 4 has not yet finalized
        which one the public entry point returns and either is independently
        useful to test against now.

    Raises:
        ValueError: via `RunSet.validate()` -- fewer than 2 runs survived
            (e.g. too many `"error"` entries), or the RunSet is otherwise
            structurally invalid.
        ComparisonAnalysisError: via `ComparisonAnalyzer.analyze` -- e.g. a
            saved file could not be reloaded.
    """
    saved_files = collector.save_batch(batch_results, output_dir, format=format)

    runs: List[Run] = []
    for index, (entry, entry_files) in enumerate(zip(batch_results, saved_files)):
        if "error" in entry:
            logger.warning(f"Batch entry {index} excluded from the RunSet (capture failed): {entry['error']}")
            continue
        runs.append(_build_batch_run(index, entry, entry_files))

    runset = RunSet(runs=runs, mode=mode, criteria_set=criteria_set)
    runset.validate()

    result = ComparisonAnalyzer.analyze(runset)
    report = build_comparison_report(result, metadata)
    return result, report
