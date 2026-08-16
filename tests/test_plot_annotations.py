"""The PlotAnnotation model: validation and sidecar round-tripping."""

import pytest

from scpi_control.report_generator.models.annotations import (
    KIND_HLINE,
    KIND_LABEL,
    KIND_SPAN,
    KIND_VLINE,
    PlotAnnotation,
)


def test_valid_constructions_of_each_kind():
    assert PlotAnnotation(kind=KIND_LABEL, text="ringing", x=1.2e-5, y=3.4).kind == "label"
    assert PlotAnnotation(kind=KIND_VLINE, text="trigger", x=0.0).x == 0.0
    assert PlotAnnotation(kind=KIND_HLINE, text="3.3 V limit", y=3.3).y == 3.3
    assert PlotAnnotation(kind=KIND_SPAN, text="settling", x=1e-6, x_end=5e-6).x_end == 5e-6


@pytest.mark.parametrize(
    "kwargs, expected_message",
    [
        ({"kind": "sparkle"}, "Unknown annotation kind"),
        ({"kind": KIND_LABEL, "x": 1.0}, "needs both x and y"),
        ({"kind": KIND_LABEL, "y": 1.0}, "needs both x and y"),
        ({"kind": KIND_VLINE}, "needs x"),
        ({"kind": KIND_HLINE}, "needs y"),
        ({"kind": KIND_SPAN, "x": 1.0}, "needs both x and x_end"),
        ({"kind": KIND_SPAN, "x": 5.0, "x_end": 1.0}, "needs x_end > x"),
        ({"kind": KIND_SPAN, "x": 1.0, "x_end": 1.0}, "needs x_end > x"),
    ],
)
def test_invalid_construction_raises_at_construction_time(kwargs, expected_message):
    with pytest.raises(ValueError, match=expected_message):
        PlotAnnotation(**kwargs)


def test_to_dict_omits_defaults_but_keeps_explicit_falsey_overrides():
    plain = PlotAnnotation(kind=KIND_VLINE, text="t0", x=0.0)
    assert plain.to_dict() == {"kind": "vline", "text": "t0", "x": 0.0}

    # arrow=False is an override, not a default, so it must survive.
    styled = PlotAnnotation(kind=KIND_LABEL, text="x", x=1.0, y=2.0, arrow=False, color="#ff0000", fontsize=14)
    d = styled.to_dict()
    assert d["arrow"] is False
    assert d["color"] == "#ff0000"
    assert d["fontsize"] == 14


@pytest.mark.parametrize(
    "annotation",
    [
        PlotAnnotation(kind=KIND_LABEL, text="ringing", x=1.2e-5, y=3.4, text_dx=0.1, text_dy=-0.2, arrow=False),
        PlotAnnotation(kind=KIND_VLINE, text="trigger", x=0.0, color="#00ff00"),
        PlotAnnotation(kind=KIND_HLINE, text="limit", y=3.3, fontsize=11),
        PlotAnnotation(kind=KIND_SPAN, text="settling", x=1e-6, x_end=5e-6),
    ],
)
def test_round_trip_through_dict(annotation):
    assert PlotAnnotation.from_dict(annotation.to_dict()) == annotation


def test_from_dict_rejects_unknown_kind_and_unknown_fields():
    with pytest.raises(ValueError, match="Unknown annotation kind"):
        PlotAnnotation.from_dict({"kind": "sparkle", "x": 1.0, "y": 1.0})
    with pytest.raises(ValueError, match="Unknown annotation fields"):
        PlotAnnotation.from_dict({"kind": "vline", "x": 1.0, "wobble": 3})


def test_plot_style_carries_annotation_defaults():
    from scpi_control.report_generator.models.plot_style import PlotStyle

    style = PlotStyle()
    assert style.annotation_color == "#333333"
    assert style.annotation_fontsize == 9
    assert style.annotation_line_color == "#d62728"
    assert style.annotation_line_style == "--"
    assert style.annotation_span_color == "#ffcc00"
    assert style.annotation_span_alpha == 0.25
    assert style.annotation_arrow is True


