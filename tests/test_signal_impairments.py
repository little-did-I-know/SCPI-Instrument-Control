"""Signal impairments: drift, glitches, edge ringing, and timing jitter.

The mock produced mathematically perfect waveforms, so measurement code had never
faced an imperfect signal. These impairments are all DEFAULT OFF -- the
default-off test below is the load-bearing one, because turning them on by
default would silently change what every existing mock-based test measures.
"""

import numpy as np
import pytest

from scpi_control import exceptions, signal_synth
from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer
from scpi_control.signal_synth import SignalSpec, make_waveform, synthesize

RATE = 100_000.0
N = 4_000


def test_new_fields_default_to_off():
    spec = SignalSpec(kind="sine", frequency=1_000.0)
    assert spec.drift_amplitude == 0.0
    assert spec.glitch_rate == 0.0
    assert spec.ringing_frequency == 0.0
    assert spec.jitter_rms == 0.0


def test_default_spec_output_is_unchanged_by_the_new_fields():
    """The guarantee that keeps this non-breaking: a spec with no impairment
    arguments must produce exactly what it produced before this sub-project."""
    spec = SignalSpec(kind="sine", frequency=1_000.0, amplitude=1.0, noise_rms=0.01, seed=7)
    a = synthesize(spec, RATE, N)
    b = synthesize(spec, RATE, N)
    np.testing.assert_array_equal(a, b)
    # A clean sine stays within its amplitude envelope; any impairment leaking in
    # by default would push it outside.
    assert np.max(np.abs(a)) < 1.0 + 6 * 0.01


@pytest.mark.parametrize(
    "kwargs",
    [
        {"drift_amplitude": -1.0},
        {"glitch_rate": -1.0},
        {"glitch_amplitude": -1.0},
        {"ringing_damping": -1.0},
        {"ringing_frequency": -1.0},
        {"jitter_rms": -1.0},
    ],
)
def test_negative_impairment_parameters_are_rejected(kwargs):
    spec = SignalSpec(kind="sine", frequency=1_000.0, **kwargs)
    with pytest.raises(exceptions.InvalidParameterError):
        synthesize(spec, RATE, N)


@pytest.mark.parametrize("drift_frequency", [0.0, -1.0], ids=["zero", "negative"])
def test_drift_frequency_must_be_positive_when_drift_is_enabled(drift_frequency):
    """M3: _validate covered every new field except drift_frequency.
    drift_amplitude=5.0, drift_frequency=0.0 used to silently produce no drift
    at all (sin(0*t) == 0), and a negative value merely inverted phase --
    both surprising and undocumented rather than rejected."""
    spec = SignalSpec(kind="dc", drift_amplitude=5.0, drift_frequency=drift_frequency)
    with pytest.raises(exceptions.InvalidParameterError):
        synthesize(spec, RATE, N)


def test_drift_frequency_is_unchecked_while_drift_is_disabled():
    """drift_amplitude's default (0.0, drift off) must not make an otherwise
    unrelated drift_frequency value (including the field's own non-positive
    edge cases) block synthesis."""
    out = synthesize(SignalSpec(kind="dc", offset=0.0, drift_frequency=0.0, seed=1), RATE, N)
    np.testing.assert_array_equal(out, np.zeros(N))


def test_drift_moves_the_baseline():
    clean = synthesize(SignalSpec(kind="dc", offset=0.0, seed=1), RATE, N)
    drifted = synthesize(SignalSpec(kind="dc", offset=0.0, drift_amplitude=0.5, drift_frequency=1.0, seed=1), RATE, N)
    assert np.max(np.abs(drifted)) > 0.1, "drift should visibly move the baseline"
    assert np.allclose(clean, 0.0), "the clean control must be flat"


def test_drift_is_continuous_across_stream_chunks():
    """stream() re-seeds per chunk. A random-walk drift would jump at each chunk
    boundary; a time-based one stays continuous."""
    from scpi_control.signal_synth import stream

    spec = SignalSpec(kind="dc", offset=0.0, drift_amplitude=0.5, drift_frequency=1.0, seed=3)
    chunks = []
    for i, chunk in enumerate(stream(spec, RATE, 1_000)):
        chunks.append(chunk)
        if i == 3:
            break
    joined = np.concatenate(chunks)
    steps = np.abs(np.diff(joined))
    # No sample-to-sample step should dwarf the typical one -- that is what a
    # per-chunk reset would look like.
    assert np.max(steps) < 20 * np.median(steps[steps > 0])


