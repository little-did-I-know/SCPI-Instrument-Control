"""A sample landing on a cycle boundary must read as the start of a cycle.

`_cycle_fraction` computes `(frequency * t + phase / 2pi) % 1.0`. The time array
is built as `t0 + i / sample_rate`, and for an arbitrary `t0` -- a trigger
crossing, a free-run drift offset, a filter's lead-in -- that sum cannot land
exactly on a whole number of periods. So the product comes out an ULP *below* an
integer and `%` maps it to 0.9999999999999991 instead of 0.0.

For a continuous kind that is invisible. For a kind that is discontinuous at the
wrap it inverts the sample: a square reads its low level at the instant it should
switch high, a sawtooth resets one sample early. One sample, full amplitude, on
an otherwise correct trace -- roughly 50 int8 codes of spike in a mock capture,
which is exactly the sort of thing that makes someone distrust the instrument
model rather than the arithmetic.

Reproduced from the mock's own trigger-aligned path: a 1 kHz square at 1 MSa/s
from `t0 = -0.006` puts boundaries at samples 9000, 11000 and 13000.
"""

import numpy as np
import pytest

from scpi_control.signal_synth import SignalSpec, synthesize

RATE = 1_000_000.0


def test_a_boundary_sample_of_a_square_reads_high_not_low():
    """The defect, at the level a user sees it: one inverted sample."""
    spec = SignalSpec(kind="square", frequency=1_000.0, amplitude=1.0)
    samples = synthesize(spec, RATE, 14_000, t0=-0.006)
    # 0.006 is 6 whole periods, so index 9000 (3 ms later) starts a cycle and a
    # 50%-duty square must be at its HIGH level there.
    for boundary in (9000, 11000, 13000):
        assert samples[boundary] == pytest.approx(1.0), f"sample {boundary} sits on a cycle boundary and must read high"


def test_a_boundary_sample_of_a_sawtooth_resets_at_the_boundary():
    """`ramp` is the other kind discontinuous at the wrap, and it fails the same
    way -- it resets one sample early, reading +amplitude where the new cycle
    should already have restarted at -amplitude."""
    spec = SignalSpec(kind="ramp", frequency=1_000.0, amplitude=1.0)
    samples = synthesize(spec, RATE, 14_000, t0=-0.006)
    for boundary in (9000, 11000, 13000):
        assert samples[boundary] == pytest.approx(-1.0), f"sample {boundary} starts a cycle and a sawtooth must have reset"


def test_every_cycle_boundary_starts_a_high_run():
    """The artifact does NOT show up as a lone spike -- it delays the RISING edge
    (the one at the cycle wrap) by one sample. So the property to pin is that a
    high run begins at every whole-cycle index, which is what fails before the
    snap and holds after it."""
    spec = SignalSpec(kind="square", frequency=1_000.0, amplitude=1.0, duty=0.5)
    samples = synthesize(spec, RATE, 14_000, t0=-0.006)
    # t0 = -0.006 is six whole periods, so cycles start every 1000 samples.
    for boundary in range(0, 14_000, 1_000):
        assert samples[boundary] > 0, f"sample {boundary} starts a cycle and must begin the high run"
        if boundary:
            assert samples[boundary - 1] < 0, f"sample {boundary - 1} is the last of the previous cycle and must still be low"


def test_the_duty_threshold_is_a_separate_boundary_and_is_not_covered():
    """Deliberately documents a KNOWN residual rather than hiding it.

    The wrap at cycle fraction 0 is not the only decision point: `_square`
    compares against `duty`, and a sample landing exactly on that threshold is
    subject to the same float error from `t0 + i / sample_rate`. Snapping the
    integer boundary does not touch it, so a 50% duty can still measure 500/501
    samples per half cycle depending on t0.

    That is a strictly smaller defect -- the falling edge moves by one sample,
    rather than a full-amplitude sample inverting -- and fixing it means making
    every threshold comparison in every generator boundary-aware, which is a
    different piece of work. This test asserts the CURRENT behaviour so the gap
    is visible and so that closing it later fails here loudly rather than
    silently.
    """
    spec = SignalSpec(kind="square", frequency=1_000.0, amplitude=1.0, duty=0.5)
    samples = synthesize(spec, RATE, 14_000, t0=-0.006)
    high = int(np.count_nonzero(samples > 0))
    assert high != 7_000, "duty-threshold snapping now works -- delete this test and tighten the one above"
    assert abs(high - 7_000) <= 14, "the residual must stay at most one sample per cycle"


def test_the_snap_leaves_every_other_sample_bit_identical():
    """The fix must be inert away from boundaries. A trace whose samples avoid
    the boundaries entirely must be unchanged to the last bit -- this is what
    makes the correction safe to apply unconditionally."""
    spec = SignalSpec(kind="square", frequency=1_000.0, amplitude=1.0)
    # t0 = 0 lands every sample cleanly, so nothing here needs correcting.
    clean = synthesize(spec, RATE, 14_000, t0=0.0)
    expected = np.where((np.arange(14_000) % 1000) < 500, 1.0, -1.0)
    np.testing.assert_array_equal(clean, expected)


@pytest.mark.parametrize("kind", ["sine", "triangle", "multitone", "exponential"])
def test_continuous_kinds_are_unaffected(kind):
    """These are continuous across the wrap, so the artifact never showed on them
    and the correction must not perturb them either."""
    spec = SignalSpec(kind=kind, frequency=1_000.0, amplitude=1.0)
    samples = synthesize(spec, RATE, 4_000, t0=-0.006)
    assert np.all(np.isfinite(samples))
    assert np.max(np.abs(np.diff(samples))) < 0.05, "a continuous kind must have no full-amplitude jump"


def test_the_snap_applies_to_the_phase_shifted_cycle_too():
    """The correction is applied to `frequency * t + phase / 2pi`, so the shifted
    boundary must be snapped as well. A half-cycle phase puts the wrap where the
    falling edge used to be, so the boundary sample must read LOW."""
    spec = SignalSpec(kind="square", frequency=1_000.0, amplitude=1.0, phase=np.pi)
    samples = synthesize(spec, RATE, 14_000, t0=-0.006)
    # A pi phase is half a cycle, so the wrap moves off the round indices: it now
    # falls at 8500, 9500, 10500... Index 9000 lands on the DUTY threshold
    # instead, which is the separate residual documented above.
    # These also cover both directions of the snap -- index 8500 computes
    # 3.0000000000000004 (just above the integer) and 9500 computes
    # 3.9999999999999996 (just below), and both must resolve to 0.0.
    for boundary in (8_500, 9_500, 10_500):
        assert samples[boundary] > 0, f"with a pi phase, sample {boundary} starts a cycle and must begin the high run"
