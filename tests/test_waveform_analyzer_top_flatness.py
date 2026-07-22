"""top_flatness: % deviation across the settled flat top; None off flat-tops."""

import numpy as np

from scpi_control.report_generator.models.report_data import WaveformData
from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer


def make_waveform(voltage, rate=1e6):
    n = len(voltage)
    return WaveformData(channel="C1", time=np.arange(n) / rate, voltage=voltage, sample_rate=rate, record_length=n)


def _square(rate=1e6, cycles=6, n=6000, top=1.0, base=-1.0):
    t = np.arange(n) / rate
    return np.where(np.sin(2 * np.pi * (cycles * rate / n) * t) >= 0, top, base).astype(float)


def test_flat_square_is_near_zero():
    tf = WaveformAnalyzer.calculate_top_flatness(make_waveform(_square()))
    assert tf is not None and tf < 0.5  # a perfectly flat top ~ 0 %


def test_sloped_top_reports_expected_percent():
    # square with a top that ramps by 0.04 across each high plateau (2% of the 2.0 amplitude)
    n, rate, cycles = 6000, 1e6, 6
    t = np.arange(n) / rate
    base = np.where(np.sin(2 * np.pi * (cycles * rate / n) * t) >= 0, 1.0, -1.0).astype(float)
    high = base > 0
    # add a per-sample ramp only on the high plateaus, spanning ~0.04 over the record's high runs
    ramp = np.linspace(-0.02, 0.02, n)
    base[high] += ramp[high]
    tf = WaveformAnalyzer.calculate_top_flatness(make_waveform(base))
    assert tf is not None and 1.0 < tf < 4.0  # order ~2 %, robust band


def test_sine_returns_none():
    t = np.arange(6000) / 1e6
    assert WaveformAnalyzer.calculate_top_flatness(make_waveform(np.sin(2 * np.pi * 1000 * t))) is None


def test_analyze_includes_top_flatness_key():
    stats = WaveformAnalyzer.analyze(make_waveform(_square()))
    assert "top_flatness" in stats
