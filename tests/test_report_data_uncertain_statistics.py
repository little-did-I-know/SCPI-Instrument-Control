"""WaveformData.uncertain_statistics: additive storage for Quantity-valued
stats, alongside the existing plain-float .statistics dict.

Requires the `uncertainty` extra (to build a real Quantity to attach).
"""

import numpy as np
import pytest

pytest.importorskip("pint")
pytest.importorskip("uncertainties")

from scpi_control.quantities import quantity
from scpi_control.report_generator.models.report_data import WaveformData


def _waveform():
    n, rate = 100, 1e6
    t = np.arange(n) / rate
    v = np.zeros(n)
    return WaveformData(channel="C1", time=t, voltage=v, sample_rate=rate, record_length=n)


def test_uncertain_statistics_defaults_to_none():
    assert _waveform().uncertain_statistics is None


def test_to_dict_omits_uncertain_statistics_when_unset():
    data = _waveform().to_dict()
    assert "uncertain_statistics" not in data


def test_to_dict_serializes_a_quantity_with_uncertainty():
    wf = _waveform()
    wf.uncertain_statistics = {"vpp": quantity(1.234, "V", uncertainty=0.012)}
    data = wf.to_dict()
    assert data["uncertain_statistics"] == {"vpp": {"value": pytest.approx(1.234), "uncertainty": pytest.approx(0.012), "unit": "V"}}


def test_to_dict_serializes_a_quantity_with_no_uncertainty():
    wf = _waveform()
    wf.uncertain_statistics = {"frequency": quantity(1000.0, "Hz")}
    data = wf.to_dict()
    assert data["uncertain_statistics"] == {"frequency": {"value": pytest.approx(1000.0), "uncertainty": None, "unit": "Hz"}}
