"""Peaks below 0 dB (small signals) must still be found in dB mode."""

import numpy as np

from scpi_control.analysis import FFTResult


def test_get_peak_frequency_finds_sub_zero_db_peak():
    freq = np.array([0.0, 10.0, 20.0, 30.0, 40.0, 50.0])
    mag_db = np.array([-40.0, -30.0, -12.0, -30.0, -35.0, -38.0])  # local max at 20 Hz, below 0 dB
    result = FFTResult(frequency=freq, magnitude=mag_db, phase=np.zeros(6), window="hann", sample_rate=100.0, magnitude_db=True)
    peaks = result.get_peak_frequency(1)
    assert peaks
    assert abs(peaks[0][0] - 20.0) < 1e-9
