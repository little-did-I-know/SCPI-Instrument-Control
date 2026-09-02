"""Trigger configuration and control for Siglent oscilloscopes."""

import logging
from typing import TYPE_CHECKING, Optional, Union

from scpi_control import exceptions
from scpi_control.models import ModelCapability
from scpi_control.scpi_commands import (
    _MODE_ALIASES,
    _PUBLIC_TRIGGER_SOURCES,
    channel_token,
    is_flat_trigger,
    mode_from_wire,
    mode_to_wire,
    normalize_status,
    slope_from_wire,
    slope_to_wire,
    source_from_wire,
    supported_trigger_level_sources,
    supported_trigger_modes,
    trigger_coupling_from_wire,
    trigger_coupling_to_wire,
    trigger_type_from_wire,
    trigger_type_to_wire,
)
from scpi_control.vocabulary import (  # noqa: F401 -- re-exported for back-compat
    TriggerCoupling,
    TriggerCouplingType,
    TriggerMode,
    TriggerModeType,
    TriggerSlope,
    TriggerSlopeType,
    TriggerSource,
    TriggerType,
    TriggerTypeType,
    normalize_token,
)

if TYPE_CHECKING:
    from scpi_control.oscilloscope import Oscilloscope

logger = logging.getLogger(__name__)


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
    def mode(self, mode: Union[TriggerMode, TriggerModeType]) -> None:
        """Set trigger mode.

        Args:
            mode: Trigger mode - 'AUTO', 'NORM'/'NORMAL', 'SINGLE', or 'STOP'
        """
        mode = normalize_token(
            mode,
            parameter="trigger mode",
            valid=supported_trigger_modes(self._dialect),
            aliases=_MODE_ALIASES,
            dialect=self._dialect,
        )

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

    def set_mode(self, mode: Union[TriggerMode, TriggerModeType]) -> None:
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
    def source(self, channel: Union[int, str, TriggerSource]) -> None:
        """Set trigger source channel.

        Args:
            channel: Source channel ('C1', 'C2', 'C3', 'C4', 'EX', 'EX5', 'LINE') or channel number

        Warning:
            A scope may silently COERCE this rather than reject it, so a write
            that raises nothing is not proof the source took. For models with
            measured quirks (see ``ModelCapability.unreliable_trigger_sources``
            and ``.warns_on_disabled_trigger_channel``), this setter logs a
            warning before writing. For everything else -- including any
            model nobody has measured yet -- no warning fires, and
            ``scope.trigger.source`` must be read back to confirm what took.

            Measured on an SDS824X HD (modern) 2026-08-04, with no error
            queued in any case:

            - Selecting a channel that is switched OFF lands on ``LINE``. Turn
              the channel on first (``scope.channel2.enable()``).
            - ``EX`` lands on ``LINE`` -- that model has no external trigger
              input, though other modern-dialect scopes do.
            - ``EX5`` never takes: it is a no-op from a channel source, and
              lands on the highest enabled channel from ``LINE``.

            ``scope.capabilities.trigger_sources`` reports what the DRIVER can
            send for the dialect, not what the attached model physically has.
        """
        channel = self._normalize_source(channel)
        channel = normalize_token(channel, parameter="trigger source", valid=_PUBLIC_TRIGGER_SOURCES, dialect=self._dialect)
        self._warn_if_unreliable_source(channel)

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

    def _warn_if_unreliable_source(self, channel: str) -> None:
        """Log a warning if `channel` is known to be silently coerced.

        Guarded by isinstance rather than getattr-with-default: a plain
        Mock() (used throughout tests/dialect_helpers.py) auto-vivifies any
        attribute access, so a missing-attribute default would never trigger
        -- only a real ModelCapability instance carries meaningful flags.
        """
        cap = getattr(self._scope, "model_capability", None)
        if not isinstance(cap, ModelCapability):
            return
        if channel in cap.unreliable_trigger_sources:
            logger.warning(
                f"{cap.model_name} is known to silently not honor trigger source "
                f"{channel!r} (no error is queued). Read scope.trigger.source back "
                f"to confirm what actually took effect."
            )
            return
        if cap.warns_on_disabled_trigger_channel and channel.startswith("C"):
            ch = self._scope.get_channel(int(channel[1:]))
            if ch is not None and not ch.enabled:
                logger.warning(
                    f"{cap.model_name} silently coerces trigger source {channel!r} "
                    f"to LINE while that channel is disabled (no error is queued). "
                    f"Enable the channel first, or read scope.trigger.source back."
                )

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
    def trigger_type(self, trig_type: Union[TriggerType, TriggerTypeType]) -> None:
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
        logger.info(f"Trigger type set to {str(getattr(trig_type, 'value', trig_type)).upper()}")

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

    def _require_level_source(self, source: str) -> str:
        """Raise unless `source` has a documented trigger-level command here.

        A scope can be triggering on a source whose threshold this dialect
        offers no way to read or set (LINE on legacy/lecroy/tektronix, the
        external input on tektronix -- modern gates nothing here). Returning
        a fabricated 0.0 for those, as this used to, makes an unset level
        indistinguishable from a real one.
        """
        if source not in supported_trigger_level_sources(self._dialect):
            raise exceptions.FeatureNotSupportedError(f"Trigger level is not available for source {source} on the {self._dialect} dialect")
        return source

    @property
    def level(self) -> float:
        """Get trigger level voltage.

        Returns:
            Trigger level in volts

        Raises:
            FeatureNotSupportedError: The current trigger source has no
                documented level command on this dialect -- LINE on
                legacy/lecroy/tektronix, and the external input on tektronix
                (no AUX form in the 4/5/6 MSO manual). EX/EX5 are supported
                on legacy/lecroy (RC01020-E01C p.128 / MAUI p.7-33). Modern's
                :TRIGger:EDGE:LEVel (EN11G p.493) takes no source argument,
                so nothing gates there -- LINE included.
        """
        if not is_flat_trigger(self._dialect):
            if self._dialect == "tektronix":
                source = self._require_level_source(self.source)
                return self._parse_float_response(self._scope.query(self._cmd("get_trigger_level", ch=int(source[1:]))))
            return self._parse_float_response(self._scope.query(self._cmd("get_trigger_level")))
        source = self._require_level_source(self.source)
        return self._parse_float_response(self._scope.query(self._cmd("get_trigger_level", src=source)))

    @level.setter
    def level(self, voltage: float) -> None:
        """Set trigger level voltage.

        Args:
            voltage: Trigger level in volts

        Raises:
            FeatureNotSupportedError: The current trigger source has no
                documented level command on this dialect -- LINE on
                legacy/lecroy/tektronix, and the external input on tektronix
                (no AUX form in the 4/5/6 MSO manual). EX/EX5 are supported
                on legacy/lecroy (RC01020-E01C p.128 / MAUI p.7-33). Modern's
                :TRIGger:EDGE:LEVel (EN11G p.493) takes no source argument,
                so nothing gates there -- LINE included. Raised before
                anything is written to the wire.
        """
        if not is_flat_trigger(self._dialect):
            if self._dialect == "tektronix":
                source = self._require_level_source(self.source)
                self._scope.write(self._cmd("set_trigger_level", ch=int(source[1:]), level=voltage))
            else:
                self._scope.write(self._cmd("set_trigger_level", level=voltage))
            logger.info(f"Trigger level set to {voltage}V")
            return
        source = self._require_level_source(self.source)
        self._scope.write(self._cmd("set_trigger_level", src=source, level=voltage))
        logger.info(f"Trigger level set to {voltage}V on {source}")

    def set_level(self, channel: Union[int, str], voltage: float) -> None:
        """Convenience wrapper to set trigger level for a specific channel.

        Note:
            This sets the source and then the level. A source write can be
            silently coerced by the instrument -- selecting a switched-off
            channel or an absent external input lands somewhere else with no
            error queued -- so this is not proof the scope is triggering where
            you asked. See the trigger source documentation.
        """
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
    def slope(self, slope: Union[TriggerSlope, TriggerSlopeType]) -> None:
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
            Coupling: 'DC', 'AC', 'HFREJ', 'LFREJ'. Unmapped instrument states
            (e.g. 'NOISEREJ' set from Tektronix front panel) pass through uppercased
            as read-only; such states cannot be set via this API.
        """
        if not is_flat_trigger(self._dialect):
            return trigger_coupling_from_wire(self._dialect, self._scope.query(self._cmd("get_trigger_coupling")))
        source = self.source
        return trigger_coupling_from_wire(self._dialect, self._scope.query(self._cmd("get_trigger_coupling", src=source)))

    @coupling.setter
    def coupling(self, coupling: Union[TriggerCoupling, TriggerCouplingType]) -> None:
        """Set trigger coupling.

        Args:
            coupling: 'DC', 'AC', 'HFREJ' (high freq reject), 'LFREJ' (low freq reject).
                     Note: Tektronix does not support AC coupling (TBS p.151 / MSO2 p.2-661)
                     and will raise FeatureNotSupportedError if attempted.
        """
        wire = trigger_coupling_to_wire(self._dialect, coupling)
        if not is_flat_trigger(self._dialect):
            self._scope.write(self._cmd("set_trigger_coupling", coupling=wire))
        else:
            source = self.source
            self._scope.write(self._cmd("set_trigger_coupling", src=source, coupling=wire))
        # getattr-unwrap: str() of a (str, Enum) mixin member is "TriggerCoupling.HFREJ", not "HFREJ"
        logger.info(f"Trigger coupling set to {str(getattr(coupling, 'value', coupling)).upper()}")

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
            "slope": self.slope,
            "coupling": self.coupling,
        }
        try:
            config["level"] = self.level
        except exceptions.FeatureNotSupportedError:
            config["level"] = None
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
