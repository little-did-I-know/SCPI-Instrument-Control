"""Mock connection shell: constructor/state, connect/disconnect, PSU/AWG/DAQ handling,
and personality dispatch to the vendor-specific scope write/query/waveform modules."""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING, Callable, Dict, Iterable, List, Optional, Set, Tuple, Union

from scpi_control import exceptions
from scpi_control.connection.base import BaseConnection
from scpi_control.connection.mock.helpers import MOCK_SCREENSHOT_BMP, _build_ieee_block
from scpi_control.connection.mock import lecroy, siglent, tektronix
from scpi_control.models import detect_model_from_idn

if TYPE_CHECKING:
    import numpy as np

    from scpi_control.signal_synth import SignalSpec

_PERSONALITIES = {
    "siglent": siglent,
    "tektronix": tektronix,
    "lecroy": lecroy,
}

# QS0503X-E01B p.40: OUTPut:TRACK's wire argument is NUMERIC ({0|1|2}); this
# maps it back to the INDEPENDENT/SERIES/PARALLEL words psu_tracking_mode
# stores internally, so the OUTP:TRACK? handler (still a documented-mismatch
# query, audit H19) keeps answering the same shape it always has.
_TRACKING_NUMERIC_TO_WORD = {"0": "INDEPENDENT", "1": "SERIES", "2": "PARALLEL"}


