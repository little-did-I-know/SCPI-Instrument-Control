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

    assert len(calls) == 4  # waveform, region zoom, overlay, FFT
    scales = [x_scale for _, x_scale in calls]
    assert scales.count(1e6) == 2  # waveform + overlay
    assert scales.count(1e3) == 1  # region zoom
    assert scales.count(1e-6) == 1  # FFT

    # The region window is 1e-5..9e-5 s, so the vline at 1e-5 survives clipping
    # but the hline (no x) is always kept and the label at 5e-5 is inside.
    region_call = next(annotations for annotations, x_scale in calls if x_scale == 1e3)
    assert {a.kind for a in region_call} == {"label", "vline", "hline", "span"}


def test_pdf_caption_text_reaches_the_document(tmp_path):
    pytest.importorskip("reportlab")
    fitz = pytest.importorskip("fitz")
    from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator

    generator = PDFReportGenerator()
    report = make_annotated_report()
    out = tmp_path / "annotated.pdf"
    assert generator.generate(report, out) is True
    assert "FigureCaption" in generator.styles

    doc = fitz.open(out)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    assert "Figure 1: C1 with a 10x probe" in text
    assert "Figure 2: spectrum of C1" in text
    assert "Figure 3: all runs" in text


def test_svg_to_drawing_preserves_patch_opacity():
    """svglib reads fill-opacity/stroke-opacity but ignores a bare `opacity:`.

    matplotlib writes a translucent PATCH -- an annotation span's fill, a legend
    frame -- as `opacity:` inside a style attribute, so every span reached the PDF
    fully opaque whatever PlotStyle.annotation_span_alpha said. Lines were never
    affected: those get stroke-opacity, which svglib already honours.

    The second path guards the rewrite against mangling an already-hyphenated
    property into `fill-fill-opacity`.
    """
    import io

    pytest.importorskip("reportlab")
    from scpi_control.report_generator.generators.pdf_generator import _svg_to_drawing

    svg = b"""<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100">
 <path d="M 10 10 L 40 10 L 40 40 L 10 40 z" style="fill: #ffcc00; opacity: 0.25; stroke: #ffcc00; stroke-linejoin: miter"/>
 <path d="M 50 10 L 90 10 L 90 40 L 50 40 z" style="fill: #00ff00; fill-opacity: 0.5"/>
</svg>
"""
    drawing = _svg_to_drawing(io.BytesIO(svg), 200, 200)

    shapes = []

    def collect(node):
        for child in getattr(node, "contents", []):
            if getattr(child, "fillColor", None) is not None:
                shapes.append(child)
            collect(child)

    collect(drawing)

    span = next(s for s in shapes if (round(s.fillColor.red, 2), round(s.fillColor.green, 2)) == (1.0, 0.8))
    assert span.fillOpacity == pytest.approx(0.25)
    assert span.strokeOpacity == pytest.approx(0.25)  # else the span keeps a hard saturated border

    untouched = next(s for s in shapes if (round(s.fillColor.red, 2), round(s.fillColor.green, 2)) == (0.0, 1.0))
    assert untouched.fillOpacity == pytest.approx(0.5)


def test_pdf_span_annotation_is_translucent(tmp_path):
    """End-to-end: the span in a generated PDF is painted at annotation_span_alpha.

    Asserted on the painted fill, not on the SVG, because the alpha was lost in the
    SVG-to-ReportLab conversion -- a test above that layer passed while every real
    report drew an opaque block over its own gridlines.
    """
    pytest.importorskip("reportlab")
    fitz = pytest.importorskip("fitz")
    from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator

    generator = PDFReportGenerator()
    out = tmp_path / "annotated.pdf"
    assert generator.generate(make_annotated_report(), out) is True

    span_rgb = tuple(int(generator.plot_style.annotation_span_color.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4))
    doc = fitz.open(out)
    try:
        opacities = [
            drawing.get("fill_opacity")
            for page in doc
            for drawing in page.get_drawings()
            if drawing.get("fill") and all(round(a, 2) == round(b, 2) for a, b in zip(drawing["fill"], span_rgb))
        ]
    finally:
        doc.close()

    assert opacities, "no span-coloured fill found in the PDF"
    assert all(o == pytest.approx(generator.plot_style.annotation_span_alpha) for o in opacities)


def test_pymupdf_is_available_for_the_preview_dialog():
    """PDF preview imports fitz (widgets/pdf_preview_dialog.py:17); without it
    declared, a clean `pip install .[report-generator]` leaves the feature dead."""
    pytest.importorskip("fitz")


def test_markdown_generation_with_annotations_emits_captions(tmp_path):
    from scpi_control.report_generator.generators.markdown_generator import MarkdownReportGenerator

    out = tmp_path / "annotated.md"
    assert MarkdownReportGenerator().generate(make_annotated_report(), out) is True

    text = out.read_text(encoding="utf-8")
    assert "Figure 1: C1 with a 10x probe" in text
    assert "Figure 2: spectrum of C1" in text
    assert "Figure 3: all runs" in text


def test_markdown_draws_annotations_on_all_four_plots(tmp_path, monkeypatch):
    from scpi_control.report_generator.generators import markdown_generator

    calls = []
    real = markdown_generator.draw_annotations

    def spy(ax, annotations, style, x_scale=1.0):
        calls.append((list(annotations or []), x_scale))
        return real(ax, annotations, style, x_scale)

    monkeypatch.setattr(markdown_generator, "draw_annotations", spy)

    out = tmp_path / "annotated.md"
    assert markdown_generator.MarkdownReportGenerator().generate(make_annotated_report(), out) is True

    # Count, not membership: the waveform and overlay plots both use 1e6, so
    # `1e6 in scales` stays true even if one of those two call sites is deleted.
    assert len(calls) == 4  # waveform, region zoom, overlay, FFT
    scales = [x_scale for _, x_scale in calls]
    assert scales.count(1e6) == 2  # waveform + overlay
    assert scales.count(1e3) == 1  # region zoom
    assert scales.count(1e-6) == 1  # FFT
