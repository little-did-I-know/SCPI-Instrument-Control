"""Draws PlotAnnotations onto a matplotlib axes.

This is the ONLY module that knows how an annotation becomes matplotlib calls.
Both the PDF and Markdown generators import it, from all four of their plot
functions. Keeping it pure -- axes in, axes mutated, nothing returned -- is what
lets it be tested against a bare plt.subplots() with no ReportLab and no PyQt.

Captions are deliberately not handled here: a caption is a ReportLab flowable in
the PDF story and a line of Markdown beneath an image file. Each generator emits
its own in its own idiom.
"""

import logging
from dataclasses import replace
from typing import Iterable, List, Optional

from scpi_control.report_generator.models.annotations import (
    KIND_HLINE,
    KIND_LABEL,
    KIND_SPAN,
    KIND_VLINE,
    PlotAnnotation,
)

logger = logging.getLogger(__name__)


def draw_annotations(ax, annotations: Optional[Iterable[PlotAnnotation]], style, x_scale: float = 1.0) -> None:
    """Draw every annotation onto `ax`.

    Args:
        ax: matplotlib axes, already carrying its trace -- the text-offset maths
            reads get_xlim()/get_ylim(), so calling this before plotting would
            place labels against placeholder limits.
        annotations: the annotations to draw. None or empty is a no-op.
        style: a PlotStyle supplying the annotation_* defaults.
        x_scale: domain-to-display multiplier for this plot. 1e6 for a
            microsecond axis, 1e3 for milliseconds, 1e-6 for megahertz. `y` is
            never scaled -- every plot shows volts or dB directly.
    """
    if not annotations:
        return

    x_min, x_max = ax.get_xlim()
    y_min, y_max = ax.get_ylim()
    x_span = x_max - x_min
    y_span = y_max - y_min

    for annotation in annotations:
        color = annotation.color or style.annotation_color
        fontsize = annotation.fontsize or style.annotation_fontsize

        if annotation.kind == KIND_LABEL:
            anchor_x = annotation.x * x_scale
            text_x = anchor_x + annotation.text_dx * x_span
            text_y = annotation.y + annotation.text_dy * y_span
            arrow = style.annotation_arrow if annotation.arrow is None else annotation.arrow
            ax.annotate(
                annotation.text,
                xy=(anchor_x, annotation.y),
                xytext=(text_x, text_y),
                textcoords="data",
                color=color,
                fontsize=fontsize,
                arrowprops={"arrowstyle": "->", "color": color, "linewidth": 0.8} if arrow else None,
            )

        elif annotation.kind == KIND_VLINE:
            position = annotation.x * x_scale
            ax.axvline(position, color=style.annotation_line_color, linestyle=style.annotation_line_style, linewidth=1.0, alpha=0.8)
            if annotation.text:
                ax.text(position, y_max - 0.02 * y_span, annotation.text, color=color, fontsize=fontsize, ha="left", va="top", rotation=90)

        elif annotation.kind == KIND_HLINE:
            ax.axhline(annotation.y, color=style.annotation_line_color, linestyle=style.annotation_line_style, linewidth=1.0, alpha=0.8)
            if annotation.text:
                ax.text(x_max - 0.01 * x_span, annotation.y, annotation.text, color=color, fontsize=fontsize, ha="right", va="bottom")

        elif annotation.kind == KIND_SPAN:
            start = annotation.x * x_scale
            end = annotation.x_end * x_scale
            ax.axvspan(start, end, color=style.annotation_span_color, alpha=style.annotation_span_alpha, zorder=0)
            if annotation.text:
                ax.text((start + end) / 2.0, y_max - 0.02 * y_span, annotation.text, color=color, fontsize=fontsize, ha="center", va="top")
