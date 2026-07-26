"""The four kind-specific generators: chirp, exponential, pulse, multitone.

Each is a closed-form function of the absolute time array, because stream()
re-enters synthesize() per chunk with a new t0 and the ringing impairment renders
samples before t0. A generator that carried state across a call, or that reset a
phase at a boundary, would show up as a discontinuity -- which is what
test_streamed_chunks_reassemble_into_one_synthesize_call exists to catch.
"""

import dataclasses
import itertools

import numpy as np
import pytest

from scpi_control import exceptions
from scpi_control.signal_synth import PERIODIC_KINDS, SignalSpec, stream, synthesize

RATE = 1_000_000.0


def test_kind_parameter_fields_default_to_the_documented_values():
    spec = SignalSpec()
    assert spec.end_frequency == 10_000.0
    assert spec.sweep_time == 0.01
    assert spec.sweep_log is False
    assert spec.tau == 1e-4
    assert spec.pulse_width == 2e-4
    assert spec.edge_time == 1e-5
    assert spec.harmonics == (0.1, 0.05)


def test_the_new_fields_are_appended_and_do_not_move_the_existing_ones():
    """The non-breaking guarantee: positional construction of every pre-existing
    field must still bind to the same field. Inserting a new field mid-class --
    where several of them read better -- would silently re-map every positional
    caller."""
    spec = SignalSpec("square", 500.0, 2.0, 0.5, 0.1, 0.25, 0.01, 3)
    assert spec.kind == "square"
    assert spec.frequency == 500.0
    assert spec.amplitude == 2.0
    assert spec.offset == 0.5
    assert spec.phase == 0.1
    assert spec.duty == 0.25
    assert spec.noise_rms == 0.01
    assert spec.seed == 3
    names = [f.name for f in dataclasses.fields(SignalSpec)]
    assert names[:14] == [
        "kind",
        "frequency",
        "amplitude",
        "offset",
        "phase",
        "duty",
        "noise_rms",
        "seed",
        "drift_amplitude",
        "drift_frequency",
        "glitch_rate",
        "glitch_amplitude",
        "ringing_frequency",
        "ringing_damping",
    ]
    assert names[14:] == ["end_frequency", "sweep_time", "sweep_log", "tau", "pulse_width", "edge_time", "harmonics"]


def _bin_amplitudes(samples, rate):
    """Single-sided amplitude per FFT bin. Only valid for an integer number of
    cycles in the buffer, which every caller below arranges -- otherwise leakage
    spreads a tone across neighbouring bins and the ratios stop being exact."""
    return np.abs(np.fft.rfft(samples)) * 2.0 / len(samples)


def test_multitone_bin_amplitudes_match_the_harmonics_tuple():
    rate, n, freq = 100_000.0, 100_000, 1_000.0  # 1 s of a 1 kHz tone -> 1 Hz bins, 1000 whole cycles
    harmonics = (0.25, 0.125, 0.0625)
    spec = SignalSpec(kind="multitone", frequency=freq, amplitude=2.0, harmonics=harmonics)
    mag = _bin_amplitudes(synthesize(spec, rate, n), rate)
    bin_hz = rate / n
    assert mag[int(freq / bin_hz)] == pytest.approx(2.0, rel=1e-6)
    for order, relative in enumerate(harmonics, start=2):
        assert mag[int(order * freq / bin_hz)] == pytest.approx(2.0 * relative, rel=1e-6)


def test_multitone_amplitude_is_the_fundamentals_not_the_peaks():
    """Documented, and load-bearing for THD: normalizing the sum to `amplitude`
    would make a multitone's THD depend on its harmonic set."""
    spec = SignalSpec(kind="multitone", frequency=1_000.0, amplitude=1.0, harmonics=(0.5,))
    samples = synthesize(spec, RATE, 2_000)
    assert np.max(samples) > 1.0


