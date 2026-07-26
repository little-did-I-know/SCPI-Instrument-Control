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
then (3) adds an RCLowPass DUT and prints how much it reduces the steepest
sample-to-sample step, i.e. how much it rounds the square wave's edges.

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

    sharp_step = float(np.max(np.abs(np.diff(sharp.voltage))))
    soft_step = float(np.max(np.abs(np.diff(soft.voltage))))
    reduction_pct = 100.0 * (1.0 - soft_step / sharp_step)
    print(f"Max sample-to-sample step with no DUT: {sharp_step:.4f} V")
    print(f"Max sample-to-sample step with RCLowPass(cutoff_hz=2000): {soft_step:.4f} V")
    print(f"The DUT reduced the steepest step by {reduction_pct:.1f} percent -- the edges are visibly rounded")


def main() -> None:
    awg = demo_live_loopback()
    try:
        demo_dut(awg)
    finally:
        awg.disconnect()


if __name__ == "__main__":
    main()
