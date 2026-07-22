"""Run-table model logic (headless) + dialog construction smoke test."""

from pathlib import Path

import pytest

from scpi_control.report_generator.comparison_dialog import ComparisonRunTableModel
from scpi_control.report_generator.models.criteria import CriteriaSet


def test_add_and_remove_runs():
    model = ComparisonRunTableModel()
    model.add_run("before", [Path("a.csv")], dut_id="DUT-1")
    model.add_run("after", [Path("b.csv")])
    assert [r.label for r in model.runs()] == ["before", "after"]
    assert model.runs()[0].metadata.dut_id == "DUT-1"
    model.remove_run(0)
    assert [r.label for r in model.runs()] == ["after"]


def test_validate_flags_problems():
    model = ComparisonRunTableModel()
    assert any("2 runs" in e for e in model.validate())
    model.add_run("a", [Path("a.csv")])
    model.add_run("a", [Path("b.csv")])
    assert any("unique" in e for e in model.validate())
    model.remove_run(1)
    model.add_run("b", [])
    assert any("file" in e.lower() for e in model.validate())


def test_valid_model_has_no_errors():
    model = ComparisonRunTableModel()
    model.add_run("a", [Path("a.csv")])
    model.add_run("b", [Path("b.csv")])
    assert model.validate() == []


def test_to_runset_carries_criteria_set():
    model = ComparisonRunTableModel()
    model.add_run("a", [Path("a.csv")])
    model.add_run("b", [Path("b.csv")])
    criteria_set = CriteriaSet(name="limits")
    runset = model.to_runset("comparison", baseline_index=0, criteria_set=criteria_set)
    assert runset.criteria_set is criteria_set


def test_comparison_dialog_construction():
    """ComparisonReportDialog can be constructed without a parent MainWindow crash."""
    import sys

    pytest.importorskip("PyQt6")
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    from scpi_control.report_generator.comparison_dialog import ComparisonReportDialog

    dialog = ComparisonReportDialog()
    assert dialog is not None
    assert hasattr(dialog, "model")
    dialog.close()
