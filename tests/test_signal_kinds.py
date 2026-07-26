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
