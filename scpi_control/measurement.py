"""Measurement and cursor control for Siglent oscilloscopes."""

import logging
from typing import TYPE_CHECKING, Any, Dict, Literal, Optional

from scpi_control import exceptions
from scpi_control.measurement_badges import BadgePool
from scpi_control.models import validate_channel
from scpi_control.scpi_commands import badge_type_to_wire, measurement_to_wire

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
        # Badge lifecycle for the modern Tek MSO families; inert on other dialects
        self._badge_pool = BadgePool(oscilloscope)

    @property
    def _dialect(self) -> str:
        """Wire dialect of the parent scope; defaults to legacy before connect."""
        return getattr(self._scope, "dialect", None) or "legacy"

    def _require(self, command_name: str) -> None:
        if not self._scope._has_command(command_name):
            raise exceptions.FeatureNotSupportedError(f"{command_name} is not supported on the {self._dialect} dialect")

    def cleanup(self) -> None:
        """Release instrument-side measurement state owned by this session."""
        self._badge_pool.cleanup()

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
        validate_channel(self._scope, channel)

        mtype = mtype.upper()

        if self._dialect == "tektronix":
            if self._scope._has_command("set_meas_immed_type"):
                # TBS1000C: immediate measurement -- configure type+source, read the value
                wire_type = measurement_to_wire(self._dialect, mtype)
                self._scope.write(self._scope._get_command("set_meas_immed_type", type=wire_type))
                self._scope.write(self._scope._get_command("set_meas_immed_source", ch=channel))
                response = self._scope.query(self._scope._get_command("get_meas_immed_value"))
                # No sentinel check here (unlike the DAQ overload check in
                # data_logger.py and the "****" check below for the modern
                # dialect): MEASUrement:IMMed:VALue? is a TBS1000C-family
                # command (TBS p.121, per scpi_commands.py), and that manual
                # is not available in this repo to confirm what it returns
                # when no valid measurement exists. The 4/5/6 Series MSO
                # Programmer Manual (also in docs/) documents a 9.91E+37
                # "invalid value" sentinel for unrelated subsystems (cursor
                # readouts p.2-393/2-429, cycle-cycle measurement statistics
                # p.2-610-2-615, unset trigger thresholds in Appendix C) but
                # never for this specific query, and that manual's own
                # RESUlts:CURRentacq:MEAN/MINimum/PK2PK/POPUlation? examples
                # (p.2-690/2-691, the badge-path command actually used below)
                # show ordinary numbers with no sentinel mentioned. Applying
                # the MSO family's convention to a TBS1000C-only command would
                # be a guess, not a citation -- do not add a check without one.
                try:
                    return float(response.strip())
                except ValueError as e:
                    raise exceptions.CommandError(f"Failed to parse measurement: {e}")
            if self._scope._has_command("add_measurement_badge"):
                # MSO 2/4/5/6: no IMMed subsystem -- measure via a badge
                return self._badge_pool.value(badge_type_to_wire(self._dialect, mtype), channel)
            raise exceptions.FeatureNotSupportedError(f"measure({mtype!r}) is not supported: this Tektronix family/configuration has neither the MEASUrement:IMMed subsystem nor measurement badges")

        if self._dialect == "modern":
            # Modern instruments have no PARAMETER_VALUE command -- PAVA appears
            # zero times in the SDS800X HD guide. Measurements come from the
            # :MEASure:SIMPle subsystem (guide p.335-373): enable the function,
            # point it at the channel, switch the item on, then read it.
            #
            # Unlike legacy PAVA?, this MUTATES instrument state -- the source is
            # global to simple measurements and enabled items show on the display.
            # We deliberately do not clear them: :SIMPle:CLEar is all-or-nothing
            # and would wipe measurements the user configured by hand.
            wire_type = measurement_to_wire(self._dialect, mtype)
            self._scope.write(self._scope._get_command("set_measure_state", state="ON"))
            # p.369: VALue? "returns the specified measurement value that appears on
            # the simple measurement" -- if the instrument is left in ADVanced mode
            # (p.365) that read may fail or return something stale, so pin SIMPle
            # mode every time rather than trusting whatever mode it was already in.
            self._scope.write(self._scope._get_command("set_measure_mode", mode="SIMPle"))
            self._scope.write(self._scope._get_command("set_simple_source", ch=channel))
            self._scope.write(self._scope._get_command("set_simple_item", param=wire_type, state="ON"))
            response = self._scope.query(self._scope._get_command("get_simple_value", param=wire_type))
            # p.369: RESPONSE FORMAT is a bare <value> in NR3 ("2.000E+00") -- no
            # parameter name and no unit suffix, so the legacy comma-splitting
            # parser below cannot be reused.
            reply = response.strip()
            # "****" is the instrument's "no value for this item right now"
            # marker, not a malformed reply -- measured on an SDS824X HD, where
            # MEAN answered a normal NR3 while PKPK/MAX/MIN each returned
            # "****" on the same live channel. p.369 documents only the bare
            # NR3 and never mentions it. Reporting this as a parse failure made
            # an ordinary transient look like an instrument fault in the
            # gateway's poll log.
            if set(reply) == {"*"}:
                raise exceptions.MeasurementUnavailableError(f"Instrument reports no value for {wire_type} on channel {channel} right now (answered {reply!r})")
            try:
                return float(reply)
            except ValueError as e:
                raise exceptions.CommandError(f"Failed to parse measurement: {e}")

        wire_type = measurement_to_wire(self._dialect, mtype)

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

        # RC01020-E01C p.88: "<trace>:PAVA <parameter>,<value>" -- the value is
        # the last comma field. Only one parameter is ever requested.
        try:
            parts = response.split(",")
            if len(parts) < 2:
                raise ValueError(f"Unexpected response format: {response}")
            value_str = parts[-1].strip()
            for unit in ["V", "S", "HZ", "%", "A"]:
                value_str = value_str.replace(unit, "").replace(unit.lower(), "")
            return float(value_str)
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
        validate_channel(self._scope, channel)

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
