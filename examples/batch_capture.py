"""Batch capture with different configurations.

This example demonstrates how to capture multiple waveforms with different
timebase and voltage scale settings. This is useful for characterizing
signals at different time scales or for automated testing.
"""

from siglent.automation import DataCollector

# Replace with your oscilloscope's IP address
SCOPE_IP = "192.168.1.100"


def progress_callback(current, total, status):
    """Display progress during batch capture."""
    percent = (current / total) * 100
    print(f"Progress: {current}/{total} ({percent:.1f}%) - {status}")


def main():
    # Create data collector with context manager
    with DataCollector(SCOPE_IP) as collector:
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
