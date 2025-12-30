"""Advanced analysis tools for waveform data."""

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
from scipy import signal

logger = logging.getLogger(__name__)


@dataclass
class FFTResult:
    """Result of FFT analysis.

    Attributes:
        frequency: Frequency array (Hz)
        magnitude: Magnitude array (linear or dB)
        phase: Phase array (radians)
        window: Window function used
        sample_rate: Sample rate (Hz)
        magnitude_db: Whether magnitude is in dB
    """

    frequency: np.ndarray
    magnitude: np.ndarray
    phase: np.ndarray
    window: str
    sample_rate: float
    magnitude_db: bool = True

    def get_peak_frequency(self, num_peaks: int = 1) -> list:
        """Get the peak frequencies.

        Args:
            num_peaks: Number of peaks to find

        Returns:
            List of (frequency, magnitude) tuples
        """
        # Find peaks
        peaks, _ = signal.find_peaks(self.magnitude, height=0)

        # Sort by magnitude (descending)
        if len(peaks) > 0:
            peak_magnitudes = self.magnitude[peaks]
            sorted_indices = np.argsort(peak_magnitudes)[::-1]
            top_peaks = peaks[sorted_indices[:num_peaks]]

            results = []
            for peak_idx in top_peaks:
                freq = self.frequency[peak_idx]
                mag = self.magnitude[peak_idx]
                results.append((freq, mag))

            return results
        else:
            return []


