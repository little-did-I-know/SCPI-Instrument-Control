"""Function generator output channel control and configuration.

Represents a single AWG output channel with waveform, frequency, amplitude, and offset control.
"""

import logging
import re
from typing import TYPE_CHECKING, Dict, Literal

from scpi_control import exceptions
from scpi_control.awg_scpi_commands import parse_key_value_response

if TYPE_CHECKING:
    from scpi_control.function_generator import FunctionGenerator
    from scpi_control.awg_models import ChannelSpec

logger = logging.getLogger(__name__)

# Type aliases for waveform functions
WaveformType = Literal["SINE", "SQUARE", "RAMP", "PULSE", "NOISE", "ARB", "DC"]


class AWGOutput:
    """Represents a single function generator output channel.

    Provides methods to configure output settings including waveform type,
    frequency, amplitude, offset, phase, and output enable/disable.
    """

    def __init__(self, awg: "FunctionGenerator", spec: "ChannelSpec"):
        """Initialize function generator output channel.

        Args:
            awg: Parent FunctionGenerator instance
            spec: ChannelSpec with frequency/amplitude limits for this channel
        """
        self._awg = awg
        self._spec = spec
        self._channel_num = spec.channel_num

        if not 1 <= self._channel_num <= 4:
            raise exceptions.InvalidParameterError(f"Invalid channel number: {self._channel_num}. Must be 1-4.")

    # --- Waveform Function Control ---

    @property
    def function(self) -> str:
        """Get current waveform function.

        Returns:
            Waveform type: 'SINE', 'SQUARE', 'RAMP', 'PULSE', 'NOISE', 'ARB', 'DC'
        """
        return self._parse_string(self._read_basic_wave("WVTP")).upper()

    @function.setter
    def function(self, waveform: WaveformType) -> None:
        """Set waveform function.

        Args:
            waveform: Waveform type ('SINE', 'SQUARE', 'RAMP', 'PULSE', etc.)

        Raises:
            InvalidParameterError: If waveform type is invalid
        """
        valid_waveforms = ["SINE", "SQUARE", "RAMP", "PULSE", "NOISE", "ARB", "DC"]
        waveform_upper = waveform.upper()

        if waveform_upper not in valid_waveforms:
            raise exceptions.InvalidParameterError(f"Invalid waveform: {waveform}. Must be one of {valid_waveforms}")

        cmd = self._awg._get_command("set_function", ch=self._channel_num, function=waveform_upper)
        self._awg.write(cmd)
        logger.info(f"Channel {self._channel_num} waveform set to {waveform_upper}")

    def set_function(self, waveform: WaveformType) -> None:
        """Set waveform function (alias for function setter).

        Args:
            waveform: Waveform type
        """
        self.function = waveform

    # --- Frequency Control ---

    @property
    def frequency(self) -> float:
        """Get frequency in Hz.

        Returns:
            Frequency in Hz
        """
        return self._parse_float(self._read_basic_wave("FRQ"))

    @frequency.setter
    def frequency(self, freq_hz: float) -> None:
        """Set frequency in Hz.

        Args:
            freq_hz: Frequency in Hz

        Raises:
            InvalidParameterError: If frequency exceeds maximum for this channel
        """
        if not 0 < freq_hz <= self._spec.max_frequency:
            raise exceptions.InvalidParameterError(f"Frequency {freq_hz}Hz exceeds maximum {self._spec.max_frequency}Hz " f"for channel {self._channel_num}")

        cmd = self._awg._get_command("set_frequency", ch=self._channel_num, frequency=freq_hz)
        self._awg.write(cmd)
        logger.info(f"Channel {self._channel_num} frequency set to {freq_hz}Hz")

    def set_frequency(self, freq_hz: float) -> None:
        """Set frequency (alias for frequency setter).

        Args:
            freq_hz: Frequency in Hz
        """
        self.frequency = freq_hz

    # --- Amplitude Control ---

    @property
    def amplitude(self) -> float:
        """Get amplitude in Vpp (peak-to-peak volts).

        Returns:
            Amplitude in Vpp
        """
        return self._parse_float(self._read_basic_wave("AMP"))

    @amplitude.setter
    def amplitude(self, vpp: float) -> None:
        """Set amplitude in Vpp (peak-to-peak volts).

        Args:
            vpp: Amplitude in Vpp

        Raises:
            InvalidParameterError: If amplitude exceeds limits for this channel
        """
        if not self._spec.min_amplitude <= vpp <= self._spec.max_amplitude:
            raise exceptions.InvalidParameterError(f"Amplitude {vpp}Vpp outside range " f"[{self._spec.min_amplitude}, {self._spec.max_amplitude}]Vpp " f"for channel {self._channel_num}")

        cmd = self._awg._get_command("set_amplitude", ch=self._channel_num, amplitude=vpp)
        self._awg.write(cmd)
        logger.info(f"Channel {self._channel_num} amplitude set to {vpp}Vpp")

    def set_amplitude(self, vpp: float) -> None:
        """Set amplitude (alias for amplitude setter).

        Args:
            vpp: Amplitude in Vpp
        """
        self.amplitude = vpp

    # --- DC Offset Control ---

    @property
    def offset(self) -> float:
        """Get DC offset in volts.

        Returns:
            DC offset in volts
        """
        return self._parse_float(self._read_basic_wave("OFST"))

    @offset.setter
    def offset(self, volts: float) -> None:
        """Set DC offset in volts.

        Args:
            volts: DC offset in volts

        Raises:
            InvalidParameterError: If offset exceeds limits for this channel
        """
        if abs(volts) > self._spec.max_offset:
            raise exceptions.InvalidParameterError(f"Offset {volts}V exceeds maximum {self._spec.max_offset}V " f"for channel {self._channel_num}")

        cmd = self._awg._get_command("set_offset", ch=self._channel_num, offset=volts)
        self._awg.write(cmd)
        logger.info(f"Channel {self._channel_num} offset set to {volts}V")

    def set_offset(self, volts: float) -> None:
        """Set DC offset (alias for offset setter).

        Args:
            volts: DC offset in volts
        """
        self.offset = volts

    # --- Phase Control ---

    @property
    def phase(self) -> float:
        """Get phase in degrees.

        Returns:
            Phase in degrees (0-360)
        """
        return self._parse_float(self._read_basic_wave("PHSE"))

    @phase.setter
    def phase(self, degrees: float) -> None:
        """Set phase in degrees.

        Args:
            degrees: Phase in degrees (0-360)

        Raises:
            InvalidParameterError: If phase is outside valid range
        """
        if not 0 <= degrees <= 360:
            raise exceptions.InvalidParameterError(f"Phase {degrees} degrees must be between 0 and 360")

        cmd = self._awg._get_command("set_phase", ch=self._channel_num, phase=degrees)
        self._awg.write(cmd)
        logger.info(f"Channel {self._channel_num} phase set to {degrees} degrees")

    def set_phase(self, degrees: float) -> None:
        """Set phase (alias for phase setter).

        Args:
            degrees: Phase in degrees
        """
        self.phase = degrees

    # --- Output Enable/Disable ---

    @property
    def enabled(self) -> bool:
        """Get output enable state.

        Returns:
            True if output is enabled, False otherwise
        """
        cmd = self._awg._get_command("get_output", ch=self._channel_num)
        response = self._awg.query(cmd)

        if self._awg._scpi_commands.variant != "siglent_sdg":
            # Generic SCPI-99 OUTP{ch}? answers a bare "ON"/"OFF", possibly
            # with an echo prefix.
            return "ON" in response.upper()

        # PG02-E05B p.27-28: QUERY SYNTAX "<channel>:OUTPut?" is bare and its
        # RESPONSE FORMAT always returns "ON|OFF,LOAD,<load>,PLRT,<polarity>"
        # together -- not just the bare state (H5, fixed Task 10).
        return parse_key_value_response(response)["STATE"] == "ON"

    @enabled.setter
    def enabled(self, state: bool) -> None:
        """Set output enable state.

        Args:
            state: True to enable output, False to disable
        """
        state_str = "ON" if state else "OFF"
        cmd = self._awg._get_command("set_output", ch=self._channel_num, state=state_str)
        self._awg.write(cmd)
        logger.info(f"Channel {self._channel_num} {'enabled' if state else 'disabled'}")

    def enable(self) -> None:
        """Enable output (turn on)."""
        self.enabled = True

    def disable(self) -> None:
        """Disable output (turn off)."""
        self.enabled = False

    # --- Pulse Waveform Specific Parameters ---

    @property
    def pulse_duty_cycle(self) -> float:
        """Get pulse duty cycle as percentage (0-100).

        Returns:
            Duty cycle as percentage

        Raises:
            NotImplementedError: If current waveform is not PULSE
        """
        if self.function != "PULSE":
            logger.warning("Duty cycle only applicable to PULSE waveform, " f"current: {self.function}")

        return self._parse_float(self._read_basic_wave("DUTY"))

    @pulse_duty_cycle.setter
    def pulse_duty_cycle(self, percent: float) -> None:
        """Set pulse duty cycle as percentage (0-100).

        Args:
            percent: Duty cycle as percentage (0-100)

        Raises:
            InvalidParameterError: If duty cycle is outside valid range
        """
        if not 0 < percent < 100:
            raise exceptions.InvalidParameterError(f"Duty cycle {percent}% must be between 0 and 100")

        cmd = self._awg._get_command("set_pulse_duty", ch=self._channel_num, duty=percent)
        self._awg.write(cmd)
        logger.info(f"Channel {self._channel_num} duty cycle set to {percent}%")

    # --- Ramp Waveform Specific Parameters ---

    @property
    def ramp_symmetry(self) -> float:
        """Get ramp symmetry as percentage (0-100).

        Returns:
            Symmetry as percentage (0=sawtooth down, 50=triangle, 100=sawtooth up)

        Raises:
            NotImplementedError: If current waveform is not RAMP
        """
        if self.function != "RAMP":
            logger.warning("Symmetry only applicable to RAMP waveform, " f"current: {self.function}")

        return self._parse_float(self._read_basic_wave("SYM"))

    @ramp_symmetry.setter
    def ramp_symmetry(self, percent: float) -> None:
        """Set ramp symmetry as percentage (0-100).

        Args:
            percent: Symmetry (0=sawtooth down, 50=triangle, 100=sawtooth up)

        Raises:
            InvalidParameterError: If symmetry is outside valid range
        """
        if not 0 <= percent <= 100:
            raise exceptions.InvalidParameterError(f"Symmetry {percent}% must be between 0 and 100")

        cmd = self._awg._get_command("set_ramp_symmetry", ch=self._channel_num, symmetry=percent)
        self._awg.write(cmd)
        logger.info(f"Channel {self._channel_num} symmetry set to {percent}%")

    # --- Convenience Methods ---

    def configure_sine(self, frequency: float, amplitude: float, offset: float = 0.0):
        """Configure sine wave with specified parameters.

        Args:
            frequency: Frequency in Hz
            amplitude: Amplitude in Vpp
            offset: DC offset in volts (default: 0.0)
        """
        self.function = "SINE"
        self.frequency = frequency
        self.amplitude = amplitude
        self.offset = offset
        logger.info(f"Channel {self._channel_num} configured: " f"SINE {frequency}Hz, {amplitude}Vpp, {offset}V offset")

    def configure_square(self, frequency: float, amplitude: float, offset: float = 0.0):
        """Configure square wave with specified parameters.

        Args:
            frequency: Frequency in Hz
            amplitude: Amplitude in Vpp
            offset: DC offset in volts (default: 0.0)
        """
        self.function = "SQUARE"
        self.frequency = frequency
        self.amplitude = amplitude
        self.offset = offset
        logger.info(f"Channel {self._channel_num} configured: " f"SQUARE {frequency}Hz, {amplitude}Vpp, {offset}V offset")

    def configure_pulse(
        self,
        frequency: float,
        amplitude: float,
        duty_cycle: float,
        offset: float = 0.0,
    ):
        """Configure pulse wave with specified parameters.

        Args:
            frequency: Frequency in Hz
            amplitude: Amplitude in Vpp
            duty_cycle: Duty cycle as percentage (0-100)
            offset: DC offset in volts (default: 0.0)
        """
        self.function = "PULSE"
        self.frequency = frequency
        self.amplitude = amplitude
        self.offset = offset
        self.pulse_duty_cycle = duty_cycle
        logger.info(f"Channel {self._channel_num} configured: " f"PULSE {frequency}Hz, {amplitude}Vpp, {duty_cycle}% duty, {offset}V offset")

    def configure_ramp(
        self,
        frequency: float,
        amplitude: float,
        symmetry: float = 50.0,
        offset: float = 0.0,
    ):
        """Configure ramp wave with specified parameters.

        Args:
            frequency: Frequency in Hz
            amplitude: Amplitude in Vpp
            symmetry: Symmetry percentage (0=sawtooth down, 50=triangle, 100=sawtooth up)
            offset: DC offset in volts (default: 0.0)
        """
        self.function = "RAMP"
        self.frequency = frequency
        self.amplitude = amplitude
        self.offset = offset
        self.ramp_symmetry = symmetry
        logger.info(f"Channel {self._channel_num} configured: " f"RAMP {frequency}Hz, {amplitude}Vpp, {symmetry}% symmetry, {offset}V offset")

    # --- Helper Methods ---

    #: Which basic-wave getter renders the query for each documented field.
    #: On the "siglent_sdg" variant every entry here renders the identical
    #: bare "C{ch}:BSWV?" (PG02-E05B p.27-28, p.29-30 for DUTY/SYM) -- the
    #: "C{ch}:BSWV? <FIELD>" selector grammar previously used was invented
    #: (audit H5, fixed Task 10). Generic SCPI-99 variants still send one
    #: distinct per-field query (e.g. "SOUR{ch}:FREQ?"), so the mapping keeps
    #: each field pointed at its own op rather than collapsing them.
    _BASIC_WAVE_FIELD_OPS: Dict[str, str] = {
        "WVTP": "get_function",
        "FRQ": "get_frequency",
        "AMP": "get_amplitude",
        "OFST": "get_offset",
        "PHSE": "get_phase",
        "DUTY": "get_pulse_duty",
        "SYM": "get_ramp_symmetry",
    }

    def _read_basic_wave(self, field: str) -> str:
        """Query the getter for `field` and return its raw value.

        On the "siglent_sdg" variant, QUERY SYNTAX for BSWV is bare (no
        parameter selector) and RESPONSE FORMAT always returns every basic-
        wave parameter as one comma-joined "KEY,value,..." reply
        (PG02-E05B p.27-28; DUTY/SYM are independently documented BSWV
        parameters, p.29-30, folded into the same reply). The response is
        parsed with `parse_key_value_response` and the requested field pulled
        out of the whole list.

        Non-Siglent (generic SCPI-99) variants still send one query per field
        that answers a single bare value (e.g. "SOUR{ch}:FREQ?" -> "1000.0");
        for those the raw response is returned unchanged so callers can keep
        applying `_parse_float`/`_parse_string`'s own echo-stripping to it,
        exactly as before this method existed.

        Units are not stripped here (e.g. "1000HZ", "1V") -- `_parse_float`'s
        existing `re.sub(r"[VvHhZz%]", ...)` already tolerates the documented
        unit suffixes, confirmed against every field used above.

        Args:
            field: Documented parameter key, e.g. "FRQ", "AMP", "OFST", "PHSE".

        Returns:
            The raw value string.

        Raises:
            CommandError: If the instrument's response omits `field` (siglent_sdg only).
        """
        cmd = self._awg._get_command(self._BASIC_WAVE_FIELD_OPS[field], ch=self._channel_num)
        response = self._awg.query(cmd)

        if self._awg._scpi_commands.variant != "siglent_sdg":
            return response

        fields = parse_key_value_response(response)
        if field not in fields:
            raise exceptions.CommandError(f"SDG response has no {field} field: {fields!r}")
        return fields[field]

    def _parse_float(self, response: str) -> float:
        """Parse float value from SCPI response.

        Handles various response formats:
        - "1000.0" -> 1000.0
        - "C1:BSWV FRQ,1000.0" -> 1000.0
        - "1.000E+03" -> 1000.0

        Args:
            response: SCPI response string

        Returns:
            Parsed float value
        """
        # Remove echo prefix if present
        if ":" in response:
            response = response.split(":", 1)[1]

        # Handle comma-separated response (Siglent format)
        if "," in response:
            response = response.split(",", 1)[1]

        # Remove common units
        response = re.sub(r"[VvHhZz%]", "", response).strip()

        try:
            return float(response)
        except ValueError as exc:
            raise exceptions.CommandError(f"Unparseable AWG response: {response!r}") from exc

    def _parse_string(self, response: str) -> str:
        """Parse string value from SCPI response.

        Args:
            response: SCPI response string

        Returns:
            Parsed string value
        """
        # Remove echo prefix if present
        if ":" in response:
            response = response.split(":", 1)[1]

        # Handle comma-separated response (Siglent format)
        if "," in response:
            response = response.split(",", 1)[1]

        return response.strip()

    def get_configuration(self) -> Dict[str, any]:
        """Get all channel configuration parameters.

        Returns:
            Dictionary with all channel settings
        """
        config = {
            "channel": self._channel_num,
            "enabled": self.enabled,
            "function": self.function,
            "frequency": self.frequency,
            "amplitude": self.amplitude,
            "offset": self.offset,
            "phase": self.phase,
            "max_frequency": self._spec.max_frequency,
            "max_amplitude": self._spec.max_amplitude,
        }

        # Add waveform-specific parameters if applicable
        try:
            if self.function == "PULSE":
                config["duty_cycle"] = self.pulse_duty_cycle
            elif self.function == "RAMP":
                config["symmetry"] = self.ramp_symmetry
        except Exception as e:
            logger.warning(f"Failed to get waveform-specific parameters: {e}")

        return config

    def __repr__(self) -> str:
        """String representation."""
        try:
            config = self.get_configuration()
            return f"Ch{self._channel_num}(" f"enabled={config['enabled']}, " f"{config['function']}, " f"{config['frequency']/1e3:.1f}kHz, " f"{config['amplitude']:.2f}Vpp)"
        except Exception:
            return f"Ch{self._channel_num}"