def test_glitches_raise_the_peak_above_the_clean_amplitude():
    base = dict(kind="sine", frequency=1_000.0, amplitude=1.0, seed=5)
    clean = synthesize(SignalSpec(**base), RATE, N)
    spiky = synthesize(SignalSpec(glitch_rate=500.0, glitch_amplitude=3.0, **base), RATE, N)
    assert np.max(np.abs(spiky)) > np.max(np.abs(clean)) + 1.0


def test_impairments_are_reproducible_under_a_seed():
    spec = SignalSpec(kind="sine", frequency=1_000.0, glitch_rate=500.0, glitch_amplitude=3.0, drift_amplitude=0.2, seed=11)
    np.testing.assert_array_equal(synthesize(spec, RATE, N), synthesize(spec, RATE, N))


def test_enabling_drift_does_not_change_the_noise_samples():
    """Impairments draw from their own generators, so switching one on must not
    perturb another's randomness -- otherwise a test asserting on noise would
    break merely because drift was enabled."""
    base = dict(kind="dc", offset=0.0, noise_rms=0.1, seed=13)
    noisy = synthesize(SignalSpec(**base), RATE, N)
    noisy_drifted = synthesize(SignalSpec(drift_amplitude=1.0, drift_frequency=0.5, **base), RATE, N)
    # Removing the (deterministic, time-based) drift must recover the same noise.
    t = np.arange(N) / RATE
    recovered = noisy_drifted - 1.0 * np.sin(2 * np.pi * 0.5 * t)
    np.testing.assert_allclose(recovered, noisy, atol=1e-9)


def test_enabling_glitches_does_not_perturb_the_shared_noise_generator():
    """I4: glitches are the only impairment that draws randomness, via a
    separate generator (`_impairment_rng(spec.seed, 1)`), so switching them on
    must not perturb `noise_rms`'s shared `rng` draw. test_enabling_drift_does_
    not_change_the_noise_samples does not prove this: drift is deterministic
    and time-based and never touches any generator, so it only proves
    additivity. If glitches drew from the same `rng` as noise instead (e.g.
    `glitch_rng = rng`), the noise draw would shift too, and every sample --
    not just the sparse glitches themselves -- would differ from the
    non-glitchy spec's output."""
    base = dict(kind="dc", offset=0.0, noise_rms=0.1, seed=13)
    noisy = synthesize(SignalSpec(**base), RATE, N)
    noisy_glitchy = synthesize(SignalSpec(glitch_rate=500.0, glitch_amplitude=3.0, **base), RATE, N)
    diff = noisy_glitchy - noisy
    changed = np.flatnonzero(diff)
    assert changed.size > 0, "glitch_rate=500 over a 4000-sample buffer should land at least one glitch"
    # A perturbed shared generator would shift every one of the 4000 samples,
    # not just the handful of sparse glitches -- this bounds "handful".
    assert changed.size < N // 4, "far more samples changed than glitches could plausibly land on -- the noise generator was perturbed"
    # Every changed sample must be an exact integer multiple of glitch_amplitude
    # (one or more glitches landing there) -- not an arbitrarily-shifted noise
    # value, which is what a perturbed shared generator would produce instead.
    remainder = diff[changed] / 3.0
    np.testing.assert_allclose(remainder, np.round(remainder), atol=1e-9)


def test_default_spec_produces_exactly_the_clean_signal():
    """The real default-off guarantee. A DC spec at zero offset with no noise must
    return EXACTLY zeros, so ANY nonzero default impairment -- drift, glitch or
    ringing, at any magnitude or timescale -- breaks this immediately. The
    envelope-based test above cannot see a slow drift; this one can."""
    out = synthesize(SignalSpec(kind="dc", offset=0.0, seed=1), RATE, N)
    np.testing.assert_array_equal(out, np.zeros(N))


def test_glitches_at_colliding_positions_sum_via_add_at_not_overwrite():
    """np.add.at accumulates every glitch landing on a repeated sample index;
    fancy-index += would silently keep only the last write to a repeated index,
    dropping the rest. At the glitch densities used elsewhere in this file,
    duplicate positions are too rare to tell the two apart (0/200 trials in the
    Task 6 review). Here n_points is tiny and glitch_rate is deliberately huge --
    about 100 glitches land on only 20 positions -- so multiple same-sign
    collisions on one sample are certain. fancy-index += can never push a sample
    past 1x glitch_amplitude no matter how many glitches land there; np.add.at
    can and does."""
    spec = SignalSpec(kind="dc", offset=0.0, glitch_rate=5000.0, glitch_amplitude=1.0, seed=0)
    out = synthesize(spec, 1000.0, 20)
    assert np.max(np.abs(out)) >= 2.0, "same-sign glitch collisions should stack past 1x glitch_amplitude"


