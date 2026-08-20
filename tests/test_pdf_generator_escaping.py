"""ReportLab's Paragraph() parses its text argument as XML mini-markup.
~40 call sites in pdf_generator.py pass report/metadata text to it; before
this fix, most were unescaped -- a channel label or comparison-run title
containing '<', '>' or '&' could corrupt the parse or silently truncate
content (AUDIT.md H25).
"""

from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("reportlab")

from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator  # noqa: E402
from scpi_control.report_generator.models.report_data import (  # noqa: E402
    ReportMetadata,
    TestReport,
    TestSection,
    WaveformData,
)


def make_report(**metadata_overrides):
    t = np.arange(100) / 1e6
    waveform = WaveformData(
        channel="C1",
        time=t,
        voltage=np.sin(2 * np.pi * 10_000 * t),
        sample_rate=1e6,
        record_length=100,
    )
    section = TestSection(title="Rise Time", content="Measured on C1.", waveforms=[waveform])
    metadata_kwargs = dict(title="Bench Check", technician="robin", test_date=datetime(2026, 7, 16))
    metadata_kwargs.update(metadata_overrides)
    metadata = ReportMetadata(**metadata_kwargs)
    return TestReport(metadata=metadata, sections=[section])


def test_para_markdown_mode_escapes_xml_specials():
    gen = PDFReportGenerator()
    para = gen._para("A & B < C > D", gen.styles["Normal"], mode="markdown")
    assert "&amp;" in para.text
    assert "&lt;" in para.text
    assert "&gt;" in para.text
    assert "<" not in para.text.replace("&lt;", "")


def test_para_literal_mode_escapes_and_does_not_interpret_markdown():
    gen = PDFReportGenerator()
    para = gen._para("**bold** & <tag>", gen.styles["Normal"], mode="literal")
    assert "<b>" not in para.text  # literal mode does not apply markdown
    assert "&amp;" in para.text
    assert "&lt;tag&gt;" in para.text


def test_para_preformatted_mode_passes_through_unchanged():
    gen = PDFReportGenerator()
    para = gen._para("<b>already escaped</b>", gen.styles["Normal"], mode="preformatted")
    assert para.text == "<b>already escaped</b>"


def test_unescaped_company_name_reaches_paragraph_escaped(tmp_path):
    """Regression for the specific H25 sites the audit named: company_name
    and title previously reached Paragraph() with no escaping at all."""
    out = tmp_path / "r.pdf"
    report = make_report(company_name="A & B Labs", title="Report <1>")
    assert PDFReportGenerator().generate(report, out) is True
    assert out.stat().st_size > 0


def test_section_title_with_xml_specials_does_not_crash_generation(tmp_path):
    out = tmp_path / "r.pdf"
    report = make_report()
    report.sections[0].title = "Overshoot <CH2> & Ringing"
    assert PDFReportGenerator().generate(report, out) is True


def test_paragraph_construction_only_happens_through__para():
    """Structural regression guard: a new call site that constructs
    Paragraph(...) directly (bypassing _para) reintroduces H25 by
    forgetting to escape. Exactly one occurrence of the literal substring
    is expected -- the `return Paragraph(escaped, style)` inside _para
    itself."""
    src = Path("scpi_control/report_generator/generators/pdf_generator.py").read_text(encoding="utf-8")
    count = src.count("Paragraph(")
    assert count == 1, f"expected exactly 1 direct Paragraph(...) call (inside _para), found {count}"
