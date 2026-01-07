"""Advanced waveform analysis and visualization.

This example demonstrates how to perform advanced analysis on captured
waveforms, including FFT analysis, statistical analysis, and visualization
using matplotlib.
"""

import matplotlib.pyplot as plt
import numpy as np

from scpi_control.automation import DataCollector

# Replace with your oscilloscope's IP address
SCOPE_IP = "192.168.1.100"


def plot_waveform(waveform, channel_num, title="Waveform"):
    """Plot time-domain waveform."""
    time = np.arange(len(waveform.voltage)) * waveform.time_interval
    time_ms = time * 1000  # Convert to milliseconds

    plt.figure(figsize=(12, 4))
    plt.plot(time_ms, waveform.voltage, linewidth=1)
    plt.xlabel("Time (ms)")
    plt.ylabel("Voltage (V)")
    plt.title(f"{title} - Channel {channel_num}")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()


def plot_fft(waveform, channel_num):
    """Plot frequency spectrum using FFT."""
    # Perform FFT
    fft_result = np.fft.fft(waveform.voltage)
    fft_freq = np.fft.fftfreq(len(waveform.voltage), waveform.time_interval)

    # Take only positive frequencies
    positive_freq_idx = fft_freq > 0
    freqs = fft_freq[positive_freq_idx]
    magnitude = np.abs(fft_result[positive_freq_idx])

    # Convert to dB
    magnitude_db = 20 * np.log10(magnitude + 1e-12)

    plt.figure(figsize=(12, 4))
    plt.plot(freqs / 1e3, magnitude_db, linewidth=1)
    plt.xlabel("Frequency (kHz)")
    plt.ylabel("Magnitude (dB)")
    plt.title(f"FFT Spectrum - Channel {channel_num}")
    plt.grid(True, alpha=0.3)
    plt.xlim(0, freqs.max() / 1e3)
    plt.tight_layout()