class MockConnection(BaseConnection):
    """Mock connection that returns deterministic SCPI responses.

    The mock is designed for offline tests that want to exercise the full
    oscilloscope/automation stack without touching networked hardware. It keeps
    lightweight internal state for common SCPI queries and waveforms. Waveform
    bytes are state-coupled synthesis by default (see connection/mock/synth.py),
    driven by each channel's SignalSpec (or a built-in default); explicit
    waveform_payloads bytes for a channel always take precedence.
    """

    def __init__(
        self,
        host: str = "mock-scope",
        port: int = 0,
        timeout: float = 1.0,
        *,
        idn: str = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0",
        channel_states: Optional[Dict[int, bool]] = None,
        voltage_scales: Optional[Dict[int, float]] = None,
        voltage_offsets: Optional[Dict[int, float]] = None,
        waveform_payloads: Optional[Dict[int, bytes]] = None,
        signals: Optional[Dict[int, Union["SignalSpec", Callable[[], "SignalSpec"]]]] = None,
        sample_rate: float = 1_000.0,
        timebase: float = 1e-3,
        trigger_status: Optional[List[str]] = None,
        custom_responses: Optional[Dict[str, Union[str, List[str]]]] = None,
        # Power supply parameters
        psu_mode: bool = False,
        psu_idn: str = "Siglent Technologies,SPD3303X,SPD123456,1.0",
        psu_outputs: Optional[Dict[int, Dict[str, float]]] = None,
        # Function generator (AWG) parameters
        awg_mode: bool = False,
        awg_idn: str = "Siglent Technologies,SDG1032X,SDG1XXXXX,2.01.01.37R1",
        awg_channels: Optional[Dict[int, Dict[str, any]]] = None,
        # Data acquisition (DAQ) parameters
        daq_mode: bool = False,
        daq_idn: str = "Keysight Technologies,34970A,MY12345678,A.01.02",
        daq_readings: str = "1.234,2.345,3.456",
        tek_badges: Optional[Dict[int, Dict[str, str]]] = None,
        # strict: When True (the default as of v5.0.0), unmatched PSU/AWG/DAQ
        # queries raise TimeoutError instead of returning "", matching real
        # instruments. Pass strict=False to restore the old lenient
        # "return empty string" behavior (the default through 4.1.0).
        strict: bool = True,
    ):
        super().__init__(host, port, timeout)
        channels = channel_states.keys() if channel_states else range(1, 3)

        self.idn = idn
        # Personality: answer only the wire dialect this model actually speaks
        capability = detect_model_from_idn(idn)
        self.scope_dialect = capability.dialect
        self.scope_vendor = capability.vendor
        self._channel_enabled: Dict[int, bool] = {ch: channel_states.get(ch, True) if channel_states else True for ch in channels}
        self._voltage_scales: Dict[int, float] = {ch: voltage_scales.get(ch, 1.0) if voltage_scales else 1.0 for ch in channels}
        self._voltage_offsets: Dict[int, float] = {ch: voltage_offsets.get(ch, 0.0) if voltage_offsets else 0.0 for ch in channels}
        # Explicit payloads only; channels without one get state-coupled synthesis
        # (connection/mock/synth.py). The old fixed 4-byte default is gone.
        self._waveform_payloads: Dict[int, bytes] = dict(waveform_payloads) if waveform_payloads else {}
        self._signals: Dict[int, Union["SignalSpec", Callable[[], "SignalSpec"]]] = dict(signals) if signals else {}
        self._acquisition_counts: Dict[int, int] = {}
        self._channel_coupling: Dict[int, str] = {ch: "D1M" for ch in channels}
        # Legacy scope probe attenuation / bandwidth-limit state (Task 14,
        # audit L3): the GUI's channel refresh reads both on every poll.
        self.probe_ratios: Dict[int, float] = {ch: 1.0 for ch in channels}
        self.bandwidth_limits: Dict[int, str] = {ch: "OFF" for ch in channels}
        # Modern :WAVeform: transfer-parameter state (Task 17, audit H9): the
        # SOURce/STARt/INTerval/POINt scalars set ahead of a
        # :WAVeform:DATA?/:WAVeform:PREamble? transfer (not implemented until
        # Task 18). Defaults match the guide's own enum ("C1" is a valid
        # <source> token) and NR1-zero starting points.
        self.waveform_source: str = "C1"
        self.waveform_start: int = 0
        self.waveform_interval: int = 1
        self.waveform_point: int = 0
        # :WAVeform:WIDTh state (Task 18, audit H9; guide p.754): BYTE is the
        # documented default (COMM_TYPE=0). Drives the PREamble?/DATA?
        # binary responses built in connection/mock/siglent.py.
        self.waveform_width: str = "BYTE"
        # Deep-memory chunking (Task 19, guide p.753 ":WAVeform:MAXPoint?",
        # query-only): max_points is the per-:WAVeform:DATA?-transfer cap a
        # real scope reports. Default is the guide's own worked EXAMPLE value
        # for SDS2000X Plus (10,000,000) -- far larger than any single-shot
        # test's synthesized record (connection/mock/synth.py's MAX_POINTS is
        # 14,000), so unmodified single-shot captures are unaffected.
        # record_length is the FULL logical record backing a capture; None
        # (default) defers to the existing single-shot point-count formula.
        # Tests set it explicitly, larger than max_points, to model a
        # deep-memory record that forces ModernTransfer.acquire to loop
        # :WAVeform:STARt across multiple windows.
        self.max_points: int = 10_000_000
        self.record_length: Optional[int] = None
        # Per-channel cache of the FULL synthesized/explicit code array for a
        # modern-dialect capture (Task 19). Populated once by
        # siglent.build_waveform_preamble so that repeated windowed
        # :WAVeform:DATA? reads slice ONE consistent waveform instead of each
        # independently re-synthesizing -- which would also each advance the
        # acquisition count (free-run drift / RNG reseed) and desync the
        # windows from each other.
        self._modern_waveform_codes: Dict[int, "np.ndarray"] = {}

        self.sample_rate = sample_rate
        self.timebase = timebase
        self.trigger_type = "EDGE"
        self.trigger_source = "C1"
        if self.scope_dialect == "modern":
            # Initial wire tokens must be modern vocabulary (guide p.482, p.494)
            self.trigger_mode = "AUTO"
            self.trigger_slope = "RISing"
        else:
            self.trigger_mode = "STOP"
            self.trigger_slope = "POS"
        self.trigger_coupling = "DC"
        self.trigger_level: Dict[int, float] = {ch: 0.0 for ch in channels}
        self.trigger_status: List[str] = trigger_status[:] if trigger_status else ["Stop"]

        # Modern :MEASure:SIMPle state (guide p.335-373). measure() on the modern
        # dialect sets a source and enables items; per the design decision these
        # are deliberately NOT cleared after a read, mirroring the instrument.
        self.measure_enabled: bool = False
        self.simple_mode: str = "SIMPle"
        self.simple_source: str = "C1"
        self.simple_items: Set[str] = set()

        # Tektronix wire-vocabulary state (shared across tek_tbs/tek_mso variants)
        self.tek_stop_after = "RUNSTOP"
        self.data_source: int = 1
        self.probe_gains: Dict[int, float] = {ch: 0.1 for ch in channels}
        self.holdoff_time = 0.0
        # Measurement badges: slot -> {"type": ..., "source": ...}. Seed via
        # tek_badges to model badges a user created on the instrument.
        self.badges: Dict[int, Dict[str, str]] = {n: dict(cfg) for n, cfg in (tek_badges or {}).items()}
        if self.scope_vendor == "tektronix":
            # Tek vocabulary differs from both Siglent dialects (guide TEKTRONIX_COMMANDS table)
            self.trigger_mode = "AUTO"
            self.trigger_slope = "RISE"
            self.trigger_source = "CH1"
            self._channel_coupling = {ch: "DC" for ch in channels}
            if not trigger_status:
                # "SAVE" is the Tek TRIGger:STATE? token for stopped; the shared
                # default ["Stop"] is Siglent vocabulary and not a valid Tek state.
                self.trigger_status = ["SAVE"]

        self.custom_responses = custom_responses or {}
        # SCPI error queue. Real instruments accept a bad command, ignore it, and
        # queue an error for collection via SYST:ERR?; they do not fail the
        # transport. Empty queue answers '+0,"No error"', which is exactly what
        # the old hardcoded stub returned -- so nothing changes until something
        # actually queues an error.
        self.error_queue: List[Tuple[int, str]] = []
        self.writes: List[str] = []
        self.queries: List[str] = []
        self.timebase_updates: List[float] = []
        self.scale_updates: Dict[int, List[float]] = {ch: [] for ch in channels}
        self.waveform_requests: List[int] = []
        self._last_waveform_channel: Optional[int] = None

        # Power supply mode
        self.psu_mode = psu_mode
        self.psu_idn = psu_idn
        self.psu_outputs: Dict[int, Dict[str, float]] = psu_outputs or {
            1: {"voltage": 0.0, "current": 0.0, "enabled": False},
            2: {"voltage": 0.0, "current": 0.0, "enabled": False},
            3: {"voltage": 0.0, "current": 0.0, "enabled": False},
        }
        # PSU advanced features state
        self.psu_tracking_mode = "INDEPENDENT"
        self.psu_timer_enabled: Dict[int, bool] = {1: False, 2: False, 3: False}
        self.psu_waveform_enabled: Dict[int, bool] = {1: False, 2: False, 3: False}
        self.psu_ovp_levels: Dict[int, float] = {1: 30.0, 2: 30.0, 3: 5.0}
        self.psu_ocp_levels: Dict[int, float] = {1: 3.0, 2: 3.0, 3: 3.0}

        # Function generator (AWG) mode
        self.awg_mode = awg_mode
        self.awg_idn = awg_idn
        self.awg_channels: Dict[int, Dict[str, any]] = awg_channels or {
            1: {
                "function": "SINE",
                "frequency": 1000.0,
                "amplitude": 1.0,
                "offset": 0.0,
                "phase": 0.0,
                "enabled": False,
                "pulse_duty": 50.0,
                "ramp_symmetry": 50.0,
            },
            2: {
                "function": "SINE",
                "frequency": 1000.0,
                "amplitude": 1.0,
                "offset": 0.0,
                "phase": 0.0,
                "enabled": False,
                "pulse_duty": 50.0,
                "ramp_symmetry": 50.0,
            },
        }

        # Data acquisition (DAQ) mode
        self.daq_mode = daq_mode
        self.daq_idn = daq_idn
        self.daq_readings = daq_readings
        self.daq_scan_list = []
        self.daq_trigger_source = "IMM"

        self.strict = strict

    def connect(self) -> None:
        """Mark the connection as established."""
        self._connected = True

    def disconnect(self) -> None:
        """Mark the connection as closed."""
        self._connected = False

    def push_error(self, code: int, message: str) -> None:
        """Queue a SCPI error for later collection via SYST:ERR?."""
        self.error_queue.append((code, message))

    # Broad plausibility bounds. These are deliberately NOT per-model limits --
    # they reject what is wrong for any oscilloscope (non-finite, non-positive,
    # absurd magnitude), which is what catches the failure that actually happens:
    # a typo'd or unit-confused value. Per-model ranges belong in the model
    # registry (models.py already carries max_sample_rate) and can tighten this
    # later without changing any caller.
    _ABSURD_MAGNITUDE = 1e6

    def reject_if_invalid(self, value: float, *, name: str, positive: bool = True, non_negative: bool = False, max_magnitude: Optional[float] = None) -> bool:
        """Queue -222 and return True when `value` is unusable on any instrument.

        Callers skip their assignment when this returns True, so the command is
        accepted by the transport, ignored, and reported on the next SYST:ERR? --
        which is how real hardware behaves for a bad parameter.

        `max_magnitude` overrides `_ABSURD_MAGNITUDE` (default 1e6) for callers
        whose quantity legitimately exceeds it in normal use -- e.g. AWG
        frequency, where registered models go up to 120e6 Hz (awg_models.py)
        and the scope-calibrated 1e6 bound would reject a real value.

        `non_negative=True` rejects a negative value while still accepting zero --
        for callers whose real-driver validation is `>= 0` rather than `> 0`
        (trigger holdoff, AWG phase/ramp symmetry, PSU voltage/current). Pass it
        together with `positive=False` (the default `positive=True` already
        excludes negatives, so `non_negative` would be redundant with it).

        `name` is folded into the queued message (M1: it used to be accepted
        by ~25 call sites and read by nothing, so a caller polling SYST:ERR?
        could tell a parameter was rejected but never which one).
        """
        bound = self._ABSURD_MAGNITUDE if max_magnitude is None else max_magnitude
        if not math.isfinite(value) or (positive and value <= 0) or (non_negative and value < 0) or abs(value) > bound:
            self.push_error(-222, f"Data out of range ({name})")
            return True
        return False

    def _pop_error(self) -> str:
        """The SYST:ERR? response: oldest queued error, or '+0,"No error"'."""
        if self.error_queue:
            code, message = self.error_queue.pop(0)
            return f'{code:+d},"{message}"'
        return '+0,"No error"'

    def write(self, command: str) -> None:
        """Record the command and update simple internal state."""
        if not self._connected:
            raise exceptions.SiglentConnectionError(f"Not connected to oscilloscope at {self.host}:{self.port}")

        command = command.strip()
        self.writes.append(command)

        if command.upper() in ("*CLS", "*RST"):
            # Real instruments clear the error queue on both *CLS and *RST
            # (M7); *RST previously fell through unmatched to a silent no-op,
            # so a caller resetting after an error would still see it queued.
            self.error_queue.clear()
            return

        # Power supply commands
        if self.psu_mode:
            # Voltage setting: CH1:VOLT 5.0 (Siglent) or SOUR1:VOLT 5.0 (generic)
            # I1: the capture used to be `([\d.]+)`, which cannot match a sign,
            # an exponent, or non-finite text -- `CH1:CURR 5e-05` matched only
            # the leading "5" and silently stored 5.0A, a 100000x error with no
            # error queued. `(.+)` (matching the scope handlers' own convention
            # elsewhere in this file) hands the full token to float() so
            # reject_if_invalid actually sees what was sent.
            if match := re.match(r"(?:CH|SOUR)(\d+):VOLT\s+(.+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                voltage = float(match.group(2))
                # A voltage setpoint of 0.0 (output at rest) is legitimate --
                # power_supply_output.py's own validation allows
                # `0 <= volts <= max_voltage` -- so it is gated on non_negative
                # (>= 0) rather than positive (> 0): zero is accepted, a
                # negative setpoint is not (I2).
                if self.reject_if_invalid(voltage, name="VOLT", positive=False, non_negative=True):
                    return
                if ch in self.psu_outputs:
                    self.psu_outputs[ch]["voltage"] = voltage
                return

            # Current setting: CH1:CURR 2.0 (Siglent) or SOUR1:CURR 2.0 (generic)
            if match := re.match(r"(?:CH|SOUR)(\d+):CURR\s+(.+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                current = float(match.group(2))
                # A current limit of 0.0 is legitimate for the same reason as
                # voltage above, so it is gated on non_negative rather than
                # positive (I2).
                if self.reject_if_invalid(current, name="CURR", positive=False, non_negative=True):
                    return
                if ch in self.psu_outputs:
                    self.psu_outputs[ch]["current"] = current
                return

            # Output enable: OUTPut CH1,ON (Siglent) or OUTP1 ON (generic)
            if match := re.match(r"OUTP(?:UT)?\s*(?:CH\s*)?(\d+)[\s,]+(ON|OFF)", command, re.IGNORECASE):
                ch = int(match.group(1))
                enabled = match.group(2).upper() == "ON"
                if ch in self.psu_outputs:
                    self.psu_outputs[ch]["enabled"] = enabled
                return

            # Tracking mode: OUTP:TRACK 1 (QS0503X-E01B p.40: NUMERIC
            # {0|1|2} -- 0=independent, 1=series, 2=parallel). Stored
            # internally as the word so existing readers (psu_tracking_mode,
            # the OUTP:TRACK? handler below) are unaffected.
            if match := re.match(r"OUTP(?:UT)?:TRACK\s+([012])", command, re.IGNORECASE):
                self.psu_tracking_mode = _TRACKING_NUMERIC_TO_WORD[match.group(1)]
                return

            # Timer enable: TIMEr CH1,ON
            if match := re.match(r"TIME(?:R)?\s+CH(\d+),(ON|OFF)", command, re.IGNORECASE):
                ch = int(match.group(1))
                enabled = match.group(2).upper() == "ON"
                self.psu_timer_enabled[ch] = enabled
                return

            # Waveform display enable: OUTPut:WAVE CH1,ON (QS0503X-E01B p.40)
            if match := re.match(r"OUTP(?:UT)?:WAVE\s+CH(\d+),(ON|OFF)", command, re.IGNORECASE):
                ch = int(match.group(1))
                enabled = match.group(2).upper() == "ON"
                self.psu_waveform_enabled[ch] = enabled
                return

            # OVP setting: CH1:VOLT:PROT 25.0 or SOUR1:VOLT:PROT 25.0
            if match := re.match(r"(?:CH|SOUR)(\d+):VOLT:PROT\s+(.+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                level = float(match.group(2))
                # Unlike voltage/current setpoints above, an OVP level of 0V
                # would trip immediately and is not a usable value, so it is
                # gated on positivity.
                if self.reject_if_invalid(level, name="VOLT:PROT"):
                    return
                self.psu_ovp_levels[ch] = level
                return

            # OCP setting: CH1:CURR:PROT 2.5 or SOUR1:CURR:PROT 2.5
            if match := re.match(r"(?:CH|SOUR)(\d+):CURR:PROT\s+(.+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                level = float(match.group(2))
                # Same reasoning as OVP: an OCP level of 0A is not usable, so
                # it is gated on positivity.
                if self.reject_if_invalid(level, name="CURR:PROT"):
                    return
                self.psu_ocp_levels[ch] = level
                return

        # Function generator (AWG) commands
        if self.awg_mode:
            # Waveform function: C1:BSWV WVTP,SINE (Siglent) or SOUR1:FUNC SINE (generic)
            if match := re.match(r"C(\d+):BSWV\s+WVTP,(\w+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                function = match.group(2).upper()
                if ch in self.awg_channels:
                    self.awg_channels[ch]["function"] = function
                return
            if match := re.match(r"SOUR(\d+):FUNC\s+(\w+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                function = match.group(2).upper()
                if ch in self.awg_channels:
                    self.awg_channels[ch]["function"] = function
                return

            # Frequency: C1:BSWV FRQ,1000 (Siglent) or SOUR1:FREQ 1000 (generic)
            # awg_output.py's own validation requires `0 < freq_hz`, so
            # frequency is gated on positivity.
            if match := re.match(r"C(\d+):BSWV\s+FRQ,([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                freq = float(match.group(2))
                # Registered AWG models go up to 120MHz (awg_models.py), well
                # above the scope-calibrated 1e6 default, so this uses a
                # frequency-appropriate bound instead.
                if self.reject_if_invalid(freq, name="FRQ", max_magnitude=1e9):
                    return
                if ch in self.awg_channels:
                    self.awg_channels[ch]["frequency"] = freq
                return
            if match := re.match(r"SOUR(\d+):FREQ\s+([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                freq = float(match.group(2))
                if self.reject_if_invalid(freq, name="FREQ", max_magnitude=1e9):
                    return
                if ch in self.awg_channels:
                    self.awg_channels[ch]["frequency"] = freq
                return

            # Amplitude: C1:BSWV AMP,5.0 (Siglent) or SOUR1:VOLT 5.0 (generic)
            # A 0 or negative Vpp amplitude is not a usable waveform, so it is
            # gated on positivity, same as scope V/div.
            if match := re.match(r"C(\d+):BSWV\s+AMP,([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                amp = float(match.group(2))
                if self.reject_if_invalid(amp, name="AMP"):
                    return
                if ch in self.awg_channels:
                    self.awg_channels[ch]["amplitude"] = amp
                return
            if match := re.match(r"SOUR(\d+):VOLT\s+([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                amp = float(match.group(2))
                if self.reject_if_invalid(amp, name="VOLT"):
                    return
                if ch in self.awg_channels:
                    self.awg_channels[ch]["amplitude"] = amp
                return

            # Offset: C1:BSWV OFST,0.5 (Siglent) or SOUR1:VOLT:OFFS 0.5 (generic)
            # Offset may legitimately be negative or zero (awg_output.py's own
            # validation only checks `abs(volts) > max_offset`, never sign),
            # so it is not gated on positivity.
            if match := re.match(r"C(\d+):BSWV\s+OFST,([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                offset = float(match.group(2))
                if self.reject_if_invalid(offset, name="OFST", positive=False):
                    return
                if ch in self.awg_channels:
                    self.awg_channels[ch]["offset"] = offset
                return
            if match := re.match(r"SOUR(\d+):VOLT:OFFS\s+([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                offset = float(match.group(2))
                if self.reject_if_invalid(offset, name="VOLT:OFFS", positive=False):
                    return
                if ch in self.awg_channels:
                    self.awg_channels[ch]["offset"] = offset
                return

            # Phase: C1:BSWV PHSE,90 (Siglent) or SOUR1:PHAS 90 (generic)
            # Phase 0 is legitimate (awg_output.py's own validation allows
            # `0 <= degrees <= 360`), so it is gated on non_negative (>= 0)
            # rather than positive (> 0) -- a negative phase is not a value
            # the real driver ever allows either (I2). max_magnitude=360: a
            # phase angle never legitimately exceeds 360 degrees, so the
            # generic 1e6 scope-calibrated bound let through nonsense like
            # PHAS 999999 (M5).
            if match := re.match(r"C(\d+):BSWV\s+PHSE,([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                phase = float(match.group(2))
                if self.reject_if_invalid(phase, name="PHSE", positive=False, non_negative=True, max_magnitude=360):
                    return
                if ch in self.awg_channels:
                    self.awg_channels[ch]["phase"] = phase
                return
            if match := re.match(r"SOUR(\d+):PHAS\s+([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                phase = float(match.group(2))
                if self.reject_if_invalid(phase, name="PHAS", positive=False, non_negative=True, max_magnitude=360):
                    return
                if ch in self.awg_channels:
                    self.awg_channels[ch]["phase"] = phase
                return

            # Pulse duty cycle: C1:BSWV DUTY,25 (Siglent) or SOUR1:FUNC:PULS:DCYC 25 (generic)
            # awg_output.py's own validation requires `0 < percent < 100`
            # (strictly exclusive), so duty cycle is gated on positivity --
            # unlike ramp symmetry below, 0% is never allowed either. M5:
            # max_magnitude=100 -- a percentage, unlike frequency, never
            # legitimately exceeds 100 in normal use, so the generic 1e6
            # scope-calibrated bound let through nonsense like DUTY 500000.
            if match := re.match(r"C(\d+):BSWV\s+DUTY,([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                duty = float(match.group(2))
                if self.reject_if_invalid(duty, name="DUTY", max_magnitude=100):
                    return
                if ch in self.awg_channels:
                    self.awg_channels[ch]["pulse_duty"] = duty
                return
            if match := re.match(r"SOUR(\d+):FUNC:PULS:DCYC\s+([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                duty = float(match.group(2))
                if self.reject_if_invalid(duty, name="FUNC:PULS:DCYC", max_magnitude=100):
                    return
                if ch in self.awg_channels:
                    self.awg_channels[ch]["pulse_duty"] = duty
                return

            # Ramp symmetry: C1:BSWV SYM,50 (Siglent) or SOUR1:FUNC:RAMP:SYMM 50 (generic)
            # Symmetry 0 (a pure downward sawtooth) is legitimate
            # (awg_output.py's own validation allows `0 <= percent <= 100`
            # inclusive, unlike duty cycle above), so it is gated on
            # non_negative (>= 0) rather than positive (> 0) -- a negative
            # symmetry is not a value the real driver ever allows either (I2).
            # max_magnitude=100 for the same percentage-bound reason as duty
            # cycle above (M5).
            if match := re.match(r"C(\d+):BSWV\s+SYM,([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                symm = float(match.group(2))
                if self.reject_if_invalid(symm, name="SYM", positive=False, non_negative=True, max_magnitude=100):
                    return
                if ch in self.awg_channels:
                    self.awg_channels[ch]["ramp_symmetry"] = symm
                return
            if match := re.match(r"SOUR(\d+):FUNC:RAMP:SYMM\s+([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                symm = float(match.group(2))
                if self.reject_if_invalid(symm, name="FUNC:RAMP:SYMM", positive=False, non_negative=True, max_magnitude=100):
                    return
                if ch in self.awg_channels:
                    self.awg_channels[ch]["ramp_symmetry"] = symm
                return

            # Output enable: C1:OUTP ON (Siglent) or OUTP1 ON (generic)
            if match := re.match(r"C(\d+):OUTP\s+(ON|OFF)", command, re.IGNORECASE):
                ch = int(match.group(1))
                enabled = match.group(2).upper() == "ON"
                if ch in self.awg_channels:
                    self.awg_channels[ch]["enabled"] = enabled
                return
            if match := re.match(r"OUTP(\d+)\s+(ON|OFF)", command, re.IGNORECASE):
                ch = int(match.group(1))
                enabled = match.group(2).upper() == "ON"
                if ch in self.awg_channels:
                    self.awg_channels[ch]["enabled"] = enabled
                return

        # Data acquisition (DAQ) commands
        if self.daq_mode:
            # Scan list: ROUT:SCAN (@101,102). Previously dropped entirely
            # (audit M8), so get_scan_list()/ROUT:SCAN? never reflected a
            # write and round-trip verification of a healthy instrument
            # reported failure.
            if match := re.match(r"ROUT:SCAN\s+\(@([\d,]*)\)", command, re.IGNORECASE):
                raw = match.group(1)
                self.daq_scan_list = [int(ch) for ch in raw.split(",") if ch]
                return

            # Trigger source: TRIG:SOUR IMM/BUS/EXT/TIM.
            if match := re.match(r"TRIG:SOUR\s+(\w+)", command, re.IGNORECASE):
                self.daq_trigger_source = match.group(1).upper()
                return

        # Oscilloscope commands: C{n}:WF? channel recording is shared across every
        # scope dialect/vendor (Tek's CURVe? uses data_source instead - Task 9), so
        # it is recorded here before personality dispatch rather than inside a
        # single vendor module's write handler.
        if match := re.match(r"C(\d+):WF\?", command, re.IGNORECASE):
            channel = int(match.group(1))
            self._last_waveform_channel = channel
            self.waveform_requests.append(channel)

        personality = _PERSONALITIES.get(self.scope_vendor, siglent)
        personality.handle_write(self, command)

    def read(self) -> str:
        """Return an empty response for completeness."""
        if not self._connected:
            raise exceptions.ConnectionError(f"Not connected to oscilloscope at {self.host}:{self.port}")
        return ""

    def query(self, command: str) -> str:
        """Return deterministic responses for known SCPI queries."""
        if not self._connected:
            raise exceptions.ConnectionError(f"Not connected to oscilloscope at {self.host}:{self.port}")

        command = command.strip()
        self.queries.append(command)

        if command in self.custom_responses:
            override = self.custom_responses[command]
            if isinstance(override, list):
                if len(override) > 1:
                    return override.pop(0)
                return override[0]
            return override

        upper = command.upper()

        if upper == "*IDN?":
            if self.daq_mode:
                return self.daq_idn
            elif self.awg_mode:
                return self.awg_idn
            elif self.psu_mode:
                return self.psu_idn
            else:
                return self.idn

        # SYST:ERR? for the three instrument classes that expose get_error()
        # (psu_scpi_commands.py:70, awg_scpi_commands.py:65,
        # daq_scpi_commands.py:59). Scopes deliberately have no get_error, so
        # scope mode falls through to the strict-mode timeout -- adding an
        # accessor there would quietly undo that gating.
        if "SYST:ERR?" in upper and (self.psu_mode or self.awg_mode or self.daq_mode):
            return self._pop_error()

        # Data acquisition (DAQ) queries
        if self.daq_mode:
            # Specific queries first -- the old readings matcher used
            # `"R?" in upper`, which is a substring test and swallowed
            # SYST:ERR? and TRIG:SOUR? (both end in "R?") before they ever
            # reached their own handlers (audit M7).

            # Scan list query
            if "ROUT:SCAN?" in upper:
                if self.daq_scan_list:
                    return f"(@{','.join(str(ch) for ch in self.daq_scan_list)})"
                return "(@)"

            # Data points query
            if "DATA:POIN?" in upper:
                return str(len(self.daq_readings.split(",")))

            # Trigger source query
            if "TRIG:SOUR?" in upper:
                return self.daq_trigger_source

            # Return configured readings for any measurement/read/fetch query.
            # Anchored to the START of the command (not a bare substring
            # test), so "R?" only matches a command that begins with it --
            # not the tail of SYST:ERR?/TRIG:SOUR? (M7). Deliberately NOT
            # anchored at the end: MEAS:*? and read_remove's "R?" commands
            # carry trailing arguments (e.g. "MEAS:VOLT:DC? AUTO,AUTO,(@101)"
            # or "R? 10"), which a full-string anchor would reject.
            if re.match(r"^(READ\?|FETC\??|MEAS:[\w:]*\?|R\?)", upper):
                return self.daq_readings

        # Function generator (AWG) queries
        if self.awg_mode:
            # Basic-wave query: C1:BSWV? (SDG_ProgrammingGuide PG02-E05B
            # p.31). QUERY SYNTAX is bare -- there is no per-field selector --
            # and RESPONSE FORMAT is function-conditional: "<parameter> :=
            # {All the parameters of the current basic waveform}". The p.31
            # worked SINE example is WVTP,FRQ,PERI,AMP,OFST,HLEV,LLEV,PHSE
            # with no DUTY/SYM; DUTY is only settable for SQUARE/PULSE and SYM
            # only for RAMP (p.29-30 parameter table), so this handler only
            # appends them when the channel's current function calls for them
            # (H5 follow-up: the mock used to always emit DUTY,SYM and never
            # HLEV,LLEV, a shape the manual never shows for any waveform type).
            if match := re.match(r"C(\d+):BSWV\?$", upper):
                ch = int(match.group(1))
                c = self.awg_channels.get(ch, {})
                function = c.get("function", "SINE")
                frequency = c.get("frequency", 1000.0)
                period = 1.0 / frequency if frequency else 0.0
                amplitude = c.get("amplitude", 1.0)
                offset = c.get("offset", 0.0)
                hlev = offset + amplitude / 2
                llev = offset - amplitude / 2
                response = (
                    f"C{ch}:BSWV WVTP,{function},"
                    f"FRQ,{frequency:.10g}HZ,"
                    f"PERI,{period:.10g}S,"
                    f"AMP,{amplitude:.10g}V,"
                    f"OFST,{offset:.10g}V,"
                    f"HLEV,{hlev:.10g}V,"
                    f"LLEV,{llev:.10g}V,"
                    f"PHSE,{c.get('phase', 0.0):.10g}"
                )
                if function in ("SQUARE", "PULSE"):
                    response += f",DUTY,{c.get('pulse_duty', 50.0):.10g}"
                elif function == "RAMP":
                    response += f",SYM,{c.get('ramp_symmetry', 50.0):.10g}"
                return response

            # Generic SCPI-99 per-field fallbacks (unaffected by H5, which is
            # a Siglent-selector-grammar defect only): SOUR1:FUNC?, SOUR1:FREQ?, etc.
            if match := re.match(r"SOUR(\d+):FUNC\?", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return self.awg_channels[ch]["function"]
                return "SINE"
            if match := re.match(r"SOUR(\d+):FREQ\?", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return f"{self.awg_channels[ch]['frequency']:.6f}"
                return "1000.0"
            if match := re.match(r"SOUR(\d+):VOLT\?", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return f"{self.awg_channels[ch]['amplitude']:.3f}"
                return "1.0"
            if match := re.match(r"SOUR(\d+):VOLT:OFFS\?", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return f"{self.awg_channels[ch]['offset']:.3f}"
                return "0.0"
            if match := re.match(r"SOUR(\d+):PHAS\?", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return f"{self.awg_channels[ch]['phase']:.1f}"
                return "0.0"
            if match := re.match(r"SOUR(\d+):FUNC:PULS:DCYC\?", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return f"{self.awg_channels[ch]['pulse_duty']:.1f}"
                return "50.0"
            if match := re.match(r"SOUR(\d+):FUNC:RAMP:SYMM\?", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return f"{self.awg_channels[ch]['ramp_symmetry']:.1f}"
                return "50.0"

            # Arbitrary waveform query: C1:ARWV? (PG02-E05B p.62). Bare query;
            # RESPONSE FORMAT always returns INDEX and NAME together. Static --
            # arb waveform selection isn't tracked in awg_channels state
            # (get_arb_waveform has no caller anywhere in this repo).
            if match := re.match(r"C(\d+):ARWV\?$", upper):
                ch = int(match.group(1))
                return f"C{ch}:ARWV INDEX,2,NAME,StairUp"

            # Output state query: C1:OUTP? (PG02-E05B p.27-28, worked EXAMPLE).
            # RESPONSE FORMAT is the state PLUS LOAD/PLRT -- not just "ON"/
            # "OFF" (H5, fixed Task 10). LOAD/PLRT aren't tracked in
            # awg_channels state, so they are reported as the manual's own
            # worked-example values.
            if match := re.match(r"C(\d+):OUTP\?$", upper):
                ch = int(match.group(1))
                state = "ON" if self.awg_channels.get(ch, {}).get("enabled") else "OFF"
                return f"C{ch}:OUTP {state},LOAD,HZ,PLRT,NOR"
            if match := re.match(r"OUTP(\d+)\?", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return "ON" if self.awg_channels[ch]["enabled"] else "OFF"
                return "OFF"

        # Power supply queries
        if self.psu_mode:
            # Voltage queries: CH1:VOLT? (Siglent) or SOUR1:VOLT? (generic)
            if match := re.match(r"(?:CH|SOUR)(\d+):VOLT\?", upper):
                ch = int(match.group(1))
                if ch in self.psu_outputs:
                    return f"{self.psu_outputs[ch]['voltage']:.3f}"
                return "0.000"

            # Current queries: CH1:CURR? (Siglent) or SOUR1:CURR? (generic)
            if match := re.match(r"(?:CH|SOUR)(\d+):CURR\?", upper):
                ch = int(match.group(1))
                if ch in self.psu_outputs:
                    return f"{self.psu_outputs[ch]['current']:.3f}"
                return "0.000"

            # Status word query: SYSTem:STATus? (QS0503X-E01B p.41-42). This is
            # the ONLY documented way to read CH1/CH2 output state on the
            # SPD3303X (audit H20, Task 8) -- bit 4 = CH1 on, bit 5 = CH2 on.
            # The 0x0204 baseline reproduces the manual's own bits {2, 9}
            # (independent tracking mode, CH2 waveform display) so that with
            # ch1=off/ch2=on this handler answers the manual's own Typical
            # Return "0x0224" verbatim.
            if match := re.match(r"SYST(?:EM)?:STAT(?:US)?\?", upper):
                bits = 0x0204
                if self.psu_outputs.get(1, {}).get("enabled"):
                    bits |= 1 << 4
                if self.psu_outputs.get(2, {}).get("enabled"):
                    bits |= 1 << 5
                return f"0x{bits:04X}"

            # Output state queries: OUTPut? CH1 (Siglent) or OUTP1? (generic)
            # Matches: OUTP1?, OUTPUT1?, OUTP? CH1, OUTPUT? CH1
            if match := re.match(r"OUTP(?:UT)?(\d+)\?|OUTP(?:UT)?\?\s*(?:CH\s*)?(\d+)", upper):
                ch = int(match.group(1) or match.group(2))
                if ch in self.psu_outputs:
                    return "ON" if self.psu_outputs[ch]["enabled"] else "OFF"
                return "OFF"

            # Measurements - simulate with slight noise
            # MEASure:VOLTage? CH1 (Siglent, QS0503X-E01B p.38; channel is an
            # argument, not fused to the keyword -- audit H6)
            if match := re.match(r"MEAS(?:URE)?:VOLT(?:AGE)?\?\s*CH(\d+)", upper):
                ch = int(match.group(1))
                if ch in self.psu_outputs:
                    v = self.psu_outputs[ch]["voltage"]
                    # Add small noise to measurement (0-2mV)
                    noise = 0.001 if v > 0 else 0.0
                    return f"{v + noise:.3f}"
                return "0.000"

            if match := re.match(r"MEAS(?:URE)?:CURR(?:ENT)?\?\s*CH(\d+)", upper):
                ch = int(match.group(1))
                if ch in self.psu_outputs:
                    i = self.psu_outputs[ch]["current"]
                    # Add small noise to measurement (0-2mA)
                    noise = 0.001 if i > 0 else 0.0
                    return f"{i + noise:.3f}"
                return "0.000"

            if match := re.match(r"MEAS(?:URE)?:POW(?:ER)?\?\s*CH(\d+)", upper):
                ch = int(match.group(1))
                if ch in self.psu_outputs:
                    v = self.psu_outputs[ch]["voltage"]
                    i = self.psu_outputs[ch]["current"]
                    p = v * i
                    return f"{p:.3f}"
                return "0.000"

            # Tracking mode query
            if "OUTP:TRACK?" in upper or "OUTPUT:TRACK?" in upper:
                return self.psu_tracking_mode

            # Timer queries
            if match := re.match(r"TIME(?:R)?\?\s*CH(\d+)", upper):
                ch = int(match.group(1))
                return "ON" if self.psu_timer_enabled.get(ch, False) else "OFF"

            # Waveform queries
            if match := re.match(r"WAVE\?\s*CH(\d+)", upper):
                ch = int(match.group(1))
                return "ON" if self.psu_waveform_enabled.get(ch, False) else "OFF"

            # OVP queries: SOUR1:VOLT:PROT? (generic) or CH1:VOLT:PROT? (Siglent)
            if match := re.match(r"(?:CH|SOUR)(\d+):VOLT:PROT\?", upper):
                ch = int(match.group(1))
                return f"{self.psu_ovp_levels.get(ch, 30.0):.3f}"

            # OCP queries: SOUR1:CURR:PROT? (generic) or CH1:CURR:PROT? (Siglent)
            if match := re.match(r"(?:CH|SOUR)(\d+):CURR:PROT\?", upper):
                ch = int(match.group(1))
                return f"{self.psu_ocp_levels.get(ch, 3.0):.3f}"

            # Output mode query (CV or CC)
            if match := re.match(r"OUTP(?:UT)?(\d+):MODE\?", upper):
                ch = int(match.group(1))
                if ch in self.psu_outputs:
                    # Return CV (constant voltage) by default
                    return "CV"
                return "CV"

        personality = _PERSONALITIES.get(self.scope_vendor, siglent)
        response = personality.handle_query(self, command)
        if response is not None:
            return response

        if self.psu_mode or self.awg_mode or self.daq_mode:
            if self.strict:
                raise exceptions.TimeoutError(f"MockConnection (strict) has no response for query: {command!r}")
            return ""

        # Real scopes produce no response at all for unknown or wrong-dialect
        # queries - the caller's read times out. Model that honestly.
        raise exceptions.TimeoutError(f"MockConnection ({self.scope_dialect}) has no response for query: {command!r}")

    def query_many(self, commands: Iterable[str]) -> List[str]:
        """Convenience helper to query multiple commands sequentially."""
        return [self.query(cmd) for cmd in commands]

    def read_raw(self, size: Optional[int] = None) -> bytes:
        """Return deterministic raw waveform data (or a mock screenshot BMP after SCDP?)."""
        if not self._connected:
            raise exceptions.ConnectionError(f"Not connected to oscilloscope at {self.host}:{self.port}")

        if self.writes and self.writes[-1].upper() == "SCDP?":
            # Bare IEEE 488.2 block (no "DESC," prefix), matching how a real
            # scope's SCDP? reply is parsed in screen_capture.py.
            payload = _build_ieee_block(MOCK_SCREENSHOT_BMP)
            return payload[:size] if size is not None else payload

        # Modern :WAVeform:PREamble?/:WAVeform:DATA? binary blocks (Task 18,
        # audit H9): which one read_raw() returns is determined by the last
        # write, exactly like the SCDP? branch above.
        if self.scope_dialect == "modern" and self.writes:
            last_write = self.writes[-1].upper()
            if last_write == ":WAVEFORM:PREAMBLE?":
                payload = siglent.build_waveform_preamble(self)
                return payload[:size] if size is not None else payload
            if last_write == ":WAVEFORM:DATA?":
                payload = siglent.build_waveform_data(self)
                return payload[:size] if size is not None else payload

        # v5.0.0: the legacy C<n>:WF? DAT2/DESC block was answered on modern
        # dialects as a back-compat shim "until v5.0.0" (Task 18). That date
        # has arrived -- the modern programming guide documents no such
        # command, so a modern instance must no longer serve it. Real modern
        # hardware gives no response at all to an unrecognized/legacy
        # waveform read; model that honestly, same as the query() timeout
        # path above.
        if self.scope_dialect == "modern":
            raise exceptions.TimeoutError(f"MockConnection ({self.scope_dialect}) has no response for read_raw() after writes={self.writes!r}")

        personality = _PERSONALITIES.get(self.scope_vendor, siglent)
        payload = personality.build_waveform_response(self)
        return payload[:size] if size is not None else payload