def test_ringing_produces_overshoot_above_the_flat_top():
    """Exercises the overshoot measurement the audit caught fabricating values for
    signals without flat tops (M42) -- now there is a signal that genuinely has
    overshoot to measure."""
    base = dict(kind="square", frequency=1_000.0, amplitude=1.0, seed=2)
    clean = synthesize(SignalSpec(**base), RATE, N)
    rung = synthesize(SignalSpec(ringing_frequency=20_000.0, ringing_damping=5_000.0, **base), RATE, N)

    assert np.max(rung) > np.max(clean) * 1.05, "ringing should overshoot the flat top"
    # And it must decay: the late part of a held level should be flatter than the
    # part right after the triggering edge. NOTE: comparing the first vs last 200
    # samples of the whole 4000-sample array (as originally drafted) does not test
    # this -- at these parameters the decay window is 5/ringing_damping seconds =
    # 100 samples, longer than the 50-sample half-period between edges, so
    # consecutive edges' ringing overlaps into a steady state and the start and
    # end of the array read as statistically indistinguishable (verified: it
    # fails, 1.052 vs 1.041). Scoping to one held level (the first one, which
    # starts from an unrung baseline) isolates the actual decay behaviour.
    edges = np.flatnonzero(np.diff(clean))
    held = rung[edges[0] + 1 : edges[1] + 1]
    assert np.std(held[-20:]) < np.std(held[:20]), "ringing should decay within a held level"


def test_ringing_is_off_by_default_for_a_square_wave():
    clean = synthesize(SignalSpec(kind="square", frequency=1_000.0, amplitude=1.0, seed=2), RATE, N)
    assert np.max(clean) == pytest.approx(1.0)


def test_ringing_damping_defaults_to_nonzero():
    """M8: the natural way to switch ringing on is setting only
    ringing_frequency. If ringing_damping stayed at its old default (0.0,
    undamped), the resulting kernel never decays, so it would run for
    n_points-1 edges * n_points samples each on a fast square wave --
    quadratic in n_points (measured, pre-fix: 0.013/0.084/0.402s at n =
    5k/20k/50k). Same fix as drift_frequency's own nonzero default, and for
    the same reason."""
    spec = SignalSpec(kind="square", frequency=1_000.0, amplitude=1.0, ringing_frequency=20_000.0, seed=2)
    assert spec.ringing_damping > 0.0
    out = synthesize(spec, 1_000_000.0, 50_000)
    assert np.isfinite(out).all()


def test_ringing_is_continuous_across_stream_chunks():
    """I3: the doc comment used to claim ringing was 'automatically continuous
    across stream() chunks'. It wasn't -- np.diff() only sees edges inside the
    current buffer, so an edge landing at a chunk boundary got no ringing at
    all, and one near a chunk's end had its ring truncated. Mirrors
    test_drift_is_continuous_across_stream_chunks, but proves the stronger
    claim directly: a stream() reconstruction must be bit-identical to a
    single contiguous synthesize() call, the same way it already is for drift.

    frequency=997.0 (not an exact divisor of chunk_size/sample_rate) is
    deliberate: at a perfectly round frequency like 1000.0 Hz, some square-wave
    edges land EXACTLY on a `cycle_fraction == duty` floating-point threshold,
    and accumulate one ULP of rounding differently depending on whether t was
    reached via one contiguous arange() or via a chunk's t0 + a smaller
    arange() -- a pre-existing quantization artifact in the base generator,
    orthogonal to this chunk-continuity fix (reproduced: it affects the plain
    square wave with NO ringing involved at all, at frequency=1000.0 exactly).
    """
    from scpi_control.signal_synth import stream

    spec = SignalSpec(kind="square", frequency=997.0, amplitude=1.0, ringing_frequency=20_000.0, ringing_damping=5_000.0, seed=2)
    contiguous = synthesize(spec, RATE, N)
    streamed = np.concatenate(list(stream(spec, RATE, 1_000, duration=N / RATE)))
    np.testing.assert_array_equal(streamed, contiguous)


# --- jitter_rms -------------------------------------------------------------
#
# Each cycle BOUNDARY gets an independent Gaussian time-shift, and every
# sample's shift is the linear interpolation between the two boundaries that
# straddle it (see SignalSpec.jitter_rms and the design doc). This replaced an
# earlier hard-step-per-cycle model that made the warped time axis
# non-monotonic at ordinary jitter values, corrupting edge detection (spurious
# double-edges, 10-30x measurement inflation) on 5 of 7 PERIODIC_KINDS --
# fixed by this file's tests below. Calibration is now EDGE-POSITION
# DEPENDENT: an edge sitting exactly at a cycle boundary (fraction 0) measures
# jitter_rms almost exactly (sigma = jitter_rms / sqrt(2) internally is tuned
# for this case); an edge elsewhere in the cycle measures less, following
# Var(period)/jitter_rms**2 = 0.5*[(1-2f)**2 + f**2 + (1-f)**2] -- verified
# empirically below for f=0 (sine), f=0.25 (triangle), and f=0.5 (ramp).


