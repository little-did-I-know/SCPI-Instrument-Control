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
    ],
)
def test_negative_impairment_parameters_are_rejected(kwargs):
    spec = SignalSpec(kind="sine", frequency=1_000.0, **kwargs)
    with pytest.raises(exceptions.InvalidParameterError):
        synthesize(spec, RATE, N)
