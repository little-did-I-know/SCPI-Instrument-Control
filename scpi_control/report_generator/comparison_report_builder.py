"""Builds TestReports from analyzed RunSets, plus the manifest/sign-off helpers
shared with the single-run report path."""

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from scpi_control.report_generator.analysis.comparison_analyzer import STAT_UNITS
from scpi_control.report_generator.models.comparison import MODE_COMPARISON, ComparisonResult, Run, RunSet
from scpi_control.report_generator.models.report_data import SUMMARY_SOURCE_COMPUTED, ReportMetadata, TestReport, TestSection
from scpi_control.report_generator.models.report_elements import (
    STATUS_FAIL,
    STATUS_PASS,
    ComparisonTable,
    DataManifest,
    ManifestEntry,
    OverlayPlotSpec,
    OverlayTrace,
    SignoffBlock,
    SignoffRole,
    TableCell,
)
from scpi_control.report_generator.models.template import ReportTemplate
from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer

logger = logging.getLogger(__name__)

DEFAULT_SIGNOFF_ROLES = ["Tested by", "Reviewed by", "Approved by"]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _instrument_string(provenance) -> Optional[str]:
    """'Manufacturer Model (Serial)' from an AcquisitionProvenance, or None."""
    if provenance is None or provenance.instrument is None:
        return None
    info = provenance.instrument
    parts = [p for p in (info.manufacturer, info.model) if p]
    if not parts and not info.serial:
        return None
    text = " ".join(parts) if parts else "Unknown instrument"
    if info.serial:
        text += f" ({info.serial})"
    return text


def build_manifest(runs: List[Run]) -> DataManifest:
    """One entry per source file per run. Timestamp: provenance acquired_at,
    else waveform capture_timestamp, else file mtime (ISO, UTC)."""
    entries: List[ManifestEntry] = []
    for run in runs:
        by_source: Dict[str, object] = {}
        for wf in run.waveforms:
            if wf.source_file is not None:
                by_source.setdefault(str(wf.source_file), wf)
        for filepath in run.files:
            path = Path(filepath)
            wf = by_source.get(str(path))
            provenance = getattr(wf, "provenance", None) if wf is not None else None
            timestamp = None
            if provenance is not None and provenance.acquired_at:
                timestamp = provenance.acquired_at
            elif wf is not None and getattr(wf, "capture_timestamp", None):
                timestamp = wf.capture_timestamp.isoformat()
            elif path.exists():
                timestamp = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
            entries.append(
                ManifestEntry(
                    run_label=run.label,
                    file_path=str(path),
                    size_bytes=path.stat().st_size if path.exists() else 0,
                    sha256=_sha256(path) if path.exists() else "",
                    capture_timestamp=timestamp,
                    instrument=_instrument_string(provenance),
                )
            )
    return DataManifest(entries=entries)


def build_signoff(roles: List[str], names: Optional[Dict[str, str]] = None) -> SignoffBlock:
    names = names or {}
    return SignoffBlock(roles=[SignoffRole(title=title, name=names.get(title)) for title in roles])


_RUN_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"]

# Shown when no criteria constrain the batch table (filtered to computed stats).
_DEFAULT_KEY_STATS = ["vpp", "vmean", "frequency"]


def _fmt(stat: str, value: Optional[float]) -> str:
    return WaveformAnalyzer.format_stat_value(stat, value) if value is not None else "—"


def _run_color(index: int) -> str:
    return _RUN_COLORS[index % len(_RUN_COLORS)]


def _status(passed: Optional[bool]) -> Optional[str]:
    if passed is None:
        return None
    return STATUS_PASS if passed else STATUS_FAIL


def _overview_section(result: ComparisonResult) -> TestSection:
    runset = result.runset
    section = TestSection(title="Overview", order=0)
    headers = ["Run", "DUT ID", "Condition", "Files", "Result"]
    rows = []
    for i, run in enumerate(runset.runs):
        label = run.label + (" (baseline)" if runset.mode == MODE_COMPARISON and i == runset.baseline_index else "")
        verdict = "PASS" if run.passed else "FAIL" if run.passed is False else "—"
        rows.append([TableCell(label), TableCell(run.metadata.dut_id or "—"), TableCell(run.metadata.condition or "—"), TableCell(str(len(run.files))), TableCell(verdict, status=_status(run.passed))])
    section.comparison_table = ComparisonTable(title="Runs", headers=headers, rows=rows)
    if result.warnings:
        section.content = "Warnings:\n" + "\n".join(f"- {w}" for w in result.warnings)
    return section


