"""The annotation dialog's anchor list.

Only the pure helper is tested. The Qt widget itself needs a display and is
covered by the smoke import below, guarded by importorskip so a PyQt6-less
environment skips rather than fails.
"""

import numpy as np
import pytest

from scpi_control.report_generator.models.report_data import WaveformData


def make_waveform():
    t = np.linspace(0, 1e-4, 500)
    voltage = np.sin(2 * np.pi * 20_000 * t)
    return WaveformData(channel="C1", time=t, voltage=voltage, sample_rate=5e6, record_length=500)


def test_anchor_choices_include_the_waveform_bounds_and_midpoint():
    from scpi_control.report_generator.widgets.annotation_dialog import build_anchor_choices

    waveform = make_waveform()
    labels = [label for label, _, _ in build_anchor_choices(waveform)]

    assert "Waveform start" in labels
    assert "Waveform midpoint" in labels
    assert "Waveform end" in labels


def test_anchor_choices_locate_the_extrema():
    """WaveformAnalyzer.analyze() returns vmax as a bare scalar with no time
    attached, so the dialog computes extrema LOCATIONS itself."""
    from scpi_control.report_generator.widgets.annotation_dialog import build_anchor_choices

    waveform = make_waveform()
    choices = {label: (x, y) for label, x, y in build_anchor_choices(waveform)}

    peak_x, peak_y = choices["Maximum"]
    expected_index = int(np.argmax(waveform.voltage))
    assert peak_x == pytest.approx(waveform.time[expected_index])
    assert peak_y == pytest.approx(waveform.voltage[expected_index])

    trough_x, trough_y = choices["Minimum"]
    expected_index = int(np.argmin(waveform.voltage))
    assert trough_x == pytest.approx(waveform.time[expected_index])
    assert trough_y == pytest.approx(waveform.voltage[expected_index])


def test_anchor_choices_expose_each_detected_region_at_start_mid_and_end():
    from scpi_control.report_generator.widgets.annotation_dialog import build_anchor_choices

    waveform = make_waveform()
    waveform.add_region(start_time=2e-5, end_time=6e-5, label="Plateau")
    choices = {label: (x, y) for label, x, y in build_anchor_choices(waveform)}

    assert choices["Plateau — start"][0] == pytest.approx(2e-5)
    assert choices["Plateau — end"][0] == pytest.approx(6e-5)
    assert choices["Plateau — mid"][0] == pytest.approx(4e-5)


def test_anchor_choices_survive_a_waveform_with_no_regions():
    from scpi_control.report_generator.widgets.annotation_dialog import build_anchor_choices

    waveform = make_waveform()
    waveform.clear_regions()
    assert len(build_anchor_choices(waveform)) >= 5


def test_dialog_module_imports_when_pyqt_is_available():
    pytest.importorskip("PyQt6")
    from scpi_control.report_generator.widgets.annotation_dialog import AnnotationDialog

    assert AnnotationDialog is not None
