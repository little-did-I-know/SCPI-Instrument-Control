"""The report THD path and the webapp THD path agree for the same capture."""

from types import SimpleNamespace

import numpy as np

from scpi_control.analysis import FFTAnalyzer
from scpi_control.report_generator.models.report_data import WaveformData
from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer


def test_report_and_webapp_thd_agree():
    fs, n = 1e6, 10000
    t = np.arange(n) / fs
    f0 = 5000.0
    v = np.sin(2 * np.pi * f0 * t) + 0.2 * np.sin(2 * np.pi * 3 * f0 * t)  # ~20 % THD
    report_wf = WaveformData(channel="C1", time=t, voltage=v, sample_rate=fs, record_length=n)
    webapp_wf = SimpleNamespace(voltage=v, time=t)

    report_thd = WaveformAnalyzer.calculate_thd(report_wf)
    webapp_thd = FFTAnalyzer.thd_of_waveform(webapp_wf)

    assert report_thd is not None and webapp_thd is not None
    assert abs(report_thd - webapp_thd) < 1e-6