def test_multitone_with_no_harmonics_is_a_sine():
    plain = synthesize(SignalSpec(kind="sine", frequency=1_000.0), RATE, 2_000)
    empty = synthesize(SignalSpec(kind="multitone", frequency=1_000.0, harmonics=()), RATE, 2_000)
    np.testing.assert_allclose(empty, plain, atol=1e-15)


def test_multitone_is_periodic_and_triggerable_in_the_mock():
    assert "multitone" in PERIODIC_KINDS


@pytest.mark.parametrize(
    "harmonics",
    [
        (-0.1,),  # negative relative amplitude
        (0.1, float("nan")),  # non-finite
        (0.1, float("inf")),
    ],
)
def test_multitone_rejects_bad_harmonics(harmonics):
    with pytest.raises(exceptions.InvalidParameterError):
        synthesize(SignalSpec(kind="multitone", frequency=1_000.0, harmonics=harmonics), RATE, 100)


def test_multitone_rejects_a_non_sequence_harmonics():
    with pytest.raises(exceptions.InvalidParameterError):
        synthesize(SignalSpec(kind="multitone", frequency=1_000.0, harmonics=0.1), RATE, 100)


def test_exponential_is_periodic_from_the_very_first_cycle():
    """What the closed-form steady-state solve buys. An implementation that
    started at 0 (or at -amplitude) and settled in over a few cycles would fail
    this -- and would also restart its settling at every stream() chunk."""
    spec = SignalSpec(kind="exponential", frequency=1_000.0, tau=1e-4)
    samples = synthesize(spec, RATE, 3_000)  # 1000 samples per period at 1 MSa/s
    np.testing.assert_allclose(samples[:1_000], samples[1_000:2_000], atol=1e-12)
    np.testing.assert_allclose(samples[:1_000], samples[2_000:3_000], atol=1e-12)


def test_a_very_fast_rc_approaches_an_ideal_square():
    fast = synthesize(SignalSpec(kind="exponential", frequency=1_000.0, tau=1e-9), RATE, 2_000)
    ideal = synthesize(SignalSpec(kind="square", frequency=1_000.0), RATE, 2_000)
    # Not identical: at the first sample of each phase the RC still sits at its
    # pre-transition level while the ideal square has already switched, so the
    # two differ by 2*amplitude at exactly one sample per edge (4 edges here).
    assert np.mean(np.abs(fast - ideal)) < 0.01


def test_a_very_slow_rc_settles_to_the_duty_weighted_average():
    """tau -> inf limit: the RC cannot follow the square at all and sits at its
    DC average, amplitude * (2*duty - 1)."""
    spec = SignalSpec(kind="exponential", frequency=1_000.0, amplitude=1.0, duty=0.25, tau=10.0)
    samples = synthesize(spec, RATE, 1_000)
    assert samples.mean() == pytest.approx(-0.5, abs=1e-3)


def test_a_symmetric_exponential_is_antisymmetric_about_zero():
    spec = SignalSpec(kind="exponential", frequency=1_000.0, duty=0.5, tau=1e-4)
    samples = synthesize(spec, RATE, 1_000)
    assert samples.max() == pytest.approx(-samples.min(), rel=1e-9)


def test_a_very_slow_rc_stays_finite():
    """Guards the expm1 form. Written naively as (2b - 1 - ab)/(1 - ab), a large
    tau makes the denominator a difference of near-equal numbers: it loses every
    significant digit and eventually divides by zero."""
    samples = synthesize(SignalSpec(kind="exponential", frequency=1_000.0, tau=1e12), RATE, 1_000)
    assert np.all(np.isfinite(samples))


def test_exponential_is_continuous_at_its_phase_boundaries():
    """Both branch boundaries evaluate to the same level by construction, so the
    trace has no jump anywhere -- which is why ringing is a documented no-op on
    this kind."""
    samples = synthesize(SignalSpec(kind="exponential", frequency=1_000.0, tau=1e-4), RATE, 3_000)
    assert np.max(np.abs(np.diff(samples))) < 0.05


def test_exponential_is_periodic_and_triggerable_in_the_mock():
    assert "exponential" in PERIODIC_KINDS


