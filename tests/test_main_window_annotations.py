"""Wiring between the report generator's main window and the annotation
dialog / sidecar loaders (Task 10).

The brief's manual walkthrough (task-10-brief.md Step 7) drives the app
interactively: launch it, import a file, click Annotate..., add
annotations, save, restart, re-import. Neither a human nor this harness can
drive that here, so this module is the automated equivalent -- it exercises
the same call paths (import handler, section build, annotate handler)
without a person clicking through the UI. See the Task 10 report for the
explicit list of what remains manually unverified.

Constructing MainWindow needs PyQt6 and a display; QT_QPA_PLATFORM=offscreen
supplies the latter. Guarded by importorskip so CI (no PyQt6 in the
dev/web extras) skips these tests instead of failing -- same pattern as
tests/test_annotation_dialog.py and tests/test_gui_initialization.py.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

pytest.importorskip("PyQt6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox  # noqa: E402

from scpi_control.report_generator import main_window as mw_module  # noqa: E402
from scpi_control.report_generator.models.report_data import WaveformData  # noqa: E402
from scpi_control.report_generator.utils.waveform_loader import WaveformLoader  # noqa: E402

_qapp = None  # module-level: a QApplication with no surviving reference is
# garbage-collected, which invalidates every widget built on top of it even
# while a Python reference to those widgets is still held. See
# tests/test_annotation_dialog.py for the same pattern.


def _make_waveform(channel: str, source_file: Path) -> WaveformData:
    t = np.linspace(0, 1e-4, 200)
    voltage = np.sin(2 * np.pi * 20_000 * t)
    return WaveformData(
        channel=channel,
        time=t,
        voltage=voltage,
        sample_rate=5e6,
        record_length=200,
        source_file=source_file,
    )


@pytest.fixture
def window(monkeypatch):
    """A real MainWindow, built headlessly. monkeypatch is threaded through
    so AppSettings.load() (run in __init__) cannot pick up a real prior
    session's on-disk settings during the test."""
    global _qapp
    _qapp = QApplication.instance() or QApplication([])
    win = mw_module.MainWindow()
    yield win
    win.close()


def test_import_calls_load_annotations_into_once_with_the_full_list(window, monkeypatch):
    """load_annotations_into must run exactly ONCE, after the whole import
    loop -- not once per waveform and not once per file. It caches one
    sidecar read per source file across the whole list; a per-waveform call
    would re-apply the same saved annotations once per channel (see the
    task brief's global constraint and annotation_store.load_annotations_into's
    docstring)."""
    spy = MagicMock(return_value=0)
    monkeypatch.setattr(mw_module, "load_annotations_into", spy)

    file1 = Path("capture1.csv")
    file2 = Path("capture2.csv")
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileNames",
        staticmethod(lambda *a, **k: ([str(file1), str(file2)], "")),
    )

    waveforms_by_file = {
        str(file1): [_make_waveform("C1", file1), _make_waveform("C2", file1)],
        str(file2): [_make_waveform("C1", file2)],
    }
    monkeypatch.setattr(
        WaveformLoader,
        "load",
        staticmethod(lambda p: waveforms_by_file[str(p)]),
    )

    window._import_waveforms()

    assert spy.call_count == 1, "load_annotations_into must be called exactly once per import operation"
    (called_arg,), _kwargs = spy.call_args
    # Passed the live, full waveform list -- three waveforms across two files.
    assert list(called_arg) == window.waveforms
    assert len(window.waveforms) == 3


def test_build_report_calls_load_fft_annotations_into_with_the_new_section(window, monkeypatch):
    """load_fft_annotations_into belongs at section-build time, not import
    time -- no TestSection exists yet when waveforms are imported."""
    spy = MagicMock(return_value=0)
    monkeypatch.setattr(mw_module, "load_fft_annotations_into", spy)

    window.waveforms.append(_make_waveform("C1", Path("capture.csv")))

    report = window._build_report()

    spy.assert_called_once()
    section_arg, waveforms_arg = spy.call_args[0]
    assert section_arg is report.sections[0]
    assert list(waveforms_arg) == window.waveforms


def test_build_report_without_waveforms_does_not_call_load_fft_annotations_into(window, monkeypatch):
    """No waveforms means no TestSection is built, so there is nothing to
    route FFT annotations onto."""
    spy = MagicMock(return_value=0)
    monkeypatch.setattr(mw_module, "load_fft_annotations_into", spy)

    window._build_report()

    spy.assert_not_called()


def test_annotate_button_exists_and_is_wired_to_the_handler(window):
    assert hasattr(window, "annotate_button")
    assert window.annotate_button.text() == "Annotate…"
    assert hasattr(window, "_on_annotate_waveform")
    assert callable(window._on_annotate_waveform)


def test_no_selection_shows_a_message_instead_of_raising(window, monkeypatch):
    info_spy = MagicMock()
    monkeypatch.setattr(QMessageBox, "information", info_spy)
    dialog_spy = MagicMock()
    monkeypatch.setattr(mw_module, "AnnotationDialog", dialog_spy)

    assert window.waveform_list.currentRow() == -1  # nothing imported, nothing selected

    window._on_annotate_waveform()  # must not raise

    info_spy.assert_called_once()
    dialog_spy.assert_not_called()


def test_selecting_a_waveform_opens_the_annotation_dialog(window, monkeypatch):
    waveform = _make_waveform("C1", Path("capture.csv"))
    window.waveforms.append(waveform)
    window.waveform_list.addItem("C1 - capture.csv")
    window.waveform_list.setCurrentRow(0)

    dialog_instance = MagicMock()
    dialog_spy = MagicMock(return_value=dialog_instance)
    monkeypatch.setattr(mw_module, "AnnotationDialog", dialog_spy)

    window._on_annotate_waveform()

    dialog_spy.assert_called_once_with(waveform, window)
    dialog_instance.exec.assert_called_once()
