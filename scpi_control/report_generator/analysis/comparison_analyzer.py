# scpi_control/report_generator/analysis/comparison_analyzer.py
"""Loads and analyzes a RunSet into a ComparisonResult.

Strict by default: a bad file fails the whole analysis with the run and file
named. skip_bad_runs=True demotes that to a warning and drops the run, except
when fewer than two runs survive or the comparison baseline itself is lost.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from scpi_control.report_generator.models.comparison import (
    MODE_COMPARISON,
    AggregateStats,
    ComparisonResult,
    DeltaEntry,
    Run,
    RunSet,
)
from scpi_control.report_generator.models.criteria import CriteriaSet
from scpi_control.report_generator.models.report_data import MeasurementResult, WaveformData
from scpi_control.report_generator.utils.waveform_loader import WaveformLoader

logger = logging.getLogger(__name__)

# Display-name -> WaveformAnalyzer stat key, for names that don't normalize directly.
_CRITERIA_ALIASES: Dict[str, str] = {
    "peak_to_peak": "vpp",
    "peaktopeak": "vpp",
    "amplitude": "vamp",
}

# Units for MeasurementResult rows, keyed by WaveformAnalyzer statistic name.
STAT_UNITS: Dict[str, str] = {
    "vmax": "V",
    "vmin": "V",
    "vpp": "V",
    "vmean": "V",
    "vrms": "V",
    "vamp": "V",
    "dc_offset": "V",
    "noise_level": "V",
    "frequency": "Hz",
    "period": "s",
    "rise_time": "s",
    "fall_time": "s",
    "pulse_width": "s",
    "jitter": "s",
    "duty_cycle": "%",
    "overshoot": "%",
    "undershoot": "%",
    "thd": "%",
    "top_flatness": "%",
    "snr": "dB",
}


class ComparisonAnalysisError(Exception):
    """Analysis could not produce a usable result."""


class ComparisonAnalyzer:
    """Turns a RunSet into a fully computed ComparisonResult."""

    @staticmethod
    def analyze(runset: RunSet, *, skip_bad_runs: bool = False) -> ComparisonResult:
        runset.validate()
        warnings: List[str] = []
        baseline_label = runset.baseline.label

        surviving: List[Run] = []
        for run in runset.runs:
            error = ComparisonAnalyzer._load_run(run)
            if error is not None:
                if not skip_bad_runs:
                    raise ComparisonAnalysisError(error)
                run.load_errors.append(error)
                warnings.append(f"Run '{run.label}' skipped: {error}")
                continue
            surviving.append(run)

        if len(surviving) < 2:
            raise ComparisonAnalysisError(f"Need at least 2 usable runs, got {len(surviving)}")
        if runset.mode == MODE_COMPARISON and all(run.label != baseline_label for run in surviving):
            raise ComparisonAnalysisError(f"Baseline run '{baseline_label}' could not be loaded")

        runset.runs = surviving
        runset.baseline_index = next(i for i, run in enumerate(surviving) if run.label == baseline_label) if runset.mode == MODE_COMPARISON else 0

        for run in runset.runs:
            for wf in run.waveforms:
                wf.analyze()
            ComparisonAnalyzer._apply_criteria(run, runset.criteria_set, warnings)

        matched, match_warnings = ComparisonAnalyzer._match_channels(runset.runs)
        warnings.extend(match_warnings)

        result = ComparisonResult(runset=runset, matched_channels=matched, warnings=warnings)
        ComparisonAnalyzer._compute(result)
        return result

    @staticmethod
    def _load_run(run: Run) -> Optional[str]:
        """Load all files for a run; return an error message or None."""
        waveforms = []
        for filepath in run.files:
            try:
                waveforms.extend(WaveformLoader.load(Path(filepath)))
            except (FileNotFoundError, ValueError, OSError) as e:
                return f"Run '{run.label}': {filepath}: {e}"
        run.waveforms = waveforms
        return None

    @staticmethod
    def _resolve_stat_key(name: str, stats: Dict) -> Optional[str]:
        """Resolve a criterion's measurement_name to a stat key: exact, then
        normalized (lower + spaces/hyphens -> underscores), then an alias map."""
        if name in stats:
            return name
        norm = name.strip().lower().replace(" ", "_").replace("-", "_")
        if norm in stats:
            return norm
        alias = _CRITERIA_ALIASES.get(norm)
        if alias is not None and alias in stats:
            return alias
        return None

    @staticmethod
    def _apply_criteria(run: Run, criteria_set: Optional[CriteriaSet], warnings: List[str]) -> None:
        """Build run.measurements from criteria (resolved to stat keys) and set
        run.passed / run.incomplete. Thin wrapper around the standalone
        `evaluate_measurements` (below), which holds the actual logic so a future
        single-run pipeline path can reuse it without duplicating criteria
        evaluation. Only `critical` criteria gate the verdict; un-evaluable
        criteria are surfaced as warnings, never silently dropped."""
        run.measurements, run.passed, run.incomplete = evaluate_measurements(run.waveforms, criteria_set, warnings, label=f"Run '{run.label}'")

    @staticmethod
    def _match_channels(runs: List[Run]):
        """Channels (by waveform label) present in every run, insertion-ordered.

        Duplicate labels within a run: first occurrence wins, with a warning.
        Labels missing from any run are unmatched, with a warning."""
        warnings: List[str] = []
        per_run: List[Dict[str, object]] = []
        for run in runs:
            seen: Dict[str, object] = {}
            for wf in run.waveforms:
                if wf.label in seen:
                    warnings.append(f"Run '{run.label}': duplicate channel label '{wf.label}'; using the first")
                    continue
                seen[wf.label] = wf
            per_run.append(seen)

        first = per_run[0]
        matched = [label for label in first if all(label in seen for seen in per_run)]
        all_labels = []
        for seen in per_run:
            for label in seen:
                if label not in all_labels:
                    all_labels.append(label)
        for label in all_labels:
            if label not in matched:
                missing = [runs[i].label for i, seen in enumerate(per_run) if label not in seen]
                warnings.append(f"Channel '{label}' missing from runs {missing}; excluded from comparison")
        return matched, warnings

    @staticmethod
    def _waveform_for(run: Run, label: str):
        for wf in run.waveforms:
            if wf.label == label:
                return wf
        return None

    @staticmethod
    def _compute(result: ComparisonResult) -> None:
        """Fill deltas (comparison), aggregates (batch), and yield."""
        runset = result.runset
        for label in result.matched_channels:
            stats_per_run = []
            for run in runset.runs:
                wf = ComparisonAnalyzer._waveform_for(run, label)
                stats_per_run.append({k: v for k, v in (wf.statistics or {}).items() if isinstance(v, (int, float)) and not isinstance(v, bool)})
            shared = set(stats_per_run[0])
            for stats in stats_per_run[1:]:
                shared &= set(stats)
            shared_ordered = [k for k in stats_per_run[0] if k in shared]

            if runset.mode == MODE_COMPARISON:
                baseline_stats = stats_per_run[runset.baseline_index]
                result.deltas[label] = {}
                for stat in shared_ordered:
                    base = float(baseline_stats[stat])
                    entries = []
                    for i, run in enumerate(runset.runs):
                        if i == runset.baseline_index:
                            continue
                        value = float(stats_per_run[i][stat])
                        delta = value - base
                        pct = (100.0 * delta / base) if base != 0 else None
                        entries.append(DeltaEntry(run_label=run.label, value=value, delta=delta, pct=pct))
                    result.deltas[label][stat] = entries
            else:
                result.aggregates[label] = {}
                for stat in shared_ordered:
                    values = np.array([float(stats[stat]) for stats in stats_per_run], dtype=float)
                    result.aggregates[label][stat] = AggregateStats(
                        mean=float(values.mean()),
                        std=float(values.std(ddof=1)) if len(values) > 1 else None,
                        min=float(values.min()),
                        max=float(values.max()),
                        n=len(values),
                    )

        evaluated = [run for run in runset.runs if run.passed is not None]
        if evaluated:
            result.yield_passed = sum(1 for run in evaluated if run.passed)
            result.yield_total = len(evaluated)
        result.yield_incomplete = sum(1 for run in runset.runs if run.incomplete)


def evaluate_measurements(
    waveforms: List[WaveformData],
    criteria_set: Optional[CriteriaSet],
    warnings: List[str],
    *,
    label: str,
) -> Tuple[List[MeasurementResult], Optional[bool], bool]:
    """Turn waveforms' `.statistics` plus a `CriteriaSet` into `MeasurementResult`
    objects, and compute the resulting pass/fail verdict.

    This is the shared core of `ComparisonAnalyzer._apply_criteria`, extracted so
    a single-capture (non-comparison) reporting path can apply the exact same
    criteria-evaluation semantics without a second, divergent implementation.

    Only `critical`-severity criteria gate the verdict; `warning`/`info` criteria
    still produce `MeasurementResult`s but never flip `passed` or `incomplete`.
    A criterion that cannot be evaluated (missing/non-numeric statistic, or not
    fully specified e.g. no min/max set) is surfaced as an entry appended to the
    caller-supplied, mutable `warnings` list -- never silently dropped. If such a
    criterion is critical, the verdict becomes `incomplete` rather than a false
    PASS or FAIL.

    Args:
        waveforms: Waveforms to evaluate; each must already have `.statistics`
            populated (i.e. `.analyze()` already called).
        criteria_set: Criteria to apply, or None to skip evaluation entirely.
        warnings: Mutable list that un-evaluable-criterion messages are appended
            to, matching `ComparisonAnalyzer.analyze`'s shared-warnings-list
            pattern -- not returned, since the caller already holds the list.
        label: Identifies the source in warning text (e.g. "Run 'baseline'"),
            keyed-word argument so call sites read clearly at the call site.

    Returns:
        (measurements, passed, incomplete):
        - measurements: one `MeasurementResult` per criterion that could be
          resolved to a numeric statistic (regardless of severity).
        - passed: False if any critical criterion failed; None if no critical
          criteria were evaluated (including when criteria_set is None); True
          if at least one critical criterion was evaluated and none failed.
        - incomplete: True only when a critical criterion could not be
          evaluated and no critical criterion definitively failed.
    """
    measurements: List[MeasurementResult] = []
    if criteria_set is None:
        return measurements, None, False

    critical_pass: List[bool] = []
    critical_unevaluable = False
    for wf in waveforms:
        stats = wf.statistics or {}
        for criteria in criteria_set.criteria_list:
            if criteria.channel is not None and criteria.channel != wf.label:
                continue
            is_critical = (criteria.severity or "").lower() == "critical"
            key = ComparisonAnalyzer._resolve_stat_key(criteria.measurement_name, stats)
            value = stats.get(key) if key is not None else None
            if value is None or not isinstance(value, (int, float)) or isinstance(value, bool):
                warnings.append(f"{label}: criterion '{criteria.measurement_name}' on '{wf.label}' could not be evaluated (no numeric statistic)")
                if is_critical:
                    critical_unevaluable = True
                continue
            outcome = criteria.validate(float(value))
            measurements.append(
                MeasurementResult(
                    name=criteria.measurement_name,
                    value=float(value),
                    unit=STAT_UNITS.get(key, ""),
                    channel=wf.label,
                    passed=outcome.passed,
                    criteria_min=criteria.min_value,
                    criteria_max=criteria.max_value,
                )
            )
            if outcome.passed is None:
                warnings.append(f"{label}: criterion '{criteria.measurement_name}' on '{wf.label}' is not fully specified; not evaluated")
                if is_critical:
                    critical_unevaluable = True
            elif is_critical:
                critical_pass.append(outcome.passed)

    if any(p is False for p in critical_pass):
        return measurements, False, False
    if critical_unevaluable:
        return measurements, None, True
    if critical_pass:
        return measurements, True, False
    return measurements, None, False