def test_jitter_rms_defaults_to_off():
    spec = SignalSpec(kind="sine", frequency=1_000.0)
    assert spec.jitter_rms == 0.0


@pytest.mark.parametrize("kind", ["sine", "square"])
def test_default_jitter_rms_produces_the_exact_clean_signal(kind):
    """Zero-default regression. jitter_rms=0.0 (the default) must not perturb
    the time array the generator sees at all: _apply_jitter's fast path
    returns the SAME array object unchanged, so the output must match a
    hand-derived closed-form reference exactly, not merely approximately --
    proof this feature is a true no-op when disabled, not just a small one.

    t0=0.0 (the default) keeps every sample away from a cycle-boundary float
    residual (see test_cycle_boundary.py), so the closed form needs no
    snapping logic of its own to match.
    """
    spec = SignalSpec(kind=kind, frequency=1_000.0, amplitude=1.0, seed=7)
    out = synthesize(spec, RATE, N)
    t = np.arange(N) / RATE
    if kind == "sine":
        expected = np.sin(2.0 * np.pi * 1_000.0 * t)
    else:
        # RATE/frequency = 100 samples per cycle, 50 high then 50 low (duty=0.5).
        expected = np.where((np.arange(N) % 100) < 50, 1.0, -1.0)
    np.testing.assert_array_equal(out, expected)


def test_jitter_moves_the_measured_period_jitter_off_zero():
    """Before this: nothing in the codebase could make
    WaveformAnalyzer.calculate_quality_stats report nonzero jitter. A clean
    (unjittered) periodic signal must read as EXACTLY zero jitter here (not
    merely "near" zero) -- proving the control is actually clean -- and
    enabling jitter_rms must move it well off that floor.

    "triangle": at RATE=100_000/frequency=1_000 (an exact 100 samples/cycle),
    the clean signal's rising v50 crossing lands on the identical sample index
    every cycle regardless of kind -- period is a constant integer, so
    std(periods) is exactly 0.0, not just small. Triangle is used here (rather
    than the default "sine") only because it is also the kind exercised by the
    fraction-dependent-attenuation tests below; either kind demonstrates the
    same off-zero behaviour equally well now that the interpolated model (see
    the section comment above) makes every PERIODIC_KINDS measurement
    reliable, not just this one.
    """
    spec_clean = SignalSpec(kind="triangle", frequency=1_000.0, amplitude=1.0, seed=4)
    spec_jittered = SignalSpec(kind="triangle", frequency=1_000.0, amplitude=1.0, jitter_rms=5e-6, seed=4)
    clean_jitter = WaveformAnalyzer.calculate_quality_stats(make_waveform(spec_clean, RATE, N))["jitter"]
    jittered_jitter = WaveformAnalyzer.calculate_quality_stats(make_waveform(spec_jittered, RATE, N))["jitter"]
    assert clean_jitter == 0.0
    assert jittered_jitter is not None and jittered_jitter > 1e-6


