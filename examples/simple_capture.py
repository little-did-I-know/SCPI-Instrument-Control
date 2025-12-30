"""Simple single capture example.

This example shows how to capture a single waveform from one or more channels
and save it to a file.
"""

from siglent.automation import DataCollector

# Replace with your oscilloscope's IP address
SCOPE_IP = "192.168.1.100"


def main():
    # Create data collector and connect
    collector = DataCollector(SCOPE_IP)
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
            print(f"  Time interval: {waveform.time_interval * 1e9:.2f} ns")
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
