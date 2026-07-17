"""Fixtures shared across the test suite."""

import numpy as np
import pytest

from scpi_control.report_generator.models.report_data import WaveformData


@pytest.fixture
def bursty_waveform():
    """A sine carrying 20 multi-sample spikes -- more real transients than the
    tools will show, so truncation paths are reachable.

    The spikes are several samples wide because detect_transients discards any
    region shorter than 0.1% of the capture; single-sample spikes never clear
    that, however many you add. Function-scoped: detect_regions mutates
    waveform.regions, so each test needs its own.
    """
    n, rate = 4000, 1e6
    t = np.arange(n) / rate
    v = np.sin(2 * np.pi * 10_000 * t)
    for start in np.linspace(50, n - 100, 20).astype(int):
        v[start : start + 6] += 8.0
    return WaveformData(channel="C1", time=t, voltage=v, sample_rate=rate, record_length=n)