def test_jitter_rms_matches_the_measured_period_jitter_within_statistical_tolerance():
    """The calibration this feature exists to prove: WaveformAnalyzer's own
    period-jitter measurement (calculate_quality_stats -- std(diff(rising-edge
    sample indices)) * dt, the standard random-jitter definition) on a
    jittered signal must come back close to the INJECTED jitter_rms, not
    merely internally self-consistent with this module's own math.

    "sine" -- the DEFAULT kind -- is exactly the validation path the original
    design doc's Testing section intended and the hard-step model's bug
    blocked: a sine's rising zero-crossing sits EXACTLY at fraction 0, the
    cycle boundary, where the OLD per-cycle-constant model's discontinuity
    landed (a jump of |delta[n+1]-delta[n]| right at the steepest-slope point
    made the discretized sine non-monotonic through the v50 threshold,
    producing spurious extra "rising edges" -- reproduced pre-fix: 22/522
    anomalous 2-6-sample "periods" at jitter_rms=1e-6 s, inflating measured
    jitter to ~20x injected). The interpolated model (see this file's jitter
    section comment) is continuous everywhere, so that failure mode is gone;
    see test_jitter_produces_no_spurious_edges_on_previously_broken_kinds
    below for the direct proof. Because a fraction-0 edge is also the
    UNBLENDED case (SignalSpec.jitter_rms), sine is additionally the kind
    where measured jitter should track injected jitter_rms most closely -- see
    test_jitter_measured_ratio_depends_on_edge_fraction_within_the_cycle for
    kinds whose edge sits elsewhere in the cycle.

    RATE=1 MHz, frequency=10 kHz -> 100 samples/cycle; N=50_000 -> 500 cycles,
    so calculate_quality_stats sees ~499 measured periods. Treating those as
    approximately independent (a mild overstatement of precision, since
    adjacent periods share one delta term, but conservative given the
    generous tolerance below), the standard error of a sample std-dev
    estimate is sigma/sqrt(2*(n-1)) = jitter_rms/sqrt(2*498) ~= 3.2% of
    jitter_rms. jitter_rms=3e-6 s is 3 samples (dt=1e-6 s), comfortably above
    the edge-detector's dt/sqrt(12) ~= 2.9e-7 s quantization floor. A +/-25%
    relative tolerance is >7 standard errors, comfortably ruling out random
    flakiness while still catching a wrong calibration constant -- a missing
    sqrt(2) would read ~41% high or ~29% low, both well outside this band.
    Measured 0.9699x the injected value with these exact parameters (seed=21).
    """
    rate = 1_000_000.0
    n = 50_000
    jitter_rms = 3e-6
    spec = SignalSpec(kind="sine", frequency=10_000.0, amplitude=1.0, jitter_rms=jitter_rms, seed=21)
    waveform = make_waveform(spec, rate, n)
    measured = WaveformAnalyzer.calculate_quality_stats(waveform)["jitter"]
    assert measured is not None
    assert measured == pytest.approx(jitter_rms, rel=0.25)


@pytest.mark.parametrize("kind", ["sine", "square", "ramp", "multitone"])
def test_jitter_produces_no_spurious_edges_on_previously_broken_kinds(kind):
    """The direct proof the fix closes the gap the prior review found: under
    the old hard-step-per-cycle model, sine/square/ramp/multitone/pulse (5 of
    7 PERIODIC_KINDS) all produced spurious double-edges at ordinary jitter
    values (reproduced pre-fix, e.g. sine: 22/522 anomalous periods at
    jitter_rms = 1% of the period). An "anomalous" period here is one under
    half the median -- a real, isolated Gaussian jitter draw essentially never
    produces one (periods cluster tightly around T with std << T/2 at these
    magnitudes), so any anomaly at all is symptomatic of the old bug, not
    statistical noise.

    RATE=1 MHz, frequency=10 kHz -> 100 samples/cycle, N=50_000 -> ~500 edges
    per trial. Three seeds x three jitter levels (1%, 3%, 5% of the period --
    covering and exceeding the levels that broke the old model) gives 9 trials
    per kind, ~4500 edges total, with zero anomalies tolerated.
    """
    rate = 1_000_000.0
    frequency = 10_000.0
    period = 1.0 / frequency
    n = 50_000
    for pct in (0.01, 0.03, 0.05):
        jitter_rms = pct * period
        for seed in (1, 2, 3):
            spec = SignalSpec(kind=kind, frequency=frequency, amplitude=1.0, jitter_rms=jitter_rms, seed=seed)
            v = synthesize(spec, rate, n)
            v50 = (float(np.max(v)) + float(np.min(v))) / 2.0
            rising = np.flatnonzero((v[:-1] < v50) & (v[1:] >= v50))
            assert rising.size > 400, f"{kind} pct={pct} seed={seed}: too few edges detected to judge -- test setup problem"
            periods = np.diff(rising)
            median = np.median(periods)
            anomalies = np.sum(periods < median * 0.5)
            assert anomalies == 0, f"{kind} pct={pct} seed={seed}: {anomalies} spurious short period(s) out of {periods.size} -- the old hard-step bug would reproduce here"


