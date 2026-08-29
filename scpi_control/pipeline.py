"""Capture pipeline: connects live/mock oscilloscope capture (`DataCollector`)
to the report_generator's analysis and reporting stack.

Design: docs/superpowers/specs/2026-08-28-capture-pipeline-design.md
Plan:   docs/superpowers/plans/2026-08-28-capture-pipeline.md

This module closes a gap confirmed by research before this feature started:
`DataCollector` (capture) and `report_generator` (analysis + reporting) had
never been imported into each other anywhere in the codebase.

Task 2/3 status: both the single-run path (`_build_single_run_report`) and
the batch/comparison path (`_build_batch_report`) are implemented; they stay
internal (leading underscore) helpers.

Task 4 status: `run_capture_pipeline` is the single public entry point. It
captures via `batch_capture()` uniformly, routes to one of the two internal
paths above by result count (see the empirical finding below), generates the
requested report format(s) via the existing, unmodified generators, and
returns a `PipelineResult` bundling the `TestReport`, the `ComparisonResult`
(batch/comparison path only), and the generated file path(s).

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
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple

from scpi_control.automation import DataCollector
from scpi_control.report_generator.analysis.comparison_analyzer import ComparisonAnalyzer, evaluate_measurements
from scpi_control.report_generator.comparison_report_builder import build_comparison_report
from scpi_control.report_generator.generators.markdown_generator import MarkdownReportGenerator
from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator
from scpi_control.report_generator.models.comparison import (
    MODE_BATCH,
    MODE_COMPARISON,
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


class PipelineCaptureError(RuntimeError):
    """Raised when too few captures succeeded to produce a report (either the sole attempt on the single-run path, or a batch dropping below the RunSet minimum of 2 surviving runs)."""


def _entry_failed(entry: Dict[str, Any]) -> bool:
    """True when a `batch_capture()` entry represents a failed capture.

    Two distinct shapes both count: an explicit `"error"` key (a `SiglentError`
    caught by `batch_capture`'s breaker), AND an entry with no usable
    `"waveforms"` at all -- e.g. every requested channel was disabled, or
    every per-channel acquisition raised and was swallowed inside
    `capture_single` (see `automation.py`: `capture_single` logs and skips a
    disabled or failing channel rather than raising, so `batch_capture` can
    return `"waveforms": {}` with NO `"error"` key). Treating only the first
    shape as a failure let an empty-but-error-free capture silently pass
    through as if it were a real, if trivial, successful one."""
    return "error" in entry or not entry.get("waveforms")


def _entry_failure_reason(entry: Dict[str, Any]) -> str:
    """Human-readable reason `_entry_failed(entry)` is True.

    Prefers the real capture error text; falls back to a fixed explanation
    when the entry simply produced no waveforms (no `"error"` key to quote)."""
    if "error" in entry:
        return entry["error"]
    return "no channels returned waveform data"


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

    Entries that `_entry_failed` identifies as failed -- carrying an
    `"error"` key (a failed capture within the batch, see
    `DataCollector.batch_capture`), OR simply producing no waveforms at all
    with no `"error"` key (every requested channel was disabled or every
    per-channel acquisition raised and was swallowed inside
    `capture_single`) -- are SKIPPED: not included as if they had succeeded,
    and not silently dropped either. Each is logged as a warning naming its
    index and `_entry_failure_reason`, and `save_batch` still writes
    whatever that entry's (empty) `"waveforms"` dict contains, i.e. nothing,
    so no stray file is created for it. `RunSet.validate()` (called below)
    then still enforces the >=2-runs structural minimum against whatever
    survives.

    An excluded empty-waveforms entry matters beyond just that one entry: if
    it were included instead, `_build_batch_run` would build a `Run` with
    `files=[]` (nothing to save), which `ComparisonAnalyzer._load_run` treats
    as a successful load of zero waveforms -- and `_match_channels` computes
    the matched set by intersecting every run's channels, so ONE phantom
    empty run zeroes `matched_channels` (and therefore `deltas`/`aggregates`)
    for the WHOLE comparison, silently, with no warning or exception. This is
    the actual mechanism the `_entry_failed` exclusion below closes.

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
        PipelineCaptureError: raised directly by this function -- fewer than
            2 entries survived AND at least one exclusion was due to an
            `"error"` key -- naming the total entry count, how many failed,
            a sample of the actual capture-error text, and how many runs
            would have resulted. A `RuntimeError` subclass, so a caller can
            still catch it as `RuntimeError` if preferred.
        ValueError: via `RunSet.validate()` for any other structural
            problem (e.g. duplicate labels, or too few entries with none of
            them having failed) -- a genuinely different failure class from
            a capture failure, not renamed here.
        ComparisonAnalysisError: via `ComparisonAnalyzer.analyze` -- e.g. a
            saved file could not be reloaded.
    """
    saved_files = collector.save_batch(batch_results, output_dir, format=format)

    runs: List[Run] = []
    failures: List[str] = []
    for index, (entry, entry_files) in enumerate(zip(batch_results, saved_files)):
        if _entry_failed(entry):
            reason = _entry_failure_reason(entry)
            logger.warning(f"Batch entry {index} excluded from the RunSet (capture failed): {reason}")
            failures.append(reason)
            continue
        runs.append(_build_batch_run(index, entry, entry_files))

    # RunSet.validate() (below) would also catch this, but its message is a
    # generic "needs at least 2 runs, got N" with no link back to why runs
    # went missing -- and the reason (batch_capture() failures) lives only in
    # the warnings logged above, which a caller may not have visibility into
    # depending on logging configuration. Raise our own actionable error
    # first whenever failed entries are the (likely) cause, so it's the only
    # thing a caller needs to see.
    if len(runs) < 2 and failures:
        sample = "; ".join(failures[:2])
        raise PipelineCaptureError(
            f"Batch capture yielded too few successful runs to build a RunSet "
            f"(needs at least 2): {len(batch_results)} entries total, "
            f"{len(failures)} failed, {len(runs)} would survive. "
            f"Sample failure(s): {sample}"
        )

    runset = RunSet(runs=runs, mode=mode, criteria_set=criteria_set)
    runset.validate()

    result = ComparisonAnalyzer.analyze(runset)
    report = build_comparison_report(result, metadata)
    return result, report


# --------------------------------------------------------------------------
# Task 4: report generation wiring + the single public entry point
# --------------------------------------------------------------------------

#: `report_format` values accepted by `run_capture_pipeline`.
REPORT_FORMAT_MARKDOWN = "markdown"
REPORT_FORMAT_PDF = "pdf"
REPORT_FORMAT_BOTH = "both"
_VALID_REPORT_FORMATS = frozenset({REPORT_FORMAT_MARKDOWN, REPORT_FORMAT_PDF, REPORT_FORMAT_BOTH})

#: `mode` values accepted by `run_capture_pipeline` (meaningful only when the
#: batch/comparison path is taken -- see `_build_batch_report`).
_VALID_MODES = frozenset({MODE_BATCH, MODE_COMPARISON})

# Basename (no extension) for generated report files -- each generator's
# `get_file_extension()` supplies the extension. Fixed rather than derived
# from `metadata.title` so a rerun into the same `output_dir` predictably
# overwrites the previous report instead of accumulating slug variants.
_REPORT_BASENAME = "capture_pipeline_report"


class PipelineResult(NamedTuple):
    """What `run_capture_pipeline` hands back -- enough for both interactive
    use (the generated file path(s)) and programmatic use (the `TestReport`,
    and, for the batch/comparison path, the `ComparisonResult` too, so a
    caller can inspect `overall_result`/`yield_passed`/deltas without
    re-parsing a generated file). A `NamedTuple` rather than a bare tuple:
    `result.report.overall_result` reads unambiguously at a call site, where
    `result[1].overall_result` (or worse, `result[0]` for the single-run path
    but `result[1]` for batch, since a bare tuple's shape would otherwise
    have to vary by path) would not.

    Attributes:
        report: The `TestReport` built by whichever internal path handled
            this capture (`_build_single_run_report` or, via
            `_build_batch_report`, `build_comparison_report`).
        comparison: The `ComparisonResult` from the batch/comparison path
            (deltas, aggregates, yield). `None` for the single-run path --
            there is no `RunSet`/`ComparisonResult` to speak of when exactly
            one capture was made (see this module's docstring and the design
            doc's routing rationale).
        report_paths: Format name (`"markdown"`/`"pdf"`) -> the `Path`
            written for that format. Only formats that were both requested
            AND actually produced a file appear here -- a requested PDF that
            was skipped because `reportlab` is not installed is simply
            absent from this dict, not present with a `None`/placeholder
            value (see `run_capture_pipeline`'s docstring for that skip
            behavior).
    """

    report: TestReport
    comparison: Optional[ComparisonResult]
    report_paths: Dict[str, Path]


def run_capture_pipeline(
    collector: DataCollector,
    channels: List[int],
    output_dir: str,
    metadata: ReportMetadata,
    *,
    timebase_scales: Optional[List[str]] = None,
    voltage_scales: Optional[Dict[int, List[str]]] = None,
    triggers_per_config: int = 1,
    criteria_set: Optional[CriteriaSet] = None,
    report_format: str = REPORT_FORMAT_MARKDOWN,
    mode: str = MODE_BATCH,
    save_format: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    max_consecutive_failures: Optional[int] = 3,
) -> PipelineResult:
    """Capture, analyze, and report -- the single public entry point this
    module exists to provide (see the design doc's "Fix" section).

    Captures uniformly via `collector.batch_capture()` (per this module's
    docstring: with no `timebase_scales`/`voltage_scales` and the default
    `triggers_per_config=1`, that degenerates to exactly one capture, the
    same effective call `capture_single()` would make), then routes by
    result count -- the caller does not need to know or decide which path
    applies:

    - Exactly 1 result -> `_build_single_run_report` (no `RunSet` involved;
      `RunSet.validate()` requires at least 2 runs).
    - 2+ results -> `_build_batch_report` (auto-constructed `RunSet` ->
      `ComparisonAnalyzer.analyze` -> `build_comparison_report`).

    Args:
        collector: An already-connected `DataCollector` (constructed the
            same way every other example in this repo does, e.g.
            `DataCollector(host, connection=...)` then `.connect()`, or via
            its context manager). Not constructed here -- connection setup
            (mock vs. real instrument, host/port) is the caller's concern,
            not this pipeline's.
        channels: Channel numbers to capture, passed straight through to
            `batch_capture()`.
        output_dir: Directory for both the batch path's saved capture files
            (via `save_batch()`, unchanged) AND the generated report
            file(s) -- both generators' `generate(report, output_path)`
            need a concrete destination path, so the single-run path also
            writes here even though it saves no raw capture files. Created
            (with parents) if it does not already exist. Report filenames
            are fixed (`_REPORT_BASENAME`, no per-call uniquification), so
            reusing the same `output_dir` across two calls -- a single-run
            call followed by a batch call, or any two calls in general --
            silently overwrites the earlier call's report file; pass a
            distinct `output_dir` per call to keep both.
        metadata: Report metadata (title, technician, test date, ...).
        timebase_scales: Optional sweep, passed through to `batch_capture()`.
            Leaving this (and `voltage_scales`) unset is what naturally
            routes to the single-run path.
        voltage_scales: Optional sweep, passed through to `batch_capture()`.
        triggers_per_config: Passed through to `batch_capture()`. The
            default of 1 (with no scales swept) is what naturally routes to
            the single-run path; 2+ triggers (or any scale swept) produces
            2+ results and routes to the batch/comparison path instead.
        criteria_set: Optional pass/fail criteria, applied identically on
            both paths via the shared `evaluate_measurements` helper
            (Task 1) -- directly on the single-run path, and through
            `ComparisonAnalyzer.analyze` on the batch/comparison path.
            Leaving this `None` (the default) is not an error: no
            `MeasurementResult`s are produced and the report's
            `overall_result` comes back `"INCONCLUSIVE"` rather than
            `"PASS"`/`"FAIL"` (see `_build_single_run_report`'s docstring).
        report_format: One of `REPORT_FORMAT_MARKDOWN` ("markdown"),
            `REPORT_FORMAT_PDF` ("pdf"), or `REPORT_FORMAT_BOTH` ("both").
            A PDF request is skipped gracefully -- logged as a warning, no
            exception raised, no "pdf" key in the returned `report_paths` --
            when `reportlab` is not installed, matching this repo's
            optional-dependency convention elsewhere (e.g.
            `examples/report_generation_example.py`'s own try/except
            ImportError around `PDFReportGenerator`).
        mode: `MODE_BATCH` (default, cross-run aggregates) or
            `MODE_COMPARISON` (deltas vs. a baseline run, index 0) --
            meaningful only when the batch/comparison path is taken (2+
            results); ignored on the single-run path.
        save_format: Passed through to `_build_batch_report` ->
            `collector.save_batch()` (file format override for saved
            captures); ignored on the single-run path, which saves no raw
            capture files.
        progress_callback: Passed through to `batch_capture()`.
        max_consecutive_failures: Passed through to `batch_capture()`.

    Returns:
        A `PipelineResult` -- see its own docstring for field details.

    Raises:
        ValueError: `report_format` or `mode` is not one of the accepted
            values.
        PipelineCaptureError: too few successful captures to produce a
            report -- either exactly one capture was attempted and it
            failed (an `"error"` entry from `batch_capture()`, OR an entry
            with no `"error"` key but no usable waveforms either -- see
            `_entry_failed` -- raised here rather than silently building a
            zero-section `TestReport` from an empty waveform dict, which
            would be a report that looks like a real (if trivial) pass/fail
            result but actually reflects no successful capture at all), or,
            on the batch/comparison path,
            too few runs survived capture errors to form a `RunSet` (see
            `_build_batch_report`). A `RuntimeError` subclass, so a single
            `except PipelineCaptureError:` (or `except RuntimeError:`)
            catches both cases.
        ComparisonAnalysisError: via `ComparisonAnalyzer.analyze`, on the
            batch/comparison path.
    """
    if report_format not in _VALID_REPORT_FORMATS:
        raise ValueError(f"report_format must be one of {sorted(_VALID_REPORT_FORMATS)}, got {report_format!r}")
    if mode not in _VALID_MODES:
        raise ValueError(f"mode must be one of {sorted(_VALID_MODES)}, got {mode!r}")

    batch_results = collector.batch_capture(
        channels,
        timebase_scales=timebase_scales,
        voltage_scales=voltage_scales,
        triggers_per_config=triggers_per_config,
        progress_callback=progress_callback,
        max_consecutive_failures=max_consecutive_failures,
    )

    comparison: Optional[ComparisonResult] = None
    if len(batch_results) == 1:
        entry = batch_results[0]
        if _entry_failed(entry):
            raise PipelineCaptureError(f"Capture failed, no report can be built: {_entry_failure_reason(entry)}")
        report = _build_single_run_report(entry["waveforms"], metadata, criteria_set=criteria_set)
    else:
        comparison, report = _build_batch_report(
            collector,
            batch_results,
            output_dir,
            metadata,
            mode=mode,
            criteria_set=criteria_set,
            format=save_format,
        )

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    report_paths: Dict[str, Path] = {}
    if report_format in (REPORT_FORMAT_MARKDOWN, REPORT_FORMAT_BOTH):
        md_path = output_path / f"{_REPORT_BASENAME}{MarkdownReportGenerator().get_file_extension()}"
        if MarkdownReportGenerator().generate(report, md_path):
            report_paths[REPORT_FORMAT_MARKDOWN] = md_path
        else:
            # generate() returns False for an environmental I/O failure OR a
            # failed self.validate_report(report) check (see its own
            # docstring/body) -- a programming error propagates instead.
            # Logged, not raised: a Markdown failure should not prevent a
            # PDF that was also requested from still being tried.
            logger.error(f"Markdown report generation failed writing to {md_path}; no file produced")

    if report_format in (REPORT_FORMAT_PDF, REPORT_FORMAT_BOTH):
        try:
            pdf_generator = PDFReportGenerator()
        except ImportError:
            logger.warning("Skipping PDF report generation: reportlab is not installed. Install with: pip install reportlab")
        else:
            pdf_path = output_path / f"{_REPORT_BASENAME}{pdf_generator.get_file_extension()}"
            if pdf_generator.generate(report, pdf_path):
                report_paths[REPORT_FORMAT_PDF] = pdf_path
            else:
                logger.error(f"PDF report generation failed writing to {pdf_path}; no file produced")

    return PipelineResult(report=report, comparison=comparison, report_paths=report_paths)
