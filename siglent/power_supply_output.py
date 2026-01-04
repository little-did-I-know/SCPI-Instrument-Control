"""Power supply output control and configuration.

Represents a single power supply output with voltage, current, and enable control.
"""

import logging
import re
from typing import TYPE_CHECKING, Dict

from siglent import exceptions

if TYPE_CHECKING:
    from siglent.power_supply import PowerSupply
    from siglent.psu_models import OutputSpec

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

    # --- Voltage Control ---

    @property
    def voltage(self) -> float:
        """Get voltage setpoint in volts.

        Returns:
            Voltage setpoint in volts
        """
        cmd = self._psu._get_command("get_voltage", ch=self._output_num)
        response = self._psu.query(cmd)
        return self._parse_float(response)

    @voltage.setter
    def voltage(self, volts: float) -> None:
        """Set voltage setpoint in volts.

        Args:
            volts: Voltage setpoint in volts

        Raises:
            InvalidParameterError: If voltage exceeds maximum for this output
        """
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
        cmd = self._psu._get_command("get_current", ch=self._output_num)
        response = self._psu.query(cmd)
        return self._parse_float(response)

    @current.setter
    def current(self, amps: float) -> None:
        """Set current limit in amps.

        Args:
            amps: Current limit in amps

        Raises:
            InvalidParameterError: If current exceeds maximum for this output
        """
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
        cmd = self._psu._get_command("measure_voltage", ch=self._output_num)
        response = self._psu.query(cmd)
        return self._parse_float(response)

    def measure_current(self) -> float:
        """Measure actual output current in amps.

        Returns:
            Actual output current in amps
        """
        cmd = self._psu._get_command("measure_current", ch=self._output_num)
        response = self._psu.query(cmd)
        return self._parse_float(response)

    def measure_power(self) -> float:
        """Measure actual output power in watts.

        Returns:
            Actual output power in watts
        """
        cmd = self._psu._get_command("measure_power", ch=self._output_num)
        response = self._psu.query(cmd)
        return self._parse_float(response)

    def get_mode(self) -> str:
        """Get current operating mode.

        Returns:
            Operating mode: 'CV' (constant voltage) or 'CC' (constant current)

        Note:
            Not all power supplies support mode query. May raise an exception
            if the command is not supported.
        """
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
            NotImplementedError: If OVP is not supported by this model
        """
        if not self._psu.model_capability.has_ovp:
            raise NotImplementedError(f"Over-voltage protection not supported on {self._psu.model_capability.model_name}")

        cmd = self._psu._get_command("get_voltage_limit", ch=self._output_num)
        response = self._psu.query(cmd)
        return self._parse_float(response)

    @ovp_level.setter
    def ovp_level(self, volts: float) -> None:
        """Set over-voltage protection level in volts.

        Args:
            volts: OVP level in volts

        Raises:
            NotImplementedError: If OVP is not supported by this model
        """
        if not self._psu.model_capability.has_ovp:
            raise NotImplementedError(f"Over-voltage protection not supported on {self._psu.model_capability.model_name}")

        cmd = self._psu._get_command("set_voltage_limit", ch=self._output_num, limit=volts)
        self._psu.write(cmd)
        logger.info(f"Output {self._output_num} OVP set to {volts}V")

    @property
    def ocp_level(self) -> float:
        """Get over-current protection level in amps.

        Returns:
            OCP level in amps

        Raises:
            NotImplementedError: If OCP is not supported by this model
        """
        if not self._psu.model_capability.has_ocp:
            raise NotImplementedError(f"Over-current protection not supported on {self._psu.model_capability.model_name}")

        cmd = self._psu._get_command("get_current_limit", ch=self._output_num)
        response = self._psu.query(cmd)
        return self._parse_float(response)

    @ocp_level.setter
    def ocp_level(self, amps: float) -> None:
        """Set over-current protection level in amps.

        Args:
            amps: OCP level in amps

        Raises:
            NotImplementedError: If OCP is not supported by this model
        """
        if not self._psu.model_capability.has_ocp:
            raise NotImplementedError(f"Over-current protection not supported on {self._psu.model_capability.model_name}")

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
            NotImplementedError: If timer is not supported by this model
        """
        if not self._psu.model_capability.has_timer:
            raise NotImplementedError(f"Timer not supported on {self._psu.model_capability.model_name}")

        cmd = self._psu._get_command("get_timer_enable", ch=self._output_num)
        response = self._psu.query(cmd)
        return "ON" in response.upper()

    @timer_enabled.setter
    def timer_enabled(self, state: bool) -> None:
        """Set timer enable state.

        Args:
            state: True to enable timer, False to disable

        Raises:
            NotImplementedError: If timer is not supported by this model
        """
        if not self._psu.model_capability.has_timer:
            raise NotImplementedError(f"Timer not supported on {self._psu.model_capability.model_name}")

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
            NotImplementedError: If waveform generation is not supported
        """
        if not self._psu.model_capability.has_waveform:
            raise NotImplementedError(f"Waveform generation not supported on {self._psu.model_capability.model_name}")

        cmd = self._psu._get_command("get_wave_enable", ch=self._output_num)
        response = self._psu.query(cmd)
        return "ON" in response.upper()

    @waveform_enabled.setter
    def waveform_enabled(self, state: bool) -> None:
        """Set waveform generation enable state.

        Args:
            state: True to enable waveform, False to disable

        Raises:
            NotImplementedError: If waveform generation is not supported
        """
        if not self._psu.model_capability.has_waveform:
            raise NotImplementedError(f"Waveform generation not supported on {self._psu.model_capability.model_name}")

        state_str = "ON" if state else "OFF"
        cmd = self._psu._get_command("set_wave_enable", ch=self._output_num, state=state_str)
        self._psu.write(cmd)
        logger.info(f"Output {self._output_num} waveform {'enabled' if state else 'disabled'}")

    # --- Helper Methods ---

    def _parse_float(self, response: str) -> float:
        """Parse float value from SCPI response.

        Handles various response formats:
        - "5.000" -> 5.0
        - "CH1:VOLT 5.000V" -> 5.0
        - "5.000E+00" -> 5.0

        Args:
            response: SCPI response string

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
        except ValueError:
            logger.error(f"Failed to parse float from response: {response}")
            return 0.0

    def get_configuration(self) -> Dict[str, any]:
        """Get all output configuration parameters.

        Returns:
            Dictionary with all output settings
        """
        config = {
            "output": self._output_num,
            "enabled": self.enabled,
            "voltage_setpoint": self.voltage,
            "current_limit": self.current,
            "max_voltage": self._spec.max_voltage,
            "max_current": self._spec.max_current,
            "max_power": self._spec.max_power,
        }

        # Add measurements
        try:
            config["measured_voltage"] = self.measure_voltage()
            config["measured_current"] = self.measure_current()
            config["measured_power"] = self.measure_power()
            config["mode"] = self.get_mode()
        except Exception as e:
            logger.warning(f"Failed to get measurements: {e}")

        return config

    def __repr__(self) -> str:
        """String representation."""
        try:
            config = self.get_configuration()
            return f"Output{self._output_num}(" f"enabled={config['enabled']}, " f"V={config['voltage_setpoint']}V, " f"I={config['current_limit']}A)"
        except Exception:
            return f"Output{self._output_num}"
