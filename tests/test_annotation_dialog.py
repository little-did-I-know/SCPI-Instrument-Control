"""The annotation dialog's anchor list.

Only the pure helper is tested. The Qt widget itself needs a display and is
covered by the smoke import below, guarded by importorskip so a PyQt6-less
environment skips rather than fails.

build_anchor_choices lives in `utils.anchors`, not in `widgets.annotation_dialog`,
specifically so these tests can import it without pulling in PyQt6 -- CI has no
PyQt6 (it is only in the gui/report-generator/all extras), and
widgets/annotation_dialog.py imports PyQt6 at module level via widgets/__init__.py.
The subprocess-based regression guard below proves that separation holds.
"""

import subprocess
import sys
from unittest.mock import MagicMock

import numpy as np
import pytest

from scpi_control.report_generator.models.report_data import WaveformData


def make_waveform():
    t = np.linspace(0, 1e-4, 500)
    voltage = np.sin(2 * np.pi * 20_000 * t)
    return WaveformData(channel="C1", time=t, voltage=voltage, sample_rate=5e6, record_length=500)


def test_anchor_choices_include_the_waveform_bounds_and_midpoint():
    from scpi_control.report_generator.utils.anchors import build_anchor_choices

    waveform = make_waveform()
    labels = [label for label, _, _ in build_anchor_choices(waveform)]

    assert "Waveform start" in labels
    assert "Waveform midpoint" in labels
    assert "Waveform end" in labels


def test_anchor_choices_locate_the_extrema():
    """WaveformAnalyzer.analyze() returns vmax as a bare scalar with no time
    attached, so the dialog computes extrema LOCATIONS itself."""
    from scpi_control.report_generator.utils.anchors import build_anchor_choices

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
    from scpi_control.report_generator.utils.anchors import build_anchor_choices

    waveform = make_waveform()
    waveform.add_region(start_time=2e-5, end_time=6e-5, label="Plateau")
    choices = {label: (x, y) for label, x, y in build_anchor_choices(waveform)}

    assert choices["Plateau — start"][0] == pytest.approx(2e-5)
    assert choices["Plateau — end"][0] == pytest.approx(6e-5)
    assert choices["Plateau — mid"][0] == pytest.approx(4e-5)


def test_anchor_choices_survive_a_waveform_with_no_regions():
    from scpi_control.report_generator.utils.anchors import build_anchor_choices

    waveform = make_waveform()
    waveform.clear_regions()
    assert len(build_anchor_choices(waveform)) >= 5


def test_anchor_choices_detect_regions_on_demand_for_a_fresh_import():
    """docs/report-generator/getting-started.md tells the user the anchor
    dropdown offers "a region's start, midpoint or end", but nothing populates
    waveform.regions at import time -- the only producer is
    ComputedAnalyzer._populate_waveforms, which runs at report-build time. Per
    the design spec (2026-08-16-plot-annotations-design.md section 6),
    build_anchor_choices must call WaveformAnalyzer.detect_regions on demand
    when the waveform has no regions yet, so the documented flow is real."""
    from scpi_control.report_generator.utils.anchors import build_anchor_choices

    # A step with clear high/low plateaus, not the sine make_waveform() uses --
    # detect_regions only looks for plateaus/edges on signal types a sine
    # isn't classified as.
    t = np.linspace(0, 1e-4, 1000)
    voltage = np.where(t < 3e-5, 0.0, 3.3)
    waveform = WaveformData(channel="C1", time=t, voltage=voltage, sample_rate=1e7, record_length=1000)
    assert waveform.regions == []

    labels = [label for label, _, _ in build_anchor_choices(waveform)]

    assert any("—" in label for label in labels), f"no region anchor among: {labels}"


def test_dialog_module_imports_when_pyqt_is_available():
    pytest.importorskip("PyQt6")
    from scpi_control.report_generator.widgets.annotation_dialog import AnnotationDialog

    assert AnnotationDialog is not None


