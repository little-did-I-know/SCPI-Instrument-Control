"""Measurement and cursor control for Siglent oscilloscopes."""

import logging
from typing import TYPE_CHECKING, Any, Dict, Literal, Optional

from siglent import exceptions

if TYPE_CHECKING:
    from siglent.oscilloscope import Oscilloscope

logger = logging.getLogger(__name__)

MeasurementType = Literal[
    "PKPK",  # Peak-to-peak
    "MAX",  # Maximum
    "MIN",  # Minimum
    "AMPL",  # Amplitude
    "TOP",  # Top value
    "BASE",  # Base value
    "CMEAN",  # Mean (cycle)
    "MEAN",  # Mean (all)
    "RMS",  # RMS (all)
    "CRMS",  # RMS (cycle)
    "FREQ",  # Frequency
    "PER",  # Period
    "RISE",  # Rise time
    "FALL",  # Fall time
    "WID",  # Positive width
    "NWID",  # Negative width
    "DUTY",  # Duty cycle
]


class Measurement:
    """Measurement and cursor control for oscilloscope.

    Provides methods for automated measurements, cursor control,
    and measurement statistics.
    """

    def __init__(self, oscilloscope: "Oscilloscope"):
        """Initialize measurement control.

        Args:
            oscilloscope: Parent Oscilloscope instance
        """
        self._scope = oscilloscope

    def measure(self, mtype: MeasurementType, channel: int) -> float:
        """Perform a measurement on a channel.

        Args:
            mtype: Measurement type (e.g., 'PKPK', 'FREQ', 'RMS')
            channel: Channel number (1-4)

        Returns:
            Measurement value

        Raises:
            InvalidParameterError: If parameters are invalid
        """
        if not 1 <= channel <= 4:
            raise exceptions.InvalidParameterError(f"Invalid channel number: {channel}. Must be 1-4.")

        mtype = mtype.upper()
        ch = f"C{channel}"

        # Query parameter value
        response = self._scope.query(f"PAVA? {mtype},{ch}")

        # Parse response (format typically: "PAVA PKPK,C1,1.23V")
        try:
            # Extract value from response
            parts = response.split(",")
            if len(parts) >= 3:
                value_str = parts[2].strip()
                # Remove units (V, s, Hz, %, etc.)
                for unit in ["V", "S", "HZ", "%", "A"]:
                    value_str = value_str.replace(unit, "").replace(unit.lower(), "")
                return float(value_str)
            else:
                raise ValueError(f"Unexpected response format: {response}")
        except (ValueError, IndexError) as e:
            raise exceptions.CommandError(f"Failed to parse measurement: {e}")

    def measure_vpp(self, channel: int) -> float:
        """Measure peak-to-peak voltage.

        Args:
            channel: Channel number (1-4)

        Returns:
            Peak-to-peak voltage in volts
        """
        return self.measure("PKPK", channel)

    def measure_amplitude(self, channel: int) -> float:
        """Measure amplitude.

        Args:
            channel: Channel number (1-4)

        Returns:
            Amplitude in volts
        """
        return self.measure("AMPL", channel)

    def measure_frequency(self, channel: int) -> float:
        """Measure frequency.

        Args:
            channel: Channel number (1-4)

        Returns:
            Frequency in Hz
        """
        return self.measure("FREQ", channel)

    def measure_period(self, channel: int) -> float:
        """Measure period.

        Args:
            channel: Channel number (1-4)

        Returns:
            Period in seconds
        """
        return self.measure("PER", channel)

    def measure_rms(self, channel: int, cycle: bool = False) -> float:
        """Measure RMS voltage.

        Args:
            channel: Channel number (1-4)
            cycle: If True, measure over one cycle; if False, measure all

        Returns:
            RMS voltage in volts
        """
        mtype = "CRMS" if cycle else "RMS"
        return self.measure(mtype, channel)

    def measure_mean(self, channel: int, cycle: bool = False) -> float:
        """Measure mean voltage.

        Args:
            channel: Channel number (1-4)
            cycle: If True, measure over one cycle; if False, measure all

        Returns:
            Mean voltage in volts
        """
        mtype = "CMEAN" if cycle else "MEAN"
        return self.measure(mtype, channel)

    def measure_max(self, channel: int) -> float:
        """Measure maximum voltage.

        Args:
            channel: Channel number (1-4)

        Returns:
            Maximum voltage in volts
        """
        return self.measure("MAX", channel)

    def measure_min(self, channel: int) -> float:
        """Measure minimum voltage.

        Args:
            channel: Channel number (1-4)

        Returns:
            Minimum voltage in volts
        """
        return self.measure("MIN", channel)

    def measure_rise_time(self, channel: int) -> float:
        """Measure rise time.

        Args:
            channel: Channel number (1-4)

        Returns:
            Rise time in seconds
        """
        return self.measure("RISE", channel)

    def measure_fall_time(self, channel: int) -> float:
        """Measure fall time.

        Args:
            channel: Channel number (1-4)

        Returns:
            Fall time in seconds
        """
        return self.measure("FALL", channel)

    def measure_duty_cycle(self, channel: int) -> float:
        """Measure duty cycle.

        Args:
            channel: Channel number (1-4)

        Returns:
            Duty cycle in percent
        """
        return self.measure("DUTY", channel)

    def measure_all(self, channel: int) -> Dict[str, float]:
        """Perform multiple common measurements on a channel.

        Args:
            channel: Channel number (1-4)

        Returns:
            Dictionary with measurement names and values
        """
        measurements = {}

        # Basic voltage measurements
        try:
            measurements["vpp"] = self.measure_vpp(channel)
        except Exception:
            measurements["vpp"] = None

        try:
            measurements["amplitude"] = self.measure_amplitude(channel)
        except Exception:
            measurements["amplitude"] = None

        try:
            measurements["max"] = self.measure_max(channel)
        except Exception:
            measurements["max"] = None

        try:
            measurements["min"] = self.measure_min(channel)
        except Exception:
            measurements["min"] = None

        try:
            measurements["mean"] = self.measure_mean(channel)
        except Exception:
            measurements["mean"] = None

        try:
            measurements["rms"] = self.measure_rms(channel)
        except Exception:
            measurements["rms"] = None

        # Timing measurements
        try:
            measurements["frequency"] = self.measure_frequency(channel)
        except Exception:
            measurements["frequency"] = None

        try:
            measurements["period"] = self.measure_period(channel)
        except Exception:
            measurements["period"] = None

        logger.info(f"Completed measurements on channel {channel}")
        return measurements

    def add_measurement(self, mtype: str, channel: int, stat: bool = False) -> None:
        """Add a measurement to the measurement table.

        Args:
            mtype: Measurement type
            channel: Channel number (1-4)
            stat: Enable statistics for this measurement
        """
        if not 1 <= channel <= 4:
            raise exceptions.InvalidParameterError(f"Invalid channel number: {channel}. Must be 1-4.")

        ch = f"C{channel}"
        stat_flag = "ON" if stat else "OFF"

        # Add measurement (command format may vary by model)
        self._scope.write(f"PACU {mtype},{ch}")

        if stat:
            self._scope.write(f"PAST {stat_flag}")

        logger.info(f"Added measurement {mtype} for {ch}")

    def clear_measurements(self) -> None:
        """Clear all measurements from the measurement table."""
        self._scope.write("PACL")
        logger.info("Cleared all measurements")

    def enable_statistics(self) -> None:
        """Enable measurement statistics."""
        self._scope.write("PAST ON")
        logger.info("Measurement statistics enabled")

    def disable_statistics(self) -> None:
        """Disable measurement statistics."""
        self._scope.write("PAST OFF")
        logger.info("Measurement statistics disabled")

    def reset_statistics(self) -> None:
        """Reset measurement statistics."""
        self._scope.write("PASTAT RESET")
        logger.info("Measurement statistics reset")

    def set_cursor_type(self, cursor_type: str) -> None:
        """Set cursor type.

        Args:
            cursor_type: Cursor type - 'OFF', 'HREL', 'VREL', 'HREF', 'VREF'
                        HREL: Horizontal relative (time)
                        VREL: Vertical relative (voltage)
                        HREF: Horizontal reference
                        VREF: Vertical reference
        """
        cursor_type = cursor_type.upper()
        valid_types = ["OFF", "HREL", "VREL", "HREF", "VREF"]

        if cursor_type not in valid_types:
            raise exceptions.InvalidParameterError(f"Invalid cursor type: {cursor_type}. Must be one of {valid_types}.")

        self._scope.write(f"CRST {cursor_type}")
        logger.info(f"Cursor type set to {cursor_type}")

    def get_cursor_value(self) -> Dict[str, Any]:
        """Get cursor measurement values.

        Returns:
            Dictionary with cursor measurements
        """
        response = self._scope.query("CRVA?")

        # Parse cursor values
        # Response format varies by cursor type
        # Example: "CRVA VREL,1.00V,2.00V,1.00V"

        parts = response.split(",")
        result = {
            "type": parts[0].replace("CRVA", "").strip() if parts else "UNKNOWN",
            "values": [p.strip() for p in parts[1:]] if len(parts) > 1 else [],
        }

        return result

    def __repr__(self) -> str:
        """String representation."""
        return "Measurement()"
