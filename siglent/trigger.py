"""Trigger configuration and control for Siglent oscilloscopes."""

import logging
from typing import TYPE_CHECKING, Literal, Optional, Union

from siglent import exceptions

if TYPE_CHECKING:
    from siglent.oscilloscope import Oscilloscope

logger = logging.getLogger(__name__)

TriggerModeType = Literal["AUTO", "NORM", "NORMAL", "SINGLE", "STOP"]
TriggerTypeType = Literal["EDGE", "SLEW", "GLIT", "INTV", "RUNT", "PATTERN"]
TriggerSlopeType = Literal["POS", "NEG", "WINDOW"]
TriggerCouplingType = Literal["DC", "AC", "HFREJ", "LFREJ"]


class Trigger:
    """Trigger configuration and control for oscilloscope.

    Provides methods to configure trigger settings including mode, source,
    level, slope, type, and other trigger parameters.
    """

    def __init__(self, oscilloscope: "Oscilloscope"):
        """Initialize trigger control.

        Args:
            oscilloscope: Parent Oscilloscope instance
        """
        self._scope = oscilloscope

    def _normalize_source(self, channel: Union[int, str]) -> str:
        """Normalize channel value to the expected SCPI string."""
        if isinstance(channel, int):
            channel = f"C{channel}"
        elif not isinstance(channel, str):
            raise exceptions.InvalidParameterError(f"Invalid trigger source type: {type(channel)}")

        channel = channel.upper()
        return channel

    @property
    def mode(self) -> str:
        """Get trigger mode.

        Returns:
            Trigger mode: 'AUTO', 'NORM', 'SINGLE', or 'STOP'
        """
        response = self._scope.query("TRIG_MODE?")
        return response.strip().upper()

    @mode.setter
    def mode(self, mode: TriggerModeType) -> None:
        """Set trigger mode.

        Args:
            mode: Trigger mode - 'AUTO', 'NORM'/'NORMAL', 'SINGLE', or 'STOP'
        """
        mode = mode.upper()
        # Normalize NORMAL to NORM
        if mode == "NORMAL":
            mode = "NORM"

        if mode not in ["AUTO", "NORM", "SINGLE", "STOP"]:
            raise exceptions.InvalidParameterError(f"Invalid trigger mode: {mode}. Must be AUTO, NORM, SINGLE, or STOP.")

        self._scope.write(f"TRIG_MODE {mode}")
        logger.info(f"Trigger mode set to {mode}")

    def set_mode(self, mode: TriggerModeType) -> None:
        """Set trigger mode (alias for mode property setter)."""
        self.mode = mode

    def auto(self) -> None:
        """Set trigger to AUTO mode."""
        self.mode = "AUTO"

    def normal(self) -> None:
        """Set trigger to NORMAL mode."""
        self.mode = "NORM"

    def single(self) -> None:
        """Set trigger to SINGLE mode (one-shot)."""
        self.mode = "SINGLE"

    def stop(self) -> None:
        """Stop triggering."""
        self.mode = "STOP"

    def force(self) -> None:
        """Force a trigger event immediately."""
        self._scope.write("FRTR")
        logger.info("Trigger forced")

    @property
    def source(self) -> str:
        """Get trigger source channel.

        Returns:
            Trigger source (e.g., 'C1', 'C2', 'C3', 'C4', 'EX', 'EX5', 'LINE')
        """
        response = self._scope.query("TRIG_SELECT?")
        # Response format typically: "EDGE,SR,C1,..."
        parts = response.split(",")
        if len(parts) >= 3:
            return parts[2].strip()
        return "UNKNOWN"

    @source.setter
    def source(self, channel: Union[int, str]) -> None:
        """Set trigger source channel.

        Args:
            channel: Source channel ('C1', 'C2', 'C3', 'C4', 'EX', 'EX5', 'LINE') or channel number
        """
        channel = self._normalize_source(channel)
        valid_sources = ["C1", "C2", "C3", "C4", "EX", "EX5", "LINE"]

        if channel not in valid_sources:
            raise exceptions.InvalidParameterError(f"Invalid trigger source: {channel}. Must be one of {valid_sources}.")

        # Get current trigger type to preserve it
        current_type = self.trigger_type

        # Set trigger with new source
        self._scope.write(f"TRIG_SELECT {current_type},SR,{channel}")
        logger.info(f"Trigger source set to {channel}")

    def set_source(self, channel: Union[int, str]) -> None:
        """Convenience wrapper to set trigger source."""
        self.source = channel

    @property
    def trigger_type(self) -> str:
        """Get trigger type.

        Returns:
            Trigger type: 'EDGE', 'SLEW', 'GLIT', 'INTV', 'RUNT', 'PATTERN', etc.
        """
        response = self._scope.query("TRIG_SELECT?")
        # Response format: "EDGE,SR,C1,..."
        parts = response.split(",")
        if len(parts) >= 1:
            return parts[0].strip()
        return "EDGE"

    @trigger_type.setter
    def trigger_type(self, trig_type: TriggerTypeType) -> None:
        """Set trigger type.

        Args:
            trig_type: Type - 'EDGE', 'SLEW', 'GLIT', 'INTV', 'RUNT', 'PATTERN'
        """
        trig_type = trig_type.upper()
        valid_types = ["EDGE", "SLEW", "GLIT", "INTV", "RUNT", "PATTERN"]

        if trig_type not in valid_types:
            raise exceptions.InvalidParameterError(f"Invalid trigger type: {trig_type}. Must be one of {valid_types}.")

        # Get current source to preserve it
        current_source = self.source

        # Set trigger with new type
        self._scope.write(f"TRIG_SELECT {trig_type},SR,{current_source}")
        logger.info(f"Trigger type set to {trig_type}")

    def set_edge_trigger(self, source: str = "C1", slope: str = "POS") -> None:
        """Configure edge trigger.

        Args:
            source: Trigger source channel (default: 'C1')
            slope: Trigger slope - 'POS' (rising), 'NEG' (falling) (default: 'POS')
        """
        source = source.upper()
        slope = slope.upper()

        self._scope.write(f"TRIG_SELECT EDGE,SR,{source}")
        self.slope = slope
        logger.info(f"Edge trigger configured: source={source}, slope={slope}")

    @property
    def level(self) -> float:
        """Get trigger level voltage.

        Returns:
            Trigger level in volts
        """
        # Get current source
        source = self.source
        if source.startswith("C"):
            # Channel trigger - query channel trigger level
            response = self._scope.query(f"{source}:TRLV?")
            # Response may include echo like "C1:TRLV 0.0E+00V"
            if ":" in response:
                response = response.split(":", 1)[1]
            if " " in response:
                response = response.split(" ", 1)[1]
            value = response.replace("V", "").strip()
            return float(value)
        return 0.0

    @level.setter
    def level(self, voltage: float) -> None:
        """Set trigger level voltage.

        Args:
            voltage: Trigger level in volts
        """
        # Set for current source
        source = self.source
        if source.startswith("C"):
            self._scope.write(f"{source}:TRLV {voltage}")
            logger.info(f"Trigger level set to {voltage}V on {source}")
        else:
            logger.warning(f"Cannot set trigger level for source {source}")

    def set_level(self, channel: Union[int, str], voltage: float) -> None:
        """Convenience wrapper to set trigger level for a specific channel."""
        self.source = channel
        self.level = voltage

    @property
    def slope(self) -> str:
        """Get trigger slope.

        Returns:
            Trigger slope: 'POS', 'NEG', or 'WINDOW'
        """
        response = self._scope.query("TRIG_SLOPE?")
        return response.strip().upper()

    @slope.setter
    def slope(self, slope: TriggerSlopeType) -> None:
        """Set trigger slope.

        Args:
            slope: 'POS' (rising edge), 'NEG' (falling edge), 'WINDOW' (either)
        """
        slope = slope.upper()
        if slope not in ["POS", "NEG", "WINDOW"]:
            raise exceptions.InvalidParameterError(f"Invalid trigger slope: {slope}. Must be POS, NEG, or WINDOW.")

        self._scope.write(f"TRIG_SLOPE {slope}")
        logger.info(f"Trigger slope set to {slope}")

    def set_slope(self, slope: TriggerSlopeType) -> None:
        """Convenience wrapper to set trigger slope."""
        self.slope = slope

    @property
    def coupling(self) -> str:
        """Get trigger coupling.

        Returns:
            Coupling: 'DC', 'AC', 'HFREJ', 'LFREJ'
        """
        response = self._scope.query("TRIG_COUPLING?")
        return response.strip().upper()

    @coupling.setter
    def coupling(self, coupling: TriggerCouplingType) -> None:
        """Set trigger coupling.

        Args:
            coupling: 'DC', 'AC', 'HFREJ' (high freq reject), 'LFREJ' (low freq reject)
        """
        coupling = coupling.upper()
        if coupling not in ["DC", "AC", "HFREJ", "LFREJ"]:
            raise exceptions.InvalidParameterError(f"Invalid trigger coupling: {coupling}. Must be DC, AC, HFREJ, or LFREJ.")

        self._scope.write(f"TRIG_COUPLING {coupling}")
        logger.info(f"Trigger coupling set to {coupling}")

    @property
    def holdoff(self) -> float:
        """Get trigger holdoff time.

        Returns:
            Holdoff time in seconds
        """
        response = self._scope.query("TRIG_DELAY?")
        # Response may include echo like "TRIG_DELAY 0.0E+00S"
        if " " in response:
            response = response.split(" ", 1)[1]
        value = response.replace("S", "").strip()
        return float(value)

    @holdoff.setter
    def holdoff(self, time_seconds: float) -> None:
        """Set trigger holdoff time.

        Args:
            time_seconds: Holdoff time in seconds
        """
        if time_seconds < 0:
            raise exceptions.InvalidParameterError(f"Holdoff time must be non-negative: {time_seconds}")

        self._scope.write(f"TRIG_DELAY {time_seconds}")
        logger.info(f"Trigger holdoff set to {time_seconds}s")

    def get_configuration(self) -> dict:
        """Get all trigger configuration parameters.

        Returns:
            Dictionary with all trigger settings
        """
        return {
            "mode": self.mode,
            "type": self.trigger_type,
            "source": self.source,
            "level": self.level,
            "slope": self.slope,
            "coupling": self.coupling,
            "holdoff": self.holdoff,
        }

    def __repr__(self) -> str:
        """String representation."""
        try:
            config = self.get_configuration()
            return f"Trigger(mode={config['mode']}, source={config['source']}, " f"level={config['level']}V, slope={config['slope']})"
        except Exception:
            return "Trigger()"
