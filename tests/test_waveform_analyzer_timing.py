"""Duty cycle must not depend on the trigger phase of the capture."""

import numpy as np

from scpi_control.report_generator.models.report_data import WaveformData
from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer


def make_waveform(voltage, rate=1e6):
    n = len(voltage)
    return WaveformData(channel="C1", time=np.arange(n) / rate, voltage=voltage, sample_rate=rate, record_length=n)


def test_duty_cycle_when_capture_starts_high():
    t = np.arange(4000) / 1e6
    # cosine-phased square: first sample sits on the high plateau
    v = np.where(np.cos(2 * np.pi * 1000 * t) >= 0, 1.0, -1.0)
    stats = WaveformAnalyzer.calculate_timing_stats(make_waveform(v))
    assert stats["duty_cycle"] is not None
    assert abs(stats["duty_cycle"] - 50.0) < 5.0  # was 0.00 %
