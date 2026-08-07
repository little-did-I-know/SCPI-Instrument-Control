"""Capture GUI screenshots showing LIVE data, driven by the built-in mock scope.

The shipped docs/images GUI shots are all of a disconnected app with empty
panels (and three of them are byte-identical). This drives the real MainWindow
through its real connect path -- only the Oscilloscope factory is swapped for
one wired to a MockConnection -- then grabs the window.

Run from the repo root:  python make_gui_shots.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox

from scpi_control.connection import MockConnection
from scpi_control.oscilloscope import Oscilloscope
from scpi_control.signal_synth import SignalSpec

OUT = Path("docs/images")

SIGNALS = {
    1: SignalSpec(kind="square", frequency=1000.0, amplitude=1.65, offset=1.65),
    2: SignalSpec(kind="sine", frequency=1000.0, amplitude=1.2, noise_rms=0.02, seed=7),
}


def mock_scope(host="mock", port=5025):
    """Stand-in for gui.main_window.Oscilloscope: a scope on a mock connection."""
    return Oscilloscope(
        host,
        connection=MockConnection(
            "mock",
            channel_states={1: True, 2: True, 3: False, 4: False},
            signals=SIGNALS,
            sample_rate=2e6,
            timebase=1e-3,
        ),
    )


def silence_modals():
    """Stop modal dialogs from blocking an unattended capture run.

    ``MainWindow._connect_to_scope()`` ends with a blocking
    ``QMessageBox.information()`` on success, which never returns without a
    human to dismiss it. Patching the class object is enough -- ``main_window``
    imported the same class, not a copy.
    """
    for name in ("information", "critical", "warning", "question", "about"):
        setattr(QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))


def main():
    silence_modals()
    app = QApplication(sys.argv)

    from scpi_control.gui import main_window as mw

    mw.Oscilloscope = mock_scope  # inject before MainWindow is built

    win = mw.MainWindow()
    win.resize(1600, 1000)
    win.show()
    app.processEvents()

    win._connect_to_scope("mock")
    app.processEvents()

    # Populate the plot the same way live view does.
    scope = win.scope
    waves = [scope.get_waveform(channel=c) for c in (1, 2)]
    win._on_waveforms_ready(waves)
    for _ in range(6):
        app.processEvents()

    # The square wave's top rail lands exactly on the axis boundary; give the
    # view a little headroom so neither trace touches the frame.
    try:
        pw = win.waveform_display.plot_widget
        vb = pw.getViewBox()
        vb.enableAutoRange(axis="y", enable=False)
        lo = min(float(w.voltage.min()) for w in waves)
        hi = max(float(w.voltage.max()) for w in waves)
        pad = (hi - lo) * 0.10
        vb.setYRange(lo - pad, hi + pad, padding=0)
        for _ in range(4):
            app.processEvents()
    except Exception as exc:  # pragma: no cover - cosmetic only
        print(f"y-range tweak skipped: {exc}")

    def grab(name):
        for _ in range(4):
            app.processEvents()
        win.grab().save(str(OUT / name))
        print(f"wrote {OUT / name}")

    def select(label):
        for i in range(win.tabs.count()):
            if win.tabs.tabText(i).startswith(label):
                win.tabs.setCurrentIndex(i)
                for _ in range(4):
                    app.processEvents()
                return True
        print(f"  ! tab not found: {label}")
        return False

    # Channels tab, both traces live.
    select("Channels")
    grab("gui-live-view.png")

    # NOTE: there is deliberately no Measurements-tab capture here. The mock
    # answers :MEASure queries with fixed constants (Peak-to-Peak 2.000 V,
    # RMS 707 mV) that do not track the waveform it synthesizes -- against the
    # 3.28 Vpp square wave above, a screenshot of that tab would advertise
    # numbers contradicting the trace drawn beside them. Restore this capture
    # once the mock derives measurements from the synthesized samples.

    # FFT: compute a spectrum from channel 1 ("C1" -- the handler does int(channel[1])).
    if select("FFT"):
        try:
            # Linear frequency to 1 MHz renders the square wave's spectrum as a
            # solid block; log frequency separates the harmonics legibly.
            win.fft_display.log_freq_check.setChecked(True)
            for _ in range(2):
                app.processEvents()
            win._on_fft_compute_requested("C1", "Hanning")
            print("  fft computed (log frequency)")
        except Exception as exc:
            print(f"  fft compute failed: {exc}")
        grab("gui-fft.png")

    win.close()
    app.quit()


if __name__ == "__main__":
    main()
