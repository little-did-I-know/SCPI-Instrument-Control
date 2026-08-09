"""Simple single capture example.

This example shows how to capture a single waveform from one or more channels
and save it to a file.

Requirements: none by default -- runs against the built-in mock scope. Pass
--host <ip> to drive a real oscilloscope on the network.

Expected output: per-channel capture stats and basic analysis (Vpp, mean,
RMS, frequency) printed to the console, and 'simple_capture.npz' saved to
the current directory.
"""

import argparse

from scpi_control.automation import DataCollector
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

    # Create data collector and connect
    collector = DataCollector(args.host, connection=_connect(args.host))
    collector.connect()

    try:
        # Capture waveforms from channels 1 and 2
        print("Capturing waveforms from channels 1 and 2...")
        waveforms = collector.capture_single([1, 2])

        # Display basic information
        for ch, waveform in waveforms.items():
            print(f"\nChannel {ch}:")
            print(f"  Samples: {len(waveform.voltage)}")
            print(f"  Sample rate: {waveform.sample_rate / 1e6:.2f} MSa/s")
            print(f"  Time interval: {(1.0 / waveform.sample_rate) * 1e9:.2f} ns")
            print(f"  Voltage range: {waveform.voltage.min():.3f}V to {waveform.voltage.max():.3f}V")

        # Analyze waveforms
        for ch, waveform in waveforms.items():
            analysis = collector.analyze_waveform(waveform)
            print(f"\nChannel {ch} Analysis:")
            print(f"  Vpp: {analysis['vpp']:.3f}V")
            print(f"  Mean: {analysis['mean']:.3f}V")
            print(f"  RMS: {analysis['rms']:.3f}V")
            if analysis["frequency"] > 0:
                print(f"  Frequency: {analysis['frequency'] / 1e3:.2f} kHz")

        # Save waveforms to file
        print("\nSaving waveforms to 'simple_capture.npz'...")
        collector.save_data(waveforms, "simple_capture.npz", format="npz")
        print("Done!")

    finally:
        collector.disconnect()


if __name__ == "__main__":
    main()