def analyze_signal_quality(waveform):
    """Analyze signal quality metrics."""
    voltage = waveform.voltage

    # Basic statistics
    mean_val = np.mean(voltage)
    std_val = np.std(voltage)
    rms_val = np.sqrt(np.mean(voltage**2))

    # Signal-to-noise ratio (simplified)
    # Assume signal is the AC component and noise is variation around it
    ac_component = voltage - mean_val
    signal_power = np.mean(ac_component**2)

    # Estimate noise as high-frequency component
    # (This is a simple approximation)
    filtered = np.convolve(voltage, np.ones(10) / 10, mode="same")
    noise = voltage - filtered
    noise_power = np.mean(noise**2)

    snr_db = 10 * np.log10(signal_power / (noise_power + 1e-12))

    # Total Harmonic Distortion (THD) estimation
    fft_result = np.fft.fft(voltage)
    fft_magnitude = np.abs(fft_result)

    # Find fundamental frequency (largest peak)
    fundamental_idx = np.argmax(fft_magnitude[1 : len(fft_magnitude) // 2]) + 1
    fundamental_power = fft_magnitude[fundamental_idx] ** 2

    # Sum harmonics (2f, 3f, 4f, 5f)
    harmonic_power = 0
    for n in range(2, 6):
        harmonic_idx = fundamental_idx * n
        if harmonic_idx < len(fft_magnitude):
            harmonic_power += fft_magnitude[harmonic_idx] ** 2

    thd = np.sqrt(harmonic_power / (fundamental_power + 1e-12)) * 100

    return {
        "mean": mean_val,
        "std_dev": std_val,
        "rms": rms_val,
        "snr_db": snr_db,
        "thd_percent": thd,
    }


def main():
    with DataCollector(SCOPE_IP) as collector:
        print(f"Connected to {collector.scope.identify()}\n")

        # Capture waveform
        print("Capturing waveform from channel 1...")
        waveforms = collector.capture_single([1])

        if 1 not in waveforms:
            print("Error: Channel 1 not available")
            return

        waveform = waveforms[1]
        print(f"Captured {len(waveform.voltage)} samples")

        # Basic analysis
        print("\n" + "=" * 60)
        print("BASIC ANALYSIS")
        print("=" * 60)
        basic_stats = collector.analyze_waveform(waveform)
        print(f"Vpp:        {basic_stats['vpp']:.4f} V")
        print(f"Amplitude:  {basic_stats['amplitude']:.4f} V")
        print(f"Mean:       {basic_stats['mean']:.4f} V")
        print(f"RMS:        {basic_stats['rms']:.4f} V")
        print(f"Std Dev:    {basic_stats['std_dev']:.4f} V")
        print(f"Max:        {basic_stats['max']:.4f} V")
        print(f"Min:        {basic_stats['min']:.4f} V")
        if basic_stats["frequency"] > 0:
            print(f"Frequency:  {basic_stats['frequency'] / 1e3:.2f} kHz")
            print(f"Period:     {basic_stats['period'] * 1e6:.2f} µs")

        # Advanced signal quality analysis
        print("\n" + "=" * 60)
        print("SIGNAL QUALITY ANALYSIS")
        print("=" * 60)
        quality = analyze_signal_quality(waveform)
        print(f"SNR:        {quality['snr_db']:.2f} dB")
        print(f"THD:        {quality['thd_percent']:.2f} %")

        # Statistical distribution
        print("\n" + "=" * 60)
        print("STATISTICAL DISTRIBUTION")
        print("=" * 60)
        percentiles = np.percentile(waveform.voltage, [1, 5, 25, 50, 75, 95, 99])
        print(f"1st percentile:   {percentiles[0]:.4f} V")
        print(f"5th percentile:   {percentiles[1]:.4f} V")
        print(f"25th percentile:  {percentiles[2]:.4f} V")
        print(f"Median (50th):    {percentiles[3]:.4f} V")
        print(f"75th percentile:  {percentiles[4]:.4f} V")
        print(f"95th percentile:  {percentiles[5]:.4f} V")
        print(f"99th percentile:  {percentiles[6]:.4f} V")

        # Visualizations
        print("\n" + "=" * 60)
        print("GENERATING VISUALIZATIONS")
        print("=" * 60)

        # Time domain plot
        print("Plotting time-domain waveform...")
        plot_waveform(waveform, 1, "Time Domain Analysis")

        # Frequency domain plot
        print("Plotting frequency spectrum...")
        plot_fft(waveform, 1)

        # Histogram
        print("Plotting voltage distribution...")
        plt.figure(figsize=(12, 4))
        plt.hist(waveform.voltage, bins=100, edgecolor="black", alpha=0.7)
        plt.xlabel("Voltage (V)")
        plt.ylabel("Count")
        plt.title("Voltage Distribution Histogram - Channel 1")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        print("\nDisplaying plots (close windows to continue)...")
        plt.show()

        # Save waveform data
        print("\nSaving waveform data and analysis...")
        collector.save_data(waveforms, "analyzed_waveform.npz")

        # Save analysis results
        with open("analysis_report.txt", "w") as f:
            f.write("WAVEFORM ANALYSIS REPORT\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Oscilloscope: {collector.scope.identify()}\n")
            f.write(f"Samples: {len(waveform.voltage)}\n")
            f.write(f"Sample Rate: {waveform.sample_rate / 1e6:.2f} MSa/s\n\n")

            f.write("BASIC MEASUREMENTS\n")
            f.write("-" * 60 + "\n")
            for key, value in basic_stats.items():
                f.write(f"{key:15s}: {value:.6f}\n")

            f.write("\nSIGNAL QUALITY\n")
            f.write("-" * 60 + "\n")
            for key, value in quality.items():
                f.write(f"{key:15s}: {value:.6f}\n")

        print("Analysis report saved to 'analysis_report.txt'")
        print("Done!")


if __name__ == "__main__":
    main()