def test_plot_style_from_dict_accepts_templates_saved_before_annotations_existed():
    """Templates on disk predate these fields. from_dict is cls(**data), so the
    absent keys must fall back to defaults rather than raise."""
    from scpi_control.report_generator.models.plot_style import PlotStyle

    legacy = {
        "waveform_color": "#1f77b4",
        "fft_color": "#ff7f0e",
        "grid_color": "#cccccc",
        "background_color": "#ffffff",
        "waveform_linewidth": 0.8,
        "grid_alpha": 0.3,
        "grid_enabled": True,
        "title_fontsize": 11,
        "label_fontsize": 10,
        "tick_fontsize": 9,
        "matplotlib_style": "default",
    }
    style = PlotStyle.from_dict(legacy)
    assert style.annotation_fontsize == 9
    assert style.waveform_color == "#1f77b4"


def test_plot_style_round_trips_annotation_fields():
    from scpi_control.report_generator.models.plot_style import PlotStyle

    style = PlotStyle(annotation_color="#000000", annotation_span_alpha=0.5)
    assert PlotStyle.from_dict(style.to_dict()) == style


def test_waveform_carries_annotations_and_a_caption():
    import numpy as np

    from scpi_control.report_generator.models.report_data import WaveformData

    t = np.arange(100) / 1e6
    waveform = WaveformData(channel="C1", time=t, voltage=np.sin(t), sample_rate=1e6, record_length=100)
    assert waveform.annotations == []
    assert waveform.caption is None

    waveform.annotations.append(PlotAnnotation(kind=KIND_LABEL, text="ringing", x=1.2e-5, y=0.5))
    waveform.caption = "Figure 1: C1 rising edge"
    d = waveform.to_dict()
    assert d["annotations"] == [{"kind": "label", "text": "ringing", "x": 1.2e-5, "y": 0.5}]
    assert d["caption"] == "Figure 1: C1 rising edge"


def test_waveform_to_dict_omits_annotation_keys_when_unset():
    import numpy as np

    from scpi_control.report_generator.models.report_data import WaveformData

    t = np.arange(10) / 1e6
    waveform = WaveformData(channel="C1", time=t, voltage=np.sin(t), sample_rate=1e6, record_length=10)
    d = waveform.to_dict()
    assert "annotations" not in d
    assert "caption" not in d


def test_section_carries_fft_annotations_and_caption():
    from scpi_control.report_generator.models.report_data import TestSection

    section = TestSection(title="Spectrum")
    assert section.fft_annotations == []
    assert section.fft_caption is None

    section.fft_annotations.append(PlotAnnotation(kind=KIND_VLINE, text="carrier", x=1.0e6))
    section.fft_caption = "Figure 2: spectrum"
    d = section.to_dict()
    assert d["fft_annotations"] == [{"kind": "vline", "text": "carrier", "x": 1.0e6}]
    assert d["fft_caption"] == "Figure 2: spectrum"


def test_overlay_spec_carries_annotations_and_caption():
    from scpi_control.report_generator.models.report_elements import OverlayPlotSpec

    spec = OverlayPlotSpec(channel_label="1")
    assert spec.annotations == []
    assert spec.caption is None

    spec.annotations.append(PlotAnnotation(kind=KIND_SPAN, text="drift", x=1e-6, x_end=2e-6))
    spec.caption = "Figure 3: all runs"
    d = spec.to_dict()
    assert d["annotations"] == [{"kind": "span", "text": "drift", "x": 1e-6, "x_end": 2e-6}]
    assert d["caption"] == "Figure 3: all runs"


def test_waveform_region_no_longer_carries_the_dead_markers_field():
    """`markers` was declared for 'Arrows, labels, etc.', serialized, and rendered
    by nothing. PlotAnnotation replaces it; leaving a second half-built annotation
    concept beside the working one only confuses the next reader."""
    from dataclasses import fields

    from scpi_control.report_generator.models.report_data import WaveformRegion

    assert "markers" not in {f.name for f in fields(WaveformRegion)}
