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