def test_anchor_helper_imports_without_pyqt():
    code = (
        "import sys\n"
        "class _Block:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name == 'PyQt6' or name.startswith('PyQt6.'):\n"
        "            raise ImportError('PyQt6 blocked for this test')\n"
        "        return None\n"
        "sys.meta_path.insert(0, _Block())\n"
        "from scpi_control.report_generator.utils.anchors import build_anchor_choices\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, f"anchors module needs PyQt6:\n{result.stderr}"


_qapp = None  # module-level: a QApplication with no surviving reference is
# garbage-collected, which invalidates every widget built on top of it even
# while a Python reference to those widgets is still held.


def _make_dialog(waveform, monkeypatch):
    """Build an AnnotationDialog headlessly. Guarded by importorskip so a
    PyQt6-less environment (CI) skips these tests rather than failing."""
    global _qapp
    pytest.importorskip("PyQt6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    from scpi_control.report_generator.widgets.annotation_dialog import AnnotationDialog

    _qapp = QApplication.instance() or QApplication([])
    return AnnotationDialog(waveform)


def test_caption_survives_closing_the_dialog_without_saving(monkeypatch):
    """The OS titlebar X goes through QDialog.closeEvent -> reject(), which
    never touches the QDialogButtonBox's rejected signal that _on_close is
    wired to. A caption typed but not explicitly saved must still survive
    that exit path."""
    waveform = make_waveform()
    dialog = _make_dialog(waveform, monkeypatch)

    # QDialog.closeEvent only calls reject() while the dialog is visible;
    # closing a never-shown dialog just accepts the close event with no
    # reject()/done() call, so show() first to exercise the real X-button path.
    dialog.show()
    dialog.caption_edit.setText("A caption typed but never explicitly saved")
    dialog.close()

    assert waveform.caption == "A caption typed but never explicitly saved"


def test_update_preserves_style_fields_not_shown_in_the_form(monkeypatch):
    """_build_annotation() only knows about the fields the form shows
    (kind/text/x/y/x_end/arrow). Update must not silently reset the four
    fields the form has no widgets for -- they round-trip through the
    sidecar via PlotAnnotation.to_dict()/from_dict(), so resetting them here
    is real, persisted data loss."""
    from scpi_control.report_generator.models.annotations import KIND_LABEL, PlotAnnotation

    waveform = make_waveform()
    original = PlotAnnotation(
        kind=KIND_LABEL,
        text="Peak",
        x=1e-5,
        y=0.5,
        text_dx=0.15,
        text_dy=0.25,
        color="red",
        fontsize=14,
    )
    waveform.annotations.append(original)

    dialog = _make_dialog(waveform, monkeypatch)
    dialog.annotation_list.setCurrentRow(0)
    dialog.text_edit.setText("Peak (typo fixed)")
    dialog._on_update()

    updated = waveform.annotations[0]
    assert updated.text == "Peak (typo fixed)"
    assert updated.text_dx == 0.15
    assert updated.text_dy == 0.25
    assert updated.color == "red"
    assert updated.fontsize == 14


def test_unexpected_save_error_shows_a_message_instead_of_crashing(monkeypatch):
    """_on_save only documents ValueError, but _atomic_write_text's
    mkstemp/os.replace raise OSError on a read-only or vanished directory,
    and json.dumps raises TypeError on a numpy.float32 coordinate. PyQt6's
    default for an unhandled exception in a slot is to print the traceback
    and call qFatal(), killing the app and every unsaved annotation with
    it -- this must not escape _on_save."""
    waveform = make_waveform()
    dialog = _make_dialog(waveform, monkeypatch)  # importorskip("PyQt6") happens here

    from PyQt6.QtWidgets import QMessageBox

    from scpi_control.report_generator.widgets import annotation_dialog as dialog_module

    def _raise(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(dialog_module, "save_annotations", _raise)
    critical_spy = MagicMock()
    monkeypatch.setattr(QMessageBox, "critical", critical_spy)

    dialog._on_save()  # must not raise

    critical_spy.assert_called_once()
