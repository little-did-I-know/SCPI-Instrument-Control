"""Signal impairments: drift, glitches and edge ringing.

The mock produced mathematically perfect waveforms, so measurement code had never
faced an imperfect signal. These impairments are all DEFAULT OFF -- the
default-off test below is the load-bearing one, because turning them on by
default would silently change what every existing mock-based test measures.
"""

import numpy as np
import pytest

from scpi_control import exceptions
from scpi_control.signal_synth import SignalSpec, synthesize

RATE = 100_000.0
N = 4_000


def test_new_fields_default_to_off():
    spec = SignalSpec(kind="sine", frequency=1_000.0)
    assert spec.drift_amplitude == 0.0
    assert spec.glitch_rate == 0.0
    assert spec.ringing_frequency == 0.0


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