def _overlay_section(result: ComparisonResult) -> TestSection:
    section = TestSection(title="Waveform Overlays", order=1)
    for label in result.matched_channels:
        traces = []
        for i, run in enumerate(result.runset.runs):
            for wf in run.waveforms:
                if wf.label == label:
                    traces.append(OverlayTrace(run_label=run.label, waveform=wf, color=_run_color(i)))
                    break
        section.overlay_plots.append(OverlayPlotSpec(channel_label=label, traces=traces))
    return section


def _comparison_section(result: ComparisonResult) -> TestSection:
    """Rows = 'stat (channel)'; columns = baseline value then value/Δ/Δ% per other run."""
    runset = result.runset
    baseline = runset.baseline
    section = TestSection(title="Comparison Results", order=2)
    others = [run for i, run in enumerate(runset.runs) if i != runset.baseline_index]
    headers = ["Measurement", f"{baseline.label} (baseline)"]
    for run in others:
        headers.extend([run.label, f"Δ vs {baseline.label}", "Δ%"])
    rows = []
    for channel in result.matched_channels:
        baseline_wf = next(wf for wf in baseline.waveforms if wf.label == channel)
        for stat, entries in result.deltas.get(channel, {}).items():
            name = f"{stat} ({channel})" if len(result.matched_channels) > 1 else stat
            row = [TableCell(name), TableCell(_fmt(stat, (baseline_wf.statistics or {}).get(stat)))]
            by_label = {e.run_label: e for e in entries}
            for run in others:
                entry = by_label.get(run.label)
                if entry is None:
                    row.extend([TableCell("—"), TableCell("—"), TableCell("—")])
                    continue
                sign = "+" if (entry.delta or 0) >= 0 else ""
                row.append(TableCell(_fmt(stat, entry.value)))
                row.append(TableCell(f"{sign}{_fmt(stat, entry.delta)}" if entry.delta is not None else "—"))
                row.append(TableCell(f"{sign}{entry.pct:.1f}%" if entry.pct is not None else "—"))
            rows.append(row)
    section.comparison_table = ComparisonTable(title="Measurements vs baseline", headers=headers, rows=rows)
    return section


def _key_stats(runset: RunSet, result: ComparisonResult) -> List[str]:
    if runset.criteria_set is not None and runset.criteria_set.criteria_list:
        return [c.measurement_name for c in runset.criteria_set.criteria_list]
    computed = set()
    for channel_stats in result.aggregates.values():
        computed.update(channel_stats)
    return [s for s in _DEFAULT_KEY_STATS if s in computed]


def _batch_section(result: ComparisonResult) -> TestSection:
    runset = result.runset
    section = TestSection(title="Batch Summary", order=2)
    stats = _key_stats(runset, result)
    channels = result.matched_channels

    def col_name(stat, channel):
        return f"{stat} ({channel})" if len(channels) > 1 else stat

    headers = ["Run", "DUT ID", "Result"] + [col_name(s, c) for c in channels for s in stats]
    rows = []
    for run in runset.runs:
        verdict = "PASS" if run.passed else "FAIL" if run.passed is False else "—"
        row = [TableCell(run.label), TableCell(run.metadata.dut_id or "—"), TableCell(verdict, status=_status(run.passed))]
        for channel in channels:
            wf = next((w for w in run.waveforms if w.label == channel), None)
            for stat in stats:
                value = (wf.statistics or {}).get(stat) if wf is not None else None
                row.append(TableCell(_fmt(stat, value)))
        rows.append(row)
    section.comparison_table = ComparisonTable(title="Per-DUT results", headers=headers, rows=rows)

    agg_headers = ["Measurement", "Mean", "Std", "Min", "Max", "n"]
    agg_rows = []
    for channel in channels:
        for stat, agg in result.aggregates.get(channel, {}).items():
            if stat not in stats:
                continue
            agg_rows.append(
                [
                    TableCell(col_name(stat, channel)),
                    TableCell(_fmt(stat, agg.mean)),
                    TableCell(_fmt(stat, agg.std) if agg.std is not None else "—"),
                    TableCell(_fmt(stat, agg.min)),
                    TableCell(_fmt(stat, agg.max)),
                    TableCell(str(agg.n)),
                ]
            )
    aggregates_section = TestSection(title="Batch Aggregates", order=3)
    aggregates_section.comparison_table = ComparisonTable(title="Across-run statistics", headers=agg_headers, rows=agg_rows)
    return section, aggregates_section


