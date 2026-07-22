"""vamp is the scope-standard amplitude (Vtop - Vbase), offset-independent."""
import numpy as np

from scpi_control.report_generator.models.report_data import WaveformData
from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer


def make_waveform(voltage, rate=1e6):
    n = len(voltage)
    return WaveformData(channel="C1", time=np.arange(n) / rate, voltage=voltage, sample_rate=rate, record_length=n)


def test_vamp_is_offset_independent_amplitude():
    t = np.arange(4000) / 1e6
    sine = np.sin(2 * np.pi * 1000 * t)  # 2 Vpp, centered at 0
    centered = WaveformAnalyzer.calculate_amplitude_stats(make_waveform(sine))
    offset = WaveformAnalyzer.calculate_amplitude_stats(make_waveform(sine + 2.5))
    # Both describe the same 2 Vpp signal, so vamp must be the same and ~2.0, not the midpoint.
    assert abs(centered["vamp"] - offset["vamp"]) < 1e-6
    assert abs(centered["vamp"] - 2.0) < 0.05
