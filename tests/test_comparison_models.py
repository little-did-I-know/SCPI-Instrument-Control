"""RunSet validation rules for comparison/batch reports."""

from pathlib import Path

import pytest

from scpi_control.report_generator.models.comparison import (
    MODE_BATCH,
    MODE_COMPARISON,
    Run,
    RunMetadata,
    RunSet,
)


def _runs(n=2):
    return [Run(label=f"run{i}", files=[Path(f"r{i}.csv")]) for i in range(n)]


def test_valid_runset_passes_validation():
    RunSet(runs=_runs(2), mode=MODE_COMPARISON).validate()
    RunSet(runs=_runs(3), mode=MODE_BATCH).validate()


def test_fewer_than_two_runs_rejected():
    with pytest.raises(ValueError, match="at least 2 runs"):
        RunSet(runs=_runs(1)).validate()


def test_duplicate_labels_rejected():
    runs = _runs(2)
    runs[1].label = "run0"
    with pytest.raises(ValueError, match="unique"):
        RunSet(runs=runs).validate()


def test_baseline_index_out_of_range_rejected():
    with pytest.raises(ValueError, match="baseline_index"):
        RunSet(runs=_runs(2), baseline_index=2).validate()


def test_unknown_mode_rejected():
    with pytest.raises(ValueError, match="mode"):
        RunSet(runs=_runs(2), mode="diff").validate()


def test_run_metadata_defaults_are_empty():
    run = Run(label="a", files=[])
    assert isinstance(run.metadata, RunMetadata)
    assert run.metadata.dut_id is None
    assert run.waveforms == [] and run.measurements == [] and run.passed is None
