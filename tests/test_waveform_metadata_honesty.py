"""The waveform model must never invent instrument metadata.

`__post_init__` may compute what the arrays determine (record_length from the
array's length, sample_rate from the time axis). It must not invent what depends
on the scope's display geometry: timebase needs a horizontal division count and
voltage_scale a vertical one, and neither is present in the samples. The old code
assumed 14 and 8 -- Siglent's grid -- inside a library that also drives Tektronix
and LeCroy, which use 10.
"""

import numpy as np
import pytest

from scpi_control.math_channel import MathOperations
from scpi_control.waveform import WaveformData


def make(n=100, rate=1e6):
    t = np.arange(n) / rate
    return t, np.sin(2 * np.pi * 10_000 * t)


def test_timebase_is_none_when_no_instrument_reported_one():
    t, v = make()
    assert WaveformData(time=t, voltage=v, channel=1).timebase is None


def test_voltage_scale_is_none_when_no_instrument_reported_one():
    t, v = make()
    assert WaveformData(time=t, voltage=v, channel=1).voltage_scale is None


def test_flat_trace_gets_no_invented_voltage_scale():
    """The old code handed a flat trace a bare 1.0 V/div -- invention, not measurement."""
    t = np.arange(10) / 1e6
    assert WaveformData(time=t, voltage=np.zeros(10), channel=1).voltage_scale is None


def test_explicit_instrument_values_survive():
    """What the scope reports must pass through untouched."""
    t, v = make()
    wf = WaveformData(time=t, voltage=v, channel=1, timebase=1e-3, voltage_scale=0.5)
    assert wf.timebase == pytest.approx(1e-3)
    assert wf.voltage_scale == pytest.approx(0.5)


def test_record_length_is_still_derived():
    """The data IS its length -- a measurement, so it stays."""
    t, v = make(n=64)
    assert WaveformData(time=t, voltage=v, channel=1).record_length == 64


def test_sample_rate_is_still_derived_from_the_time_axis():
    """dt is IN the data -- a measurement, so it stays."""
    t, v = make(n=100, rate=1e6)
    assert WaveformData(time=t, voltage=v, channel=1).sample_rate == pytest.approx(1e6)


def test_shape_mismatch_still_raises():
    with pytest.raises(ValueError):
        WaveformData(time=np.arange(10), voltage=np.ones(9), channel=1)


def test_math_channel_propagates_real_instrument_values():
    t, v = make()
    src = WaveformData(time=t, voltage=v, channel=1, timebase=1e-3, voltage_scale=0.5)
    result = MathOperations._create_result_waveform(src, v * 2)
    assert result.timebase == pytest.approx(1e-3)
    assert result.voltage_scale == pytest.approx(0.5)


def test_math_channel_invents_nothing_when_the_source_has_nothing():
    t, v = make()
    src = WaveformData(time=t, voltage=v, channel=1)
    result = MathOperations._create_result_waveform(src, v * 2)
    assert result.timebase is None
    assert result.voltage_scale is None


def test_math_channel_still_derives_sample_rate():
    t, v = make(rate=1e6)
    src = WaveformData(time=t, voltage=v, channel=1)
    result = MathOperations._create_result_waveform(src, v * 2)
    assert result.sample_rate == pytest.approx(1e6)


def test_dead_metadata_fields_are_gone():
    """`source` and `description` were write-only: set by a manual script and a few
    tests, read by nothing. Removing them leaves the library type as exactly the
    core the report type shares, which is what lets the report type subclass it."""
    t, v = make()
    with pytest.raises(TypeError):
        WaveformData(time=t, voltage=v, channel=1, source="Test")
    with pytest.raises(TypeError):
        WaveformData(time=t, voltage=v, channel=1, description="1kHz Sine")


def test_the_canonical_field_set_is_exactly_the_shared_core():
    from dataclasses import fields

    assert [f.name for f in fields(WaveformData)] == [
        "time",
        "voltage",
        "channel",
        "sample_rate",
        "record_length",
        "timebase",
        "voltage_scale",
        "voltage_offset",
        "provenance",
    ]
