"""Waveform math: adding and subtracting captured channels.

Combines two captured channels arithmetically with scpi_control.math_channel.
MathOperations works on captured WaveformData objects, so the arithmetic
happens in Python on real samples -- it does not depend on the instrument
having a MATH channel.

Requirements: none by default -- runs against the built-in mock scope. Pass
--host <ip> to drive a real oscilloscope on the network.

Expected output: per-channel and combined Vpp figures printed to the console.
No files are written.
"""

import argparse

from scpi_control import Oscilloscope
from scpi_control.connection import MockConnection
from scpi_control.math_channel import MathOperations
from scpi_control.signal_synth import SignalSpec


def _connect(host):
    if host != "mock":
        return None
    return MockConnection(
        "mock",
        channel_states={1: True, 2: True},
        signals={
            1: SignalSpec(kind="sine", frequency=1000.0, amplitude=1.0),
            2: SignalSpec(kind="sine", frequency=1000.0, amplitude=0.7),
        },
        sample_rate=1e6,
        timebase=1e-3,
    )


def _vpp(waveform):
    return float(waveform.voltage.max() - waveform.voltage.min())


def main():
    parser = argparse.ArgumentParser(description="Waveform math on two captured channels")
    parser.add_argument("--host", default="mock", help="Instrument hostname/IP, or 'mock' (default: mock)")
    args = parser.parse_args()

    scope = Oscilloscope(args.host, connection=_connect(args.host))
    scope.connect()
    try:
        ch1 = scope.get_waveform(channel=1)
        ch2 = scope.get_waveform(channel=2)
        print(f"CH1 Vpp: {_vpp(ch1):.3f} V")
        print(f"CH2 Vpp: {_vpp(ch2):.3f} V")

        total = MathOperations.add(ch1, ch2)
        diff = MathOperations.subtract(ch1, ch2)
        print(f"CH1 + CH2 Vpp: {_vpp(total):.3f} V")
        print(f"CH1 - CH2 Vpp: {_vpp(diff):.3f} V")
    finally:
        scope.disconnect()


if __name__ == "__main__":
    main()
