"""Quality metrics: overshoot/undershoot and noise/SNR are honest (no fabrication)."""

import numpy as np

from scpi_control.report_generator.models.report_data import WaveformData
from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer


def make_waveform(voltage, rate=1e6):
    n = len(voltage)
    return WaveformData(channel="C1", time=np.arange(n) / rate, voltage=voltage, sample_rate=rate, record_length=n)


def _square_with_overshoot(overshoot_frac=0.05):
    t = np.arange(4000) / 1e6
    v = np.where(np.sin(2 * np.pi * 1000 * t) >= 0, 1.0, -1.0).astype(float)  # -1..+1, amplitude 2.0
    spike = overshoot_frac * 2.0  # fraction of the peak-to-peak amplitude
    rising = np.where((v[:-1] < 0) & (v[1:] >= 0))[0]
    falling = np.where((v[:-1] > 0) & (v[1:] <= 0))[0]
    for idx in rising:
        v[idx + 1 : idx + 4] = 1.0 + spike
    for idx in falling:
        v[idx + 1 : idx + 4] = -1.0 - spike
    return v


def test_clean_sine_reports_no_overshoot():
    t = np.arange(4000) / 1e6
    v = np.sin(2 * np.pi * 1000 * t)
    q = WaveformAnalyzer.calculate_quality_stats(make_waveform(v))
    assert q["overshoot"] is None
    assert q["undershoot"] is None


def test_square_overshoot_is_measured():
    q = WaveformAnalyzer.calculate_quality_stats(make_waveform(_square_with_overshoot(0.05)))
    assert q["overshoot"] is not None
    assert 3.0 < q["overshoot"] < 7.0


def test_clean_sine_has_near_zero_noise_and_no_snr():
    t = np.arange(8000) / 1e6
    v = np.sin(2 * np.pi * 1000 * t)  # perfectly clean, integer number of periods
    q = WaveformAnalyzer.calculate_quality_stats(make_waveform(v))
    assert q["noise_level"] is not None and q["noise_level"] < 1e-3  # ~0, not 0.707
    assert q["snr"] is None  # no measurable noise -> no fabricated dB


def test_noisy_sine_noise_estimate_matches_injected():
    rng = np.random.default_rng(0)
    t = np.arange(8000) / 1e6
    v = np.sin(2 * np.pi * 1000 * t) + 0.01 * rng.standard_normal(t.size)  # 10 mV RMS noise
    q = WaveformAnalyzer.calculate_quality_stats(make_waveform(v))
    assert q["noise_level"] is not None
    assert 0.006 < q["noise_level"] < 0.014  # ~10 mV
    assert q["snr"] is not None and 30 < q["snr"] < 50  # ~37 dB (0.707 / 0.01)


def test_single_cycle_capture_noise_is_none_not_zero():
    rng = np.random.default_rng(1)
    n, rate = 1000, 1e6
    t = np.arange(n) / rate
    v = np.sin(2 * np.pi * (rate / n) * t) + 0.01 * rng.standard_normal(n)  # one period over the record
    q = WaveformAnalyzer.calculate_quality_stats(make_waveform(v, rate))
    assert q["noise_level"] is None  # cannot separate noise from a 1-cycle capture; must not fabricate 0.0
