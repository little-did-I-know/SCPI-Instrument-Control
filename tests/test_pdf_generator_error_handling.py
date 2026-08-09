"""PDFReportGenerator.generate() must distinguish environmental failures
(OSError -- permission denied, disk full, a bad output path) from programming
errors (AttributeError, TypeError, ...). Only the former is documented to
return `False`; the latter must propagate rather than being reported as a
plain `False` indistinguishable from a full disk (audit 2026-08-09, L2).

Needs reportlab (the report-generator extra); CI's test job installs
`.[dev,web]` only, so this skips cleanly there -- same pattern as
tests/test_report_generators.py and tests/test_pdf_page_framework.py.
"""

from datetime import datetime

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


def make_report():
    """A minimal but complete TestReport, including one waveform."""
    t = np.arange(100) / 1e6
    waveform = WaveformData(
        channel="C1",
        time=t,
        voltage=np.sin(2 * np.pi * 10_000 * t),
        sample_rate=1e6,
        record_length=100,
    )
    section = TestSection(title="Rise Time", content="Measured on C1.", waveforms=[waveform])
    metadata = ReportMetadata(title="Bench Check", technician="robin", test_date=datetime(2026, 7, 16))
    return TestReport(metadata=metadata, sections=[section])


def test_generate_returns_true_and_writes_the_file_on_the_happy_path(tmp_path):
    out = tmp_path / "r.pdf"
    assert PDFReportGenerator().generate(make_report(), out) is True
    assert out.stat().st_size > 0


def test_oserror_writing_the_file_is_still_reported_as_false(tmp_path):
    """A bad output path (nonexistent parent directory) is an environmental
    failure -- reportlab's canvas can't open the file and raises
    FileNotFoundError (an OSError) from inside doc.build(). The documented
    `False` contract must be preserved for it."""
    out = tmp_path / "does_not_exist" / "r.pdf"
    assert PDFReportGenerator().generate(make_report(), out) is False
    assert not out.exists()


def test_a_programming_error_propagates_instead_of_returning_false(tmp_path, monkeypatch):
    """Pins the defect: an AttributeError from a bug in report rendering must
    not be swallowed and reported as a plain False -- it must be raised so it
    is visible, instead of masquerading as an environmental failure."""
    generator = PDFReportGenerator()

    def _boom(self, report):
        raise AttributeError("simulated programming error in report rendering")

    monkeypatch.setattr(PDFReportGenerator, "_generate_header", _boom)

    out = tmp_path / "r.pdf"
    with pytest.raises(AttributeError):
        generator.generate(make_report(), out)

    assert not out.exists()
