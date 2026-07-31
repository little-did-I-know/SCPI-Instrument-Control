"""Trigger configuration and control for Siglent oscilloscopes."""

import logging
from typing import TYPE_CHECKING, Literal, Optional, Union

from scpi_control import exceptions
from scpi_control.scpi_commands import (
    channel_token,
    is_flat_trigger,
    mode_from_wire,
    mode_to_wire,
    normalize_status,
    slope_from_wire,
    slope_to_wire,
    source_from_wire,
    trigger_type_from_wire,
    trigger_type_to_wire,
)

if TYPE_CHECKING:
    from scpi_control.oscilloscope import Oscilloscope

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
    def _dialect(self) -> str:
        """Wire dialect of the parent scope; defaults to legacy before connect."""
        return getattr(self._scope, "dialect", None) or "legacy"

    def _cmd(self, name: str, **kwargs) -> str:
        return self._scope._get_command(name, **kwargs)

    @staticmethod
    def _parse_float_response(response: str) -> float:
        """Parse a numeric response, tolerating echoes and a V unit suffix."""
        token = response.strip().split()[-1] if response.strip() else ""
        return float(token.replace("V", "").replace("v", ""))

    @property
    def mode(self) -> str:
        """Get trigger mode.

        Returns:
            Trigger mode: 'AUTO', 'NORM', 'SINGLE', or 'STOP'
        """
        if not is_flat_trigger(self._dialect):
            # Global-style dialects (modern, tektronix) have no STOP mode
            # token; a stopped scope is detected via the acquisition status
            # (guide p.483 / TBS p.162, MSO2 p.2-686)
            status = normalize_status(self._scope.query(self._cmd("get_acq_status")))
            if status == "STOP":
                return "STOP"
        response = self._scope.query(self._cmd("get_trigger_mode"))
        return mode_from_wire(self._dialect, response)

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

        if mode == "STOP":
            self._scope.write(self._cmd("stop"))
        elif self._dialect == "tektronix" and mode == "SINGLE":
            # Single-shot is a stop-after sequence, not a trigger mode (Tek PM)
            self._scope.write(self._cmd("set_stop_after", mode="SEQuence"))
            self._scope.write(self._cmd("run"))
        else:
            if self._dialect == "tektronix":
                self._scope.write(self._cmd("set_stop_after", mode="RUNSTop"))
            self._scope.write(self._cmd("set_trigger_mode", mode=mode_to_wire(self._dialect, mode)))
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
        self._scope.write(self._cmd("force_trigger"))
        logger.info("Trigger forced")

    @property
    def source(self) -> str:
        """Get trigger source channel.

        Returns:
            Trigger source (e.g., 'C1', 'C2', 'C3', 'C4', 'EX', 'EX5', 'LINE')
        """
        if not is_flat_trigger(self._dialect):
            return source_from_wire(self._dialect, self._scope.query(self._cmd("get_trigger_source")).strip())
        response = self._scope.query(self._cmd("get_trigger_select"))
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

        if not is_flat_trigger(self._dialect):
            self._scope.write(self._cmd("set_trigger_source", src=channel_token(self._dialect, channel)))
        else:
            # Get current trigger type to preserve it. self.trigger_type now
            # yields a PUBLIC token, so it needs converting back to a wire
            # token before going out on the wire (identity for legacy/lecroy
            # today, but keeps the frames straight).
            current_type = self.trigger_type
            wire_type = trigger_type_to_wire(self._dialect, current_type)
            self._scope.write(self._cmd("set_trigger_select", type=wire_type, src=channel))
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
        if not is_flat_trigger(self._dialect):
            response = self._scope.query(self._cmd("get_trigger_type")).strip()
            return trigger_type_from_wire(self._dialect, response)
        response = self._scope.query(self._cmd("get_trigger_select"))
        # Response format: "EDGE,SR,C1,..."
        parts = response.split(",")
        if len(parts) >= 1 and parts[0].strip():
            return trigger_type_from_wire(self._dialect, parts[0])
        return "EDGE"

    @trigger_type.setter
    def trigger_type(self, trig_type: TriggerTypeType) -> None:
        """Set trigger type.

        Args:
            trig_type: Type - 'EDGE', 'SLEW', 'GLIT', 'INTV', 'RUNT', 'PATTERN'

        Raises:
            ValueError: If trig_type is not in the public vocabulary
            FeatureNotSupportedError: If this dialect cannot express it
        """
        wire = trigger_type_to_wire(self._dialect, trig_type)
        if not is_flat_trigger(self._dialect):
            self._scope.write(self._cmd("set_trigger_type", type=wire))
        else:
            current_source = self.source
            self._scope.write(self._cmd("set_trigger_select", type=wire, src=current_source))
        logger.info(f"Trigger type set to {trig_type}")

    def set_edge_trigger(self, source: str = "C1", slope: str = "POS") -> None:
        """Configure edge trigger.

        Args:
            source: Trigger source channel (default: 'C1')
            slope: Trigger slope - 'POS' (rising), 'NEG' (falling) (default: 'POS')
        """
        source = source.upper()
        if not is_flat_trigger(self._dialect):
            self._scope.write(self._cmd("set_trigger_type", type="EDGE"))
            self._scope.write(self._cmd("set_trigger_source", src=channel_token(self._dialect, source)))
        else:
            self._scope.write(self._cmd("set_trigger_select", type="EDGE", src=source))
        self.slope = slope
        logger.info(f"Edge trigger configured: source={source}, slope={slope}")

    @property
    def level(self) -> float:
        """Get trigger level voltage.

        Returns:
            Trigger level in volts
        """
        if not is_flat_trigger(self._dialect):
            if self._dialect == "tektronix":
                source = self.source  # public token like "C3"
                if not source.startswith("C") or not source[1:].isdigit():
                    logger.warning(f"Cannot get trigger level for source {source}")
                    return 0.0
                return self._parse_float_response(self._scope.query(self._cmd("get_trigger_level", ch=int(source[1:]))))
            return self._parse_float_response(self._scope.query(self._cmd("get_trigger_level")))
        source = self.source
        if source.startswith("C"):
            return self._parse_float_response(self._scope.query(self._cmd("get_trigger_level", src=source)))
        return 0.0

    @level.setter
    def level(self, voltage: float) -> None:
        """Set trigger level voltage.

        Args:
            voltage: Trigger level in volts
        """
        if not is_flat_trigger(self._dialect):
            if self._dialect == "tektronix":
                source = self.source  # public token like "C3"
                if not source.startswith("C") or not source[1:].isdigit():
                    logger.warning(f"Cannot set trigger level for source {source}")
                    return
                self._scope.write(self._cmd("set_trigger_level", ch=int(source[1:]), level=voltage))
            else:
                self._scope.write(self._cmd("set_trigger_level", level=voltage))
            logger.info(f"Trigger level set to {voltage}V")
            return
        source = self.source
        if source.startswith("C"):
            self._scope.write(self._cmd("set_trigger_level", src=source, level=voltage))
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
        if not is_flat_trigger(self._dialect):
            return slope_from_wire(self._dialect, self._scope.query(self._cmd("get_trigger_slope")))
        source = self.source
        return slope_from_wire(self._dialect, self._scope.query(self._cmd("get_trigger_slope", src=source)))

    @slope.setter
    def slope(self, slope: TriggerSlopeType) -> None:
        """Set trigger slope.

        Args:
            slope: 'POS' (rising edge), 'NEG' (falling edge), 'WINDOW' (either)
        """
        # NOTE: WINDOW maps to the modern ALTernate slope, which triggers on
        # alternating edges rather than either edge - approximate parity only
        wire = slope_to_wire(self._dialect, slope)
        if not is_flat_trigger(self._dialect):
            self._scope.write(self._cmd("set_trigger_slope", slope=wire))
        else:
            source = self.source
            self._scope.write(self._cmd("set_trigger_slope", src=source, slope=wire))
        logger.info(f"Trigger slope set to {slope.upper()}")

    def set_slope(self, slope: TriggerSlopeType) -> None:
        """Convenience wrapper to set trigger slope."""
        self.slope = slope

    @property
    def coupling(self) -> str:
        """Get trigger coupling.

        Returns:
            Coupling: 'DC', 'AC', 'HFREJ', 'LFREJ'
        """
        if not is_flat_trigger(self._dialect):
            token = self._scope.query(self._cmd("get_trigger_coupling")).strip().upper()
            if self._dialect == "modern":
                # Reverse of the setter's HFREJ->HFREJect mapping (guide p.486)
                return {"HFREJECT": "HFREJ", "LFREJECT": "LFREJ"}.get(token, token)
            # tektronix wire tokens (HFRej/LFRej) already match the public
            # vocabulary uppercased -- TBS p.151 / MSO2 p.2-661
            return token
        source = self.source
        return self._scope.query(self._cmd("get_trigger_coupling", src=source)).strip().split()[-1].upper()

    @coupling.setter
    def coupling(self, coupling: TriggerCouplingType) -> None:
        """Set trigger coupling.

        Args:
            coupling: 'DC', 'AC', 'HFREJ' (high freq reject), 'LFREJ' (low freq reject)
        """
        coupling = coupling.upper()
        if coupling not in ["DC", "AC", "HFREJ", "LFREJ"]:
            raise exceptions.InvalidParameterError(f"Invalid trigger coupling: {coupling}. Must be DC, AC, HFREJ, or LFREJ.")

        if not is_flat_trigger(self._dialect):
            if self._dialect == "modern":
                # Modern wire tokens spell out the reject modes (guide p.486)
                wire = {"HFREJ": "HFREJect", "LFREJ": "LFREJect"}.get(coupling, coupling)
            else:
                # tektronix wire tokens: DC|HFRej|LFRej|NOISErej -- TBS p.151 / MSO2 p.2-661
                wire = {"HFREJ": "HFRej", "LFREJ": "LFRej"}.get(coupling, coupling)
            self._scope.write(self._cmd("set_trigger_coupling", coupling=wire))
        else:
            source = self.source
            self._scope.write(self._cmd("set_trigger_coupling", src=source, coupling=coupling))
        logger.info(f"Trigger coupling set to {coupling}")

    # NOTE: TRIG_DELAY is legacy-only and actually controls trigger delay, not holdoff (AUDIT M4); routing deferred to a trigger-rework follow-up.
    @property
    def holdoff(self) -> float:
        """Get trigger holdoff time.

        Returns:
            Holdoff time in seconds
        """
        if not self._scope._has_command("get_trigger_holdoff"):
            raise exceptions.FeatureNotSupportedError(f"trigger holdoff is not supported on the {self._dialect} dialect")
        response = self._scope.query(self._cmd("get_trigger_holdoff"))
        # Response may include echo like "TRIG_DELAY 0.0E+00S"
        if " " in response:
            response = response.split(" ", 1)[1]
        return float(response.replace("S", "").strip())

    @holdoff.setter
    def holdoff(self, time_seconds: float) -> None:
        """Set trigger holdoff time.

        Args:
            time_seconds: Holdoff time in seconds
        """
        if time_seconds < 0:
            raise exceptions.InvalidParameterError(f"Holdoff time must be non-negative: {time_seconds}")
        if not self._scope._has_command("set_trigger_holdoff"):
            raise exceptions.FeatureNotSupportedError(f"trigger holdoff is not supported on the {self._dialect} dialect")
        self._scope.write(self._cmd("set_trigger_holdoff", t=time_seconds))
        logger.info(f"Trigger holdoff set to {time_seconds}s")

    def get_configuration(self) -> dict:
        """Get all trigger configuration parameters.

        Returns:
            Dictionary with all trigger settings
        """
        config = {
            "mode": self.mode,
            "type": self.trigger_type,
            "source": self.source,
            "level": self.level,
            "slope": self.slope,
            "coupling": self.coupling,
        }
        try:
            config["holdoff"] = self.holdoff
        except exceptions.FeatureNotSupportedError:
            config["holdoff"] = None
        return config

    def __repr__(self) -> str:
        """String representation."""
        try:
            config = self.get_configuration()
            return f"Trigger(mode={config['mode']}, source={config['source']}, " f"level={config['level']}V, slope={config['slope']})"
        except Exception:
            return "Trigger()"
