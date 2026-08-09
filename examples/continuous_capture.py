"""Continuous time-series data collection.

This example demonstrates how to collect waveforms continuously over a
period of time. This is useful for monitoring signals, collecting statistics,
or capturing time-varying phenomena.

Requirements: none by default -- runs against the built-in mock scope. Pass
--host <ip> to drive a real oscilloscope on the network. Use --duration to
control the length of the first (in-memory) run (default: 2.0 seconds); the
second (file-saving) run lasts 3x as long, mirroring the original 10s/30s
ratio while staying well inside a test timeout.

Expected output: an in-memory capture run with Vpp statistics printed to
the console, followed by a second run that saves waveform files to a
'continuous_data/' directory in the current directory.
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


def progress_callback(captures_done, status):
    """Display progress during continuous capture."""
    print(f"[{captures_done}] {status}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="mock", help="Instrument hostname/IP, or 'mock' for the built-in mock scope (default: mock)")
    parser.add_argument("--duration", type=float, default=2.0, help="Duration in seconds of the first (in-memory) run; the second run lasts 3x as long (default: 2.0)")
    args = parser.parse_args()

    with DataCollector(args.host, connection=_connect(args.host)) as collector:
        print(f"Connected to {collector.scope.identify()}\n")

        # Example 1: Collect to memory (good for short durations)
        print(f"Example 1: Collecting to memory for {args.duration:.1f} seconds...")
        results = collector.start_continuous_capture(channels=[1, 2], duration=args.duration, interval=0.5, progress_callback=progress_callback)

        print(f"\nCollected {len(results)} captures to memory")
        print(f"First capture timestamp: {results[0]['timestamp']}")
        print(f"Last capture timestamp: {results[-1]['timestamp']}")

        # Analyze the captured data
        print("\nAnalyzing captured data...")
        ch1_vpps = []
        for result in results:
            if 1 in result["waveforms"]:
                analysis = collector.analyze_waveform(result["waveforms"][1])
                ch1_vpps.append(analysis["vpp"])

        if ch1_vpps:
            import numpy as np

            print(f"Channel 1 Vpp statistics:")
            print(f"  Mean: {np.mean(ch1_vpps):.3f}V")
            print(f"  Std Dev: {np.std(ch1_vpps):.3f}V")
            print(f"  Min: {np.min(ch1_vpps):.3f}V")
            print(f"  Max: {np.max(ch1_vpps):.3f}V")

        # Example 2: Collect to files (good for long durations)
        second_duration = args.duration * 3
        print("\n" + "=" * 60)
        print(f"Example 2: Collecting to files for {second_duration:.1f} seconds...")
        print("Files will be saved to 'continuous_data/' directory")
        print("Press Ctrl+C to stop early\n")

        collector.start_continuous_capture(
            channels=[1, 2],
            duration=second_duration,
            interval=1.0,
            output_dir="continuous_data",
            file_format="npz",
            progress_callback=progress_callback,
        )

        print("\nContinuous capture complete! Files saved to 'continuous_data/'")


if __name__ == "__main__":
    main()
