"""_is_noise is O(n) and behaviorally identical to the old O(n^2) autocorrelation."""

import time
import warnings

import numpy as np
import pytest

from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer


def _reference_is_noise(v: np.ndarray) -> bool:
    """The ORIGINAL O(n^2) implementation, kept as the behavioral oracle.

    The optimized _is_noise must return the same boolean as this for every input.
    """
    v_normalized = v - np.mean(v)
    autocorr = np.correlate(v_normalized, v_normalized, mode="full")
    autocorr = autocorr[len(autocorr) // 2 :]
    with np.errstate(invalid="ignore", divide="ignore"):
        autocorr = autocorr / autocorr[0]
    lag = max(1, len(autocorr) // 10)
    if lag < len(autocorr):
        return bool(autocorr[lag] < 0.3)
    return False


def _fixtures():
    rng = np.random.default_rng(0)
    t = np.linspace(0, 1e-3, 5000, endpoint=False)
    return {
        "sine": np.sin(2 * np.pi * 1000 * t),
        "square": np.sign(np.sin(2 * np.pi * 1000 * t)),
        "ramp": np.linspace(-1.0, 1.0, 5000),
        "white_noise": rng.standard_normal(5000),
        "dc": np.full(5000, 2.5),
        "tiny1": np.array([3.0]),
        "tiny2": np.array([1.0, -1.0]),
        "tiny15": rng.standard_normal(15),
    }


@pytest.mark.parametrize("name", list(_fixtures().keys()))
def test_matches_reference(name):
    v = _fixtures()[name]
    # Silence the reference's divide warning on the constant fixture; we only
    # care that the OPTIMIZED function agrees on the boolean.
    with np.errstate(invalid="ignore", divide="ignore"):
        expected = _reference_is_noise(v)
    assert WaveformAnalyzer._is_noise(v) == expected


def test_sine_is_not_noise():
    t = np.linspace(0, 1e-3, 5000, endpoint=False)
    assert WaveformAnalyzer._is_noise(np.sin(2 * np.pi * 1000 * t)) is False


def test_white_noise_is_noise():
    rng = np.random.default_rng(1)
    assert WaveformAnalyzer._is_noise(rng.standard_normal(5000)) is True


def test_constant_is_not_noise_and_raises_no_warning():
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any RuntimeWarning becomes a test failure
        assert WaveformAnalyzer._is_noise(np.full(4000, 2.5)) is False


def test_large_input_is_fast():
    rng = np.random.default_rng(2)
    v = rng.standard_normal(1_000_000)
    start = time.perf_counter()
    WaveformAnalyzer._is_noise(v)
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0, f"_is_noise took {elapsed:.2f}s on 1M samples (O(n^2) regression?)"
