"""_is_noise classifies noise vs periodic signals by spectral concentration.

A periodic signal (sine, square, ramp) concentrates energy in a dominant
spectral peak; noise spreads it. _is_noise is True only for the latter.
"""

import time
import types
import warnings

import numpy as np

from scpi_control.report_generator.utils.waveform_analyzer import SignalType, WaveformAnalyzer

SR = 1_000_000
T = np.arange(20_000) / SR


def test_white_noise_is_noise():
    rng = np.random.default_rng(0)
    assert WaveformAnalyzer._is_noise(rng.standard_normal(20_000)) is True


def test_sine_is_not_noise():
    assert WaveformAnalyzer._is_noise(np.sin(2 * np.pi * 1000 * T)) is False


def test_single_period_square_is_not_noise():
    t = np.arange(1000) / SR  # exactly one 1 kHz period
    assert WaveformAnalyzer._is_noise(np.sign(np.sin(2 * np.pi * 1000 * t))) is False


def test_multi_period_square_is_not_noise():
    # 5 periods in the record puts the old 10%-of-record lag near a half-period,
    # where a square is anti-correlated -- the exact case the old heuristic called
    # "noise" (this is the shape of the real SDS824X HD capture).
    square = np.sign(np.sin(2 * np.pi * 5 * np.linspace(0.0, 1.0, 20_000, endpoint=False)))
    assert WaveformAnalyzer._is_noise(square) is False


def test_sawtooth_is_not_noise():
    saw = (np.mod(np.arange(20_000), 200) / 200.0).astype(float)
    assert WaveformAnalyzer._is_noise(saw) is False


def test_sine_in_moderate_noise_is_not_noise():
    rng = np.random.default_rng(1)
    v = np.sin(2 * np.pi * 1000 * T) + 0.3 * rng.standard_normal(T.size)
    assert WaveformAnalyzer._is_noise(v) is False


def test_constant_is_not_noise_and_raises_no_warning():
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any RuntimeWarning fails the test
        assert WaveformAnalyzer._is_noise(np.full(4000, 2.5)) is False


def test_empty_and_short_are_not_noise():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert WaveformAnalyzer._is_noise(np.array([])) is False
        assert WaveformAnalyzer._is_noise(np.array([1.0, -1.0, 1.0])) is False  # n < 4


def test_detect_signal_type_empty_is_unknown():
    waveform = types.SimpleNamespace(voltage=np.array([]))
    assert WaveformAnalyzer.detect_signal_type(waveform) == (SignalType.UNKNOWN, 0.0)


def test_large_input_is_fast():
    rng = np.random.default_rng(2)
    v = rng.standard_normal(1_000_000)
    start = time.perf_counter()
    WaveformAnalyzer._is_noise(v)
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0, f"_is_noise took {elapsed:.2f}s on 1M samples"
