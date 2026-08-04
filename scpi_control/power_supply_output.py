"""Power supply output control and configuration.

Represents a single power supply output with voltage, current, and enable control.
"""

import logging
import re
from typing import TYPE_CHECKING, Dict, Optional

from scpi_control import exceptions
from scpi_control.psu_scpi_commands import decode_spd_status

if TYPE_CHECKING:
    from scpi_control.power_supply import PowerSupply
    from scpi_control.psu_models import OutputSpec

logger = logging.getLogger(__name__)


class PowerSupplyOutput:
    """Represents a single power supply output channel.

    Provides methods to configure output settings including voltage setpoint,
    current limit, output enable/disable, and measurements.
    """

    def __init__(self, psu: "PowerSupply", spec: "OutputSpec"):
        """Initialize power supply output.

        Args:
            psu: Parent PowerSupply instance
            spec: OutputSpec with voltage/current limits for this output
        """
        self._psu = psu
        self._spec = spec
        self._output_num = spec.output_num

        if not 1 <= self._output_num <= 3:
            raise exceptions.InvalidParameterError(f"Invalid output number: {self._output_num}. Must be 1-3.")

    def _require(self, flag: str, what: str) -> None:
        """Raise unless this output's spec documents `what` as supported.

        The flags come from the model's programming manual (see OutputSpec);
        an output the manual does not cover must fail loudly rather than send
        a command the firmware silently discards.
        """
        if not getattr(self._spec, flag, True):
            raise exceptions.FeatureNotSupportedError(f"{what} is not supported on output {self._output_num} of {self._psu.model_capability.model_name}")

    # --- Voltage Control ---

    @property
    def voltage(self) -> float:
        """Get voltage setpoint in volts.

        Returns:
            Voltage setpoint in volts
        """
        self._require("programmable", "Voltage setpoint control")
        cmd = self._psu._get_command("get_voltage", ch=self._output_num)
        response = self._psu.query(cmd)
        return self._parse_float(response, cmd)

    @voltage.setter
    def voltage(self, volts: float) -> None:
        """Set voltage setpoint in volts.

        Args:
            volts: Voltage setpoint in volts

        Raises:
            InvalidParameterError: If voltage exceeds maximum for this output
        """
        self._require("programmable", "Voltage setpoint control")
        if not 0 <= volts <= self._spec.max_voltage:
            raise exceptions.InvalidParameterError(f"Voltage {volts}V exceeds maximum {self._spec.max_voltage}V " f"for output {self._output_num}")

        cmd = self._psu._get_command("set_voltage", ch=self._output_num, voltage=volts)
        self._psu.write(cmd)
        logger.info(f"Output {self._output_num} voltage set to {volts}V")

    def set_voltage(self, volts: float) -> None:
        """Set voltage setpoint (alias for voltage setter).

        Args:
            volts: Voltage setpoint in volts
        """
        self.voltage = volts

    # --- Current Control ---

    @property
    def current(self) -> float:
        """Get current limit setpoint in amps.

        Returns:
            Current limit in amps
        """
        self._require("programmable", "Current setpoint control")
        cmd = self._psu._get_command("get_current", ch=self._output_num)
        response = self._psu.query(cmd)
        return self._parse_float(response, cmd)

    @current.setter
    def current(self, amps: float) -> None:
        """Set current limit in amps.

        Args:
            amps: Current limit in amps

        Raises:
            InvalidParameterError: If current exceeds maximum for this output
        """
        self._require("programmable", "Current setpoint control")
        if not 0 <= amps <= self._spec.max_current:
            raise exceptions.InvalidParameterError(f"Current {amps}A exceeds maximum {self._spec.max_current}A " f"for output {self._output_num}")

        cmd = self._psu._get_command("set_current", ch=self._output_num, current=amps)
        self._psu.write(cmd)
        logger.info(f"Output {self._output_num} current limit set to {amps}A")

    def set_current(self, amps: float) -> None:
        """Set current limit (alias for current setter).

        Args:
            amps: Current limit in amps
        """
        self.current = amps

    # --- Output Enable/Disable ---

    @property
    def enabled(self) -> bool:
        """Get output enable state.

        Returns:
            True if output is enabled, False otherwise
        """
        self._require("state_readable", "Output state read-back")
        scpi_commands = self._psu._scpi_commands
        if scpi_commands is not None and scpi_commands.supports_command("get_status"):
            # QS0503X-E01B p.36/p.40-41: the SPD3303X has no output-state
            # query at all -- state is decoded from the bit-encoded
            # SYSTem:STATus? response instead (audit H20, Task 8).
            cmd = self._psu._get_command("get_status")
            response = self._psu.query(cmd)
            state = decode_spd_status(response)
            key = f"ch{self._output_num}_output"
            if key in state:
                return state[key]

        cmd = self._psu._get_command("get_output", ch=self._output_num)
        response = self._psu.query(cmd)
        # Response may be "ON", "OFF", or include echo like "OUTPUT CH1,ON"
        return "ON" in response.upper()

    @enabled.setter
    def enabled(self, state: bool) -> None:
        """Set output enable state.

        Args:
            state: True to enable output, False to disable
        """
        self._require("switchable", "Output switching")
        state_str = "ON" if state else "OFF"
        cmd = self._psu._get_command("set_output", ch=self._output_num, state=state_str)
        self._psu.write(cmd)
        logger.info(f"Output {self._output_num} {'enabled' if state else 'disabled'}")

    def enable(self) -> None:
        """Enable output (turn on)."""
        self.enabled = True

    def disable(self) -> None:
        """Disable output (turn off)."""
        self.enabled = False

    # --- Measurements ---

    def measure_voltage(self) -> float:
        """Measure actual output voltage in volts.

        Returns:
            Actual output voltage in volts
        """
        self._require("measurable", "Measurement")
        cmd = self._psu._get_command("measure_voltage", ch=self._output_num)
        response = self._psu.query(cmd)
        return self._parse_float(response, cmd)

    def measure_current(self) -> float:
        """Measure actual output current in amps.

        Returns:
            Actual output current in amps
        """
        self._require("measurable", "Measurement")
        cmd = self._psu._get_command("measure_current", ch=self._output_num)
        response = self._psu.query(cmd)
        return self._parse_float(response, cmd)

    def measure_power(self) -> float:
        """Measure actual output power in watts.

        Returns:
            Actual output power in watts
        """
        self._require("measurable", "Measurement")
        cmd = self._psu._get_command("measure_power", ch=self._output_num)
        response = self._psu.query(cmd)
        return self._parse_float(response, cmd)

    def get_mode(self) -> str:
        """Get current operating mode.

        Returns:
            Operating mode: 'CV' (constant voltage) or 'CC' (constant current)

        Note:
            Not all power supplies support mode query. May raise an exception
            if the command is not supported.
        """
        self._require("measurable", "Operating-mode read-back")
        try:
            cmd = self._psu._get_command("get_output_mode", ch=self._output_num)
            response = self._psu.query(cmd)
            return response.strip()
        except Exception as e:
            logger.warning(f"Failed to get output mode: {e}")
            return "UNKNOWN"

    # --- Advanced Features (if supported by model) ---

    @property
    def ovp_level(self) -> float:
        """Get over-voltage protection level in volts.

        Returns:
            OVP level in volts

        Raises:
            FeatureNotSupportedError: If OVP is not supported by this model
        """
        if not self._psu.model_capability.has_ovp:
            raise exceptions.FeatureNotSupportedError(f"Over-voltage protection not supported on {self._psu.model_capability.model_name}")

        cmd = self._psu._get_command("get_voltage_limit", ch=self._output_num)
        response = self._psu.query(cmd)
        return self._parse_float(response, cmd)

    @ovp_level.setter
    def ovp_level(self, volts: float) -> None:
        """Set over-voltage protection level in volts.

        Args:
            volts: OVP level in volts

        Raises:
            FeatureNotSupportedError: If OVP is not supported by this model
        """
        if not self._psu.model_capability.has_ovp:
            raise exceptions.FeatureNotSupportedError(f"Over-voltage protection not supported on {self._psu.model_capability.model_name}")

        cmd = self._psu._get_command("set_voltage_limit", ch=self._output_num, limit=volts)
        self._psu.write(cmd)
        logger.info(f"Output {self._output_num} OVP set to {volts}V")

    @property
    def ocp_level(self) -> float:
        """Get over-current protection level in amps.

        Returns:
            OCP level in amps

        Raises:
            FeatureNotSupportedError: If OCP is not supported by this model
        """
        if not self._psu.model_capability.has_ocp:
            raise exceptions.FeatureNotSupportedError(f"Over-current protection not supported on {self._psu.model_capability.model_name}")

        cmd = self._psu._get_command("get_current_limit", ch=self._output_num)
        response = self._psu.query(cmd)
        return self._parse_float(response, cmd)

    @ocp_level.setter
    def ocp_level(self, amps: float) -> None:
        """Set over-current protection level in amps.

        Args:
            amps: OCP level in amps

        Raises:
            FeatureNotSupportedError: If OCP is not supported by this model
        """
        if not self._psu.model_capability.has_ocp:
            raise exceptions.FeatureNotSupportedError(f"Over-current protection not supported on {self._psu.model_capability.model_name}")

        cmd = self._psu._get_command("set_current_limit", ch=self._output_num, limit=amps)
        self._psu.write(cmd)
        logger.info(f"Output {self._output_num} OCP set to {amps}A")

    # --- Timer Functionality (Siglent SPD specific) ---

    @property
    def timer_enabled(self) -> bool:
        """Get timer enable state.

        Returns:
            True if timer is enabled, False otherwise

        Raises:
            FeatureNotSupportedError: If timer is not supported by this model
        """
        if not self._psu.model_capability.has_timer:
            raise exceptions.FeatureNotSupportedError(f"Timer not supported on {self._psu.model_capability.model_name}")
        self._require("supports_timer", "Timer control")

        cmd = self._psu._get_command("get_timer_enable", ch=self._output_num)
        response = self._psu.query(cmd)
        return "ON" in response.upper()

    @timer_enabled.setter
    def timer_enabled(self, state: bool) -> None:
        """Set timer enable state.

        Args:
            state: True to enable timer, False to disable

        Raises:
            FeatureNotSupportedError: If timer is not supported by this model
        """
        if not self._psu.model_capability.has_timer:
            raise exceptions.FeatureNotSupportedError(f"Timer not supported on {self._psu.model_capability.model_name}")
        self._require("supports_timer", "Timer control")

        state_str = "ON" if state else "OFF"
        cmd = self._psu._get_command("set_timer_enable", ch=self._output_num, state=state_str)
        self._psu.write(cmd)
        logger.info(f"Output {self._output_num} timer {'enabled' if state else 'disabled'}")

    # --- Waveform Generation (Siglent SPD3303X specific) ---

    @property
    def waveform_enabled(self) -> bool:
        """Get waveform generation enable state.

        Returns:
            True if waveform is enabled, False otherwise

        Raises:
            FeatureNotSupportedError: If waveform generation is not supported
        """
        if not self._psu.model_capability.has_waveform:
            raise exceptions.FeatureNotSupportedError(f"Waveform generation not supported on {self._psu.model_capability.model_name}")
        self._require("supports_waveform", "Waveform display control")

        cmd = self._psu._get_command("get_wave_enable", ch=self._output_num)
        response = self._psu.query(cmd)
        return "ON" in response.upper()

    @waveform_enabled.setter
    def waveform_enabled(self, state: bool) -> None:
        """Set waveform generation enable state.

        Args:
            state: True to enable waveform, False to disable

        Raises:
            FeatureNotSupportedError: If waveform generation is not supported
        """
        if not self._psu.model_capability.has_waveform:
            raise exceptions.FeatureNotSupportedError(f"Waveform generation not supported on {self._psu.model_capability.model_name}")
        self._require("supports_waveform", "Waveform display control")

        state_str = "ON" if state else "OFF"
        cmd = self._psu._get_command("set_wave_enable", ch=self._output_num, state=state_str)
        self._psu.write(cmd)
        logger.info(f"Output {self._output_num} waveform {'enabled' if state else 'disabled'}")

    # --- Helper Methods ---

    def _parse_float(self, response: str, command: Optional[str] = None) -> float:
        """Parse float value from SCPI response.

        Handles various response formats:
        - "5.000" -> 5.0
        - "CH1:VOLT 5.000V" -> 5.0
        - "5.000E+00" -> 5.0

        Args:
            response: SCPI response string
            command: SCPI command that was sent (for error reporting)

        Returns:
            Parsed float value
        """
        # Remove echo prefix if present (e.g., "CH1:VOLT 5.000")
        if ":" in response:
            response = response.split(":", 1)[1]

        # Remove command part if present (e.g., "VOLT 5.000")
        if " " in response:
            response = response.split(" ", 1)[1]

        # Remove common units
        response = re.sub(r"[VvAaWw]", "", response).strip()

        try:
            return float(response)
        except ValueError as exc:
            raise exceptions.CommandError(f"Unparseable PSU response: {response!r}", command=command) from exc

    def get_configuration(self) -> Dict[str, any]:
        """Summarize this output, omitting anything the model cannot report.

        Diagnostic aggregate: an unsupported field is left OUT rather than
        raising or being filled with a plausible number. `capabilities` says
        which fields the model documents, so a caller can tell an absent
        reading from an unsupported one.
        """
        config: Dict[str, any] = {
            "output": self._output_num,
            "max_voltage": self._spec.max_voltage,
            "max_current": self._spec.max_current,
            "max_power": self._spec.max_power,
            "capabilities": {
                "programmable": self._spec.programmable,
                "measurable": self._spec.measurable,
                "switchable": self._spec.switchable,
                "state_readable": self._spec.state_readable,
                "supports_timer": self._spec.supports_timer,
                "supports_waveform": self._spec.supports_waveform,
            },
        }
        if self._spec.programmable:
            config["voltage_setpoint"] = self.voltage
            config["current_limit"] = self.current
        if self._spec.state_readable:
            config["enabled"] = self.enabled
        if self._spec.measurable:
            try:
                config["measured_voltage"] = self.measure_voltage()
                config["measured_current"] = self.measure_current()
                config["measured_power"] = self.measure_power()
                config["mode"] = self.get_mode()
            except Exception as e:
                logger.warning(f"Failed to get measurements: {e}")
        if self._psu.model_capability.has_ovp:
            config["ovp_level"] = self.ovp_level
        if self._psu.model_capability.has_ocp:
            config["ocp_level"] = self.ocp_level
        return config

    def __repr__(self) -> str:
        """String representation."""
        try:
            config = self.get_configuration()
            return f"Output{self._output_num}(" f"enabled={config.get('enabled')}, " f"V={config.get('voltage_setpoint')}V, " f"I={config.get('current_limit')}A)"
        except Exception:
            return f"Output{self._output_num}"
