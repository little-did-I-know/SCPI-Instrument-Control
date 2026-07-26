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
