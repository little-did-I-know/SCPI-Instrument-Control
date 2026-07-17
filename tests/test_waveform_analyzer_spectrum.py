"""WaveformAnalyzer.calculate_spectrum -- dominant peaks and harmonic content.

Pure CPU over synthesized signals with known frequency content. No LLM, no mock,
no network.
"""

import numpy as np

from scpi_control.report_generator.models.report_data import WaveformData
from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer


def make_waveform(voltage, rate=1e6):
    n = len(voltage)
    return WaveformData(channel="C1", time=np.arange(n) / rate, voltage=voltage, sample_rate=rate, record_length=n)


def test_dominant_peak_is_the_strongest_tone():
    """A 10 kHz tone at twice the amplitude of a 30 kHz tone must come back as the
    strongest peak, and the 30 kHz tone must appear among the peaks."""
    t = np.arange(2000) / 1e6  # 1 MHz sample rate -> 500 Hz FFT bins
    v = 1.0 * np.sin(2 * np.pi * 10_000 * t) + 0.5 * np.sin(2 * np.pi * 30_000 * t)
    spec = WaveformAnalyzer.calculate_spectrum(make_waveform(v))

    assert abs(spec["fundamental_hz"] - 10_000) < 500  # within one bin
    freqs = [f for f, _ in spec["dominant_peaks"]]
    assert any(abs(f - 30_000) < 500 for f in freqs)


def test_peaks_are_ordered_strongest_first_and_relative_to_the_strongest():
    t = np.arange(2000) / 1e6
    v = 1.0 * np.sin(2 * np.pi * 10_000 * t) + 0.5 * np.sin(2 * np.pi * 30_000 * t)
    spec = WaveformAnalyzer.calculate_spectrum(make_waveform(v))

    mags = [m for _, m in spec["dominant_peaks"]]
    assert mags == sorted(mags, reverse=True)
    assert mags[0] == 1.0  # strongest peak is the reference


def test_square_wave_has_odd_harmonic_content():
    """A square wave's 3rd harmonic is stronger than its 2nd (odd-harmonic rich).
    This proves harmonic_ratios is populated and correctly ordered."""
    t = np.arange(2000) / 1e6
    v = np.where(np.sin(2 * np.pi * 5_000 * t) >= 0, 1.0, -1.0)
    spec = WaveformAnalyzer.calculate_spectrum(make_waveform(v))

    ratios = spec["harmonic_ratios"]
    assert ratios is not None
    assert ratios[0] == 1.0  # normalized to the fundamental
    assert ratios[2] > ratios[1]  # 3rd harmonic > 2nd


def test_degenerate_signal_returns_empty_rather_than_raising():
    spec = WaveformAnalyzer.calculate_spectrum(make_waveform(np.array([0.0, 0.0, 0.0])))
    assert spec["dominant_peaks"] == []
    assert spec["fundamental_hz"] is None
    assert spec["harmonic_ratios"] is None


def test_non_positive_num_peaks_returns_empty_rather_than_raising():
    """num_peaks<=0 slices the peak list to empty; without a guard the [0] index
    raises. The docstring promises never to raise on degenerate input."""
    v = np.sin(2 * np.pi * 1000 * np.arange(2000) / 1e6)
    for bad in (0, -1):
        spec = WaveformAnalyzer.calculate_spectrum(make_waveform(v), num_peaks=bad)
        assert spec["dominant_peaks"] == []
        assert spec["fundamental_hz"] is None