class FFTAnalyzer:
    """FFT analyzer for frequency domain analysis of waveforms."""

    WINDOW_FUNCTIONS = {
        "rectangular": np.ones,
        "hanning": np.hanning,
        "hamming": np.hamming,
        "blackman": np.blackman,
        "bartlett": np.bartlett,
        "flattop": signal.windows.flattop,
    }

    def __init__(self):
        """Initialize FFT analyzer."""
        logger.info("FFT analyzer initialized")

    def compute_fft(self, waveform, window: str = "hanning", output_db: bool = True, detrend: bool = True) -> Optional[FFTResult]:
        """Compute FFT of a waveform.

        Args:
            waveform: Input waveform
            window: Window function name ('rectangular', 'hanning', 'hamming', 'blackman', 'bartlett', 'flattop')
            output_db: If True, output magnitude in dB; otherwise linear
            detrend: If True, remove DC component before FFT

        Returns:
            FFTResult or None if error
        """
        if waveform is None:
            logger.warning("Cannot compute FFT on None waveform")
            return None

        try:
            # Get voltage data
            voltage = waveform.voltage
            time = waveform.time

            if len(voltage) < 2:
                logger.warning("Waveform too short for FFT")
                return None

            # Calculate sample rate
            dt = np.mean(np.diff(time))
            sample_rate = 1.0 / dt

            # Detrend if requested (remove DC component)
            if detrend:
                voltage = voltage - np.mean(voltage)

            # Apply window function
            if window.lower() in self.WINDOW_FUNCTIONS:
                window_func = self.WINDOW_FUNCTIONS[window.lower()]
                windowed_voltage = voltage * window_func(len(voltage))
            else:
                logger.warning(f"Unknown window function '{window}', using rectangular")
                windowed_voltage = voltage

            # Compute FFT
            fft_result = np.fft.rfft(windowed_voltage)
            frequencies = np.fft.rfftfreq(len(voltage), dt)

            # Calculate magnitude and phase
            magnitude_linear = np.abs(fft_result)
            phase = np.angle(fft_result)

            # Convert to dB if requested
            if output_db:
                # Avoid log(0) by using a small epsilon
                epsilon = 1e-12
                magnitude = 20 * np.log10(magnitude_linear + epsilon)
            else:
                magnitude = magnitude_linear

            result = FFTResult(
                frequency=frequencies,
                magnitude=magnitude,
                phase=phase,
                window=window,
                sample_rate=sample_rate,
                magnitude_db=output_db,
            )

            logger.info(f"FFT computed: {len(frequencies)} frequency bins, " f"sample rate {sample_rate/1e6:.3f} MHz, window={window}")

            return result

        except Exception as e:
            logger.error(f"FFT computation error: {e}")
            return None

    def compute_power_spectrum(self, waveform, window: str = "hanning", nperseg: Optional[int] = None) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """Compute power spectral density using Welch's method.

        Args:
            waveform: Input waveform
            window: Window function name
            nperseg: Length of each segment (default: 256)

        Returns:
            Tuple of (frequencies, power_spectrum) or None if error
        """
        if waveform is None:
            return None

        try:
            voltage = waveform.voltage
            time = waveform.time
            dt = np.mean(np.diff(time))
            sample_rate = 1.0 / dt

            if nperseg is None:
                nperseg = min(256, len(voltage) // 4)

            # Compute power spectral density using Welch's method
            frequencies, psd = signal.welch(voltage, fs=sample_rate, window=window, nperseg=nperseg, scaling="density")

            logger.info(f"Power spectrum computed using Welch's method")

            return frequencies, psd

        except Exception as e:
            logger.error(f"Power spectrum computation error: {e}")
            return None

    def compute_spectrogram(self, waveform, window: str = "hanning", nperseg: Optional[int] = None) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """Compute spectrogram (time-frequency representation).

        Args:
            waveform: Input waveform
            window: Window function name
            nperseg: Length of each segment (default: 256)

        Returns:
            Tuple of (frequencies, times, spectrogram) or None if error
        """
        if waveform is None:
            return None

        try:
            voltage = waveform.voltage
            time = waveform.time
            dt = np.mean(np.diff(time))
            sample_rate = 1.0 / dt

            if nperseg is None:
                nperseg = min(256, len(voltage) // 4)

            # Compute spectrogram
            frequencies, times, Sxx = signal.spectrogram(voltage, fs=sample_rate, window=window, nperseg=nperseg)

            logger.info(f"Spectrogram computed: {len(frequencies)}x{len(times)} matrix")

            return frequencies, times, Sxx

        except Exception as e:
            logger.error(f"Spectrogram computation error: {e}")
            return None

    def apply_bandpass_filter(self, waveform, lowcut: float, highcut: float, order: int = 5):
        """Apply bandpass filter to waveform.

        Args:
            waveform: Input waveform
            lowcut: Low frequency cutoff (Hz)
            highcut: High frequency cutoff (Hz)
            order: Filter order

        Returns:
            Filtered waveform or None if error
        """
        if waveform is None:
            return None

        try:
            voltage = waveform.voltage
            time = waveform.time
            dt = np.mean(np.diff(time))
            sample_rate = 1.0 / dt

            # Design Butterworth bandpass filter
            nyquist = sample_rate / 2.0
            low = lowcut / nyquist
            high = highcut / nyquist

            if low <= 0 or high >= 1:
                logger.error("Filter frequencies out of valid range")
                return None

            sos = signal.butter(order, [low, high], btype="band", output="sos")

            # Apply filter
            filtered_voltage = signal.sosfilt(sos, voltage)

            # Create filtered waveform
            result = type(waveform)(time=time, voltage=filtered_voltage, channel=f"{waveform.channel}_FILTERED")

            logger.info(f"Bandpass filter applied: {lowcut:.2f}-{highcut:.2f} Hz, order={order}")

            return result

        except Exception as e:
            logger.error(f"Bandpass filter error: {e}")
            return None

    def apply_lowpass_filter(self, waveform, cutoff: float, order: int = 5):
        """Apply lowpass filter to waveform.

        Args:
            waveform: Input waveform
            cutoff: Cutoff frequency (Hz)
            order: Filter order

        Returns:
            Filtered waveform or None if error
        """
        if waveform is None:
            return None

        try:
            voltage = waveform.voltage
            time = waveform.time
            dt = np.mean(np.diff(time))
            sample_rate = 1.0 / dt

            # Design Butterworth lowpass filter
            nyquist = sample_rate / 2.0
            normal_cutoff = cutoff / nyquist

            if normal_cutoff <= 0 or normal_cutoff >= 1:
                logger.error("Filter cutoff out of valid range")
                return None

            sos = signal.butter(order, normal_cutoff, btype="low", output="sos")

            # Apply filter
            filtered_voltage = signal.sosfilt(sos, voltage)

            # Create filtered waveform
            result = type(waveform)(time=time, voltage=filtered_voltage, channel=f"{waveform.channel}_FILTERED")

            logger.info(f"Lowpass filter applied: {cutoff:.2f} Hz, order={order}")

            return result

        except Exception as e:
            logger.error(f"Lowpass filter error: {e}")
            return None

    def apply_highpass_filter(self, waveform, cutoff: float, order: int = 5):
        """Apply highpass filter to waveform.

        Args:
            waveform: Input waveform
            cutoff: Cutoff frequency (Hz)
            order: Filter order

        Returns:
            Filtered waveform or None if error
        """
        if waveform is None:
            return None

        try:
            voltage = waveform.voltage
            time = waveform.time
            dt = np.mean(np.diff(time))
            sample_rate = 1.0 / dt

            # Design Butterworth highpass filter
            nyquist = sample_rate / 2.0
            normal_cutoff = cutoff / nyquist

            if normal_cutoff <= 0 or normal_cutoff >= 1:
                logger.error("Filter cutoff out of valid range")
                return None

            sos = signal.butter(order, normal_cutoff, btype="high", output="sos")

            # Apply filter
            filtered_voltage = signal.sosfilt(sos, voltage)

            # Create filtered waveform
            result = type(waveform)(time=time, voltage=filtered_voltage, channel=f"{waveform.channel}_FILTERED")

            logger.info(f"Highpass filter applied: {cutoff:.2f} Hz, order={order}")

            return result

        except Exception as e:
            logger.error(f"Highpass filter error: {e}")
            return None

    @staticmethod
    def calculate_thd(fft_result: FFTResult, fundamental_freq: float, num_harmonics: int = 5) -> Optional[float]:
        """Calculate Total Harmonic Distortion (THD).

        Args:
            fft_result: FFT result
            fundamental_freq: Fundamental frequency (Hz)
            num_harmonics: Number of harmonics to include

        Returns:
            THD in percent or None if error
        """
        try:
            # Find fundamental frequency bin
            freq_resolution = fft_result.frequency[1] - fft_result.frequency[0]
            fund_idx = int(round(fundamental_freq / freq_resolution))

            if fund_idx >= len(fft_result.magnitude):
                logger.error("Fundamental frequency out of range")
                return None

            # Get fundamental magnitude (linear)
            if fft_result.magnitude_db:
                fund_mag = 10 ** (fft_result.magnitude[fund_idx] / 20.0)
            else:
                fund_mag = fft_result.magnitude[fund_idx]

            # Calculate harmonic magnitudes
            harmonic_power = 0.0
            for n in range(2, num_harmonics + 2):
                harmonic_idx = n * fund_idx
                if harmonic_idx < len(fft_result.magnitude):
                    if fft_result.magnitude_db:
                        harm_mag = 10 ** (fft_result.magnitude[harmonic_idx] / 20.0)
                    else:
                        harm_mag = fft_result.magnitude[harmonic_idx]
                    harmonic_power += harm_mag**2

            # Calculate THD
            thd = 100.0 * np.sqrt(harmonic_power) / fund_mag

            logger.info(f"THD calculated: {thd:.2f}% (fundamental={fundamental_freq:.2f} Hz)")

            return thd

        except Exception as e:
            logger.error(f"THD calculation error: {e}")
            return None
