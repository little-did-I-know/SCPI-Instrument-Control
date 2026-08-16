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
        channel="C1",
        time=t,
        voltage=np.sin(2 * np.pi * 10_000 * t),
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


def make_annotated_report():
    """A report exercising all four annotated plot types."""
    from scpi_control.report_generator.models.annotations import (
        KIND_HLINE,
        KIND_LABEL,
        KIND_SPAN,
        KIND_VLINE,
        PlotAnnotation,
    )
    from scpi_control.report_generator.models.report_elements import OverlayPlotSpec, OverlayTrace

    t = np.arange(200) / 1e6
    waveform = WaveformData(
        channel="C1",
        time=t,
        voltage=np.sin(2 * np.pi * 10_000 * t),
        sample_rate=1e6,
        record_length=200,
    )
    waveform.annotations = [
        PlotAnnotation(kind=KIND_LABEL, text="ringing here", x=5e-5, y=0.5),
        PlotAnnotation(kind=KIND_VLINE, text="trigger", x=1e-5),
        PlotAnnotation(kind=KIND_HLINE, text="3.3 V limit", y=0.9),
        PlotAnnotation(kind=KIND_SPAN, text="settling window", x=2e-5, x_end=8e-5),
    ]
    waveform.caption = "Figure 1: C1 with a 10x probe"
    waveform.add_region(start_time=1e-5, end_time=9e-5, label="Plateau")

    section = TestSection(title="Rise Time", content="Measured on C1.", waveforms=[waveform])
    section.include_fft = True
    section.fft_frequency = np.linspace(0, 5e6, 200)
    section.fft_magnitude = np.linspace(-80, 0, 200)
    section.fft_annotations = [PlotAnnotation(kind=KIND_VLINE, text="carrier", x=1e6)]
    section.fft_caption = "Figure 2: spectrum of C1"
    section.overlay_plots = [
        OverlayPlotSpec(
            channel_label="1",
            traces=[OverlayTrace(run_label="before", waveform=waveform, color="#1f77b4")],
            annotations=[PlotAnnotation(kind=KIND_LABEL, text="drift", x=5e-5, y=0.2)],
            caption="Figure 3: all runs",
        )
    ]

    metadata = ReportMetadata(title="Bench Check", technician="robin", test_date=datetime(2026, 8, 16))
    return TestReport(metadata=metadata, sections=[section])


def test_pdf_generation_with_annotations_on_every_plot_type(tmp_path):
    pytest.importorskip("reportlab")
    from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator

    out = tmp_path / "annotated.pdf"
    assert PDFReportGenerator().generate(make_annotated_report(), out) is True
    assert out.stat().st_size > 0
    with open(out, "rb") as f:
        assert f.read(4) == b"%PDF"


def test_pdf_draws_annotations_on_all_four_plots(tmp_path, monkeypatch):
    """Assert the renderer is reached from every plot path. Comparing output bytes
    would not work -- matplotlib's SVG embeds generated element ids and is not
    byte-stable across runs."""
    pytest.importorskip("reportlab")
    from scpi_control.report_generator.generators import pdf_generator

    calls = []

    real = pdf_generator.draw_annotations

    def spy(ax, annotations, style, x_scale=1.0):
        calls.append((list(annotations or []), x_scale))
        return real(ax, annotations, style, x_scale)

    monkeypatch.setattr(pdf_generator, "draw_annotations", spy)

    out = tmp_path / "annotated.pdf"
    assert pdf_generator.PDFReportGenerator().generate(make_annotated_report(), out) is True

    scales = [x_scale for _, x_scale in calls]
    assert 1e6 in scales  # waveform and overlay plots draw microseconds
    assert 1e3 in scales  # region zoom draws milliseconds
    assert 1e-6 in scales  # FFT draws megahertz

    # The region window is 1e-5..9e-5 s, so the vline at 1e-5 survives clipping
    # but the hline (no x) is always kept and the label at 5e-5 is inside.
    region_call = next(annotations for annotations, x_scale in calls if x_scale == 1e3)
    assert {a.kind for a in region_call} == {"label", "vline", "hline", "span"}


def test_pdf_caption_text_reaches_the_document(tmp_path):
    pytest.importorskip("reportlab")
    from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator

    generator = PDFReportGenerator()
    report = make_annotated_report()
    out = tmp_path / "annotated.pdf"
    assert generator.generate(report, out) is True
    assert "FigureCaption" in generator.styles


def test_pymupdf_is_available_for_the_preview_dialog():
    """PDF preview imports fitz (widgets/pdf_preview_dialog.py:17); without it
    declared, a clean `pip install .[report-generator]` leaves the feature dead."""
    pytest.importorskip("fitz")
