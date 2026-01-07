"""Measurement example for Siglent oscilloscope.

This script demonstrates how to perform automated measurements
on oscilloscope channels.
"""

import time

from scpi_control import Oscilloscope

# Replace with your oscilloscope's IP address
SCOPE_IP = "192.168.1.100"


def main():
    # Create oscilloscope instance and connect
    with Oscilloscope(SCOPE_IP) as scope:
        print(f"Connected to: {scope.device_info['model']}")

        # Configure channel 1
        print("\nConfiguring Channel 1...")
        scope.channel1.enable()
        scope.channel1.coupling = "DC"
        scope.channel1.voltage_scale = 1.0

        # Start acquisition
        scope.run()
        print("Acquisition running...")

        # Wait a moment for stable signal
        time.sleep(0.5)

        # Perform individual measurements
        print("\n--- Individual Measurements on Channel 1 ---")

        try:
            freq = scope.measurement.measure_frequency(1)
            print(f"Frequency:    {freq/1e6:.6f} MHz ({freq:.2f} Hz)")
        except Exception as e:
            print(f"Frequency:    Error - {e}")

        try:
            period = scope.measurement.measure_period(1)
            print(f"Period:       {period*1e6:.6f} µs")
        except Exception as e:
            print(f"Period:       Error - {e}")

        try:
            vpp = scope.measurement.measure_vpp(1)
            print(f"Vpp:          {vpp:.6f} V")
        except Exception as e:
            print(f"Vpp:          Error - {e}")

        try:
            amplitude = scope.measurement.measure_amplitude(1)
            print(f"Amplitude:    {amplitude:.6f} V")
        except Exception as e:
            print(f"Amplitude:    Error - {e}")

        try:
            vmax = scope.measurement.measure_max(1)
            print(f"Max:          {vmax:.6f} V")
        except Exception as e:
            print(f"Max:          Error - {e}")

        try:
            vmin = scope.measurement.measure_min(1)
            print(f"Min:          {vmin:.6f} V")
        except Exception as e:
            print(f"Min:          Error - {e}")

        try:
            vrms = scope.measurement.measure_rms(1)
            print(f"RMS:          {vrms:.6f} V")
        except Exception as e:
            print(f"RMS:          Error - {e}")

        try:
            vmean = scope.measurement.measure_mean(1)
            print(f"Mean:         {vmean:.6f} V")
        except Exception as e:
            print(f"Mean:         Error - {e}")

        # Perform all measurements at once
        print("\n--- All Measurements ---")
        all_measurements = scope.measurement.measure_all(1)

        for name, value in all_measurements.items():
            if value is not None:
                if "freq" in name.lower():
                    print(f"{name:12s}: {value/1e6:.6f} MHz")
                elif "period" in name.lower():
                    print(f"{name:12s}: {value*1e6:.6f} µs")
                else:
                    print(f"{name:12s}: {value:.6f} V")
            else:
                print(f"{name:12s}: N/A")

        print("\nDone!")


if __name__ == "__main__":
    main()
