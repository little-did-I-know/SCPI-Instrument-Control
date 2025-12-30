"""Continuous time-series data collection.

This example demonstrates how to collect waveforms continuously over a
period of time. This is useful for monitoring signals, collecting statistics,
or capturing time-varying phenomena.
"""

from siglent.automation import DataCollector

# Replace with your oscilloscope's IP address
SCOPE_IP = "192.168.1.100"


def progress_callback(captures_done, status):
    """Display progress during continuous capture."""
    print(f"[{captures_done}] {status}")


def main():
    with DataCollector(SCOPE_IP) as collector:
        print(f"Connected to {collector.scope.identify()}\n")

        # Example 1: Collect to memory (good for short durations)
        print("Example 1: Collecting to memory for 10 seconds...")
        results = collector.start_continuous_capture(channels=[1, 2], duration=10, interval=0.5, progress_callback=progress_callback)  # 10 seconds  # Capture every 0.5 seconds

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
        print("\n" + "=" * 60)
        print("Example 2: Collecting to files for 30 seconds...")
        print("Files will be saved to 'continuous_data/' directory")
        print("Press Ctrl+C to stop early\n")

        collector.start_continuous_capture(
            channels=[1, 2],
            duration=30,
            interval=1.0,
            output_dir="continuous_data",
            file_format="npz",
            progress_callback=progress_callback,
        )  # 30 seconds  # Capture every 1 second

        print("\nContinuous capture complete! Files saved to 'continuous_data/'")


if __name__ == "__main__":
    main()
