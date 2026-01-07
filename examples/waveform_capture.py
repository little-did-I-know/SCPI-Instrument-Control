"""Waveform capture example for Siglent oscilloscope.

This script demonstrates how to capture waveform data from
the oscilloscope and save it to a file.
"""

import matplotlib.pyplot as plt

from scpi_control import Oscilloscope

# Replace with your oscilloscope's IP address
SCOPE_IP = "192.168.1.100"


def main():
    # Create oscilloscope instance and connect
    scope = Oscilloscope(SCOPE_IP)

    try:
        print(f"Connecting to oscilloscope at {SCOPE_IP}...")
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
        print(f"Timebase: {waveform.timebase*1e6:.3f} µs/div")

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

    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()

    finally:
        print("\nDisconnecting...")
        scope.disconnect()
        print("Done!")


if __name__ == "__main__":
    main()
