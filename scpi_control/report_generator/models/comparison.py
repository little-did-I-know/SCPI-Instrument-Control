"""Multi-run input model for comparison and batch reports.

A Run is a set of capture files plus per-run metadata; a RunSet is the ordered
collection the ComparisonAnalyzer consumes. Comparison mode measures deltas
against a baseline run; batch mode aggregates across runs (DUTs).
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from scpi_control.report_generator.models.criteria import CriteriaSet
from scpi_control.report_generator.models.report_data import MeasurementResult, WaveformData

MODE_COMPARISON = "comparison"  # deltas vs a baseline run (before/after = 2 runs)
MODE_BATCH = "batch"  # cross-DUT aggregates + yield


@dataclass
class RunMetadata:
    """Descriptive, optional context for one run."""

    dut_id: Optional[str] = None
    condition: Optional[str] = None
    operator: Optional[str] = None
    timestamp: Optional[datetime] = None
    notes: Optional[str] = None


@dataclass
class Run:
    """One test run: capture files in, analyzed waveforms/measurements out."""

    label: str
    files: List[Path]
    metadata: RunMetadata = field(default_factory=RunMetadata)

    # Populated by ComparisonAnalyzer.analyze:
    waveforms: List[WaveformData] = field(default_factory=list)
    measurements: List[MeasurementResult] = field(default_factory=list)
    passed: Optional[bool] = None  # None when no criteria applied
    incomplete: bool = False  # True when a critical criterion could not be evaluated
    load_errors: List[str] = field(default_factory=list)


@dataclass
class RunSet:
    """The full input to a comparison or batch analysis."""

    runs: List[Run]
    mode: str = MODE_COMPARISON
    baseline_index: int = 0  # comparison mode only
    criteria_set: Optional[CriteriaSet] = None

    def validate(self) -> None:
        """Raise ValueError on structural problems (before any file I/O)."""
        if len(self.runs) < 2:
            raise ValueError(f"A RunSet needs at least 2 runs, got {len(self.runs)}")
        labels = [run.label for run in self.runs]
        if len(set(labels)) != len(labels):
            raise ValueError(f"Run labels must be unique, got {labels}")
        if self.mode not in (MODE_COMPARISON, MODE_BATCH):
            raise ValueError(f"Unknown mode {self.mode!r}; use {MODE_COMPARISON!r} or {MODE_BATCH!r}")
        if not (0 <= self.baseline_index < len(self.runs)):
            raise ValueError(f"baseline_index {self.baseline_index} out of range for {len(self.runs)} runs")

    @property
    def baseline(self) -> Run:
        return self.runs[self.baseline_index]


@dataclass
class DeltaEntry:
    """One non-baseline run's value for one statistic, relative to baseline."""

    run_label: str
    value: Optional[float]
    delta: Optional[float]  # value - baseline_value
    pct: Optional[float]  # None when baseline value is 0 or a value is missing


@dataclass
class AggregateStats:
    """Cross-run aggregate of one statistic (batch mode)."""

    mean: float
    std: Optional[float]  # ddof=1; None for n < 2
    min: float
    max: float
    n: int


@dataclass
class ComparisonResult:
    """Everything the report builder needs, fully computed."""

    runset: RunSet
    matched_channels: List[str]
    # channel label -> stat name -> per-run delta entries (comparison mode)
    deltas: Dict[str, Dict[str, List[DeltaEntry]]] = field(default_factory=dict)
    # channel label -> stat name -> aggregate (batch mode)
    aggregates: Dict[str, Dict[str, AggregateStats]] = field(default_factory=dict)
    yield_passed: Optional[int] = None
    yield_total: Optional[int] = None
    yield_incomplete: Optional[int] = None
    warnings: List[str] = field(default_factory=list)
