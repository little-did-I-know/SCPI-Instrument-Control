"""Every PDF page gets a footer with a page number; pages 2+ get a running header.

Needs reportlab + svglib + fitz (the report-generator extra) -- runs locally,
skips in CI, like tests/test_report_generators.py.
"""

from datetime import datetime

import numpy as np
import pytest

pytest.importorskip("reportlab")
pytest.importorskip("svglib")
fitz = pytest.importorskip("fitz")

from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator  # noqa: E402
from scpi_control.report_generator.models.report_data import (  # noqa: E402
    ReportMetadata,
    TestReport,
    TestSection,
    WaveformData,
)

RUN_HDR = "RUNNINGHEADERXYZ"
FOOT = "CONFIDENTIALFOOTERXYZ"


def make_waveforms(n):
    t = np.arange(200) / 1e6
    return [WaveformData(channel=f"C{i}", time=t, voltage=np.sin(2 * np.pi * 10_000 * t), sample_rate=1e6, record_length=200, label=f"Capture {i}") for i in range(n)]


def make_report(n_waveforms=10, header_text=RUN_HDR, footer_text=FOOT):
    md = ReportMetadata(title="Bench Check", technician="robin", test_date=datetime(2026, 7, 17), header_text=header_text, footer_text=footer_text)
    return TestReport(metadata=md, sections=[TestSection(title="Captures", waveforms=make_waveforms(n_waveforms))])


def test_every_page_has_a_page_number_and_footer_text(tmp_path):
    out = tmp_path / "r.pdf"
    assert PDFReportGenerator().generate(make_report(), str(out)) is True
    doc = fitz.open(out)
    try:
        assert doc.page_count >= 2  # enough waveforms to span pages
        total = doc.page_count
        for i in range(total):
            text = doc[i].get_text()
            assert f"Page {i + 1} of {total}" in text  # footer page number on every page
            assert FOOT in text  # footer_text on every page
    finally:
        doc.close()


def test_running_header_is_on_pages_two_plus_only(tmp_path):
    """header_text is drawn ONLY in the running header, so it is the clean
    discriminator: absent on page 1 (which has the big title block instead),
    present on pages 2+."""
    out = tmp_path / "r.pdf"
    assert PDFReportGenerator().generate(make_report(), str(out)) is True
    doc = fitz.open(out)
    try:
        assert RUN_HDR not in doc[0].get_text()
        assert RUN_HDR in doc[1].get_text()
    finally:
        doc.close()


def test_report_without_header_footer_text_still_builds_with_page_numbers(tmp_path):
    out = tmp_path / "r.pdf"
    report = make_report(n_waveforms=1, header_text=None, footer_text=None)
    assert PDFReportGenerator().generate(report, str(out)) is True
    doc = fitz.open(out)
    try:
        assert "Page 1 of" in doc[0].get_text()  # page number always renders
    finally:
        doc.close()


def test_a_multi_section_report_builds_to_a_valid_multipage_pdf(tmp_path):
    """Integration: sections with CondPageBreaks between them still compile to a
    valid multi-page PDF. (The anti-stranding EFFECT is layout-dependent and is
    verified manually; this pins that the CondPageBreaks don't break the build.)"""
    t = np.arange(200) / 1e6
    sections = [
        TestSection(title=f"Section {i}", content=f"Body {i}.", waveforms=[WaveformData(channel="C1", time=t, voltage=np.sin(2 * np.pi * 10_000 * t), sample_rate=1e6, record_length=200, label="C1")])
        for i in range(6)
    ]
    report = TestReport(metadata=ReportMetadata(title="Bench", technician="robin", test_date=datetime(2026, 7, 17)), sections=sections)
    out = tmp_path / "multi.pdf"
    assert PDFReportGenerator().generate(report, str(out)) is True
    doc = fitz.open(out)
    try:
        assert doc.page_count >= 2
        # each section heading appears in the rendered text
        text = "".join(doc[i].get_text() for i in range(doc.page_count))
        for i in range(6):
            assert f"Section {i}" in text
    finally:
        doc.close()
