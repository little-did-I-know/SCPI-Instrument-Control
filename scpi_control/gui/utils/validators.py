"""Validation utilities for waveform data quality checks.

This module provides validators to ensure waveform data is valid before
plotting or processing. Invalid data can cause blank plots, crashes, or
misleading visualizations.
"""

import logging
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class WaveformValidator:
    """Validates waveform data quality before plotting or processing.

    This validator catches common issues that cause blank plots:
    - None/missing waveforms
    - Empty voltage or time arrays
    - Mismatched array lengths
    - All-NaN values
    - Invalid voltage ranges
    """

    @staticmethod
    def validate(waveform) -> Tuple[bool, List[str]]:
        """Validate a waveform object.

        Args:
            waveform: WaveformData object to validate

        Returns:
            Tuple of (is_valid, list_of_issues)
            - is_valid: True if waveform is valid for plotting
            - list_of_issues: List of validation error messages (empty if valid)

        Example:
            >>> valid, issues = WaveformValidator.validate(waveform)
            >>> if not valid:
            ...     logger.warning(f"Invalid waveform: {', '.join(issues)}")
        """
        issues = []

        # Check 1: Waveform object exists
        if waveform is None:
            issues.append("Waveform is None")
            return False, issues

        # Check 2: Channel attribute exists
        if not hasattr(waveform, "channel"):
            issues.append("Waveform missing 'channel' attribute")
            return False, issues

        channel = waveform.channel

        # Check 3: Voltage array exists and is not None
        if not hasattr(waveform, "voltage"):
            issues.append(f"CH{channel}: Missing 'voltage' attribute")
        elif waveform.voltage is None:
            issues.append(f"CH{channel}: Voltage array is None")
        elif not isinstance(waveform.voltage, np.ndarray):
            issues.append(f"CH{channel}: Voltage is not a numpy array (got {type(waveform.voltage).__name__})")
        elif len(waveform.voltage) == 0:
            issues.append(f"CH{channel}: Voltage array is empty (0 samples)")
        else:
            # Check for all-NaN values
            if np.all(np.isnan(waveform.voltage)):
                issues.append(f"CH{channel}: All voltage values are NaN")
            # Check for excessive NaN values (>50%)
            elif np.sum(np.isnan(waveform.voltage)) > len(waveform.voltage) * 0.5:
                nan_pct = 100 * np.sum(np.isnan(waveform.voltage)) / len(waveform.voltage)
                issues.append(f"CH{channel}: {nan_pct:.1f}% of voltage values are NaN")

        # Check 4: Time array exists and is not None
        if not hasattr(waveform, "time"):
            issues.append(f"CH{channel}: Missing 'time' attribute")
        elif waveform.time is None:
            issues.append(f"CH{channel}: Time array is None")
        elif not isinstance(waveform.time, np.ndarray):
            issues.append(f"CH{channel}: Time is not a numpy array (got {type(waveform.time).__name__})")
        elif len(waveform.time) == 0:
            issues.append(f"CH{channel}: Time array is empty (0 samples)")

        # Check 5: Time and voltage arrays have matching lengths
        if (
            hasattr(waveform, "voltage")
            and hasattr(waveform, "time")
            and waveform.voltage is not None
            and waveform.time is not None
            and isinstance(waveform.voltage, np.ndarray)
            and isinstance(waveform.time, np.ndarray)
        ):

            if len(waveform.time) != len(waveform.voltage):
                issues.append(f"CH{channel}: Time/voltage length mismatch " f"(time: {len(waveform.time)}, voltage: {len(waveform.voltage)})")

        # Check 6: Voltage range is reasonable (not all zeros, not infinite)
        if hasattr(waveform, "voltage") and waveform.voltage is not None and isinstance(waveform.voltage, np.ndarray) and len(waveform.voltage) > 0:

            # Filter out NaN values for range check
            valid_voltages = waveform.voltage[~np.isnan(waveform.voltage)]

            if len(valid_voltages) > 0:
                # Check for all zeros
                if np.all(valid_voltages == 0):
                    issues.append(f"CH{channel}: All voltage values are zero (signal may be off)")

                # Check for infinite values
                if np.any(np.isinf(valid_voltages)):
                    issues.append(f"CH{channel}: Voltage contains infinite values")

                # Check for unreasonably large voltages (>1000V is suspicious for most scopes)
                max_abs_voltage = np.max(np.abs(valid_voltages))
                if max_abs_voltage > 1000:
                    issues.append(f"CH{channel}: Suspiciously large voltage value ({max_abs_voltage:.2f}V). " "Check voltage scale and probe settings.")

        is_valid = len(issues) == 0
        return is_valid, issues

    @staticmethod
    def validate_multiple(waveforms) -> Tuple[List, List[Tuple[int, List[str]]]]:
        """Validate multiple waveforms and separate valid from invalid.

        Args:
            waveforms: List of WaveformData objects

        Returns:
            Tuple of (valid_waveforms, invalid_waveforms_with_issues)
            - valid_waveforms: List of valid WaveformData objects
            - invalid_waveforms_with_issues: List of (channel, issues) tuples for invalid waveforms

        Example:
            >>> valid, invalid = WaveformValidator.validate_multiple(waveforms)
            >>> for channel, issues in invalid:
            ...     logger.warning(f"CH{channel} invalid: {', '.join(issues)}")
        """
        valid_waveforms = []
        invalid_info = []

        for waveform in waveforms:
            is_valid, issues = WaveformValidator.validate(waveform)
            if is_valid:
                valid_waveforms.append(waveform)
            else:
                channel = waveform.channel if hasattr(waveform, "channel") else "unknown"
                invalid_info.append((channel, issues))

        return valid_waveforms, invalid_info

    @staticmethod
    def get_summary(waveform) -> Optional[str]:
        """Get a summary string for a valid waveform.

        Args:
            waveform: WaveformData object

        Returns:
            Summary string like "CH1: 50,000 samples, range -2.5V to +2.5V"
            Returns None if waveform is invalid
        """
        is_valid, issues = WaveformValidator.validate(waveform)
        if not is_valid:
            return None

        channel = waveform.channel
        num_samples = len(waveform.voltage)

        # Get voltage range (excluding NaN values)
        valid_voltages = waveform.voltage[~np.isnan(waveform.voltage)]
        if len(valid_voltages) > 0:
            v_min = np.min(valid_voltages)
            v_max = np.max(valid_voltages)
            return f"CH{channel}: {num_samples:,} samples, range {v_min:.3f}V to {v_max:.3f}V"
        else:
            return f"CH{channel}: {num_samples:,} samples (all NaN)"
