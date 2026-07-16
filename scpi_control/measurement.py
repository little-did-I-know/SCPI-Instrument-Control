"""Measurement and cursor control for Siglent oscilloscopes."""

import logging
from typing import TYPE_CHECKING, Any, Dict, Literal, Optional

from scpi_control import exceptions
from scpi_control.scpi_commands import measurement_to_wire

if TYPE_CHECKING:
    from scpi_control.oscilloscope import Oscilloscope

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

    @property
    def _dialect(self) -> str:
        """Wire dialect of the parent scope; defaults to legacy before connect."""
        return getattr(self._scope, "dialect", None) or "legacy"

    def _require(self, command_name: str) -> None:
        if not self._scope._has_command(command_name):
            raise exceptions.FeatureNotSupportedError(f"{command_name} is not supported on the {self._dialect} dialect")

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
        wire_type = measurement_to_wire(self._dialect, mtype)

        if self._dialect == "tektronix":
            if not self._scope._has_command("set_meas_immed_type"):
                raise exceptions.FeatureNotSupportedError(
                    f"measure({mtype!r}) is not supported: this Tektronix family/configuration lacks the " "MEASUrement:IMMed subsystem (badge-based measurements are a follow-up)"
                )
            # Immediate measurement: configure type+source, then read the value
            self._scope.write(self._scope._get_command("set_meas_immed_type", type=wire_type))
            self._scope.write(self._scope._get_command("set_meas_immed_source", ch=channel))
            response = self._scope.query(self._scope._get_command("get_meas_immed_value"))
            try:
                return float(response.strip())
            except ValueError as e:
                raise exceptions.CommandError(f"Failed to parse measurement: {e}")

        # Query parameter value
        response = self._scope.query(self._scope._get_command("get_parameter_value", ch=channel, param=wire_type))

        if self._dialect == "lecroy":
            # LeCroy's PAVA? answers its own native shape "<param>,<value>,
            # <state>" (3 fields; CHDR OFF strips the unit suffix) -- MAUI
            # remote manual p.7-70. Value is the 2nd field (parts[1]).
            try:
                parts = response.split(",")
                return float(parts[1].strip())
            except (ValueError, IndexError) as e:
                raise exceptions.CommandError(f"Failed to parse measurement: {e}")

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

        self._require("add_measurement")
        wire_type = measurement_to_wire(self._dialect, mtype.upper())
        ch = f"C{channel}"

        # Add measurement (command format may vary by model)
        self._scope.write(self._scope._get_command("add_measurement", mtype=wire_type, ch=channel))

        if stat:
            self._require("set_statistics")
            self._scope.write(self._scope._get_command("set_statistics", state="ON"))

        logger.info(f"Added measurement {mtype} for {ch}")

    def clear_measurements(self) -> None:
        """Clear all measurements from the measurement table."""
        self._require("clear_measurements")
        self._scope.write(self._scope._get_command("clear_measurements"))
        logger.info("Cleared all measurements")

    def enable_statistics(self) -> None:
        """Enable measurement statistics."""
        self._require("set_statistics")
        self._scope.write(self._scope._get_command("set_statistics", state="ON"))
        logger.info("Measurement statistics enabled")

    def disable_statistics(self) -> None:
        """Disable measurement statistics."""
        self._require("set_statistics")
        self._scope.write(self._scope._get_command("set_statistics", state="OFF"))
        logger.info("Measurement statistics disabled")

    def reset_statistics(self) -> None:
        """Reset measurement statistics."""
        self._require("reset_statistics")
        self._scope.write(self._scope._get_command("reset_statistics"))
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

        self._require("set_cursor_type")
        self._scope.write(self._scope._get_command("set_cursor_type", type=cursor_type))
        logger.info(f"Cursor type set to {cursor_type}")

    def get_cursor_value(self) -> Dict[str, Any]:
        """Get cursor measurement values.

        Returns:
            Dictionary with cursor measurements
        """
        self._require("get_cursor_value")
        response = self._scope.query(self._scope._get_command("get_cursor_value"))

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
