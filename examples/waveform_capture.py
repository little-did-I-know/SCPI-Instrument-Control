"""Waveform capture example for Siglent oscilloscope.

This script demonstrates how to capture waveform data from
the oscilloscope and save it to a file.

Requirements: none by default -- runs against the built-in mock scope. Pass
--host <ip> to drive a real oscilloscope on the network. matplotlib is a
core dependency, no extra install needed.

Expected output: captures Channel 1, saves 'waveform.csv' and 'waveform.png'
to the current directory, and opens a plot window (a no-op under a
non-interactive matplotlib backend, e.g. in tests).
"""

import argparse

import matplotlib.pyplot as plt

from scpi_control import Oscilloscope
from scpi_control.connection import MockConnection
from scpi_control.signal_synth import SignalSpec


def _connect(host):
    """Return a mock connection for --host mock, or None to use a real socket."""
    if host != "mock":
        return None
    return MockConnection(
        "mock",
        channel_states={1: True},
        signals={1: SignalSpec(kind="square", frequency=1000.0, amplitude=1.65, offset=1.65)},
        sample_rate=20e6,
        timebase=500e-6,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="mock", help="Instrument hostname/IP, or 'mock' for the built-in mock scope (default: mock)")
    args = parser.parse_args()

    scope = Oscilloscope(args.host, connection=_connect(args.host))

    try:
        print(f"Connecting to oscilloscope at {args.host}...")
        scope.connect()
        print(f"Connected to: {scope.device_info['model']}")

        # Configure channel 1
        print("\nConfiguring Channel 1...")
        scope.channel1.enable()
        scope.channel1.coupling = "DC"
        scope.channel1.voltage_scale = 1.0

        # Set trigger
        scope.trigger.mode = "NORMAL"
        scope.trigger.source = "C1"
        scope.trigger.level = 0.0

        # Capture waveform
        print("\nCapturing waveform from Channel 1...")
        waveform = scope.get_waveform(channel=1)

        print(f"Captured {len(waveform)} samples")
        print(f"Sample rate: {waveform.sample_rate/1e9:.3f} GSa/s")
        print(f"Timebase: {waveform.timebase*1e6:.3f} us/div")

        # Save waveform to CSV
        print("\nSaving waveform data to 'waveform.csv'...")
        scope.waveform.save_waveform(waveform, "waveform.csv", format="CSV")

        # Plot waveform
        print("\nPlotting waveform...")
        plt.figure(figsize=(12, 6))
        plt.plot(waveform.time * 1e6, waveform.voltage, linewidth=0.5)
        plt.xlabel("Time (µs)")
        plt.ylabel("Voltage (V)")
        plt.title(f"Waveform from Channel {waveform.channel}")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        # Save plot
        plt.savefig("waveform.png", dpi=150)
        print("Waveform plot saved to 'waveform.png'")

        # Show plot
        plt.show()

    finally:
        print("\nDisconnecting...")
        scope.disconnect()
        print("Done!")


if __name__ == "__main__":
    main()