def _full_stats_table(result: ComparisonResult) -> ComparisonTable:
    """Appendix: every shared numeric statistic, per matched channel, per run."""
    runset = result.runset
    headers = ["Measurement"] + [run.label for run in runset.runs]
    rows = []
    for channel in result.matched_channels:
        stat_source = result.deltas.get(channel) or result.aggregates.get(channel) or {}
        for stat in stat_source:
            name = f"{stat} ({channel})" if len(result.matched_channels) > 1 else stat
            row = [TableCell(name)]
            for run in runset.runs:
                wf = next((w for w in run.waveforms if w.label == channel), None)
                row.append(TableCell(_fmt(stat, (wf.statistics or {}).get(stat) if wf is not None else None)))
            rows.append(row)
    return ComparisonTable(title="Per-run statistics", headers=headers, rows=rows)


def _executive_summary(result: ComparisonResult) -> str:
    runset = result.runset
    if runset.mode == MODE_COMPARISON:
        parts = [f"Compared {len(runset.runs)} runs against baseline '{runset.baseline.label}'."]
        largest = None
        for channel, stats in result.deltas.items():
            for stat, entries in stats.items():
                for e in entries:
                    if e.pct is not None and (largest is None or abs(e.pct) > abs(largest[3])):
                        largest = (channel, stat, e.run_label, e.pct)
        if largest is not None:
            channel, stat, run_label, pct = largest
            parts.append(f"Largest relative change: {stat} on channel {channel}, {pct:+.1f}% in '{run_label}'.")
    else:
        parts = [f"Batch of {len(runset.runs)} runs."]
        if result.yield_total:
            parts.append(f"Yield: {result.yield_passed}/{result.yield_total} passed ({100.0 * result.yield_passed / result.yield_total:.0f}%).")
    if result.warnings:
        parts.append(f"{len(result.warnings)} warning(s) — see Overview.")
    return " ".join(parts)


def build_comparison_report(
    result: ComparisonResult,
    metadata: ReportMetadata,
    template: Optional[ReportTemplate] = None,
    *,
    include_appendix: Optional[bool] = None,
    include_signoff: Optional[bool] = None,
) -> TestReport:
    """Assemble a standard TestReport from an analyzed RunSet.

    Explicit kwargs win; otherwise template settings; with neither, both the
    appendix and sign-off are included (comparison reports exist for
    traceability)."""
    runset = result.runset
    if include_appendix is None:
        include_appendix = template.include_raw_data_appendix if template is not None else True
    if include_signoff is None:
        include_signoff = template.include_signoff if template is not None else True

    report = TestReport(metadata=metadata)
    report.add_section(_overview_section(result))
    report.add_section(_overlay_section(result))
    if runset.mode == MODE_COMPARISON:
        report.add_section(_comparison_section(result))
    else:
        batch, aggregates = _batch_section(result)
        report.add_section(batch)
        report.add_section(aggregates)

    next_order = len(report.sections)
    if include_appendix:
        appendix = TestSection(title="Raw Data Appendix", order=next_order)
        appendix.manifest = build_manifest(runset.runs)
        appendix.comparison_table = _full_stats_table(result)
        for run in runset.runs:
            appendix.measurements.extend(run.measurements)
        report.add_section(appendix)
        next_order += 1
    if include_signoff:
        roles = template.signoff_roles if template is not None else list(DEFAULT_SIGNOFF_ROLES)
        names = template.signoff_names if template is not None else None
        signoff_section = TestSection(title="Sign-Off", order=next_order)
        signoff_section.signoff = build_signoff(roles, names)
        report.add_section(signoff_section)

    report.executive_summary = _executive_summary(result)
    report.summary_source = SUMMARY_SOURCE_COMPUTED
    evaluated = [run.passed for run in runset.runs if run.passed is not None]
    report.overall_result = "FAIL" if False in evaluated else ("PASS" if evaluated else "INCONCLUSIVE")
    return report


def append_signoff_and_appendix(report: TestReport, template: ReportTemplate) -> None:
    """Single-run path: honor the template's appendix/sign-off flags on an
    already-built report. Manifest is derived from section waveforms."""
    next_order = max((s.order for s in report.sections), default=-1) + 1
    if template.include_raw_data_appendix:
        pseudo = Run(label=report.metadata.title, files=[])
        for section in report.sections:
            for wf in section.waveforms:
                if wf.source_file is not None:
                    pseudo.files.append(Path(wf.source_file))
                    pseudo.waveforms.append(wf)
        appendix = TestSection(title="Raw Data Appendix", order=next_order)
        appendix.manifest = build_manifest([pseudo])
        report.add_section(appendix)
        next_order += 1
    if template.include_signoff:
        signoff_section = TestSection(title="Sign-Off", order=next_order)
        signoff_section.signoff = build_signoff(template.signoff_roles, template.signoff_names)
        report.add_section(signoff_section)
