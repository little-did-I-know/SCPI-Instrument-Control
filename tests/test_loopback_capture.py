"""The DUT applied to a mock capture, and the lead-in that makes it seamless.

RCLowPass is stateful while every generator in signal_synth is closed-form, so a
naive application would put a settling transient at the head of every
acquisition. raw_volts renders a lead-in before t0, filters across it and slices
it off -- the same fix, for the same reason, as the ringing impairment's pre-t0
window.
"""

import numpy as np
import pytest

from scpi_control.connection import MockConnection
from scpi_control.connection.mock.loopback import AwgLoopback
from scpi_control.dut import RCLowPass
from scpi_control.oscilloscope import Oscilloscope
from scpi_control.signal_synth import SignalSpec, synthesize

LEGACY_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"
RATE = 1_000_000.0


def _awg(**overrides):
    conn = MockConnection(awg_mode=True, awg_idn="Siglent Technologies,SDG1032X,SDG1XXXXX,2.01.01.37R1")
    conn.awg_channels[1].update({"enabled": True})
    conn.awg_channels[1].update(overrides)
    return conn


def _scope(source):
    conn = MockConnection(
        "mock",
        idn=LEGACY_IDN,
        channel_states={1: True, 2: False, 3: False, 4: False},
        trigger_status=["Stop"],
        sample_rate=RATE,
        timebase=1e-3,
        signals={1: source},
    )
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    return scope


def test_the_capture_is_in_steady_state_from_its_very_first_period():
    """The lead-in is what makes this true. Filtering a bare capture starts from
    y=0, so the first period would carry a settling ramp the last period does not
    -- and at 1 kHz the RC settles in ~159 samples, well inside one 1000-sample
    period, so the two windows would visibly disagree."""
    awg = _awg(function="SQUARE", frequency=1_000.0, amplitude=2.0)
    scope = _scope(AwgLoopback(awg, dut=RCLowPass(cutoff_hz=5_000.0)))
    try:
        data = scope.get_waveform(1, provenance=False)
    finally:
        scope.disconnect()
    period = 1_000  # 1 kHz at 1 MSa/s
    # atol covers one int8 code: 25 codes/div at the mock's 1 V/div default.
    np.testing.assert_allclose(data.voltage[:period], data.voltage[-period:], atol=0.05)


def test_consecutive_captures_of_a_triggered_signal_agree():
    """A transient that depended on filter state would make them differ."""
    awg = _awg(function="SQUARE", frequency=1_000.0, amplitude=2.0)
    scope = _scope(AwgLoopback(awg, dut=RCLowPass(cutoff_hz=5_000.0)))
    try:
        first = scope.get_waveform(1, provenance=False)
        second = scope.get_waveform(1, provenance=False)
    finally:
        scope.disconnect()
    np.testing.assert_array_equal(first.voltage, second.voltage)


def test_the_dut_visibly_rounds_a_square_wave():
    awg = _awg(function="SQUARE", frequency=1_000.0, amplitude=2.0)
    sharp = _scope(AwgLoopback(awg))
    try:
        unfiltered = sharp.get_waveform(1, provenance=False)
    finally:
        sharp.disconnect()
    soft = _scope(AwgLoopback(awg, dut=RCLowPass(cutoff_hz=2_000.0)))
    try:
        filtered = soft.get_waveform(1, provenance=False)
    finally:
        soft.disconnect()
    # The steepest sample-to-sample step is the direct measure of edge rounding.
    assert np.max(np.abs(np.diff(filtered.voltage))) < np.max(np.abs(np.diff(unfiltered.voltage)))


def test_no_dut_means_no_filtering():
    """A loopback without a DUT must produce exactly what the unfiltered path does."""
    awg = _awg(function="SINE", frequency=1_000.0, amplitude=2.0)
    scope = _scope(AwgLoopback(awg))
    try:
        via_loopback = scope.get_waveform(1, provenance=False)
    finally:
        scope.disconnect()
    direct = _scope(SignalSpec(kind="sine", frequency=1_000.0, amplitude=1.0))
    try:
        via_spec = direct.get_waveform(1, provenance=False)
    finally:
        direct.disconnect()
    np.testing.assert_array_equal(via_loopback.voltage, via_spec.voltage)


def test_a_filtered_square_matches_the_independently_derived_exponential_kind():
    """An RC low-pass fed a square wave IS the `exponential` kind, which was
    implemented separately in 5.5.0 as a closed-form periodic steady state. Two
    independently derived implementations of the same physics should agree on
    the bulk of the waveform; neither is checked against a golden array.

    This does NOT converge to machine precision, and that is expected rather
    than a defect to chase. RCLowPass.apply uses the exact zero-order-hold
    discretisation (alpha = 1 - exp(-dt/tau)), so the per-step approximation gap
    between the IIR and the closed form is not the story here -- switching from
    backward Euler to exact ZOH only moved the measured max from 0.020047 to
    0.019811, not the order-of-magnitude drop a per-step fix would produce.
    Per-sample inspection shows the ~2% error is concentrated at each square-
    wave transition and decays with the filter's own tau over the following
    samples (0.0198 at the edge, ~0.0072 by 100 samples later, ~0.0027 by 200 --
    matching 0.0198*exp(-k/tau) closely). A one-sample registration offset (the
    discrete square's transition landing between samples n and n+1 while the
    closed form assumes an ideal step at an exact instant) was tested directly
    and ruled out as the (sole) explanation: shifting the comparison by one
    sample in either direction does not collapse the error by an order of
    magnitude -- one shift roughly doubles it (0.0394) and the other roughly
    thirds it (0.0066), neither of which is the clean collapse a pure one-sample
    offset would produce. So the residual is treated here as a structural
    artifact of comparing a discrete causal filter against a continuous,
    idealised closed form at a signal discontinuity -- not a bug, and not
    something to tighten away by changing the filter's own sample-timing
    convention (that would be contorting production code to shrink a test
    number)."""
    tau = 1e-4
    cutoff = 1.0 / (2 * np.pi * tau)
    dut = RCLowPass(cutoff_hz=cutoff)
    warmup = dut.warmup_samples(RATE)
    n = 4_000  # four whole 1 kHz periods at 1 MSa/s

    square = synthesize(SignalSpec(kind="square", frequency=1_000.0, amplitude=1.0), RATE, n + warmup, t0=-warmup / RATE)
    filtered = dut.apply(square, RATE)[warmup:]
    closed_form = synthesize(SignalSpec(kind="exponential", frequency=1_000.0, amplitude=1.0, tau=tau), RATE, n)

    # Bound is ~2% of amplitude, with a small margin above the measured 0.019811
    # -- not slack to be tightened. Do not shrink this without re-running the
    # per-sample/shift investigation above; a tighter bound will make this test
    # flake on transition-adjacent samples for no gain in real coverage.
    assert np.max(np.abs(filtered - closed_form)) < 0.021
