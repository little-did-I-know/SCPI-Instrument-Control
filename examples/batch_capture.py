"""Batch capture with different configurations.

This example demonstrates how to capture multiple waveforms with different
timebase and voltage scale settings. This is useful for characterizing
signals at different time scales or for automated testing.

Requirements: none by default -- runs against the built-in mock scope. Pass
--host <ip> to drive a real oscilloscope on the network.

Expected output: progress lines for each capture, a summary of the first
five results, and the batch saved to a 'batch_output/' directory (waveform
files plus metadata.txt) in the current directory.
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


def progress_callback(current, total, status):
    """Display progress during batch capture."""
    percent = (current / total) * 100
    print(f"Progress: {current}/{total} ({percent:.1f}%) - {status}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="mock", help="Instrument hostname/IP, or 'mock' for the built-in mock scope (default: mock)")
    args = parser.parse_args()

    # Create data collector with context manager
    with DataCollector(args.host, connection=_connect(args.host)) as collector:
        print(f"Connected to {collector.scope.identify()}\n")

        # Configure batch capture parameters
        timebase_scales = ["1us", "10us", "100us", "1ms"]
        voltage_scales = {1: ["500mV", "1V", "2V"]}  # Different scales for channel 1
        triggers_per_config = 3

        print("Starting batch capture...")
        print(f"  Timebase scales: {timebase_scales}")
        print(f"  Voltage scales: {voltage_scales}")
        print(f"  Triggers per config: {triggers_per_config}")
        print(f"  Total captures: {len(timebase_scales) * len(voltage_scales[1]) * triggers_per_config}\n")

        # Perform batch capture
        results = collector.batch_capture(
            channels=[1],
            timebase_scales=timebase_scales,
            voltage_scales=voltage_scales,
            triggers_per_config=triggers_per_config,
            progress_callback=progress_callback,
        )

        print(f"\nBatch capture complete! Collected {len(results)} waveforms")

        # Display summary of first few captures
        print("\nFirst 5 captures:")
        for i, result in enumerate(results[:5]):
            config = result["config"]
            waveforms = result["waveforms"]
            print(f"  {i+1}. Config: {config}, Channels: {list(waveforms.keys())}")

        # Save batch results
        print("\nSaving batch results to 'batch_output' directory...")
        collector.save_batch(results, "batch_output", format="npz")
        print("Done! Results saved to 'batch_output/' with metadata.txt")


if __name__ == "__main__":
    main()
