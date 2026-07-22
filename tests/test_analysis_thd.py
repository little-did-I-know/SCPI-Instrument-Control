"""THD reads each harmonic at its own rounded bin, robust to an off-bin fundamental."""

from types import SimpleNamespace

import numpy as np

from scpi_control.analysis import FFTAnalyzer


def test_thd_off_bin_fundamental():
    fs, n = 1e6, 10000
    t = np.arange(n) / fs
    f0 = 10040.0  # 0.4 bins off-center (df = 100 Hz)
    v = np.sin(2 * np.pi * f0 * t) + 0.2 * np.sin(2 * np.pi * 3 * f0 * t) + 0.1 * np.sin(2 * np.pi * 5 * f0 * t)
    wf = SimpleNamespace(voltage=v, time=t)
    analyzer = FFTAnalyzer()
    result = analyzer.compute_fft(wf, window="hanning", output_db=False, detrend=True)
    thd = FFTAnalyzer.calculate_thd(result, f0, num_harmonics=5)
    # true THD = sqrt(0.2^2 + 0.1^2) = 22.36 %
    assert thd is not None
    assert 18.0 < thd < 27.0


def test_thd_of_waveform_is_none_for_pure_noise():
    rng = np.random.default_rng(2)
    fs, n = 1e6, 4000
    t = np.arange(n) / fs
    noise = SimpleNamespace(voltage=rng.standard_normal(n), time=t)
    assert FFTAnalyzer.thd_of_waveform(noise) is None
    tone = SimpleNamespace(voltage=np.sin(2 * np.pi * 5000 * t) + 0.2 * np.sin(2 * np.pi * 15000 * t), time=t)
    assert FFTAnalyzer.thd_of_waveform(tone) is not None
