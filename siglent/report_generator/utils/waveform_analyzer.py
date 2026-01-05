"""
Waveform analyzer for calculating signal statistics.

Automatically computes frequency, amplitude, timing, and quality metrics
from oscilloscope waveform data.
"""

from typing import Dict, Optional, Tuple

import numpy as np
from scipy import signal as scipy_signal
from scipy.fft import fft, fftfreq

from siglent.report_generator.models.report_data import WaveformData, WaveformRegion


class SignalType:
    """Signal type constants."""

    SINE = "sine"
    SQUARE = "square"
    TRIANGLE = "triangle"
    SAWTOOTH = "sawtooth"
    PULSE = "pulse"
    DC = "dc"
    NOISE = "noise"
    COMPLEX = "complex"
    UNKNOWN = "unknown"


class WaveformAnalyzer:
    """Analyzes waveform data to extract signal statistics."""

    @staticmethod
    def analyze(waveform: WaveformData, include_plateau_stability: bool = False) -> Dict[str, Optional[float]]:
        """
        Analyze a waveform and calculate all statistics.

        Args:
            waveform: Waveform data to analyze

        Returns:
            Dictionary of calculated statistics
        """
        stats = {}

        # Signal type detection
        signal_type, confidence = WaveformAnalyzer.detect_signal_type(waveform)
        stats["signal_type"] = signal_type
        stats["signal_type_confidence"] = confidence

        # Amplitude measurements
        stats.update(WaveformAnalyzer.calculate_amplitude_stats(waveform))

        # Frequency and period
        stats.update(WaveformAnalyzer.calculate_frequency_stats(waveform))

        # Timing measurements
        stats.update(WaveformAnalyzer.calculate_timing_stats(waveform))

        # Signal quality metrics
        stats.update(WaveformAnalyzer.calculate_quality_stats(waveform))

        # Calculate THD for periodic signals
        if signal_type in [SignalType.SINE, SignalType.SQUARE, SignalType.TRIANGLE, SignalType.SAWTOOTH]:
            thd = WaveformAnalyzer.calculate_thd(waveform)
            stats["thd"] = thd

        # Calculate plateau stability for applicable signals
        if include_plateau_stability:
            # Apply to square, pulse, and all periodic signals
            if signal_type in [SignalType.SQUARE, SignalType.PULSE, SignalType.TRIANGLE, SignalType.SAWTOOTH, SignalType.SINE]:
                plateau_stats = WaveformAnalyzer.calculate_plateau_stability(waveform, signal_type)
                stats.update(plateau_stats)

        return stats

    @staticmethod
    def calculate_amplitude_stats(waveform: WaveformData) -> Dict[str, float]:
        """Calculate amplitude-related statistics."""
        v = waveform.voltage_data

        vmax = np.max(v)
        vmin = np.min(v)
        vpp = vmax - vmin
        vmean = np.mean(v)
        vrms = np.sqrt(np.mean(v**2))
        vamp = (vmax + vmin) / 2  # Amplitude (middle of range)

        return {
            "vmax": vmax,
            "vmin": vmin,
            "vpp": vpp,
            "vmean": vmean,
            "vrms": vrms,
            "vamp": vamp,
            "dc_offset": vmean,
        }

    @staticmethod
    def calculate_frequency_stats(waveform: WaveformData) -> Dict[str, Optional[float]]:
        """Calculate frequency and period using FFT."""
        try:
            v = waveform.voltage_data
            sample_rate = waveform.sample_rate

            # Compute FFT
            n = len(v)
            yf = fft(v)
            xf = fftfreq(n, 1 / sample_rate)

            # Get positive frequencies only
            pos_mask = xf > 0
            xf_pos = xf[pos_mask]
            yf_pos = np.abs(yf[pos_mask])

            # Find peak frequency (excluding DC component)
            if len(yf_pos) > 1:
                # Skip first bin (DC)
                peak_idx = np.argmax(yf_pos[1:]) + 1
                frequency = xf_pos[peak_idx]
                period = 1 / frequency if frequency > 0 else None

                return {
                    "frequency": frequency,
                    "period": period,
                }
            else:
                return {
                    "frequency": None,
                    "period": None,
                }

        except Exception as e:
            print(f"Error calculating frequency: {e}")
            return {
                "frequency": None,
                "period": None,
            }

    @staticmethod
    def calculate_timing_stats(waveform: WaveformData) -> Dict[str, Optional[float]]:
        """Calculate timing measurements (rise time, fall time, pulse width, duty cycle)."""
        try:
            v = waveform.voltage_data
            t = waveform.time_data
            dt = np.mean(np.diff(t))  # Average time step

            vmax = np.max(v)
            vmin = np.min(v)
            vrange = vmax - vmin

            # Thresholds for timing measurements
            v_low = vmin + 0.1 * vrange  # 10%
            v_high = vmin + 0.9 * vrange  # 90%
            v_50 = vmin + 0.5 * vrange  # 50%

            # Find edges (zero crossings of derivative)
            dv = np.diff(v)
            rising_edges = np.where((v[:-1] < v_50) & (v[1:] >= v_50))[0]
            falling_edges = np.where((v[:-1] > v_50) & (v[1:] <= v_50))[0]

            rise_time = None
            fall_time = None
            pulse_width = None
            duty_cycle = None

            # Calculate rise time (first rising edge)
            if len(rising_edges) > 0:
                edge_idx = rising_edges[0]
                # Find 10% and 90% points around this edge
                start_idx = edge_idx
                while start_idx > 0 and v[start_idx] > v_low:
                    start_idx -= 1
                end_idx = edge_idx
                while end_idx < len(v) - 1 and v[end_idx] < v_high:
                    end_idx += 1

                if end_idx > start_idx:
                    rise_time = (end_idx - start_idx) * dt

            # Calculate fall time (first falling edge)
            if len(falling_edges) > 0:
                edge_idx = falling_edges[0]
                start_idx = edge_idx
                while start_idx > 0 and v[start_idx] < v_high:
                    start_idx -= 1
                end_idx = edge_idx
                while end_idx < len(v) - 1 and v[end_idx] > v_low:
                    end_idx += 1

                if end_idx > start_idx:
                    fall_time = (end_idx - start_idx) * dt

            # Calculate pulse width and duty cycle
            if len(rising_edges) > 0 and len(falling_edges) > 0:
                # Pulse width: time from rising edge to next falling edge
                if falling_edges[0] > rising_edges[0]:
                    pulse_width = (falling_edges[0] - rising_edges[0]) * dt

                # Duty cycle: ratio of high time to period
                if len(rising_edges) > 1:
                    period_samples = rising_edges[1] - rising_edges[0]
                    high_samples = falling_edges[0] - rising_edges[0] if falling_edges[0] > rising_edges[0] else 0
                    duty_cycle = (high_samples / period_samples) * 100  # Percentage

            return {
                "rise_time": rise_time,
                "fall_time": fall_time,
                "pulse_width": pulse_width,
                "duty_cycle": duty_cycle,
            }

        except Exception as e:
            print(f"Error calculating timing stats: {e}")
            return {
                "rise_time": None,
                "fall_time": None,
                "pulse_width": None,
                "duty_cycle": None,
            }

    @staticmethod
    def calculate_quality_stats(waveform: WaveformData) -> Dict[str, Optional[float]]:
        """Calculate signal quality metrics (SNR, noise, overshoot, undershoot, jitter)."""
        try:
            v = waveform.voltage_data

            # Estimate noise level (high-frequency component)
            # Use standard deviation of detrended signal
            v_detrended = v - np.mean(v)
            noise_level = np.std(v_detrended)

            # Signal to Noise Ratio (SNR)
            vmax = np.max(v)
            vmin = np.min(v)
            signal_amplitude = (vmax - vmin) / 2
            snr = 20 * np.log10(signal_amplitude / noise_level) if noise_level > 0 else None

            # Overshoot and undershoot (percentage above/below steady-state levels)
            # This is approximate - we'll use top 10% and bottom 10% as steady state
            v_sorted = np.sort(v)
            n = len(v_sorted)
            v_high_steady = np.mean(v_sorted[int(0.85 * n) : int(0.95 * n)])  # High steady state
            v_low_steady = np.mean(v_sorted[int(0.05 * n) : int(0.15 * n)])  # Low steady state

            overshoot = ((vmax - v_high_steady) / (v_high_steady - v_low_steady)) * 100 if v_high_steady != v_low_steady else 0
            undershoot = ((v_low_steady - vmin) / (v_high_steady - v_low_steady)) * 100 if v_high_steady != v_low_steady else 0

            # Jitter (standard deviation of edge timing)
            # Find all rising edges
            v_50 = (vmax + vmin) / 2
            rising_edges = np.where((v[:-1] < v_50) & (v[1:] >= v_50))[0]

            jitter = None
            if len(rising_edges) > 2:
                # Calculate period jitter
                periods = np.diff(rising_edges)
                jitter = np.std(periods) * np.mean(np.diff(waveform.time_data))

            return {
                "noise_level": noise_level,
                "snr": snr,
                "overshoot": max(0, overshoot),  # Don't show negative overshoot
                "undershoot": max(0, undershoot),  # Don't show negative undershoot
                "jitter": jitter,
            }

        except Exception as e:
            print(f"Error calculating quality stats: {e}")
            return {
                "noise_level": None,
                "snr": None,
                "overshoot": None,
                "undershoot": None,
                "jitter": None,
            }

    @staticmethod
    def format_stat_value(name: str, value: Optional[float]) -> str:
        """
        Format a statistic value with appropriate units and precision.

        Args:
            name: Statistic name
            value: Value to format

        Returns:
            Formatted string with value and units
        """
        if value is None:
            return "N/A"

        # Voltage measurements
        if name in ["vmax", "vmin", "vpp", "vmean", "vrms", "vamp", "dc_offset", "noise_level", "plateau_high_noise", "plateau_low_noise", "plateau_stability"]:
            if abs(value) >= 1:
                return f"{value:.3f} V"
            elif abs(value) >= 0.001:
                return f"{value*1000:.2f} mV"
            else:
                return f"{value*1e6:.2f} µV"

        # Frequency
        elif name == "frequency":
            if value >= 1e6:
                return f"{value/1e6:.3f} MHz"
            elif value >= 1e3:
                return f"{value/1e3:.3f} kHz"
            else:
                return f"{value:.2f} Hz"

        # Time measurements
        elif name in ["period", "rise_time", "fall_time", "pulse_width", "jitter"]:
            if value >= 1:
                return f"{value:.3f} s"
            elif value >= 1e-3:
                return f"{value*1e3:.3f} ms"
            elif value >= 1e-6:
                return f"{value*1e6:.3f} µs"
            else:
                return f"{value*1e9:.2f} ns"

        # Percentage
        elif name in ["duty_cycle", "overshoot", "undershoot"]:
            return f"{value:.2f} %"

        # SNR (dB)
        elif name == "snr":
            return f"{value:.2f} dB"

        # THD (percentage)
        elif name == "thd":
            return f"{value:.2f} %"

        # Signal type (string)
        elif name == "signal_type":
            if isinstance(value, str):
                return value.capitalize()
            return str(value)

        # Signal type confidence (percentage)
        elif name == "signal_type_confidence":
            return f"{value:.1f} %"

        # Default
        else:
            return f"{value:.4g}"

    @staticmethod
    def detect_signal_type(waveform: WaveformData) -> Tuple[str, float]:
        """
        Detect the type of signal in the waveform.

        Args:
            waveform: Waveform data to analyze

        Returns:
            Tuple of (signal_type, confidence) where confidence is 0-100%
        """
        try:
            v = waveform.voltage_data

            # Check for DC signal first
            if WaveformAnalyzer._is_dc_signal(v):
                return SignalType.DC, 95.0

            # Check for noise
            if WaveformAnalyzer._is_noise(v):
                return SignalType.NOISE, 85.0

            # Analyze frequency content
            harmonics = WaveformAnalyzer._get_harmonic_ratios(waveform)

            if harmonics is not None and len(harmonics) >= 3:
                # Calculate THD as indicator of harmonic content
                # For sine: very low THD (<5%)
                # For square/triangle/sawtooth: higher THD
                total_harmonic_power = np.sum(harmonics[1:] ** 2)
                fundamental_power = harmonics[0] ** 2
                thd_ratio = np.sqrt(total_harmonic_power / fundamental_power) if fundamental_power > 0 else 0

                # Check for sine wave first (very low THD)
                if thd_ratio < 0.1:  # THD < 10%
                    return SignalType.SINE, min(95.0, (1 - thd_ratio) * 100)

                # Check waveform patterns based on harmonic signatures
                square_score = WaveformAnalyzer._score_square_wave(harmonics)
                triangle_score = WaveformAnalyzer._score_triangle_wave(harmonics)
                sawtooth_score = WaveformAnalyzer._score_sawtooth_wave(harmonics)

                # Find best match
                scores = {SignalType.SQUARE: square_score, SignalType.TRIANGLE: triangle_score, SignalType.SAWTOOTH: sawtooth_score}

                best_type = max(scores, key=scores.get)
                best_score = scores[best_type]

                if best_score > 0.6:
                    return best_type, min(90.0, best_score * 100)

            # Check for pulse/PWM based on duty cycle
            duty_cycle = WaveformAnalyzer._estimate_duty_cycle(v)
            if duty_cycle is not None and (duty_cycle < 40 or duty_cycle > 60):
                return SignalType.PULSE, 80.0

            # If periodic but doesn't match standard types
            if harmonics is not None and len(harmonics) > 0:
                return SignalType.COMPLEX, 70.0

            return SignalType.UNKNOWN, 50.0

        except Exception as e:
            print(f"Error detecting signal type: {e}")
            return SignalType.UNKNOWN, 0.0

    @staticmethod
    def _is_dc_signal(v: np.ndarray, threshold: float = 0.01) -> bool:
        """Check if signal is DC (very low variation)."""
        std = np.std(v)
        mean = np.mean(np.abs(v))
        if mean == 0:
            return std < threshold
        return (std / mean) < threshold

    @staticmethod
    def _is_noise(v: np.ndarray) -> bool:
        """Check if signal is primarily noise."""
        # Calculate autocorrelation
        v_normalized = v - np.mean(v)
        autocorr = np.correlate(v_normalized, v_normalized, mode="full")
        autocorr = autocorr[len(autocorr) // 2 :]
        autocorr = autocorr / autocorr[0]

        # For noise, autocorrelation drops quickly
        # Check if autocorrelation at lag=10% of signal is < 0.3
        lag = max(1, len(autocorr) // 10)
        if lag < len(autocorr):
            return autocorr[lag] < 0.3
        return False

    @staticmethod
    def _get_harmonic_ratios(waveform: WaveformData, num_harmonics: int = 5) -> Optional[np.ndarray]:
        """
        Get the relative amplitudes of harmonics.

        Returns array where [0] is fundamental, [1] is 2nd harmonic, etc.
        Values are normalized so fundamental = 1.0 for periodic signals.
        """
        try:
            v = waveform.voltage_data
            sample_rate = waveform.sample_rate

            # Compute FFT
            n = len(v)
            yf = fft(v - np.mean(v))  # Remove DC
            xf = fftfreq(n, 1 / sample_rate)

            # Get positive frequencies only
            pos_mask = xf > 0
            xf_pos = xf[pos_mask]
            yf_pos = np.abs(yf[pos_mask])

            if len(yf_pos) < 2:
                return None

            # Find fundamental frequency (peak)
            peak_idx = np.argmax(yf_pos[1:]) + 1  # Skip DC
            fundamental_freq = xf_pos[peak_idx]
            fundamental_amp = yf_pos[peak_idx]

            if fundamental_freq == 0 or fundamental_amp == 0:
                return None

            # Find harmonics
            harmonic_amps = []
            for i in range(1, num_harmonics + 1):
                harmonic_freq = fundamental_freq * i
                # Find closest frequency bin
                idx = np.argmin(np.abs(xf_pos - harmonic_freq))
                # Check if we're actually close to the harmonic
                if np.abs(xf_pos[idx] - harmonic_freq) < (sample_rate / n * 3):
                    harmonic_amps.append(yf_pos[idx])
                else:
                    harmonic_amps.append(0.0)

            # Normalize to fundamental
            harmonic_ratios = np.array(harmonic_amps) / fundamental_amp
            return harmonic_ratios

        except Exception:
            return None

    @staticmethod
    def _score_square_wave(harmonics: np.ndarray) -> float:
        """
        Score how well harmonics match a square wave.
        Square wave has odd harmonics at 1/n amplitude.
        """
        if len(harmonics) < 3:
            return 0.0

        # Expected pattern: [1, 0, 1/3, 0, 1/5, ...]
        expected = []
        for i in range(len(harmonics)):
            n = i + 1
            if n % 2 == 1:  # Odd harmonic
                expected.append(1.0 / n)
            else:  # Even harmonic (should be ~0)
                expected.append(0.0)

        expected = np.array(expected)

        # Normalize both to fundamental
        if expected[0] > 0:
            expected = expected / expected[0]

        # Calculate correlation
        correlation = np.corrcoef(harmonics[: len(expected)], expected)[0, 1]
        if np.isnan(correlation):
            return 0.0

        return max(0.0, correlation)

    @staticmethod
    def _score_triangle_wave(harmonics: np.ndarray) -> float:
        """
        Score how well harmonics match a triangle wave.
        Triangle wave has odd harmonics at 1/n^2 amplitude.
        """
        if len(harmonics) < 3:
            return 0.0

        # Expected pattern: [1, 0, 1/9, 0, 1/25, ...]
        expected = []
        for i in range(len(harmonics)):
            n = i + 1
            if n % 2 == 1:  # Odd harmonic
                expected.append(1.0 / (n * n))
            else:  # Even harmonic
                expected.append(0.0)

        expected = np.array(expected)

        # Normalize
        if expected[0] > 0:
            expected = expected / expected[0]

        # Calculate correlation
        correlation = np.corrcoef(harmonics[: len(expected)], expected)[0, 1]
        if np.isnan(correlation):
            return 0.0

        return max(0.0, correlation)

    @staticmethod
    def _score_sawtooth_wave(harmonics: np.ndarray) -> float:
        """
        Score how well harmonics match a sawtooth wave.
        Sawtooth has all harmonics at 1/n amplitude.
        """
        if len(harmonics) < 3:
            return 0.0

        # Expected pattern: [1, 1/2, 1/3, 1/4, 1/5, ...]
        expected = np.array([1.0 / (i + 1) for i in range(len(harmonics))])

        # Normalize
        if expected[0] > 0:
            expected = expected / expected[0]

        # Calculate correlation
        correlation = np.corrcoef(harmonics, expected)[0, 1]
        if np.isnan(correlation):
            return 0.0

        return max(0.0, correlation)

    @staticmethod
    def _estimate_duty_cycle(v: np.ndarray) -> Optional[float]:
        """Estimate duty cycle of a pulse signal."""
        try:
            vmax = np.max(v)
            vmin = np.min(v)
            v_threshold = (vmax + vmin) / 2

            # Count samples above threshold
            high_samples = np.sum(v > v_threshold)
            duty_cycle = (high_samples / len(v)) * 100

            return duty_cycle
        except Exception:
            return None

    @staticmethod
    def calculate_thd(waveform: WaveformData, num_harmonics: int = 10) -> Optional[float]:
        """
        Calculate Total Harmonic Distortion (THD) as a percentage.

        THD = sqrt(sum(harmonics[2:]^2)) / fundamental * 100

        Args:
            waveform: Waveform data
            num_harmonics: Number of harmonics to include

        Returns:
            THD percentage, or None if calculation fails
        """
        try:
            harmonics = WaveformAnalyzer._get_harmonic_ratios(waveform, num_harmonics)

            if harmonics is None or len(harmonics) < 2:
                return None

            # THD = sqrt(sum of squares of harmonics) / fundamental
            fundamental = harmonics[0]
            if fundamental == 0:
                return None

            harmonic_power = np.sum(harmonics[1:] ** 2)
            thd = np.sqrt(harmonic_power) / fundamental * 100

            return thd

        except Exception as e:
            print(f"Error calculating THD: {e}")
            return None

    @staticmethod
    def calculate_plateau_stability(waveform: WaveformData, signal_type: str) -> Dict[str, Optional[float]]:
        """
        Calculate plateau stability (noise on high and low levels).

        Measures the standard deviation of voltage during stable plateau regions.
        Uses the middle 60% of each plateau to exclude edge transitions.

        Args:
            waveform: Waveform data
            signal_type: Detected signal type

        Returns:
            Dictionary with plateau stability metrics
        """
        try:
            v = waveform.voltage_data
            t = waveform.time_data

            vmax = np.max(v)
            vmin = np.min(v)
            v_50 = (vmax + vmin) / 2

            # Find high and low regions
            high_samples = v > v_50
            low_samples = v <= v_50

            # Find contiguous regions for better analysis
            # This helps identify stable plateaus
            high_regions = []
            low_regions = []

            # Simple run-length encoding to find plateau regions
            current_high = []
            current_low = []

            for i, is_high in enumerate(high_samples):
                if is_high:
                    if current_low:
                        if len(current_low) > 10:  # Minimum plateau length
                            low_regions.append(current_low)
                        current_low = []
                    current_high.append(i)
                else:
                    if current_high:
                        if len(current_high) > 10:
                            high_regions.append(current_high)
                        current_high = []
                    current_low.append(i)

            # Don't forget the last region
            if current_high and len(current_high) > 10:
                high_regions.append(current_high)
            if current_low and len(current_low) > 10:
                low_regions.append(current_low)

            high_plateau_noise = None
            low_plateau_noise = None

            # Analyze high plateaus (use middle 60%)
            if high_regions:
                high_plateau_samples = []
                for region in high_regions:
                    if len(region) >= 5:
                        # Use middle 60%
                        start_idx = int(len(region) * 0.2)
                        end_idx = int(len(region) * 0.8)
                        middle_indices = region[start_idx:end_idx]
                        if middle_indices:
                            high_plateau_samples.extend(v[middle_indices])

                if high_plateau_samples:
                    high_plateau_noise = np.std(high_plateau_samples)

            # Analyze low plateaus (use middle 60%)
            if low_regions:
                low_plateau_samples = []
                for region in low_regions:
                    if len(region) >= 5:
                        # Use middle 60%
                        start_idx = int(len(region) * 0.2)
                        end_idx = int(len(region) * 0.8)
                        middle_indices = region[start_idx:end_idx]
                        if middle_indices:
                            low_plateau_samples.extend(v[middle_indices])

                if low_plateau_samples:
                    low_plateau_noise = np.std(low_plateau_samples)

            # Calculate combined plateau stability metric
            plateau_stability = None
            if high_plateau_noise is not None and low_plateau_noise is not None:
                # Average of both plateaus
                plateau_stability = (high_plateau_noise + low_plateau_noise) / 2

            return {
                "plateau_high_noise": high_plateau_noise,
                "plateau_low_noise": low_plateau_noise,
                "plateau_stability": plateau_stability,
            }

        except Exception as e:
            print(f"Error calculating plateau stability: {e}")
            return {
                "plateau_high_noise": None,
                "plateau_low_noise": None,
                "plateau_stability": None,
            }

    @staticmethod
    def detect_regions(waveform: "WaveformData", auto_detect_plateaus: bool = True, auto_detect_edges: bool = True, auto_detect_transients: bool = False) -> None:
        """
        Automatically detect and add regions of interest to a waveform.

        This method analyzes the waveform and automatically creates WaveformRegion
        objects for detected features, adding them to waveform.regions.

        Args:
            waveform: WaveformData object to analyze
            auto_detect_plateaus: Detect plateau regions in square/pulse waveforms
            auto_detect_edges: Detect rising and falling edges
            auto_detect_transients: Detect transient responses

        Note:
            This method modifies the waveform object by adding detected regions.
            Call waveform.clear_regions() first if you want to start fresh.
        """
        from siglent.report_generator.models.report_data import WaveformRegion

        # Ensure waveform has been analyzed for signal type
        if waveform.signal_type is None:
            waveform.analyze()

        # Detect plateaus for square/pulse waveforms
        if auto_detect_plateaus and waveform.signal_type in [SignalType.SQUARE, SignalType.PULSE]:
            plateaus = WaveformAnalyzer.detect_plateaus(waveform)
            for plateau in plateaus:
                waveform.regions.append(plateau)

        # Detect edges for all periodic signals
        if auto_detect_edges and waveform.signal_type in [SignalType.SQUARE, SignalType.PULSE, SignalType.TRIANGLE, SignalType.SAWTOOTH]:
            edges = WaveformAnalyzer.detect_edges(waveform)
            for edge in edges:
                waveform.regions.append(edge)

        # Detect transients if requested
        if auto_detect_transients:
            transients = WaveformAnalyzer.detect_transients(waveform)
            for transient in transients:
                waveform.regions.append(transient)

    @staticmethod
    def detect_plateaus(waveform: "WaveformData", min_duration: Optional[float] = None) -> list:
        """
        Detect plateau regions in a waveform (flat high and low regions).

        Uses the same run-length encoding approach as plateau stability analysis
        to identify continuous regions at high and low voltage levels.

        Args:
            waveform: WaveformData object
            min_duration: Minimum plateau duration in seconds (auto-calculated if None)

        Returns:
            List of WaveformRegion objects for detected plateaus
        """
        from siglent.report_generator.models.report_data import WaveformRegion

        t = waveform.time_data
        v = waveform.voltage_data

        if len(v) < 10:
            return []

        # Calculate thresholds (same as plateau stability)
        v_median = np.median(v)
        v_std = np.std(v)
        threshold_high = v_median + 0.3 * v_std
        threshold_low = v_median - 0.3 * v_std

        # Auto-calculate minimum duration if not specified
        if min_duration is None:
            # Minimum plateau should be at least 1% of total waveform
            min_duration = (t[-1] - t[0]) * 0.01

        # Find plateau regions using run-length encoding
        high_level = v > threshold_high
        low_level = v < threshold_low

        plateaus = []

        # Detect high plateaus
        high_diff = np.diff(np.concatenate(([False], high_level, [False])).astype(int))
        high_starts = np.where(high_diff == 1)[0]
        high_ends = np.where(high_diff == -1)[0]

        for start, end in zip(high_starts, high_ends):
            if start < end and end < len(t):
                duration = t[end - 1] - t[start]
                if duration >= min_duration:
                    # Extract region data for analysis
                    region_time = t[start:end]
                    region_voltage = v[start:end]

                    plateau = WaveformRegion(
                        start_time=float(t[start]),
                        end_time=float(t[end - 1]),
                        label=f"High Plateau ({duration*1e3:.2f}ms)",
                        region_type="plateau_high",
                        auto_detected=True,
                        ideal_value=float(np.median(region_voltage)),
                    )
                    plateaus.append(plateau)

        # Detect low plateaus
        low_diff = np.diff(np.concatenate(([False], low_level, [False])).astype(int))
        low_starts = np.where(low_diff == 1)[0]
        low_ends = np.where(low_diff == -1)[0]

        for start, end in zip(low_starts, low_ends):
            if start < end and end < len(t):
                duration = t[end - 1] - t[start]
                if duration >= min_duration:
                    region_time = t[start:end]
                    region_voltage = v[start:end]

                    plateau = WaveformRegion(
                        start_time=float(t[start]),
                        end_time=float(t[end - 1]),
                        label=f"Low Plateau ({duration*1e3:.2f}ms)",
                        region_type="plateau_low",
                        auto_detected=True,
                        ideal_value=float(np.median(region_voltage)),
                    )
                    plateaus.append(plateau)

        return plateaus

    @staticmethod
    def detect_edges(waveform: "WaveformData", max_edges: int = 4) -> list:
        """
        Detect rising and falling edges in a waveform.

        Identifies transitions between voltage levels by finding regions
        with high rate of change.

        Args:
            waveform: WaveformData object
            max_edges: Maximum number of edges to detect (prevents too many regions)

        Returns:
            List of WaveformRegion objects for detected edges
        """
        from siglent.report_generator.models.report_data import WaveformRegion

        t = waveform.time_data
        v = waveform.voltage_data

        if len(v) < 10:
            return []

        # Calculate derivative (rate of change)
        dt = np.diff(t)
        dv = np.diff(v)
        derivative = dv / dt

        # Find peaks in derivative (edges)
        # Rising edges: positive peaks
        # Falling edges: negative peaks
        threshold = np.std(derivative) * 2

        edges = []

        # Find rising edges
        rising_peaks, _ = scipy_signal.find_peaks(derivative, height=threshold, distance=int(len(t) * 0.05))
        for idx in rising_peaks[: max_edges // 2]:
            if idx < len(t) - 10:
                # Define edge region as ±5% around the peak
                window = int(len(t) * 0.02)
                start_idx = max(0, idx - window)
                end_idx = min(len(t), idx + window)

                edge = WaveformRegion(
                    start_time=float(t[start_idx]),
                    end_time=float(t[end_idx]),
                    label=f"Rising Edge @ {t[idx]*1e3:.2f}ms",
                    region_type="edge_rising",
                    auto_detected=True,
                    highlight_color="#00ff00",
                )
                edges.append(edge)

        # Find falling edges
        falling_peaks, _ = scipy_signal.find_peaks(-derivative, height=threshold, distance=int(len(t) * 0.05))
        for idx in falling_peaks[: max_edges // 2]:
            if idx < len(t) - 10:
                window = int(len(t) * 0.02)
                start_idx = max(0, idx - window)
                end_idx = min(len(t), idx + window)

                edge = WaveformRegion(
                    start_time=float(t[start_idx]),
                    end_time=float(t[end_idx]),
                    label=f"Falling Edge @ {t[idx]*1e3:.2f}ms",
                    region_type="edge_falling",
                    auto_detected=True,
                    highlight_color="#ff0000",
                )
                edges.append(edge)

        # Sort by time
        edges.sort(key=lambda r: r.start_time)

        return edges

    @staticmethod
    def detect_transients(waveform: "WaveformData", sensitivity: float = 3.0) -> list:
        """
        Detect transient responses in a waveform.

        Identifies sudden changes or anomalies that deviate significantly
        from the baseline signal.

        Args:
            waveform: WaveformData object
            sensitivity: Detection sensitivity (sigma multiplier)

        Returns:
            List of WaveformRegion objects for detected transients
        """
        from siglent.report_generator.models.report_data import WaveformRegion

        t = waveform.time_data
        v = waveform.voltage_data

        if len(v) < 20:
            return []

        # Smooth the signal to find baseline
        from scipy.ndimage import median_filter

        baseline = median_filter(v, size=max(5, len(v) // 20))

        # Find deviation from baseline
        deviation = np.abs(v - baseline)
        threshold = np.mean(deviation) + sensitivity * np.std(deviation)

        # Find regions that exceed threshold
        above_threshold = deviation > threshold

        transients = []

        # Use run-length encoding to find continuous transient regions
        diff = np.diff(np.concatenate(([False], above_threshold, [False])).astype(int))
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0]

        for start, end in zip(starts, ends):
            if start < end and end < len(t):
                duration = t[end - 1] - t[start]
                # Only report transients longer than 0.1% of total time
                min_duration = (t[-1] - t[0]) * 0.001
                if duration >= min_duration:
                    transient = WaveformRegion(
                        start_time=float(t[start]),
                        end_time=float(t[end - 1]),
                        label=f"Transient @ {t[start]*1e3:.2f}ms",
                        region_type="transient",
                        auto_detected=True,
                        highlight_color="#ffaa00",
                    )
                    transients.append(transient)

        return transients[:10]  # Limit to 10 transients

    @staticmethod
    def analyze_region(waveform: "WaveformData", region: "WaveformRegion", calculate_calibration: bool = True) -> None:
        """
        Analyze a specific region and populate its analysis fields.

        Calculates slope, flatness, noise, drift, and optionally generates
        calibration guidance for the region.

        Args:
            waveform: Parent WaveformData object
            region: WaveformRegion to analyze
            calculate_calibration: Generate calibration recommendations

        Note:
            This method modifies the region object in-place.
        """
        # Extract region data
        t, v = waveform.get_region_data(region)

        if len(v) < 3:
            return

        # Calculate slope using linear regression
        coeffs = np.polyfit(t, v, 1)
        region.slope = float(coeffs[0])  # V/s

        # Calculate flatness (standard deviation)
        region.flatness = float(np.std(v))

        # Calculate RMS noise
        # Remove linear trend first
        trend = np.polyval(coeffs, t)
        detrended = v - trend
        region.noise_level = float(np.sqrt(np.mean(detrended**2)))

        # Calculate drift (total change over region)
        region.drift = float(v[-1] - v[0])

        # Calculate deviation from ideal (if ideal_value is set)
        if region.ideal_value is not None:
            mean_value = np.mean(v)
            region.deviation_from_ideal = float(mean_value - region.ideal_value)

            # Check tolerance if set
            if region.tolerance_min is not None or region.tolerance_max is not None:
                within_min = region.tolerance_min is None or mean_value >= region.tolerance_min
                within_max = region.tolerance_max is None or mean_value <= region.tolerance_max
                region.passes_spec = within_min and within_max

        # Generate calibration guidance for plateaus
        if calculate_calibration and region.region_type in ["plateau_high", "plateau_low"]:
            region.calibration_recommendation = WaveformAnalyzer.generate_calibration_guidance(region.slope, region.flatness, region.region_type)

        # Calculate region-specific statistics
        region.statistics = {
            "mean": float(np.mean(v)),
            "median": float(np.median(v)),
            "std": float(np.std(v)),
            "min": float(np.min(v)),
            "max": float(np.max(v)),
            "range": float(np.max(v) - np.min(v)),
        }

    @staticmethod
    def generate_calibration_guidance(slope: Optional[float], flatness: Optional[float], region_type: str) -> Optional[str]:
        """
        Generate probe calibration guidance based on plateau characteristics.

        This provides specific recommendations for adjusting oscilloscope probe
        compensation based on the slope observed on square wave plateaus.

        Args:
            slope: Plateau slope in V/s
            flatness: Plateau flatness (std dev) in V
            region_type: Type of plateau ('plateau_high' or 'plateau_low')

        Returns:
            Calibration recommendation string, or None if analysis not possible
        """
        if slope is None:
            return None

        # Thresholds for probe compensation assessment
        # These are rough guidelines - actual values depend on probe specs
        SLOPE_THRESHOLD_GOOD = 1000  # V/s - below this is considered well-compensated
        SLOPE_THRESHOLD_MODERATE = 5000  # V/s - moderate compensation needed
        SLOPE_THRESHOLD_POOR = 20000  # V/s - significant compensation needed

        abs_slope = abs(slope)

        if abs_slope < SLOPE_THRESHOLD_GOOD:
            return "✓ Probe compensation is good. Plateau is flat and stable."

        elif abs_slope < SLOPE_THRESHOLD_MODERATE:
            # Determine direction based on slope sign
            if slope > 0:
                # Positive slope (rising plateau) indicates undercompensation
                return "⚠ Probe is slightly undercompensated. " "Turn trimmer capacitor clockwise 10-15° and retest. " f"(Measured slope: {slope:.0f} V/s)"
            else:
                # Negative slope (falling plateau) indicates overcompensation
                return "⚠ Probe is slightly overcompensated. " "Turn trimmer capacitor counter-clockwise 10-15° and retest. " f"(Measured slope: {slope:.0f} V/s)"

        elif abs_slope < SLOPE_THRESHOLD_POOR:
            if slope > 0:
                return "⚠⚠ Probe is undercompensated. " "Turn trimmer capacitor clockwise 30-45° and retest. " f"(Measured slope: {slope:.0f} V/s)"
            else:
                return "⚠⚠ Probe is overcompensated. " "Turn trimmer capacitor counter-clockwise 30-45° and retest. " f"(Measured slope: {slope:.0f} V/s)"

        else:
            # Severe compensation issue
            if slope > 0:
                return (
                    "⚠⚠⚠ Probe is severely undercompensated! "
                    "Turn trimmer capacitor clockwise 60-90° and retest. "
                    "If problem persists, check probe connection and cable. "
                    f"(Measured slope: {slope:.0f} V/s)"
                )
            else:
                return (
                    "⚠⚠⚠ Probe is severely overcompensated! "
                    "Turn trimmer capacitor counter-clockwise 60-90° and retest. "
                    "If problem persists, check probe connection and cable. "
                    f"(Measured slope: {slope:.0f} V/s)"
                )

    @staticmethod
    def analyze_all_regions(waveform: "WaveformData") -> None:
        """
        Analyze all regions in a waveform.

        Convenience method that calls analyze_region() for each region.

        Args:
            waveform: WaveformData object with regions to analyze
        """
        for region in waveform.regions:
            WaveformAnalyzer.analyze_region(waveform, region)
