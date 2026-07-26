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
    """The strongest evidence in this plan. An RC low-pass fed a square wave IS
    the `exponential` kind, which was implemented separately in 5.5.0 as a
    closed-form periodic steady state. Two independently derived implementations
    of the same physics must agree; neither is checked against a golden array."""
    tau = 1e-4
    cutoff = 1.0 / (2 * np.pi * tau)
    dut = RCLowPass(cutoff_hz=cutoff)
    warmup = dut.warmup_samples(RATE)
    n = 4_000  # four whole 1 kHz periods at 1 MSa/s

    square = synthesize(SignalSpec(kind="square", frequency=1_000.0, amplitude=1.0), RATE, n + warmup, t0=-warmup / RATE)
    filtered = dut.apply(square, RATE)[warmup:]
    closed_form = synthesize(SignalSpec(kind="exponential", frequency=1_000.0, amplitude=1.0, tau=tau), RATE, n)

    # RCLowPass.apply uses the exact zero-order-hold discretisation (alpha = 1 -
    # exp(-dt/tau)), so this is NOT a per-step approximation gap between the IIR
    # and the closed form -- measured max ~0.0198, concentrated at each square-
    # wave transition and decaying with the filter's own tau over the following
    # samples (an inherent one-sample edge-registration artifact where a
    # discretely-sampled instantaneous edge meets a causal recurrence, present
    # under any single-pole discretisation, not specific to this one). Bound
    # carries a small margin above the measured value rather than the 0.02 a
    # backward-Euler discretisation needed.
    assert np.max(np.abs(filtered - closed_form)) < 0.021
