"""The DUT applied to a mock capture, and the lead-in that makes it seamless.

RCLowPass is stateful while every generator in signal_synth is closed-form, so a
naive application would put a settling transient at the head of every
acquisition. raw_volts renders a lead-in before t0, filters across it and slices
it off -- the same fix, for the same reason, as the ringing impairment's pre-t0
window.
"""

import math

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
    independently derived implementations of the same physics must agree;
    neither is checked against a golden array.

    Now that RCLowPass.apply is the exact, strictly-proper zero-order-hold
    discretisation (see dut.py), the two agree to near machine precision. The
    only remaining floor is how much lead-in THIS TEST renders before the
    comparison window -- production's `warmup_samples()` alone leaves ~0.0067 V
    of the initial y=0 transient un-settled (fine there: it's below the mock's
    ~0.04 V int8 quantization step), so this test renders more (see `lead_in`
    below) to push that floor far below the precision being asserted here."""
    tau = 1e-4
    cutoff = 1.0 / (2 * np.pi * tau)
    dut = RCLowPass(cutoff_hz=cutoff)
    warmup = dut.warmup_samples(RATE)
    n = 4_000  # four whole 1 kHz periods at 1 MSa/s

    # At least 3x warmup_samples(), per the above, but ALSO rounded up to a whole
    # number of the signal's own periods and rendered from t0=0.0 rather than
    # t0=-lead_in/RATE. Both matter, and skipping either reintroduces a full
    # spurious error unrelated to the filter:
    #   - A non-whole-period lead-in can leave the square wave in the WRONG
    #     phase relative to `closed_form` (which always starts high at t=0),
    #     producing a phase-inverted ~2x amplitude mismatch that looks like a
    #     total failure of the filter when it is actually a bookkeeping error
    #     (verified: 1x and 3x warmup here are 0.5 and 1.5 periods -- both
    #     wrong; 2x and 4x are 1 and 2 whole periods -- both fine).
    #   - Passing t0 as a pre-computed `-lead_in / RATE` looks equivalent to
    #     starting the extended array at t0=0.0 and slicing off `lead_in`
    #     samples, but is NOT bit-for-bit equivalent: synthesize() computes
    #     `t0 + arange(n)/sample_rate`, so a subtraction-based t0 accumulates a
    #     DIFFERENT rounding error than `closed_form`'s own t=0-based times get,
    #     in exactly the "razor's-edge boundary comparison" way signal_synth.py's
    #     ringing path already documents and avoids (t0 + (index-decay_len)/sr,
    #     NOT (t0-decay_len/sr)+index/sr). Verified: with t0=-lead_in/RATE, some
    #     lead-in lengths misregister exactly one transition by a full sample,
    #     producing a spurious ~0.02 error that looks like a filter defect but
    #     disappears entirely once t0=0.0 is used instead.
    period_samples = RATE / 1_000.0
    periods_needed = math.ceil((3 * warmup) / period_samples)
    lead_in = int(periods_needed * period_samples)

    square = synthesize(SignalSpec(kind="square", frequency=1_000.0, amplitude=1.0), RATE, n + lead_in, t0=0.0)
    filtered = dut.apply(square, RATE)[lead_in:]
    closed_form = synthesize(SignalSpec(kind="exponential", frequency=1_000.0, amplitude=1.0, tau=tau), RATE, n)

    # Measured 2.0e-9 with the correct construction above. For comparison,
    # against this SAME construction: backward Euler (the pre-fix discretisation)
    # measures 3.5e-3, and a tau mistuned by 2% measures 1.4e-2 -- both several
    # orders of magnitude over this bound, so this test would catch either
    # regression.
    assert np.max(np.abs(filtered - closed_form)) < 1e-6


def test_writing_to_the_awg_changes_the_next_scope_capture():
    """The whole feature in one test: two instruments, one cable, a SCPI write on
    one visibly changing what the other captures."""
    from scpi_control.function_generator import FunctionGenerator

    awg_conn = _awg(function="SINE", frequency=1_000.0, amplitude=2.0)
    awg = FunctionGenerator("mock", connection=awg_conn)
    awg.connect()
    scope = _scope(AwgLoopback(awg_conn))
    try:
        as_sine = scope.get_waveform(1, provenance=False)
        awg_conn.write("C1:BSWV WVTP,SQUARE")
        as_square = scope.get_waveform(1, provenance=False)
    finally:
        scope.disconnect()
        awg.disconnect()

    # A square spends its time at the rails; a sine sweeps through the middle.
    # The fraction of samples near an extreme separates them without relying on
    # any particular amplitude.
    def rail_fraction(v):
        return float(np.mean(np.abs(v) > 0.8 * np.max(np.abs(v))))

    assert rail_fraction(as_square.voltage) > 2 * rail_fraction(as_sine.voltage)


def test_turning_the_output_off_flattens_the_capture():
    awg_conn = _awg(function="SINE", frequency=1_000.0, amplitude=2.0)
    scope = _scope(AwgLoopback(awg_conn))
    try:
        driven = scope.get_waveform(1, provenance=False)
        awg_conn.awg_channels[1]["enabled"] = False
        idle = scope.get_waveform(1, provenance=False)
    finally:
        scope.disconnect()
    assert np.ptp(driven.voltage) > 1.5
    assert np.ptp(idle.voltage) < 0.1


def test_the_captured_amplitude_is_the_awg_setting_not_double_it():
    """End-to-end guard on the Vpp conversion: an AMP of 2.0 Vpp must arrive as a
    2.0 V peak-to-peak trace, not 4.0."""
    awg_conn = _awg(function="SINE", frequency=1_000.0, amplitude=2.0)
    scope = _scope(AwgLoopback(awg_conn))
    try:
        data = scope.get_waveform(1, provenance=False)
    finally:
        scope.disconnect()
    assert np.ptp(data.voltage) == pytest.approx(2.0, abs=0.2)
