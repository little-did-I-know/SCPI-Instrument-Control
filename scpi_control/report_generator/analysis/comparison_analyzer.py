# scpi_control/report_generator/analysis/comparison_analyzer.py
"""Loads and analyzes a RunSet into a ComparisonResult.

Strict by default: a bad file fails the whole analysis with the run and file
named. skip_bad_runs=True demotes that to a warning and drops the run, except
when fewer than two runs survive or the comparison baseline itself is lost.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

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
from scpi_control.report_generator.models.report_data import MeasurementResult
from scpi_control.report_generator.utils.waveform_loader import WaveformLoader

logger = logging.getLogger(__name__)

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
            ComparisonAnalyzer._apply_criteria(run, runset.criteria_set)

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
    def _apply_criteria(run: Run, criteria_set: Optional[CriteriaSet]) -> None:
        """Build run.measurements from criteria (matched by statistic key) and set run.passed."""
        run.measurements = []
        if criteria_set is None:
            run.passed = None
            return
        evaluated: List[bool] = []
        for wf in run.waveforms:
            stats = wf.statistics or {}
            for criteria in criteria_set.criteria_list:
                if criteria.channel is not None and criteria.channel != wf.label:
                    continue
                value = stats.get(criteria.measurement_name)
                if value is None:
                    continue
                outcome = criteria.validate(float(value))
                run.measurements.append(
                    MeasurementResult(
                        name=criteria.measurement_name,
                        value=float(value),
                        unit=STAT_UNITS.get(criteria.measurement_name, ""),
                        channel=wf.label,
                        passed=outcome.passed,
                        criteria_min=criteria.min_value,
                        criteria_max=criteria.max_value,
                    )
                )
                evaluated.append(outcome.passed)
        run.passed = all(evaluated) if evaluated else None

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