@pytest.mark.parametrize(
    "kind, edge_fraction, expected_ratio",
    [
        ("sine", 0.0, 1.0),
        ("triangle", 0.25, 0.6614),
        ("ramp", 0.5, 0.5),
    ],
)
def test_jitter_measured_ratio_depends_on_edge_fraction_within_the_cycle(kind, edge_fraction, expected_ratio):
    """Characterizes the real side effect of whole-cycle linear interpolation:
    an edge's measured jitter depends on WHERE in the cycle it sits, per
    Var(period)/jitter_rms**2 = 0.5*[(1-2f)**2 + f**2 + (1-f)**2] (see
    SignalSpec.jitter_rms and _apply_jitter). f=0 (the cycle boundary --
    "sine"'s ascending v50 crossing at the default phase=0.0) is the
    UNBLENDED case, predicted ratio 1.0. "triangle"'s ascending crossing sits
    at f=0.25 (predicted ratio sqrt(0.4375) ~= 0.6614). "ramp" is the
    surprising one: its own hard discontinuity sits at the cycle boundary, but
    that is a FALLING transition -- the analyzer's RISING v50 crossing is the
    ramp's own continuous rise from -amplitude to +amplitude, which crosses
    zero at f=0.5, cycle CENTER, the formula's minimum (predicted ratio 0.5).

    RATE=1 MHz, frequency=10 kHz, N=50_000 (~500 cycles), jitter_rms = 3% of
    the period, seed=0 -- chosen because it lands close to each kind's
    respective mean across a 5-seed sample taken during verification (sine
    0.96, triangle 0.688, ramp 0.537, vs. predicted 1.0/0.6614/0.5). A +/-20%
    relative tolerance comfortably covers single-seed sampling variation at
    ~500 cycles while still distinguishing the three fractions from each
    other and from a same-for-every-kind (unfixed) model.
    """
    rate = 1_000_000.0
    frequency = 10_000.0
    n = 50_000
    jitter_rms = 0.03 / frequency
    spec = SignalSpec(kind=kind, frequency=frequency, amplitude=1.0, jitter_rms=jitter_rms, seed=0)
    waveform = make_waveform(spec, rate, n)
    measured = WaveformAnalyzer.calculate_quality_stats(waveform)["jitter"]
    assert measured is not None
    assert measured == pytest.approx(expected_ratio * jitter_rms, rel=0.20)


def test_jitter_is_reproducible_under_a_seed():
    spec = SignalSpec(kind="sine", frequency=1_000.0, jitter_rms=2e-5, seed=17)
    np.testing.assert_array_equal(synthesize(spec, RATE, N), synthesize(spec, RATE, N))


def test_jitter_differs_across_seeds():
    base = dict(kind="sine", frequency=1_000.0, jitter_rms=2e-5)
    a = synthesize(SignalSpec(seed=17, **base), RATE, N)
    b = synthesize(SignalSpec(seed=18, **base), RATE, N)
    assert not np.array_equal(a, b)


def test_jitter_is_a_no_op_on_kinds_without_a_stable_period():
    """PERIODIC_KINDS excludes "dc" (no cycle structure at all), "noise" (ditto),
    and "chirp" (frequency sweeps, so "cycle index" is undefined). jitter_rms
    must not raise or change their output."""
    dc_clean = synthesize(SignalSpec(kind="dc", offset=0.5, seed=1), RATE, N)
    dc_jittered = synthesize(SignalSpec(kind="dc", offset=0.5, jitter_rms=1e-5, seed=1), RATE, N)
    np.testing.assert_array_equal(dc_clean, dc_jittered)

    chirp_clean = synthesize(SignalSpec(kind="chirp", frequency=1_000.0, seed=1), RATE, N)
    chirp_jittered = synthesize(SignalSpec(kind="chirp", frequency=1_000.0, jitter_rms=1e-5, seed=1), RATE, N)
    np.testing.assert_array_equal(chirp_clean, chirp_jittered)


