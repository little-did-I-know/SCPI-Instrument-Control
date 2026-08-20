"""Plot filenames are built directly from report text (section titles,
channel labels) -- AUDIT.md H24. An unsanitized name can escape
plots_path (path traversal), crash on '/', or collide with NTFS
alternate-data-stream syntax on ':'.
"""

from datetime import datetime

import numpy as np
import pytest

from scpi_control.report_generator.generators.markdown_generator import MarkdownReportGenerator
from scpi_control.report_generator.models.report_data import (
    ReportMetadata,
    TestReport,
    TestSection,
    WaveformData,
)


@pytest.mark.parametrize(
    "name,forbidden_char",
    [
        ("a/b", "/"),
        ("name:stream", ":"),
    ],
)
def test_sanitize_plot_name_allowlists_unsafe_characters(name, forbidden_char):
    sanitized = MarkdownReportGenerator()._sanitize_plot_name(name)
    assert sanitized != ""
    assert forbidden_char not in sanitized


def test_sanitize_plot_name_never_returns_empty():
    assert MarkdownReportGenerator()._sanitize_plot_name("") == "plot"


def test_sanitize_plot_name_cannot_produce_a_path_separator_from_traversal_text():
    """'..' survives as characters -- harmless on its own, since with no '/'
    there is no path component boundary for it to act as a parent-directory
    reference across. The sanitizer's actual job is making sure '..' can
    never be RECOMBINED with a separator it introduces."""
    sanitized = MarkdownReportGenerator()._sanitize_plot_name("../../../evil")
    assert "/" not in sanitized
    assert "\\" not in sanitized


def test_sanitize_plot_name_is_stable_for_an_ordinary_title():
    gen = MarkdownReportGenerator()
    assert gen._sanitize_plot_name("Test 1: Rise Time") == "Test_1__Rise_Time"


def _make_report_with_section_title(title: str) -> TestReport:
    t = np.arange(100) / 1e6
    waveform = WaveformData(
        channel="C1",
        time=t,
        voltage=np.sin(2 * np.pi * 10_000 * t),
        sample_rate=1e6,
        record_length=100,
    )
    section = TestSection(title=title, content="Measured on C1.", waveforms=[waveform])
    metadata = ReportMetadata(title="Bench Check", technician="robin", test_date=datetime(2026, 7, 16))
    return TestReport(metadata=metadata, sections=[section])


def test_a_path_traversal_section_title_cannot_escape_plots_path(tmp_path):
    """End-to-end: drive generate() with an adversarial section title and
    confirm the plot file lands under plots_path, not somewhere it escaped to."""
    out = tmp_path / "r.md"
    report = _make_report_with_section_title("../../../evil")

    assert MarkdownReportGenerator().generate(report, out) is True

    plots_path = out.parent / "plots"
    written = list(plots_path.glob("*.png"))
    assert len(written) == 1
    assert written[0].resolve().is_relative_to(plots_path.resolve())
    # No file was written outside plots_path.
    assert not (tmp_path.parent / "evil.png").exists()
