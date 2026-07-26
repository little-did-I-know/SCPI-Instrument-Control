"""AWG-to-scope loopback: a mock function generator's live state drives what a
mock oscilloscope captures, optionally through an RC device-under-test model.

scpi_control.connection.mock.loopback.AwgLoopback is a callable suitable for
MockConnection(signals={...}): it reads a separate mock AWG connection's
current channel state every time the scope acquires, so a SCPI write on the
AWG changes the very next scope capture -- two mock instruments joined by one
virtual cable. An optional scpi_control.dut.RCLowPass sits on that cable,
standing in for a device under test between the two instruments and rounding
the edges of whatever the AWG outputs.

This example (1) opens a mock AWG and a mock scope wired together with
AwgLoopback and prints the captured peak-to-peak of a sine, (2) switches the
AWG to a square wave with a plain SCPI write and prints the new peak-to-peak,
then (3) adds an RCLowPass DUT and prints the 10%-90% rise time of the
square wave's rising edge with and without the DUT, to show how much it
rounds the edge. Rise time is used rather than a raw sample-to-sample step
because the mock's int8 code quantization (25 codes/division, see
docs/user-guide/synthetic-signals.md) would dominate a step-height
comparison at a gentle cutoff; a 10%-90% time span is many samples wide and
is not limited by the code grid.

Requirements: SCPI-Instrument-Control (core install) -- runs entirely against
mock connections, no instrument needed.
"""

import numpy as np

from scpi_control.connection import MockConnection
from scpi_control.connection.mock.loopback import AwgLoopback
from scpi_control.dut import RCLowPass
from scpi_control.oscilloscope import Oscilloscope

SAMPLE_RATE = 1_000_000.0
TIMEBASE = 1e-3


def _make_awg() -> MockConnection:
    """A mock AWG, output enabled at 2.0 Vpp / 1 kHz sine."""
    awg = MockConnection("mock", awg_mode=True)
    awg.connect()
    awg.write("C1:BSWV FRQ,1000")
    awg.write("C1:BSWV AMP,2.0")
    awg.write("C1:OUTP ON")
    return awg


def _make_scope(source) -> Oscilloscope:
    """A mock scope whose channel 1 synthesizes from `source` (an AwgLoopback)."""
    conn = MockConnection(
        "mock",
        channel_states={1: True, 2: False, 3: False, 4: False},
        trigger_status=["Stop"],
        sample_rate=SAMPLE_RATE,
        timebase=TIMEBASE,
        signals={1: source},
    )
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    return scope


def _vpp(voltage) -> float:
    return float(voltage.max() - voltage.min())


def _rising_crossing(time_s: np.ndarray, voltage: np.ndarray, level: float, start_index: int = 0):
    """Sub-sample time of the first rising crossing of `level` at/after `start_index`.

    Linear interpolation between the two bracketing samples locates the
    crossing between samples, not just to the nearest one. Returns
    (crossing_time, index_of_the_sample_just_before_the_crossing).
    """
    candidates = np.flatnonzero((voltage[start_index:-1] < level) & (voltage[start_index + 1 :] >= level))
    if candidates.size == 0:
        raise ValueError(f"no rising crossing of {level} found at or after index {start_index}")
    i = start_index + int(candidates[0])
    t0, t1 = time_s[i], time_s[i + 1]
    v0, v1 = voltage[i], voltage[i + 1]
    crossing_time = float(t0 + (level - v0) * (t1 - t0) / (v1 - v0))
    return crossing_time, i


def _rise_time_10_90_us(waveform) -> float:
    """10%-90% rise time (microseconds) of the first rising transition.

    The 10% and 90% levels are relative to the trace's own min/max, so this
    works the same way whether or not a DUT has rounded the edge. Unlike a
    raw sample-to-sample step, a rise time spans many samples and is not
    limited by the mock's int8 code quantization.
    """
    voltage = waveform.voltage
    time_s = waveform.time
    lo, hi = float(voltage.min()), float(voltage.max())
    v10 = lo + 0.10 * (hi - lo)
    v90 = lo + 0.90 * (hi - lo)
    t10, i10 = _rising_crossing(time_s, voltage, v10)
    t90, _ = _rising_crossing(time_s, voltage, v90, start_index=i10)
    return (t90 - t10) * 1e6


def demo_live_loopback() -> MockConnection:
    """Capture a sine, switch the AWG to a square over SCPI, capture again."""
    print("=== Part 1: the scope captures whatever the AWG is currently outputting ===")
    awg = _make_awg()
    scope = _make_scope(AwgLoopback(awg, awg_channel=1))
    try:
        sine = scope.get_waveform(1, provenance=False)
        print(f"AWG set to SINE, 2.0 Vpp: scope captures Vpp={_vpp(sine.voltage):.3f} V")

        awg.write("C1:BSWV WVTP,SQUARE")
        square = scope.get_waveform(1, provenance=False)
        print(f"AWG switched to SQUARE via 'C1:BSWV WVTP,SQUARE': scope captures Vpp={_vpp(square.voltage):.3f} V")
    finally:
        scope.disconnect()
    return awg


def demo_dut(awg: MockConnection) -> None:
    """Add an RCLowPass DUT between the (now square-wave) AWG and the scope."""
    print()
    print("=== Part 2: an RCLowPass DUT rounds the square wave's edges ===")
    sharp_scope = _make_scope(AwgLoopback(awg))
    soft_scope = _make_scope(AwgLoopback(awg, dut=RCLowPass(cutoff_hz=2_000.0)))
    try:
        sharp = sharp_scope.get_waveform(1, provenance=False)
        soft = soft_scope.get_waveform(1, provenance=False)
    finally:
        sharp_scope.disconnect()
        soft_scope.disconnect()

    sharp_rise_us = _rise_time_10_90_us(sharp)
    soft_rise_us = _rise_time_10_90_us(soft)
    print(f"10-90 percent rise time with no DUT: {sharp_rise_us:.3f} us (an ideal edge, a fraction of one sample)")
    print(f"10-90 percent rise time with RCLowPass(cutoff_hz=2000): {soft_rise_us:.1f} us")
    print("The DUT stretched the rising edge from a fraction of a microsecond to roughly " f"{soft_rise_us:.0f} us -- the edge is visibly rounded")


def main() -> None:
    awg = demo_live_loopback()
    try:
        demo_dut(awg)
    finally:
        awg.disconnect()


if __name__ == "__main__":
    main()
