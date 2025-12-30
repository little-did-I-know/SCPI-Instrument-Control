"""Channel configuration and control for Siglent oscilloscopes."""

import logging
from typing import TYPE_CHECKING, Literal, Optional

from siglent import exceptions

if TYPE_CHECKING:
    from siglent.oscilloscope import Oscilloscope

logger = logging.getLogger(__name__)

CouplingType = Literal["DC", "AC", "GND"]
BandwidthLimitType = Literal["OFF", "ON", "FULL"]


class Channel:
    """Represents a single oscilloscope channel with configuration controls.

    Provides methods to configure channel settings including coupling,
    voltage scale, offset, probe ratio, and bandwidth limiting.
    """

    def __init__(self, oscilloscope: "Oscilloscope", channel_number: int):
        """Initialize channel.

        Args:
            oscilloscope: Parent Oscilloscope instance
            channel_number: Channel number (1-4)
        """
        self._scope = oscilloscope
        self._channel = channel_number
        self._prefix = f"C{channel_number}"

        if not 1 <= channel_number <= 4:
            raise exceptions.InvalidParameterError(f"Invalid channel number: {channel_number}. Must be 1-4.")

    @property
    def enabled(self) -> bool:
        """Get channel display state.

        Returns:
            True if channel is displayed, False otherwise
        """
        response = self._scope.query(f"{self._prefix}:TRA?")
        # Response format: "C1:TRA ON" or "C1:TRA OFF"
        # Extract the last word
        return "ON" in response.upper()

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Set channel display state.

        Args:
            value: True to display channel, False to hide
        """
        state = "ON" if value else "OFF"
        self._scope.write(f"{self._prefix}:TRA {state}")
        logger.info(f"Channel {self._channel} {'enabled' if value else 'disabled'}")

    def enable(self) -> None:
        """Enable channel display."""
        self.enabled = True

    def disable(self) -> None:
        """Disable channel display."""
        self.enabled = False

    @property
    def coupling(self) -> str:
        """Get channel coupling mode.

        Returns:
            Coupling mode: 'DC', 'AC', or 'GND'
        """
        response = self._scope.query(f"{self._prefix}:CPL?")
        return response.upper().strip()

    @coupling.setter
    def coupling(self, mode: CouplingType) -> None:
        """Set channel coupling mode.

        Args:
            mode: Coupling mode - 'DC', 'AC', or 'GND'
        """
        mode = mode.upper()
        if mode not in ["DC", "AC", "GND"]:
            raise exceptions.InvalidParameterError(f"Invalid coupling mode: {mode}. Must be DC, AC, or GND.")
        self._scope.write(f"{self._prefix}:CPL {mode}")
        logger.info(f"Channel {self._channel} coupling set to {mode}")

    @property
    def voltage_scale(self) -> float:
        """Get vertical scale (volts/division).

        Returns:
            Voltage scale in volts/division
        """
        response = self._scope.query(f"{self._prefix}:VDIV?")
        # Response may include echo like "C1:VDIV 1.0E+00V" or just "1.0E+00V"
        # Remove the echo prefix if present
        if ":" in response:
            response = response.split(":", 1)[1]  # Get everything after first ':'
        # Remove command part if present (e.g., "VDIV 1.0E+00")
        if " " in response:
            response = response.split(" ", 1)[1]  # Get everything after first space
        # Remove unit
        value = response.replace("V", "").strip()
        return float(value)

    @voltage_scale.setter
    def voltage_scale(self, volts_per_div: float) -> None:
        """Set vertical scale (volts/division).

        Args:
            volts_per_div: Voltage scale in volts/division

        Typical values: 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5,
                       1.0, 2.0, 5.0, 10.0
        """
        if volts_per_div <= 0:
            raise exceptions.InvalidParameterError(f"Voltage scale must be positive: {volts_per_div}")
        self._scope.write(f"{self._prefix}:VDIV {volts_per_div}")
        logger.info(f"Channel {self._channel} scale set to {volts_per_div} V/div")

    def set_scale(self, volts_per_div: float) -> None:
        """Set vertical scale (alias for voltage_scale setter).

        Args:
            volts_per_div: Voltage scale in volts/division
        """
        self.voltage_scale = volts_per_div

    @property
    def voltage_offset(self) -> float:
        """Get vertical offset voltage.

        Returns:
            Offset voltage in volts
        """
        response = self._scope.query(f"{self._prefix}:OFST?")
        # Response may include echo like "C1:OFST 1.0E+00V"
        if ":" in response:
            response = response.split(":", 1)[1]
        if " " in response:
            response = response.split(" ", 1)[1]
        value = response.replace("V", "").strip()
        return float(value)

    @voltage_offset.setter
    def voltage_offset(self, offset: float) -> None:
        """Set vertical offset voltage.

        Args:
            offset: Offset voltage in volts
        """
        self._scope.write(f"{self._prefix}:OFST {offset}")
        logger.info(f"Channel {self._channel} offset set to {offset} V")

    @property
    def probe_ratio(self) -> float:
        """Get probe attenuation ratio.

        Returns:
            Probe ratio (e.g., 1.0 for 1X, 10.0 for 10X)
        """
        response = self._scope.query(f"{self._prefix}:ATTN?")
        # Response may include echo like "C1:ATTN 10"
        if ":" in response:
            response = response.split(":", 1)[1]
        if " " in response:
            response = response.split(" ", 1)[1]
        return float(response.strip())

    @probe_ratio.setter
    def probe_ratio(self, ratio: float) -> None:
        """Set probe attenuation ratio.

        Args:
            ratio: Probe attenuation (1, 10, 100, 1000, etc.)

        Common values: 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000
        """
        if ratio <= 0:
            raise exceptions.InvalidParameterError(f"Probe ratio must be positive: {ratio}")
        self._scope.write(f"{self._prefix}:ATTN {ratio}")
        logger.info(f"Channel {self._channel} probe ratio set to {ratio}X")

    @property
    def bandwidth_limit(self) -> str:
        """Get bandwidth limit setting.

        Returns:
            Bandwidth limit: 'ON', 'OFF', or frequency limit
        """
        response = self._scope.query(f"{self._prefix}:BWL?")
        return response.upper().strip()

    @bandwidth_limit.setter
    def bandwidth_limit(self, limit: BandwidthLimitType) -> None:
        """Set bandwidth limit.

        Args:
            limit: 'ON' to enable 20MHz limit, 'OFF' or 'FULL' for full bandwidth
        """
        limit = limit.upper()
        if limit not in ["ON", "OFF", "FULL"]:
            raise exceptions.InvalidParameterError(f"Invalid bandwidth limit: {limit}. Must be ON, OFF, or FULL.")
        # Convert FULL to OFF for compatibility
        if limit == "FULL":
            limit = "OFF"
        self._scope.write(f"{self._prefix}:BWL {limit}")
        logger.info(f"Channel {self._channel} bandwidth limit set to {limit}")

    @property
    def unit(self) -> str:
        """Get channel vertical unit.

        Returns:
            Unit string (typically 'V' for volts)
        """
        response = self._scope.query(f"{self._prefix}:UNIT?")
        return response.strip()

    @unit.setter
    def unit(self, unit: str) -> None:
        """Set channel vertical unit.

        Args:
            unit: Unit string ('V' for volts, 'A' for amps)
        """
        self._scope.write(f"{self._prefix}:UNIT {unit}")
        logger.info(f"Channel {self._channel} unit set to {unit}")

    def auto_scale(self) -> None:
        """Perform auto-scale for this channel.

        Automatically adjusts voltage scale and offset for optimal viewing.
        """
        # Note: Some Siglent models use ASET for global auto-setup
        # For per-channel auto-scale, we might need to use different commands
        # This is a basic implementation that may need adjustment for SD824x
        logger.info(f"Auto-scaling channel {self._channel}")
        self._scope.write("ASET")

    def get_configuration(self) -> dict:
        """Get all channel configuration parameters.

        Returns:
            Dictionary with all channel settings
        """
        return {
            "channel": self._channel,
            "enabled": self.enabled,
            "coupling": self.coupling,
            "voltage_scale": self.voltage_scale,
            "voltage_offset": self.voltage_offset,
            "probe_ratio": self.probe_ratio,
            "bandwidth_limit": self.bandwidth_limit,
            "unit": self.unit,
        }

    def __repr__(self) -> str:
        """String representation."""
        try:
            config = self.get_configuration()
            return f"Channel{self._channel}(enabled={config['enabled']}, " f"scale={config['voltage_scale']}V/div, " f"coupling={config['coupling']})"
        except Exception:
            return f"Channel{self._channel}"