def test_jitter_shifts_where_ringing_anchors():
    """Jitter warps time BEFORE ringing's own edge detection runs (both the
    plain call and, inside the ringing branch, the extended-window call), so
    ringing keys on the ACTUAL jittered edge, not the nominal grid position --
    the physically-correct behaviour the design doc calls out as needing no
    special-casing in the ringing code path itself.

    Targets the RISING edge at the cycle-1 BOUNDARY (nominal sample 1000, not
    cycle 0's falling duty-threshold edge at sample 500 used before this fix):
    under the old per-cycle-constant model, EVERY sample in a cycle shifted by
    that cycle's single delta, so predicting any edge from one delta value was
    exact. Under the new interpolated model that is only true again AT a
    boundary sample (frac=0 by construction: delta = d[n]*(1-0) + d[n+1]*0 =
    d[n] exactly), which is why this test now targets a boundary-fraction edge
    specifically -- see
    test_jitter_measured_ratio_depends_on_edge_fraction_within_the_cycle for
    why an interior-fraction edge (e.g. the OLD test's duty=0.5 target) would
    no longer be a simple single-delta prediction.

    signal_synth._jitter_cycle_rng(seed, 1) is called directly to obtain
    boundary 1's delta -- this is ground truth precisely because it is the
    same seeded-generator call synthesize() itself makes internally for that
    boundary, not an independent re-derivation of the math. ringing_damping=
    200_000 (vs. the module's usual 5_000) is deliberate: it shrinks the decay
    kernel to ~25 samples so the ring stays local to its own edge and cannot
    spill into -- or be confused with -- ringing from a neighbouring edge.
    """
    rate = 1_000_000.0
    n = 4_000
    frequency = 1_000.0  # 1000 samples/cycle at this rate
    jitter_rms = 5e-5  # 50 us: several tens of samples of expected shift
    seed = 9
    base = dict(kind="square", frequency=frequency, amplitude=1.0, seed=seed)

    clean = synthesize(SignalSpec(**base), rate, n)
    rung_jittered = synthesize(SignalSpec(jitter_rms=jitter_rms, ringing_frequency=50_000.0, ringing_damping=200_000.0, **base), rate, n)

    sigma = jitter_rms / np.sqrt(2.0)
    delta1 = signal_synth._jitter_cycle_rng(seed, 1).normal(0.0, sigma)
    # Boundary 1 (the rising transition into cycle 1) is nominally at sample
    # 1000 (1 * samples-per-cycle); a sample exactly at a boundary is the
    # UNBLENDED case, so it shifts by that boundary's own delta alone.
    predicted_edge = 1000 + delta1 * rate

    nominal_rising = np.flatnonzero(np.diff(clean) > 0)[0] + 1
    assert nominal_rising == 1000, "sanity check on the nominal edge position"
    assert abs(predicted_edge - 1000) > 20, "test parameters should produce a shift large enough to be unambiguous -- widen jitter_rms if this ever fails"

    # Search a window centered on the PREDICTED position, not a blind scan of
    # the whole cycle -- ringing's own damped oscillation produces many small
    # sample-to-sample sign flips as it decays, so "first positive diff
    # anywhere" is not a safe way to find the real transition once ringing is
    # on; anchoring the search to the predicted location is.
    lo = int(predicted_edge) - 30
    rising_in_window = np.flatnonzero(np.diff(rung_jittered[lo : lo + 60]) > 0)
    assert rising_in_window.size > 0, "expected a rising edge near the predicted jittered position"
    actual_edge = lo + rising_in_window[0] + 1

    assert actual_edge == pytest.approx(predicted_edge, abs=3.0), "the edge must land at the jittered position, not the nominal grid position 1000"

    # And the ring itself (an edge impairment) must be anchored at that ACTUAL
    # edge: the samples right after it should show much more oscillation than
    # the same-width window sitting at the now-wrong nominal position 1000,
    # where (with this short a decay kernel) the ring has already fully died
    # out by the time cycle 1's real transition happens elsewhere.
    ring_at_actual = rung_jittered[actual_edge : actual_edge + 15]
    ring_at_nominal = rung_jittered[1000:1015]
    assert np.std(ring_at_actual) > 0.1
    assert np.std(ring_at_nominal) == 0.0, "sanity check: this short ringing kernel should have fully settled by the (now-empty) nominal edge position"


