"""DC classification must not be fooled by a large offset over real ripple."""

import numpy as np

from scpi_control.report_generator.models.report_data import WaveformData
from scpi_control.report_generator.utils.waveform_analyzer import SignalType, WaveformAnalyzer


def make_waveform(voltage, rate=1e6):
    n = len(voltage)
    return WaveformData(channel="C1", time=np.arange(n) / rate, voltage=voltage, sample_rate=rate, record_length=n)


def test_rail_with_ripple_is_not_dc():
    t = np.arange(20000) / 1e6
    v = 12.0 + 0.05 * np.sin(2 * np.pi * 100_000 * t)  # 12 V rail + 100 mVpp ripple
    stype, _ = WaveformAnalyzer.detect_signal_type(make_waveform(v))
    assert stype != SignalType.DC


def test_constant_rail_is_dc():
    v = np.full(2000, 5.0)
    stype, _ = WaveformAnalyzer.detect_signal_type(make_waveform(v))
    assert stype == SignalType.DC
