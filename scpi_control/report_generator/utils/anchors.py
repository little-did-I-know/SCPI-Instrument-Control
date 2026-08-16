"""Anchor-point computation for the annotation dialog.

Kept Qt-free and separate from `widgets/annotation_dialog.py` on purpose: this
is the part of the annotation editor worth testing without a display, and
`annotation_dialog.py` imports PyQt6 at module level, so anything that lives
there drags PyQt6 into any test that imports it -- including CI, which has no
PyQt6 (it is only in the gui/report-generator/all extras). Splitting the pure
computation out here lets it be tested and used in environments with no Qt.
"""

from typing import List, Optional, Tuple

import numpy as np


def build_anchor_choices(waveform) -> List[Tuple[str, float, Optional[float]]]:
    """Every feature the user can anchor an annotation to.

    Returns (label, x_seconds, y_volts_or_None) triples. Extrema locations are
    computed here rather than read from WaveformAnalyzer.analyze(), which returns
    vmax/vmin as bare scalars with no time attached.
    """
    time = np.asarray(waveform.time)
    voltage = np.asarray(waveform.voltage)
    if time.size == 0:
        return []

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
