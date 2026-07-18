"""detect_signal_type classifies the standard waveform battery correctly.

One table-driven test (kept deliberately to a single test: the suite is already
large): build each signal, classify it, and assert there are no mismatches. This
doubles as the regression guard against classifier drift -- how the noise and
pulse bugs slipped in. The real cal-square is covered by test_real_capture_fixture.py
and not repeated here.

Known limitation (documented, not asserted): a SINGLE-period sine misclassifies
as triangle (one cycle gives poor FFT resolution); multi-period sine is correct.
"""

import numpy as np
from scipy import signal as sp

from scpi_control.report_generator.models.report_data import WaveformData
from scpi_control.report_generator.utils.waveform_analyzer import SignalType, WaveformAnalyzer

_SR = 1_000_000
_N = 20_000
_T = np.linspace(0.0, 1.0, _N, endpoint=False)


def _wf(v):
    v = np.asarray(v, dtype=float)
    return WaveformData(channel="C1", time=np.arange(v.size) / _SR, voltage=v, sample_rate=_SR, record_length=v.size)


def test_signal_type_classification_battery():
    rng = np.random.default_rng(0)
    battery = {
        "sine": (np.sin(2 * np.pi * 5 * _T), SignalType.SINE),
        "square_50pct": (np.sign(np.sin(2 * np.pi * 5 * _T)), SignalType.SQUARE),
        "triangle": (sp.sawtooth(2 * np.pi * 5 * _T, 0.5), SignalType.TRIANGLE),
        "sawtooth": (sp.sawtooth(2 * np.pi * 5 * _T), SignalType.SAWTOOTH),
        "pulse_20pct": (sp.square(2 * np.pi * 5 * _T, 0.2), SignalType.PULSE),
        "pulse_80pct": (sp.square(2 * np.pi * 5 * _T, 0.8), SignalType.PULSE),
        "white_noise": (rng.standard_normal(_N), SignalType.NOISE),
        "dc": (np.full(_N, 2.5), SignalType.DC),
        "sine_plus_noise": (np.sin(2 * np.pi * 5 * _T) + 0.2 * rng.standard_normal(_N), SignalType.SINE),
    }
    mismatches = []
    for name, (v, expected) in battery.items():
        got, _ = WaveformAnalyzer.detect_signal_type(_wf(v))
        if got != expected:
            mismatches.append(f"{name}: expected {expected!r}, got {got!r}")
    assert not mismatches, "signal-type misclassifications:\n" + "\n".join(mismatches)
