"""Report generation: markdown content and a PDF smoke test.

A characterisation floor for paths believed to work -- these are the only
generator tests in a 0%-covered subsystem, so a failure here is a real find.
"""

from datetime import datetime

import numpy as np
import pytest

from scpi_control.report_generator.models.report_data import (
    ReportMetadata,
    TestReport,
    TestSection,
    WaveformData,
)


def make_report():
    """A minimal but complete TestReport, including one waveform."""
    t = np.arange(100) / 1e6
    waveform = WaveformData(
        channel_name="C1",
        time_data=t,
        voltage_data=np.sin(2 * np.pi * 10_000 * t),
        sample_rate=1e6,
        record_length=100,
    )
    section = TestSection(title="Rise Time", content="Measured on C1.", waveforms=[waveform])
    metadata = ReportMetadata(title="Bench Check", technician="robin", test_date=datetime(2026, 7, 16))
    return TestReport(metadata=metadata, sections=[section])


def test_markdown_generation_contains_the_report_content(tmp_path):
    from scpi_control.report_generator.generators.markdown_generator import MarkdownReportGenerator

    out = tmp_path / "r.md"
    assert MarkdownReportGenerator().generate(make_report(), out) is True

    text = out.read_text(encoding="utf-8")
    assert "Bench Check" in text
    assert "Rise Time" in text


def test_pdf_generation_produces_a_real_pdf(tmp_path):
    pytest.importorskip("reportlab")
    from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator

    out = tmp_path / "r.pdf"
    assert PDFReportGenerator().generate(make_report(), out) is True

    assert out.stat().st_size > 0
    with open(out, "rb") as f:
        assert f.read(4) == b"%PDF"  # salvaged from the root-level test_pdf_generation.py


def test_pymupdf_is_available_for_the_preview_dialog():
    """PDF preview imports fitz (widgets/pdf_preview_dialog.py:17); without it
    declared, a clean `pip install .[report-generator]` leaves the feature dead."""
    pytest.importorskip("fitz")