def test_jitter_across_a_stream_chunk_boundary_is_a_pinned_known_limitation():
    """Documents (does not hide) the design's accepted "Known limitation":
    stream() bumps spec.seed by chunk_index per chunk (existing, deliberate
    behaviour -- see stream()'s own docstring). A cycle that straddles a
    stream() chunk boundary is rendered by TWO different synthesize() calls --
    one per chunk -- each computing this cycle's two boundary deltas
    (_jitter_cycle_rng(seed, n) and (..., n + 1)) under a DIFFERENT seed, so
    the SAME nominal cycle gets two different, uncorrelated control-point
    pairs depending on which half of it is being rendered.

    This is NOT merely "the jump at this boundary looks bigger than average":
    a jump between one cycle and the next is EXPECTED and normal everywhere in
    this model (that is what produces jitter's period variation in the first
    place -- see SignalSpec.jitter_rms), so an ordinary between-cycle jump is
    no evidence of anything wrong. The actual defect is narrower: a
    within-cycle inconsistency where two ADJACENT samples that belong to the
    SAME nominal cycle (n_before == n_after below) get interpolated deltas
    computed from two DIFFERENT boundary-delta pairs, only because stream()
    happened to cut the buffer there.

    Under the OLD hard-step model this showed up as a single-sample jump of a
    constant size (one delta difference). Under the NEW interpolated model the
    shape changed: the jump size now also depends on WHERE in the cycle the
    stream boundary happens to fall (the frac-weighted blend of two
    independent delta differences, not one) -- reproduced below at
    frequency=997.0/chunk_size=1_000: the streamed reconstruction's delta jump
    at each of the three probed boundaries is ~1e-5, roughly two orders of
    magnitude larger than the SAME two adjacent samples' delta difference
    under one contiguous call (~4e-7, the ordinary sub-sample drift of a
    smooth interpolation -- not a defect, ~4e-7 s corresponds to well under
    half a sample at RATE=100_000). This test pins that precisely by
    reproducing, from the seeded generators directly, exactly which boundary
    deltas produced the streamed samples on either side of each chunk
    boundary -- and contrasting that with `contiguous`, where every sample
    uses boundary deltas from a SINGLE seed throughout, so it has no such
    inconsistency.

    frequency=997.0 and chunk_size=1_000 (as in the ringing continuity test
    above) put a chunk boundary in the middle of most cycles, not on one.
    """
    from scpi_control.signal_synth import stream

    spec = SignalSpec(kind="sine", frequency=997.0, amplitude=1.0, jitter_rms=3e-5, seed=2)
    contiguous = synthesize(spec, RATE, N)
    streamed = np.concatenate(list(stream(spec, RATE, 1_000, duration=N / RATE)))
    assert not np.array_equal(streamed, contiguous), "stream()'s per-chunk seed bump must actually change jittered output vs. one contiguous call"

    sigma = spec.jitter_rms / np.sqrt(2.0)
    dt = 1.0 / RATE
    chunk_size = 1_000

    def boundary_delta(seed_offset, idx):
        return signal_synth._jitter_cycle_rng(spec.seed + seed_offset, idx).normal(0.0, sigma)

    boundaries_straddling_one_cycle = 0
    for b in (1_000, 2_000, 3_000):
        t_before, t_after = (b - 1) * dt, b * dt
        pos_before = spec.frequency * t_before + spec.phase / (2.0 * np.pi)
        pos_after = spec.frequency * t_after + spec.phase / (2.0 * np.pi)
        n_before = int(np.floor(pos_before))
        n_after = int(np.floor(pos_after))
        if n_before != n_after:
            continue  # this particular boundary happened to land exactly on a cycle wrap -- nothing to pin
        boundaries_straddling_one_cycle += 1
        frac_before = pos_before - n_before
        frac_after = pos_after - n_after

        chunk_before, chunk_after = (b - 1) // chunk_size, b // chunk_size

        d_before_n = boundary_delta(chunk_before, n_before)
        d_before_n1 = boundary_delta(chunk_before, n_before + 1)
        d_after_n = boundary_delta(chunk_after, n_after)
        d_after_n1 = boundary_delta(chunk_after, n_after + 1)
        assert (d_before_n, d_before_n1) != (d_after_n, d_after_n1), "the whole point of the limitation: the SAME cycle's boundary deltas differ depending on which chunk rendered them"

        delta_before = d_before_n * (1.0 - frac_before) + d_before_n1 * frac_before
        delta_after = d_after_n * (1.0 - frac_after) + d_after_n1 * frac_after

        # The streamed reconstruction must match the TWO-CHUNK (inconsistent)
        # prediction, sample for sample.
        predicted_before = spec.amplitude * np.sin(2 * np.pi * spec.frequency * (t_before - delta_before) + spec.phase)
        predicted_after = spec.amplitude * np.sin(2 * np.pi * spec.frequency * (t_after - delta_after) + spec.phase)
        assert streamed[b - 1] == pytest.approx(predicted_before, abs=1e-9)
        assert streamed[b] == pytest.approx(predicted_after, abs=1e-9)

        # Whereas the single contiguous call used boundary deltas from ONE
        # seed (unbumped spec.seed) throughout -- its own before/after delta
        # difference is just the ordinary smooth interpolation drift over one
        # sample, not a chunk-seam artifact.
        d_contig_n = boundary_delta(0, n_before)
        d_contig_n1 = boundary_delta(0, n_before + 1)
        delta_contig_before = d_contig_n * (1.0 - frac_before) + d_contig_n1 * frac_before
        delta_contig_after = d_contig_n * (1.0 - frac_after) + d_contig_n1 * frac_after
        predicted_contig_before = spec.amplitude * np.sin(2 * np.pi * spec.frequency * (t_before - delta_contig_before) + spec.phase)
        predicted_contig_after = spec.amplitude * np.sin(2 * np.pi * spec.frequency * (t_after - delta_contig_after) + spec.phase)
        assert contiguous[b - 1] == pytest.approx(predicted_contig_before, abs=1e-9)
        assert contiguous[b] == pytest.approx(predicted_contig_after, abs=1e-9)

        # Characterizes the "spread-out ramp, not a hard jump" shape change:
        # the streamed seam's delta discontinuity is real and an order of
        # magnitude (or more) larger than the ordinary one-sample drift the
        # same two samples show under one contiguous, self-consistent call.
        jump_streamed = abs(delta_after - delta_before)
        jump_contiguous = abs(delta_contig_after - delta_contig_before)
        assert jump_streamed > 10 * jump_contiguous, "the chunk-boundary discontinuity should dwarf ordinary within-cycle interpolation drift"

    assert boundaries_straddling_one_cycle > 0, "test setup should produce at least one boundary that actually straddles a single cycle"