@pytest.mark.parametrize("kwargs", [{"tau": 0.0}, {"tau": -1e-4}, {"duty": 0.0}, {"duty": 1.0}, {"duty": 1.5}])
def test_exponential_rejects_bad_parameters(kwargs):
    with pytest.raises(exceptions.InvalidParameterError):
        synthesize(SignalSpec(kind="exponential", frequency=1_000.0, **kwargs), RATE, 100)


def _fwhm_seconds(samples, rate):
    """50%-to-50% width of the first pulse, the same threshold the repo's timing
    analyzer uses."""
    mid = (samples.max() + samples.min()) / 2.0
    above = samples >= mid
    rising = np.flatnonzero(~above[:-1] & above[1:])
    falling = np.flatnonzero(above[:-1] & ~above[1:])
    falling = falling[falling > rising[0]]
    return (falling[0] - rising[0]) / rate


def test_pulse_width_is_the_50_percent_width():
    """pulse_width is FWHM, not top duration: it matches SOUR{ch}:FUNC:PULS:WIDT
    and the threshold calculate_timing_stats() measures at, so the flat top runs
    for pulse_width - edge_time."""
    spec = SignalSpec(kind="pulse", frequency=1_000.0, pulse_width=2e-4, edge_time=1e-5)
    samples = synthesize(spec, RATE, 2_000)
    assert _fwhm_seconds(samples, RATE) == pytest.approx(2e-4, abs=2.0 / RATE)


def test_pulse_plateaus_sit_at_plus_and_minus_amplitude():
    spec = SignalSpec(kind="pulse", frequency=1_000.0, amplitude=3.0, pulse_width=2e-4, edge_time=1e-5)
    samples = synthesize(spec, RATE, 2_000)
    assert samples.max() == pytest.approx(3.0)
    assert samples.min() == pytest.approx(-3.0)


def test_pulse_edge_time_sets_the_transition_rate():
    slow = synthesize(SignalSpec(kind="pulse", frequency=1_000.0, pulse_width=2e-4, edge_time=5e-5), RATE, 2_000)
    fast = synthesize(SignalSpec(kind="pulse", frequency=1_000.0, pulse_width=2e-4, edge_time=1e-6), RATE, 2_000)
    assert np.max(np.abs(np.diff(slow))) < np.max(np.abs(np.diff(fast)))


def test_pulse_accepts_a_zero_edge_time():
    """An ideal instantaneous edge is legal, and must not divide by zero."""
    spec = SignalSpec(kind="pulse", frequency=1_000.0, pulse_width=2e-4, edge_time=0.0)
    samples = synthesize(spec, RATE, 2_000)
    assert np.all(np.isfinite(samples))
    assert set(np.unique(np.round(samples, 9))) == {-1.0, 1.0}
    assert _fwhm_seconds(samples, RATE) == pytest.approx(2e-4, abs=2.0 / RATE)


def test_pulse_ignores_duty():
    wide = synthesize(SignalSpec(kind="pulse", frequency=1_000.0, duty=0.9), RATE, 2_000)
    narrow = synthesize(SignalSpec(kind="pulse", frequency=1_000.0, duty=0.1), RATE, 2_000)
    np.testing.assert_array_equal(wide, narrow)


def test_pulse_is_periodic_and_triggerable_in_the_mock():
    assert "pulse" in PERIODIC_KINDS


@pytest.mark.parametrize(
    "kwargs",
    [
        {"edge_time": -1e-6},  # negative edge
        {"pulse_width": 1e-6, "edge_time": 1e-5},  # width below the edge time
        {"pulse_width": 0.0, "edge_time": 0.0},  # zero width
        {"pulse_width": 9e-4, "edge_time": 2e-4},  # trapezoid longer than the 1 ms period
    ],
)
def test_pulse_rejects_a_trapezoid_that_cannot_exist(kwargs):
    with pytest.raises(exceptions.InvalidParameterError):
        synthesize(SignalSpec(kind="pulse", frequency=1_000.0, **kwargs), RATE, 100)


