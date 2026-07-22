"""The fundamental in the first positive FFT bin must not be skipped."""

import numpy as np

from scpi_control.report_generator.models.report_data import WaveformData
from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer


def make_waveform(voltage, rate=1e6):
    n = len(voltage)
    return WaveformData(channel="C1", time=np.arange(n) / rate, voltage=voltage, sample_rate=rate, record_length=n)


def test_single_period_sine_frequency():
    n, rate = 1000, 1e6
    t = np.arange(n) / rate
    f0 = rate / n  # exactly one period over the record -> fundamental in bin 1
    v = np.sin(2 * np.pi * f0 * t)
    stats = WaveformAnalyzer.calculate_frequency_stats(make_waveform(v, rate))
    assert stats["frequency"] is not None
    assert abs(stats["frequency"] - f0) < rate / n  # within one bin


def test_single_period_sine_harmonics_negligible():
    n, rate = 1000, 1e6
    t = np.arange(n) / rate
    v = np.sin(2 * np.pi * (rate / n) * t)
    ratios = WaveformAnalyzer._get_harmonic_ratios(make_waveform(v, rate))
    assert ratios is not None
    assert ratios[1] < 0.1  # a pure sine has a negligible 2nd harmonic
