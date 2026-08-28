"""WaveformAnalyzer.compute_statistical_quantity: mean +/- stddev across N
repeated captures of the same measurement, as a unit-aware Quantity.

Pure-CPU, no instrument. Requires the `uncertainty` extra.
"""

import numpy as np
import pytest

pytest.importorskip("pint")
pytest.importorskip("uncertainties")

from scpi_control.exceptions import InvalidParameterError
from scpi_control.report_generator.models.report_data import WaveformData
from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer


def _stub_waveform(stat_value):
    """A minimal WaveformData with .statistics pre-populated -- this test
    exercises the aggregation, not .analyze() itself."""
    n, rate = 100, 1e6
    t = np.arange(n) / rate
    v = np.zeros(n)
    wf = WaveformData(channel="C1", time=t, voltage=v, sample_rate=rate, record_length=n)
    wf.statistics = {"vpp": stat_value}
    return wf


def test_mean_and_stddev_match_a_hand_computed_example():
    # values = [2.0, 4.0]: mean 3.0, sample stddev (ddof=1) sqrt(2) = 1.4142135623730951
    waveforms = [_stub_waveform(2.0), _stub_waveform(4.0)]
    q = WaveformAnalyzer.compute_statistical_quantity(waveforms, "vpp")
    assert q.magnitude.nominal_value == pytest.approx(3.0)
    assert q.magnitude.std_dev == pytest.approx(1.4142135623730951)
    assert str(q.units) == "volt"


def test_four_repeated_captures():
    # values = [1,2,3,4]: mean 2.5, sample stddev (ddof=1) = 1.2909944487358056
    waveforms = [_stub_waveform(v) for v in (1.0, 2.0, 3.0, 4.0)]
    q = WaveformAnalyzer.compute_statistical_quantity(waveforms, "vpp")
    assert q.magnitude.nominal_value == pytest.approx(2.5)
    assert q.magnitude.std_dev == pytest.approx(1.2909944487358056)


def test_fewer_than_two_waveforms_raises():
    with pytest.raises(InvalidParameterError, match="at least 2"):
        WaveformAnalyzer.compute_statistical_quantity([_stub_waveform(1.0)], "vpp")


def test_unknown_stat_name_raises():
    waveforms = [_stub_waveform(1.0), _stub_waveform(2.0)]
    with pytest.raises(InvalidParameterError, match="Unknown statistic"):
        WaveformAnalyzer.compute_statistical_quantity(waveforms, "not_a_real_stat")


def test_missing_stat_on_one_waveform_raises():
    wf1 = _stub_waveform(1.0)
    wf2 = _stub_waveform(2.0)
    wf2.statistics = {}  # 'vpp' never computed for this one
    with pytest.raises(InvalidParameterError, match="no 'vpp' statistic"):
        WaveformAnalyzer.compute_statistical_quantity([wf1, wf2], "vpp")
