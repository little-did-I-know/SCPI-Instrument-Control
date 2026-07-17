"""PDF plots are vector Drawings, and the matplotlib style does not leak.

These need reportlab + svglib (the report-generator extra), so they run locally
and skip in CI -- the same convention as tests/test_report_generators.py.
"""

import matplotlib as mpl
import numpy as np
import pytest

pytest.importorskip("reportlab")
pytest.importorskip("svglib")

from reportlab.graphics.shapes import Drawing  # noqa: E402

from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator  # noqa: E402
from scpi_control.report_generator.models.plot_style import PlotStyle  # noqa: E402
from scpi_control.report_generator.models.report_data import WaveformData  # noqa: E402


def make_waveform():
    t = np.arange(2000) / 1e6
    return WaveformData(channel="C1", time=t, voltage=np.sin(2 * np.pi * 10_000 * t), sample_rate=1e6, record_length=2000, label="C1")


def test_waveform_plot_is_a_vector_drawing_scaled_to_the_box():
    gen = PDFReportGenerator()
    drawing = gen._generate_waveform_plot(make_waveform())
    assert isinstance(drawing, Drawing)  # vector, not a raster RLImage
    assert drawing.width <= gen.plot_width + 1 and drawing.height <= gen.plot_height + 1


def test_fft_plot_is_a_vector_drawing():
    gen = PDFReportGenerator()
    freq = np.linspace(0, 1e6, 500)
    magnitude = -np.abs(np.linspace(-40, 0, 500))
    drawing = gen._generate_fft_plot(freq, magnitude)
    assert isinstance(drawing, Drawing)


def test_the_matplotlib_style_does_not_leak():
    """A non-default plot style must revert after rendering, so it does not bleed
    into the next report in the same process. Without plt.style.context this
    assertion fails: ggplot's axes.facecolor would still be active afterward."""
    mpl.style.use("default")
    default_facecolor = mpl.rcParams["axes.facecolor"]

    gen = PDFReportGenerator(plot_style=PlotStyle(matplotlib_style="ggplot"))
    gen._generate_waveform_plot(make_waveform())

    assert mpl.rcParams["axes.facecolor"] == default_facecolor