def _zero_crossings(samples):
    return np.count_nonzero(np.diff(np.signbit(samples)))


def test_chirp_frequency_rises_across_a_sweep():
    span = 0.01
    spec = SignalSpec(kind="chirp", frequency=1_000.0, end_frequency=10_000.0, sweep_time=span)
    samples = synthesize(spec, RATE, int(RATE * span))
    half = len(samples) // 2
    # First half averages ~3.25 kHz, second half ~7.75 kHz.
    assert _zero_crossings(samples[half:]) > 2 * _zero_crossings(samples[:half])


def test_chirp_phase_is_continuous_across_a_sweep_retrace():
    """The reason phase accumulates (n * PHI(sweep_time) + PHI(within)) instead
    of resetting each sweep. A reset would put a step of order the amplitude at
    every sweep_time -- and the ringing impairment would then treat it as a real
    edge."""
    spec = SignalSpec(kind="chirp", frequency=1_000.0, end_frequency=5_000.0, sweep_time=1e-3)
    samples = synthesize(spec, RATE, 3_000)  # three full sweeps
    steepest = 2 * np.pi * 5_000.0 * 1.0 / RATE  # the fastest legitimate slope, per sample
    assert np.max(np.abs(np.diff(samples))) < 1.5 * steepest


def test_a_log_sweep_spends_equal_time_per_octave():
    span = 0.02
    spec = SignalSpec(kind="chirp", frequency=1_000.0, end_frequency=4_000.0, sweep_time=span, sweep_log=True)
    samples = synthesize(spec, RATE, int(RATE * span))
    half = len(samples) // 2
    # Two octaves over 20 ms: 1->2 kHz in the first half, 2->4 kHz in the second.
    # At double the frequency throughout, the second half has twice the crossings.
    assert _zero_crossings(samples[half:]) == pytest.approx(2 * _zero_crossings(samples[:half]), rel=0.05)


def test_a_log_sweep_with_equal_endpoints_degenerates_to_a_sine():
    """The limit of the log form as end_frequency -> frequency. Taken here rather
    than raising, because log(1) == 0 would otherwise divide by zero on a spec
    that is degenerate but perfectly sane."""
    spec = SignalSpec(kind="chirp", frequency=1_000.0, end_frequency=1_000.0, sweep_time=1e-3, sweep_log=True)
    chirped = synthesize(spec, RATE, 3_000)
    plain = synthesize(SignalSpec(kind="sine", frequency=1_000.0), RATE, 3_000)
    np.testing.assert_allclose(chirped, plain, atol=1e-9)


def test_chirp_handles_negative_times():
    """t is routinely negative: the mock free-runs from a negative t0 and the
    ringing impairment renders samples before t0. np.floor (not int truncation)
    is what makes the sweep index correct there."""
    spec = SignalSpec(kind="chirp", frequency=1_000.0, end_frequency=5_000.0, sweep_time=1e-3)
    samples = synthesize(spec, RATE, 4_000, t0=-2e-3)
    assert np.all(np.isfinite(samples))
    steepest = 2 * np.pi * 5_000.0 * 1.0 / RATE
    assert np.max(np.abs(np.diff(samples))) < 1.5 * steepest


def test_chirp_is_not_treated_as_periodic():
    """It has no stable period, so the mock must free-run rather than try to
    align it to a trigger level."""
    assert "chirp" not in PERIODIC_KINDS


@pytest.mark.parametrize(
    "kwargs",
    [
        {"frequency": 0.0},
        {"frequency": -1_000.0},
        {"end_frequency": 0.0},
        {"end_frequency": -5_000.0},
        {"sweep_time": 0.0},
        {"sweep_time": -1e-3},
    ],
)
def test_chirp_rejects_bad_parameters(kwargs):
    params = {"kind": "chirp", "frequency": 1_000.0, "end_frequency": 5_000.0, "sweep_time": 1e-3}
    params.update(kwargs)
    with pytest.raises(exceptions.InvalidParameterError):
        synthesize(SignalSpec(**params), RATE, 100)
