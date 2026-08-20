"""The PDF generator's text sanitizer keeps output within the built-in font's
WinAnsi/cp1252 coverage, so no glyph renders as a blank box.

reportlab's built-in Type-1 fonts (Helvetica) can only draw WinAnsi/cp1252
characters; anything outside that (warning sign, check/ballot-x, Greek letters,
CJK, ...) renders as an empty box. `_markdown_to_reportlab` must map or replace
those so the PDF never shows a missing glyph.
"""

import pytest

pytest.importorskip("reportlab")

from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator  # noqa: E402


def test_markdown_to_reportlab_output_is_winansi_safe():
    gen = PDFReportGenerator()
    # Glyphs the built-in font cannot draw: warning sign, check mark, ballot-x,
    # Greek sigma/omega, plus an arbitrary CJK char to exercise the catch-all.
    problem = "⚠ warn ✓ ok ✗ bad σ sd Ω ohm 你 cjk"
    out = gen._markdown_to_reportlab(problem)

    # Everything the built-in PDF font will be asked to draw must be cp1252-encodable.
    out.encode("cp1252")  # raises UnicodeEncodeError if an un-renderable glyph survived

    # And the known symbols are mapped to readable text, not silently dropped.
    assert "!" in out  # warning sign -> "!"


def test_code_span_survives_alongside_bold_markdown():
    """AUDIT.md H26: save_code() placeholders were __CODE_n__, and the bold
    regex re.sub(r"__(.+?)__", ...) matched that placeholder itself (both are
    double-underscore-delimited), corrupting or losing the code span."""
    gen = PDFReportGenerator()
    out = gen._markdown_to_reportlab("Vpp measured `1.2 V` vs limit `1.0 V`, **exceeds spec**")

    assert '<font face="Courier">1.2 V</font>' in out
    assert '<font face="Courier">1.0 V</font>' in out
    assert "<b>exceeds spec</b>" in out
    assert "CODE" not in out  # no leaked placeholder text
