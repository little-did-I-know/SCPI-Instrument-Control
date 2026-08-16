"""Anchor-point computation for the annotation dialog.

Kept Qt-free and separate from `widgets/annotation_dialog.py` on purpose: this
is the part of the annotation editor worth testing without a display, and
`annotation_dialog.py` imports PyQt6 at module level, so anything that lives
there drags PyQt6 into any test that imports it -- including CI, which has no
PyQt6 (it is only in the gui/report-generator/all extras). Splitting the pure
computation out here lets it be tested and used in environments with no Qt.

WaveformAnalyzer (imported below) lives in the same utils package and does not
import PyQt6 itself, so importing it at module level here does not compromise
that Qt-free property -- see test_anchor_helper_imports_without_pyqt in
tests/test_annotation_dialog.py, which subprocess-blocks PyQt6 and asserts
this module still imports cleanly.
"""

import logging
from typing import List, Optional, Tuple

import numpy as np

from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer

logger = logging.getLogger(__name__)


def build_anchor_choices(waveform) -> List[Tuple[str, float, Optional[float]]]:
    """Every feature the user can anchor an annotation to.

    Returns (label, x_seconds, y_volts_or_None) triples. Extrema locations are
    computed here rather than read from WaveformAnalyzer.analyze(), which returns
    vmax/vmin as bare scalars with no time attached.

    On a fresh import, `waveform.regions` is empty -- the only producer is
    ComputedAnalyzer._populate_waveforms, which runs at report-build time, not
    import time. So region anchors are detected here on demand (spec
    2026-08-16-plot-annotations-design.md §6) rather than only ever appearing
    after a report has already been built once. This is safe to call more than
    once: _populate_waveforms calls clear_regions() before its own detection
    pass, so a later report build is unaffected. Detection failure must not
    take out the whole anchor list -- an odd waveform still gets the five
    non-region anchors.
    """
    time = np.asarray(waveform.time)
    voltage = np.asarray(waveform.voltage)
    if time.size == 0:
        return []

    if not waveform.regions:
        try:
            WaveformAnalyzer.detect_regions(waveform)
        except Exception:
            logger.warning("detect_regions failed for anchor choices; region anchors unavailable", exc_info=True)

    start, end = float(time[0]), float(time[-1])
    peak = int(np.argmax(voltage))
    trough = int(np.argmin(voltage))

    choices: List[Tuple[str, float, Optional[float]]] = [
        ("Waveform start", start, float(voltage[0])),
        ("Waveform midpoint", (start + end) / 2.0, None),
        ("Waveform end", end, float(voltage[-1])),
        ("Maximum", float(time[peak]), float(voltage[peak])),
        ("Minimum", float(time[trough]), float(voltage[trough])),
    ]

    for region in waveform.regions:
        mid = (region.start_time + region.end_time) / 2.0
        choices.append((f"{region.label} — start", float(region.start_time), None))
        choices.append((f"{region.label} — mid", float(mid), None))
        choices.append((f"{region.label} — end", float(region.end_time), None))

    return choices
