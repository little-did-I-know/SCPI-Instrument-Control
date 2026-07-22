"""PDF generator renders the comparison/batch elements without error."""

from datetime import datetime

import numpy as np
import pytest

reportlab = pytest.importorskip("reportlab")

from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator
from scpi_control.report_generator.models.report_data import ReportMetadata, TestReport, TestSection, WaveformData
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


def _wf(label):
    t = np.linspace(0, 1e-3, 200)
    return WaveformData(channel=label, time=t, voltage=np.sin(2 * np.pi * 1000 * t), sample_rate=200_000.0, record_length=200)


def _full_section():
    section = TestSection(title="Everything")
    section.comparison_table = ComparisonTable(title="T", headers=["M", "a", "b"], rows=[[TableCell("vpp"), TableCell("2 V", status=STATUS_PASS), TableCell("3 V", status=STATUS_FAIL)]])
    section.overlay_plots = [OverlayPlotSpec(channel_label="1", traces=[OverlayTrace("before", _wf("1"), "#1f77b4"), OverlayTrace("after", _wf("1"), "#ff7f0e")])]
    section.manifest = DataManifest(entries=[ManifestEntry(run_label="r", file_path="a.csv", size_bytes=1, sha256="ab" * 32)])
    section.signoff = SignoffBlock(roles=[SignoffRole(title="Tested by", name="Robin"), SignoffRole(title="Approved by")])
    return section


def test_pdf_generates_with_all_new_elements(tmp_path):
    report = TestReport(metadata=ReportMetadata(title="T", technician="R", test_date=datetime(2026, 7, 22)), sections=[_full_section()])
    out = tmp_path / "report.pdf"
    assert PDFReportGenerator().generate(report, out)
    assert out.exists() and out.stat().st_size > 2_000


def test_pdf_generates_without_new_elements_unchanged(tmp_path):
    report = TestReport(metadata=ReportMetadata(title="T", technician="R", test_date=datetime(2026, 7, 22)), sections=[TestSection(title="Plain", content="hello")])
    out = tmp_path / "plain.pdf"
    assert PDFReportGenerator().generate(report, out)
    assert out.exists()


def test_signoff_role_with_xml_special_chars_generates_successfully(tmp_path):
    """Sign-off role title/name containing XML-special characters must be
    escaped, not raw-interpolated into Paragraph markup."""
    section = TestSection(title="Sign-Off")
    section.signoff = SignoffBlock(roles=[SignoffRole(title="R&D Approver <QA>", name="A & B")])
    report = TestReport(metadata=ReportMetadata(title="T", technician="R", test_date=datetime(2026, 7, 22)), sections=[section])
    out = tmp_path / "signoff.pdf"
    assert PDFReportGenerator().generate(report, out)
    assert out.exists() and out.stat().st_size > 0


def test_comparison_table_element_method_exists_and_returns_table():
    from reportlab.platypus import Table as RLTable

    gen = PDFReportGenerator()
    table = gen._generate_comparison_table_element(ComparisonTable(title="T", headers=["M", "v"], rows=[[TableCell("vpp"), TableCell("2 V", status=STATUS_FAIL)]]))
    assert isinstance(table, RLTable)
