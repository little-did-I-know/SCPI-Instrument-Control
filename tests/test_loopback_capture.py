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
    -- and at 1 kHz the RC settles in ~159 samples (5 tau), well inside one
    1000-sample period, so the two windows would visibly disagree."""
    awg = _awg(function="SQUARE", frequency=1_000.0, amplitude=2.0)
    scope = _scope(AwgLoopback(awg, dut=RCLowPass(cutoff_hz=5_000.0)))
    try:
        data = scope.get_waveform(1, provenance=False)
    finally:
        scope.disconnect()
    period = 1_000  # 1 kHz at 1 MSa/s
    # This bound is set by a float64 ARTIFACT, not by anything this comparison
    # is actually checking. It is signal_synth._cycle_fraction's razor's-edge
    # boundary: trigger alignment puts t0 exactly on a cycle boundary (t0 =
    # -6.000 ms for a 1 kHz square in a 14 ms window), and `(f*t) % 1.0` maps
    # the mathematically identical instant 13 periods later to 0.99999999999
    # rather than 0.0, so one sample takes the opposite rail. That artifact is
    # PRE-EXISTING in signal_synth and unrelated to the DUT -- the same flip is
    # present in the un-filtered capture. It is NOT confined to a single
    # sample, either: the RC smears it forward, and measured on this capture's
    # quantized volts (25 codes/div at the mock's 1 V/div default), 8 samples
    # tie at the 2-code peak (0.0800 V) before decaying below 1 code by
    # roughly the 90th sample. So excluding "the worst sample" buys nothing --
    # the runner-up ties the leader -- and which samples it hits at all is a
    # float64 lottery that shifts with numpy/scipy version (it already moved
    # once, when _WARMUP_TIME_CONSTANTS went 5 -> 12), so no fixed exclusion
    # count would be safe across CI. Hence a flat, wider bound rather than
    # per-sample surgery. The regression this test actually exists for is a
    # missing lead-in, measured on this capture (via a mutation that forces
    # RCLowPass.warmup_samples() to 0) at 1.0309 V pre-quantization / 1.04 V
    # quantized -- four orders of magnitude past the artifact, so 0.12 still
    # keeps an 8.6x margin under it.
    np.testing.assert_allclose(data.voltage[:period], data.voltage[-period:], atol=0.12)


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
    comparison window -- production's `warmup_samples()` alone leaves e^-12,
    about 6.1e-6 of the step, of the initial y=0 transient un-settled (fine
    there: it is under 0.05 LSB of the finest grid the mock quantizes to, the
    modern WORD path's 6400 codes/div -- see dut._WARMUP_TIME_CONSTANTS), so
    this test renders more (see `lead_in` below) to push that floor far below
    the precision being asserted here."""
    tau = 1e-4
    cutoff = 1.0 / (2 * np.pi * tau)
    dut = RCLowPass(cutoff_hz=cutoff)
    warmup = dut.warmup_samples(RATE)
    n = 4_000  # four whole 1 kHz periods at 1 MSa/s

    # At least 3x warmup_samples(), per the above, but ALSO rounded up to a whole
    # number of the signal's own periods and rendered from t0=0.0 rather than
    # t0=-lead_in/RATE. Both matter, and skipping either reintroduces a full
    # spurious error unrelated to the filter:
    #   - The lead-in must satisfy TWO INDEPENDENT conditions, and no raw
    #     multiple of warmup_samples() reliably satisfies both:
    #       (a) WHOLE PERIODS. `closed_form` always starts high at t=0, so a
    #           fractional-period lead-in hands the filter a square wave in the
    #           wrong phase; the comparison then picks up a phase-inversion term
    #           of order 2 * amplitude, which looks like a total failure of the
    #           filter but is pure bookkeeping.
    #       (b) ENOUGH TIME CONSTANTS. Whole-period alignment removes ONLY that
    #           ~2.0 term. What is left is the SETTLING FLOOR -- the un-decayed
    #           remainder of the initial y=0 transient, ~e^(-lead_in*dt/tau) --
    #           which alignment does nothing about.
    #     Measured as max|filtered - closed_form| across multiples of
    #     warmup_samples(), against this test's 1e-6 bound. With the older
    #     5-time-constant warmup (500 samples = 0.5 period each):
    #         1x 1.98        2x 4.479e-05   3x 1.973
    #         4x 2.034e-09   5x 1.973       6x 9.27e-14
    #     -- only 2x and 4x are whole periods (1 and 2), and 2x STILL FAILS: one
    #     period is just 10 tau, e^-10 = 4.5e-5, 45x over the bound. Condition
    #     (a) alone was never sufficient. With today's 12-time-constant warmup
    #     (1200 samples = 1.2 periods each) the multiples land differently again:
    #         1x 1.718   2x 1.950   3x 1.950
    #         4x 1.718   5x 7.94e-15   6x 1.718
    #     -- now only 5x is whole-period (6 periods = 60 tau) at all.
    #     Hence rounding up to whole periods below rather than trusting any fixed
    #     multiple: that makes (a) true by construction, and >=3x warmup (>=36
    #     tau) makes (b) true with enormous margin. As built it comes out at 4
    #     periods = 4000 samples = 40 tau, measuring 7.9e-15 -- machine
    #     precision, not a settling floor at all.
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

    # Measured 7.9e-15 with the correct construction above. For comparison,
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


def test_a_captured_noise_trace_has_roughly_the_requested_peak_to_peak():
    """The one kind where `SignalSpec.amplitude` is a standard deviation rather
    than a peak, so the Vpp->peak halving every other kind needs is a unit error
    here -- it captured 7.560 Vpp at sigma = 1.006 V for a 2.0 Vpp request. The
    mapping takes Vpp as the +/-3 sigma span, so sigma is asserted tightly (it is
    exactly what the mapping sets, and 14,000 samples estimate it well), while
    the trace's peak-to-peak is asserted loosely: the extreme of N Gaussian
    samples is itself a random variable that grows with N, and this spec is
    unseeded. Measured over 12 unseeded captures: sigma 0.329 to 0.336,
    peak-to-peak 2.44 to 2.76."""
    awg_conn = _awg(function="NOISE", amplitude=2.0)
    scope = _scope(AwgLoopback(awg_conn))
    try:
        data = scope.get_waveform(1, provenance=False)
    finally:
        scope.disconnect()
    assert np.std(data.voltage) == pytest.approx(2.0 / 6.0, abs=0.03)
    # Wide enough to survive the randomness, narrow enough that the pre-fix
    # 7.56 Vpp (and an unconverted 2.0-as-sigma, ~15 Vpp) both fail.
    assert 1.5 < np.ptp(data.voltage) < 4.0
