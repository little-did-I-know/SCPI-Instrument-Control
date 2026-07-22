"""Welch/spectrogram must accept the module's public window names on modern SciPy."""

from types import SimpleNamespace

import numpy as np

from scpi_control.analysis import FFTAnalyzer


def _sine():
    fs, n = 1e6, 10000
    t = np.arange(n) / fs
    return SimpleNamespace(voltage=np.sin(2 * np.pi * 50_000 * t), time=t)


def test_power_spectrum_returns_result():
    assert FFTAnalyzer().compute_power_spectrum(_sine()) is not None


def test_spectrogram_returns_result():
    assert FFTAnalyzer().compute_spectrogram(_sine()) is not None
