"""The annotation renderer, tested against a bare matplotlib axes.

draw_annotations is pure -- axes in, axes mutated, nothing returned -- so these
tests need no ReportLab, no PyQt and no PDF generation.
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pytest

from scpi_control.report_generator.generators.annotation_renderer import draw_annotations
from scpi_control.report_generator.models.annotations import (
    KIND_HLINE,
    KIND_LABEL,
    KIND_SPAN,
    KIND_VLINE,
    PlotAnnotation,
)
from scpi_control.report_generator.models.plot_style import PlotStyle


@pytest.fixture
def axes():
    """An axes with a real trace, so get_xlim()/get_ylim() return real limits."""
    fig, ax = plt.subplots()
    t = np.linspace(0, 20.0, 100)  # display units: microseconds
    ax.plot(t, np.sin(t))
    yield ax
    plt.close(fig)


def test_label_anchor_is_converted_from_domain_units_to_display_units(axes):
    # 1.2e-5 seconds at x_scale 1e6 is 12.0 microseconds on the axis.
    annotation = PlotAnnotation(kind=KIND_LABEL, text="ringing", x=1.2e-5, y=0.5)
    draw_annotations(axes, [annotation], PlotStyle(), x_scale=1e6)

    assert len(axes.texts) == 1
    assert axes.texts[0].xy == pytest.approx((12.0, 0.5))
    assert axes.texts[0].get_text() == "ringing"


def test_y_is_never_scaled(axes):
    annotation = PlotAnnotation(kind=KIND_HLINE, text="limit", y=0.75)
    draw_annotations(axes, [annotation], PlotStyle(), x_scale=1e6)

    hline = axes.lines[-1]
    assert hline.get_ydata()[0] == pytest.approx(0.75)


def test_text_offset_is_a_fraction_of_the_axis_span(axes):
    x_span = axes.get_xlim()[1] - axes.get_xlim()[0]
    y_span = axes.get_ylim()[1] - axes.get_ylim()[0]
    annotation = PlotAnnotation(kind=KIND_LABEL, text="x", x=1.0e-5, y=0.0, text_dx=0.1, text_dy=0.25)
    draw_annotations(axes, [annotation], PlotStyle(), x_scale=1e6)

    tx, ty = axes.texts[0].get_position()
    assert tx == pytest.approx(10.0 + 0.1 * x_span)
    assert ty == pytest.approx(0.0 + 0.25 * y_span)


def test_each_kind_produces_the_expected_artists(axes):
    lines_before = len(axes.lines)
    annotations = [
        PlotAnnotation(kind=KIND_LABEL, text="a", x=5e-6, y=0.1),
        PlotAnnotation(kind=KIND_VLINE, text="b", x=6e-6),
        PlotAnnotation(kind=KIND_HLINE, text="c", y=0.2),
        PlotAnnotation(kind=KIND_SPAN, text="d", x=7e-6, x_end=9e-6),
    ]
    draw_annotations(axes, annotations, PlotStyle(), x_scale=1e6)

    assert len(axes.lines) == lines_before + 2  # vline + hline
    assert len(axes.patches) == 1  # span
    assert len(axes.texts) == 4  # one text per kind


def test_empty_and_none_annotation_lists_are_no_ops(axes):
    before = (len(axes.lines), len(axes.texts), len(axes.patches))
    draw_annotations(axes, [], PlotStyle(), x_scale=1e6)
    draw_annotations(axes, None, PlotStyle(), x_scale=1e6)
    assert (len(axes.lines), len(axes.texts), len(axes.patches)) == before


def test_per_annotation_overrides_beat_the_style(axes):
    style = PlotStyle(annotation_color="#333333", annotation_fontsize=9)
    annotations = [
        PlotAnnotation(kind=KIND_LABEL, text="styled", x=5e-6, y=0.1),
        PlotAnnotation(kind=KIND_LABEL, text="override", x=6e-6, y=0.2, color="#ff0000", fontsize=20),
    ]
    draw_annotations(axes, annotations, style, x_scale=1e6)

    assert axes.texts[0].get_fontsize() == 9
    assert axes.texts[1].get_fontsize() == 20
    assert axes.texts[1].get_color() == "#ff0000"


def test_style_arrow_default_applies_when_the_annotation_leaves_it_unset(axes):
    """arrow is tri-state: None follows the style. If it were a plain bool the
    style default could never win, because every annotation would claim True."""
    style = PlotStyle(annotation_arrow=False)
    draw_annotations(axes, [PlotAnnotation(kind=KIND_LABEL, text="a", x=5e-6, y=0.1)], style, x_scale=1e6)
    assert axes.texts[0].arrow_patch is None

    draw_annotations(axes, [PlotAnnotation(kind=KIND_LABEL, text="b", x=6e-6, y=0.2, arrow=True)], style, x_scale=1e6)
    assert axes.texts[1].arrow_patch is not None


def test_annotation_without_text_draws_the_line_but_no_label(axes):
    lines_before = len(axes.lines)
    draw_annotations(axes, [PlotAnnotation(kind=KIND_VLINE, x=5e-6)], PlotStyle(), x_scale=1e6)
    assert len(axes.lines) == lines_before + 1
    assert len(axes.texts) == 0


from scpi_control.report_generator.generators.annotation_renderer import clip_to_window


def test_clip_keeps_annotations_inside_the_window_and_drops_those_outside():
    inside = PlotAnnotation(kind=KIND_LABEL, text="in", x=5e-6, y=0.1)
    before = PlotAnnotation(kind=KIND_VLINE, text="early", x=1e-6)
    after = PlotAnnotation(kind=KIND_VLINE, text="late", x=9e-6)

    kept = clip_to_window([inside, before, after], 4e-6, 6e-6)

    assert kept == [inside]


def test_clip_always_keeps_horizontal_lines():
    """An hline has no x position, so no window can exclude it."""
    hline = PlotAnnotation(kind=KIND_HLINE, text="3.3 V", y=3.3)
    assert clip_to_window([hline], 4e-6, 6e-6) == [hline]


def test_clip_clamps_a_straddling_span_without_mutating_the_original():
    span = PlotAnnotation(kind=KIND_SPAN, text="settling", x=1e-6, x_end=9e-6)
    kept = clip_to_window([span], 4e-6, 6e-6)

    assert len(kept) == 1
    assert kept[0].x == pytest.approx(4e-6)
    assert kept[0].x_end == pytest.approx(6e-6)
    assert kept[0].text == "settling"
    # The caller's annotation is untouched -- the full-trace plot still needs it.
    assert span.x == pytest.approx(1e-6)
    assert span.x_end == pytest.approx(9e-6)


def test_clip_drops_spans_that_do_not_intersect_the_window():
    wholly_before = PlotAnnotation(kind=KIND_SPAN, text="a", x=1e-6, x_end=3e-6)
    wholly_after = PlotAnnotation(kind=KIND_SPAN, text="b", x=7e-6, x_end=9e-6)
    touching_edge = PlotAnnotation(kind=KIND_SPAN, text="c", x=1e-6, x_end=4e-6)

    assert clip_to_window([wholly_before, wholly_after, touching_edge], 4e-6, 6e-6) == []


def test_clip_leaves_a_fully_contained_span_alone():
    span = PlotAnnotation(kind=KIND_SPAN, text="inner", x=4.5e-6, x_end=5.5e-6)
    assert clip_to_window([span], 4e-6, 6e-6) == [span]


def test_clip_boundary_values_are_inclusive_for_points():
    at_start = PlotAnnotation(kind=KIND_VLINE, text="s", x=4e-6)
    at_end = PlotAnnotation(kind=KIND_VLINE, text="e", x=6e-6)
    assert clip_to_window([at_start, at_end], 4e-6, 6e-6) == [at_start, at_end]


def test_clip_handles_empty_and_none():
    assert clip_to_window([], 0.0, 1.0) == []
    assert clip_to_window(None, 0.0, 1.0) == []


def test_clip_drops_a_span_straddling_a_zero_width_window_instead_of_raising():
    """A degenerate clamp (start == end) must not construct an invalid
    zero-width PlotAnnotation -- the span is simply not visible here."""
    span = PlotAnnotation(kind=KIND_SPAN, text="settling", x=1e-6, x_end=9e-6)
    assert clip_to_window([span], 4e-6, 4e-6) == []


def test_clip_point_kinds_on_a_zero_width_window_still_use_inclusive_bounds():
    on_point = PlotAnnotation(kind=KIND_VLINE, text="on", x=4e-6)
    off_point = PlotAnnotation(kind=KIND_LABEL, text="off", x=5e-6, y=0.1)
    assert clip_to_window([on_point, off_point], 4e-6, 4e-6) == [on_point]
