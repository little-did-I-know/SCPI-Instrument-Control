"""User-supplied annotations drawn onto report plots.

One dataclass covers all four kinds, discriminated by `kind`. Coordinates are
stored in DOMAIN units -- seconds on time plots, hertz on FFT plots -- never in
the units a plot happens to display. The waveform plot draws microseconds, the
region plot milliseconds and the FFT megahertz; storing display units would make
an annotation jump when a plot's scale changed. The renderer applies the
conversion via its x_scale argument.
"""

from dataclasses import dataclass, fields
from typing import Any, Dict, Optional

KIND_LABEL = "label"
KIND_VLINE = "vline"
KIND_HLINE = "hline"
KIND_SPAN = "span"

VALID_KINDS = frozenset({KIND_LABEL, KIND_VLINE, KIND_HLINE, KIND_SPAN})

# (field name, default) pairs that to_dict() omits when unchanged.
_OPTIONAL_DEFAULTS = (
    ("x", None),
    ("y", None),
    ("x_end", None),
    ("text_dx", 0.0),
    ("text_dy", 0.06),
    ("arrow", None),
    ("color", None),
    ("fontsize", None),
)


@dataclass
class PlotAnnotation:
    """One annotation on one plot.

    Which coordinate fields are required depends on `kind`, and __post_init__
    enforces it: an invalid annotation fails where it is built, not silently at
    render time where the traceback would point at matplotlib.
    """

    kind: str
    text: str = ""
    x: Optional[float] = None  # seconds (time plots) or hertz (FFT)
    y: Optional[float] = None  # volts, or dB on FFT
    x_end: Optional[float] = None  # span only
    text_dx: float = 0.0  # text offset from the anchor, as a fraction of the axis span
    text_dy: float = 0.06
    arrow: Optional[bool] = None  # label only; None means "follow PlotStyle"
    color: Optional[str] = None  # None means "follow PlotStyle"
    fontsize: Optional[int] = None  # None means "follow PlotStyle"

    def __post_init__(self) -> None:
        if self.kind not in VALID_KINDS:
            raise ValueError(f"Unknown annotation kind {self.kind!r}; expected one of {sorted(VALID_KINDS)}")
        if self.kind == KIND_LABEL and (self.x is None or self.y is None):
            raise ValueError("A 'label' annotation needs both x and y")
        if self.kind == KIND_VLINE and self.x is None:
            raise ValueError("A 'vline' annotation needs x")
        if self.kind == KIND_HLINE and self.y is None:
            raise ValueError("An 'hline' annotation needs y")
        if self.kind == KIND_SPAN:
            if self.x is None or self.x_end is None:
                raise ValueError("A 'span' annotation needs both x and x_end")
            if self.x_end <= self.x:
                raise ValueError(f"A 'span' annotation needs x_end > x; got x={self.x}, x_end={self.x_end}")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize, omitting fields left at their default for a readable sidecar."""
        data: Dict[str, Any] = {"kind": self.kind, "text": self.text}
        for name, default in _OPTIONAL_DEFAULTS:
            value = getattr(self, name)
            if value != default:
                data[name] = value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlotAnnotation":
        """Rebuild from a sidecar dict. Unknown keys are an error, not ignored --
        a typo'd field name should not silently drop the user's styling."""
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"Unknown annotation fields: {sorted(unknown)}")
        return cls(**data)
