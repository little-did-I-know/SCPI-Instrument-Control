#!/usr/bin/env python3
"""
Test script for signal type detection and waveform analysis.

This script generates synthetic waveforms of different types and tests
the signal detection and statistics calculation.
"""

import numpy as np
from siglent.report_generator.models.report_data import WaveformData
from siglent.report_generator.utils.waveform_analyzer import WaveformAnalyzer, SignalType


def generate_sine_wave(freq=1000, sample_rate=100000, duration=0.01, amplitude=1.0, noise_level=0.0):
    """Generate a sine wave."""
    t = np.linspace(0, duration, int(sample_rate * duration))
    v = amplitude * np.sin(2 * np.pi * freq * t)
    if noise_level > 0:
        v += np.random.normal(0, noise_level, len(v))
    return t, v


def generate_square_wave(freq=1000, sample_rate=100000, duration=0.01, amplitude=1.0):
    """Generate a square wave."""
    t = np.linspace(0, duration, int(sample_rate * duration))
    v = amplitude * np.sign(np.sin(2 * np.pi * freq * t))
    return t, v


def generate_triangle_wave(freq=1000, sample_rate=100000, duration=0.01, amplitude=1.0):
    """Generate a triangle wave."""
    from scipy import signal
    t = np.linspace(0, duration, int(sample_rate * duration))
    v = amplitude * signal.sawtooth(2 * np.pi * freq * t, width=0.5)
    return t, v


def generate_sawtooth_wave(freq=1000, sample_rate=100000, duration=0.01, amplitude=1.0):
    """Generate a sawtooth wave."""
    from scipy import signal
    t = np.linspace(0, duration, int(sample_rate * duration))
    v = amplitude * signal.sawtooth(2 * np.pi * freq * t)
    return t, v


def generate_pulse_wave(freq=1000, sample_rate=100000, duration=0.01, amplitude=1.0, duty_cycle=0.2):
    """Generate a pulse wave with specified duty cycle."""
    t = np.linspace(0, duration, int(sample_rate * duration))
    v = amplitude * (np.sin(2 * np.pi * freq * t) > (1 - 2 * duty_cycle)).astype(float)
    return t, v


def generate_dc_signal(sample_rate=100000, duration=0.01, level=2.5):
    """Generate a DC signal."""
    t = np.linspace(0, duration, int(sample_rate * duration))
    v = np.ones_like(t) * level
    return t, v


def generate_noise(sample_rate=100000, duration=0.01, amplitude=1.0):
    """Generate random noise."""
    t = np.linspace(0, duration, int(sample_rate * duration))
    v = np.random.normal(0, amplitude, len(v))
    return t, v


def test_waveform(name, time_data, voltage_data, sample_rate, expected_type=None):
    """Test signal detection on a waveform."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")

    # Create waveform data
    waveform = WaveformData(
        channel_name="CH1",
        time_data=time_data,
        voltage_data=voltage_data,
        sample_rate=sample_rate,
        record_length=len(time_data)
    )

    # Analyze the waveform
    waveform.analyze()

    # Display results
    print(f"Detected Signal Type: {waveform.signal_type}")
    print(f"Confidence: {waveform.signal_type_confidence:.1f}%")

    if expected_type:
        match = "PASS" if waveform.signal_type == expected_type else "FAIL"
        print(f"Expected: {expected_type} [{match}]")

    # Show key statistics
    print("\nKey Statistics:")
    if waveform.statistics:
        stats_to_show = ['frequency', 'vpp', 'vrms', 'duty_cycle', 'thd', 'snr']
        for stat in stats_to_show:
            value = waveform.get_statistic(stat)
            if value is not None:
                formatted = waveform.format_statistic(stat)
                print(f"  {stat:15s}: {formatted}")

    return waveform.signal_type == expected_type if expected_type else True


def main():
    """Run all tests."""
    print("Signal Type Detection Test Suite")
    print("="*60)

    sample_rate = 100000  # 100 kS/s
    duration = 0.01  # 10 ms

    results = []

    # Test 1: Sine wave
    t, v = generate_sine_wave(freq=1000, sample_rate=sample_rate, duration=duration)
    results.append(test_waveform("Pure Sine Wave (1 kHz)", t, v, sample_rate, SignalType.SINE))

    # Test 2: Square wave
    t, v = generate_square_wave(freq=1000, sample_rate=sample_rate, duration=duration)
    results.append(test_waveform("Square Wave (1 kHz)", t, v, sample_rate, SignalType.SQUARE))

    # Test 3: Triangle wave
    t, v = generate_triangle_wave(freq=1000, sample_rate=sample_rate, duration=duration)
    results.append(test_waveform("Triangle Wave (1 kHz)", t, v, sample_rate, SignalType.TRIANGLE))

    # Test 4: Sawtooth wave
    t, v = generate_sawtooth_wave(freq=1000, sample_rate=sample_rate, duration=duration)
    results.append(test_waveform("Sawtooth Wave (1 kHz)", t, v, sample_rate, SignalType.SAWTOOTH))

    # Test 5: Pulse wave (20% duty cycle)
    t, v = generate_pulse_wave(freq=1000, sample_rate=sample_rate, duration=duration, duty_cycle=0.2)
    results.append(test_waveform("Pulse Wave (1 kHz, 20% duty)", t, v, sample_rate, SignalType.PULSE))

    # Test 6: DC signal
    t, v = generate_dc_signal(sample_rate=sample_rate, duration=duration, level=2.5)
    results.append(test_waveform("DC Signal (2.5V)", t, v, sample_rate, SignalType.DC))

    # Test 7: Noisy sine wave
    t, v = generate_sine_wave(freq=1000, sample_rate=sample_rate, duration=duration, noise_level=0.1)
    results.append(test_waveform("Noisy Sine Wave (1 kHz, SNR ~20dB)", t, v, sample_rate))

    # Summary
    print(f"\n{'='*60}")
    print("Test Summary")
    print(f"{'='*60}")
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("[PASS] All tests passed!")
    else:
        print(f"[FAIL] {total - passed} test(s) failed")

    return passed == total


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
