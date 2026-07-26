"""The RC low-pass standing in for a device under test.

Its defining property is the one the tests lead with: at the cutoff frequency a
first-order response is down 3 dB, i.e. 1/sqrt(2). Everything else follows from
that. The filter is STATEFUL, which is why warmup_samples exists -- see the
module docstring for why that matters to a mock that must produce seamless
consecutive captures.
"""

import numpy as np
import pytest

from scpi_control import exceptions
from scpi_control.dut import RCLowPass
from scpi_control.signal_synth import SignalSpec, synthesize

RATE = 1_000_000.0


def _steady_amplitude(filtered, warmup):
    """Peak amplitude after the filter has settled, measured past the lead-in."""
    settled = filtered[warmup:]
    return (settled.max() - settled.min()) / 2.0


def _filtered_sine(cutoff_hz, signal_hz, amplitude=1.0):
    dut = RCLowPass(cutoff_hz=cutoff_hz)
    warmup = dut.warmup_samples(RATE)
    n = warmup + int(RATE / signal_hz) * 20  # 20 whole periods past the lead-in
    samples = synthesize(SignalSpec(kind="sine", frequency=signal_hz, amplitude=amplitude), RATE, n)
    return _steady_amplitude(dut.apply(samples, RATE), warmup)


def test_at_the_cutoff_the_response_is_down_three_db():
    """The defining property of a first-order low-pass: 1/sqrt(2) at f_c."""
    assert _filtered_sine(cutoff_hz=1_000.0, signal_hz=1_000.0) == pytest.approx(1.0 / np.sqrt(2.0), rel=0.02)


def test_well_below_the_cutoff_the_signal_passes():
    assert _filtered_sine(cutoff_hz=10_000.0, signal_hz=100.0) == pytest.approx(1.0, rel=0.01)


def test_well_above_the_cutoff_the_signal_is_attenuated():
    """First order rolls off 20 dB/decade, so a decade up is ~1/10."""
    assert _filtered_sine(cutoff_hz=1_000.0, signal_hz=10_000.0) == pytest.approx(0.1, rel=0.1)


def test_dc_passes_unchanged():
    dut = RCLowPass(cutoff_hz=1_000.0)
    warmup = dut.warmup_samples(RATE)
    samples = synthesize(SignalSpec(kind="dc", offset=2.5), RATE, warmup + 1_000)
    assert dut.apply(samples, RATE)[-1] == pytest.approx(2.5, rel=1e-3)


def test_warmup_scales_with_the_time_constant_and_the_sample_rate():
    slow = RCLowPass(cutoff_hz=100.0)
    fast = RCLowPass(cutoff_hz=10_000.0)
    assert slow.warmup_samples(RATE) > fast.warmup_samples(RATE)
    assert slow.warmup_samples(2 * RATE) == pytest.approx(2 * slow.warmup_samples(RATE), rel=0.01)


def test_the_warmup_window_is_capped():
    """A near-zero cutoff would otherwise make tau -- and the lead-in -- unbounded,
    the same backstop signal_synth applies to the ringing kernel."""
    assert RCLowPass(cutoff_hz=1e-9).warmup_samples(RATE) == 200_000


def test_the_time_constant_matches_the_cutoff():
    assert RCLowPass(cutoff_hz=1_000.0).tau == pytest.approx(1.0 / (2 * np.pi * 1_000.0))


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
def test_an_invalid_cutoff_is_rejected(bad):
    with pytest.raises(exceptions.InvalidParameterError):
        RCLowPass(cutoff_hz=bad)


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan")])
def test_an_invalid_sample_rate_is_rejected(bad):
    with pytest.raises(exceptions.InvalidParameterError):
        RCLowPass(cutoff_hz=1_000.0).warmup_samples(bad)
