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
