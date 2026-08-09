"""Channel configuration and control for Siglent oscilloscopes."""

import logging
from typing import TYPE_CHECKING, Optional, Union

from scpi_control import exceptions
from scpi_control.models import validate_channel
from scpi_control.scpi_commands import coupling_from_wire, coupling_to_wire, probe_from_wire, probe_to_wire
from scpi_control.vocabulary import BandwidthLimit, BandwidthLimitType, Coupling, CouplingType, normalize_token  # noqa: F401 -- re-exported for back-compat

if TYPE_CHECKING:
    from scpi_control.oscilloscope import Oscilloscope

logger = logging.getLogger(__name__)


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

        validate_channel(oscilloscope, channel_number)

    @property
    def _dialect(self) -> str:
        return getattr(self._scope, "dialect", None) or "legacy"

    def _cmd(self, name: str, **kwargs) -> str:
        return self._scope._get_command(name, **kwargs)

    @property
    def enabled(self) -> bool:
        """Get channel display state.

        Returns:
            True if channel is displayed, False otherwise
        """
        response = self._scope.query(self._cmd("get_channel_display", ch=self._channel))
        # Response format: "C1:TRA ON"/"C1:TRA OFF" (legacy/modern) or a bare
        # "1"/"0" numeric select (tektronix SELect:CH<x>? -- TBS p.144)
        token = response.strip().split()[-1].upper() if response.strip() else ""
        return token in ("ON", "1")

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Set channel display state.

        Args:
            value: True to display channel, False to hide
        """
        state = "ON" if value else "OFF"
        self._scope.write(self._cmd("set_channel_display", ch=self._channel, state=state))
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
        return coupling_from_wire(self._dialect, self._scope.query(self._cmd("get_coupling", ch=self._channel)))

    @coupling.setter
    def coupling(self, mode: Union[Coupling, CouplingType]) -> None:
        """Set channel coupling mode.

        Args:
            mode: Coupling mode - 'DC', 'AC', or 'GND'
        """
        wire = coupling_to_wire(self._dialect, mode)  # validates: InvalidParameterError / FeatureNotSupportedError
        self._scope.write(self._cmd("set_coupling", ch=self._channel, coupling=wire))
        # getattr-unwrap: str() of a (str, Enum) member is "Coupling.DC" on Py<3.12
        logger.info(f"Channel {self._channel} coupling set to {str(getattr(mode, 'value', mode)).upper()}")

    @property
    def voltage_scale(self) -> float:
        """Get vertical scale (volts/division).

        Returns:
            Voltage scale in volts/division
        """
        response = self._scope.query(self._cmd("get_voltage_div", ch=self._channel))
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
        self._scope.write(self._cmd("set_voltage_div", ch=self._channel, vdiv=volts_per_div))
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
        response = self._scope.query(self._cmd("get_voltage_offset", ch=self._channel))
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
        self._scope.write(self._cmd("set_voltage_offset", ch=self._channel, offset=offset))
        logger.info(f"Channel {self._channel} offset set to {offset} V")

    @property
    def probe_ratio(self) -> float:
        """Get probe attenuation ratio.

        Returns:
            Probe ratio (e.g., 1.0 for 1X, 10.0 for 10X)
        """
        # Probe commands are family-split on Tek (tek_tbs/tek_mso) and absent
        # from the plain base table; gate before querying so a forced-dialect
        # variant fallback raises cleanly instead of a raw KeyError.
        if not self._scope._has_command("get_probe_ratio"):
            raise exceptions.FeatureNotSupportedError(f"probe ratio is not supported on the {self._dialect} dialect")
        response = self._scope.query(self._cmd("get_probe_ratio", ch=self._channel))
        # Response may include echo like "C1:ATTN 10"
        if ":" in response:
            response = response.split(":", 1)[1]
        if " " in response:
            response = response.split(" ", 1)[1]
        return probe_from_wire(self._dialect, response.strip())

    @probe_ratio.setter
    def probe_ratio(self, ratio: float) -> None:
        """Set probe attenuation ratio.

        Args:
            ratio: Probe attenuation (1, 10, 100, 1000, etc.)

        Common values: 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000
        """
        if ratio <= 0:
            raise exceptions.InvalidParameterError(f"Probe ratio must be positive: {ratio}")
        if not self._scope._has_command("set_probe_ratio"):
            raise exceptions.FeatureNotSupportedError(f"probe ratio is not supported on the {self._dialect} dialect")
        if self._dialect == "tektronix":
            # Tek speaks probe attenuation as a gain factor (1/ratio); the
            # tek_tbs/tek_mso family templates use the {gain} placeholder
            self._scope.write(self._cmd("set_probe_ratio", ch=self._channel, gain=probe_to_wire(self._dialect, ratio)))
        else:
            self._scope.write(self._cmd("set_probe_ratio", ch=self._channel, ratio=probe_to_wire(self._dialect, ratio)))
        logger.info(f"Channel {self._channel} probe ratio set to {ratio}X")

    @property
    def bandwidth_limit(self) -> str:
        """Get bandwidth limit setting.

        Returns:
            Bandwidth limit: 'ON', 'OFF', or frequency limit
        """
        if self._dialect in ("lecroy", "legacy"):
            # BWL? is global on both dialects: RESPONSE FORMAT is all-channel
            # <channel>,<mode> pairs (RC01020-E01C p.27 legacy: "BWL C1,OFF,
            # C2,ON,..."; MAUI p.7-18 LeCroy: "C1,OFF,C2,20MHZ,..."). Legacy's
            # response echoes the "BWL " header, like every other legacy query
            # in this driver; LeCroy's CHDR OFF connect-time setup suppresses
            # response headers entirely (scpi_commands.py CONNECT_SETUP), so
            # its reply has none -- strip a leading "BWL " only for legacy.
            # The real LeCroy <mode> vocabulary is {OFF,20MHZ,200MHZ,...} --
            # there is no "ON" token, so any non-OFF wire token maps to the
            # public "ON" (mirrors the modern/tektronix ON/OFF normalization
            # below); legacy's own vocabulary is a literal {ON,OFF} that the
            # same rule handles for free.
            raw = self._scope.query(self._cmd("get_bandwidth_limit"))
            if self._dialect == "legacy" and raw.strip().upper().startswith("BWL "):
                raw = raw.strip().split(" ", 1)[1]
            tokens = [t.strip().upper() for t in raw.split(",")]
            try:
                wire = tokens[tokens.index(f"C{self._channel}") + 1]
            except (ValueError, IndexError):
                return "OFF"
            return "OFF" if wire == "OFF" else "ON"
        response = self._scope.query(self._cmd("get_bandwidth_limit", ch=self._channel)).strip().upper()
        if self._dialect in ("modern", "tektronix"):
            # Modern wire tokens are FULL/20M/200M; Tek's are FULl/TWENty (or
            # a hertz value on MSO2) -- both speak ON/OFF at the public layer
            return "OFF" if response == "FULL" else "ON"
        return response

    @bandwidth_limit.setter
    def bandwidth_limit(self, limit: Union[BandwidthLimit, BandwidthLimitType]) -> None:
        """Set bandwidth limit.

        Args:
            limit: 'ON' to enable 20MHz limit, 'OFF' or 'FULL' for full bandwidth
        """
        limit_orig = limit  # preserve original for logging
        limit = normalize_token(limit, parameter="bandwidth limit", valid={"ON", "OFF", "FULL"}, dialect=self._dialect)
        if self._dialect == "modern":
            wire = "FULL" if limit in ("OFF", "FULL") else "20M"
        elif self._dialect == "tektronix":
            if limit in ("OFF", "FULL"):
                wire = "FULL"
            elif getattr(getattr(self._scope, "model_capability", None), "scpi_variant", None) == "tek_mso":
                # MSO 2-Series bandwidth vocabulary is {<NR3>|FULl} -- it has no
                # TWENty keyword, so send 20 MHz as an explicit hertz value
                # (2 Series MSO PM 077-1776-07 p.2-183).
                wire = "20E6"
            else:
                # TBS1000C accepts the TWEnty keyword (TBS PM 077-1691-01 p.53).
                wire = "TWENty"
        elif self._dialect == "lecroy":
            # LeCroy BWL <mode> vocabulary has no "ON" token -- {OFF,20MHZ,
            # 200MHZ,...} (MAUI p.7-18). Map public ON to the 20MHz limit.
            wire = "OFF" if limit in ("OFF", "FULL") else "20MHZ"
        else:
            wire = "OFF" if limit == "FULL" else limit
        self._scope.write(self._cmd("set_bandwidth_limit", ch=self._channel, limit=wire))
        # getattr-unwrap: str() of a (str, Enum) member is "BandwidthLimit.ON" on Py<3.12
        logger.info(f"Channel {self._channel} bandwidth limit set to {str(getattr(limit_orig, 'value', limit_orig)).upper()}")

    @property
    def unit(self) -> str:
        """Get channel vertical unit.

        Returns:
            Unit string (typically 'V' for volts)
        """
        if not self._scope._has_command("get_channel_unit"):
            raise exceptions.FeatureNotSupportedError(f"channel unit is not supported on the {self._dialect} dialect")
        response = self._scope.query(self._cmd("get_channel_unit", ch=self._channel))
        # Real hardware echoes the header (RC01020-E01C p.137: `<channel>: UNIT <type>`);
        # some dialects and older mocks return the bare value. Handle both, as
        # voltage_scale/voltage_offset/probe_ratio do.
        if ":" in response:
            response = response.split(":", 1)[1]
        if " " in response:
            response = response.rsplit(" ", 1)[-1]
        return response.strip()

    @unit.setter
    def unit(self, unit: str) -> None:
        """Set channel vertical unit.

        Args:
            unit: Unit string ('V' for volts, 'A' for amps)
        """
        if not self._scope._has_command("set_channel_unit"):
            raise exceptions.FeatureNotSupportedError(f"channel unit is not supported on the {self._dialect} dialect")
        self._scope.write(self._cmd("set_channel_unit", ch=self._channel, unit=unit))
        logger.info(f"Channel {self._channel} unit set to {unit}")

    def auto_scale(self) -> None:
        """Perform auto-scale for this channel.

        Automatically adjusts voltage scale and offset for optimal viewing.
        """
        # Note: Some Siglent models use ASET for global auto-setup
        # For per-channel auto-scale, we might need to use different commands
        # This is a basic implementation that may need adjustment for SD824x
        logger.info(f"Auto-scaling channel {self._channel}")
        self._scope.write(self._cmd("auto_setup"))

    def get_configuration(self) -> dict:
        """Get all channel configuration parameters.

        Returns:
            Dictionary with all channel settings
        """
        config = {
            "channel": self._channel,
            "enabled": self.enabled,
            "coupling": self.coupling,
            "voltage_scale": self.voltage_scale,
            "voltage_offset": self.voltage_offset,
        }
        try:
            config["probe_ratio"] = self.probe_ratio
        except exceptions.FeatureNotSupportedError:
            config["probe_ratio"] = None
        config["bandwidth_limit"] = self.bandwidth_limit
        try:
            config["unit"] = self.unit
        except exceptions.FeatureNotSupportedError:
            config["unit"] = None
        return config

    def __repr__(self) -> str:
        """String representation."""
        try:
            config = self.get_configuration()
            return f"Channel{self._channel}(enabled={config['enabled']}, " f"scale={config['voltage_scale']}V/div, " f"coupling={config['coupling']})"
        except Exception:
            return f"Channel{self._channel}"
