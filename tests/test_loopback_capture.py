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


def test_the_capture_has_no_settling_transient_at_its_head():
    """The load-bearing test. Without the lead-in the first samples ramp up from
    zero, so the head of the capture would differ wildly from its body."""
    awg = _awg(function="SQUARE", frequency=1_000.0, amplitude=2.0)
    scope = _scope(AwgLoopback(awg, dut=RCLowPass(cutoff_hz=5_000.0)))
    try:
        data = scope.get_waveform(1, provenance=False)
    finally:
        scope.disconnect()
    head = data.voltage[:2_000]
    body = data.voltage[6_000:8_000]
    assert np.ptp(head) == pytest.approx(np.ptp(body), rel=0.15), "the head must already be settled"


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

    # Tolerance is the IIR's first-order discretisation error at tau/dt = 100.
    # Report the measured maximum in the task report -- if it is far below this,
    # tighten the bound rather than leaving slack.
    assert np.max(np.abs(filtered - closed_form)) < 0.02
