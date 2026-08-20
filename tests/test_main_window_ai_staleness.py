"""AIAnalysisPanel.generated_content persisted across _new_report() /
waveform re-import, so a report built from new data could silently ship AI
summary/findings that describe the previous dataset (AUDIT.md H27).

Constructing MainWindow needs PyQt6 and a display; QT_QPA_PLATFORM=offscreen
supplies the latter. Guarded by importorskip so CI (no PyQt6 in the
dev/web extras) skips these tests instead of failing -- same pattern as
tests/test_main_window_annotations.py.
"""

import os
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("PyQt6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox  # noqa: E402

from scpi_control.report_generator import main_window as mw_module  # noqa: E402
from scpi_control.report_generator.models.app_settings import AppSettings  # noqa: E402
from scpi_control.report_generator.models.report_data import WaveformData  # noqa: E402
from scpi_control.report_generator.utils.waveform_loader import WaveformLoader  # noqa: E402

_qapp = None  # module-level: see tests/test_main_window_annotations.py for why
# this must survive as a live reference.


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
    monkeypatch.setattr(AppSettings, "load", classmethod(lambda cls: AppSettings()))

    global _qapp
    _qapp = QApplication.instance() or QApplication([])
    win = mw_module.MainWindow()
    yield win
    win.close()


def _seed_ai_content(window):
    window.ai_analysis_panel.generated_content = {
        "executive_summary": "1 kHz square wave, Vpp 3.3 V",
        "key_findings": ["Rise time within spec"],
        "recommendations": [],
    }
    assert window.ai_analysis_panel.has_generated_content()


def test_clear_data_invalidates_ai_content(window, monkeypatch):
    window.waveforms.append(_make_waveform("C1", Path("capture.csv")))
    _seed_ai_content(window)

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)

    window._clear_data()

    assert not window.ai_analysis_panel.has_generated_content()


def test_import_waveforms_invalidates_ai_content(window, monkeypatch):
    _seed_ai_content(window)

    file1 = Path("capture1.csv")
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileNames",
        staticmethod(lambda *a, **k: ([str(file1)], "")),
    )
    monkeypatch.setattr(
        WaveformLoader,
        "load",
        staticmethod(lambda p: [_make_waveform("C1", file1)]),
    )

    window._import_waveforms()

    assert not window.ai_analysis_panel.has_generated_content()


def test_import_waveforms_partial_failure_still_invalidates_ai_content(window, monkeypatch):
    """Regression for the whole-branch review finding (H27 partial-import
    case): if WaveformLoader.load raises partway through a multi-file
    import, self.waveforms already changed from the files loaded before
    the failure, so stale AI content must still be invalidated even though
    the overall _import_waveforms() call ends up reporting an error."""
    _seed_ai_content(window)

    file1 = Path("capture1.csv")
    file2 = Path("corrupt2.csv")
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileNames",
        staticmethod(lambda *a, **k: ([str(file1), str(file2)], "")),
    )

    def _load(p):
        if str(p) == str(file1):
            return [_make_waveform("C1", file1)]
        raise ValueError("corrupt waveform file")

    monkeypatch.setattr(WaveformLoader, "load", staticmethod(_load))
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)

    window._import_waveforms()

    assert len(window.waveforms) == 1  # file1's waveform was kept
    assert not window.ai_analysis_panel.has_generated_content()
