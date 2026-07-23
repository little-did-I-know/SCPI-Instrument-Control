"""Mock connection shell: constructor/state, connect/disconnect, PSU/AWG/DAQ handling,
and personality dispatch to the vendor-specific scope write/query/waveform modules."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Union

from scpi_control import exceptions
from scpi_control.connection.base import BaseConnection
from scpi_control.connection.mock.helpers import MOCK_SCREENSHOT_BMP, _build_ieee_block
from scpi_control.connection.mock import lecroy, siglent, tektronix
from scpi_control.models import detect_model_from_idn

if TYPE_CHECKING:
    from scpi_control.signal_synth import SignalSpec

_PERSONALITIES = {
    "siglent": siglent,
    "tektronix": tektronix,
    "lecroy": lecroy,
}


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
        signals: Optional[Dict[int, "SignalSpec"]] = None,
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
        self._signals: Dict[int, "SignalSpec"] = dict(signals) if signals else {}
        self._acquisition_counts: Dict[int, int] = {}
        self._channel_coupling: Dict[int, str] = {ch: "D1M" for ch in channels}

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

    def connect(self) -> None:
        """Mark the connection as established."""
        self._connected = True

    def disconnect(self) -> None:
        """Mark the connection as closed."""
        self._connected = False

    def write(self, command: str) -> None:
        """Record the command and update simple internal state."""
        if not self._connected:
            raise exceptions.SiglentConnectionError(f"Not connected to oscilloscope at {self.host}:{self.port}")

        command = command.strip()
        self.writes.append(command)

        # Power supply commands
        if self.psu_mode:
            # Voltage setting: CH1:VOLT 5.0 (Siglent) or SOUR1:VOLT 5.0 (generic)
            if match := re.match(r"(?:CH|SOUR)(\d+):VOLT\s+([\d.]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                voltage = float(match.group(2))
                if ch in self.psu_outputs:
                    self.psu_outputs[ch]["voltage"] = voltage
                return

            # Current setting: CH1:CURR 2.0 (Siglent) or SOUR1:CURR 2.0 (generic)
            if match := re.match(r"(?:CH|SOUR)(\d+):CURR\s+([\d.]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                current = float(match.group(2))
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

            # Tracking mode: OUTP:TRACK SERIES
            if match := re.match(r"OUTP(?:UT)?:TRACK\s+(INDEPENDENT|SERIES|PARALLEL)", command, re.IGNORECASE):
                self.psu_tracking_mode = match.group(1).upper()
                return

            # Timer enable: TIMEr CH1,ON
            if match := re.match(r"TIME(?:R)?\s+CH(\d+),(ON|OFF)", command, re.IGNORECASE):
                ch = int(match.group(1))
                enabled = match.group(2).upper() == "ON"
                self.psu_timer_enabled[ch] = enabled
                return

            # Waveform enable: WAVE CH1,ON
            if match := re.match(r"WAVE\s+CH(\d+),(ON|OFF)", command, re.IGNORECASE):
                ch = int(match.group(1))
                enabled = match.group(2).upper() == "ON"
                self.psu_waveform_enabled[ch] = enabled
                return

            # OVP setting: CH1:VOLT:PROT 25.0 or SOUR1:VOLT:PROT 25.0
            if match := re.match(r"(?:CH|SOUR)(\d+):VOLT:PROT\s+([\d.]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                level = float(match.group(2))
                self.psu_ovp_levels[ch] = level
                return

            # OCP setting: CH1:CURR:PROT 2.5 or SOUR1:CURR:PROT 2.5
            if match := re.match(r"(?:CH|SOUR)(\d+):CURR:PROT\s+([\d.]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                level = float(match.group(2))
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
            if match := re.match(r"C(\d+):BSWV\s+FRQ,([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                freq = float(match.group(2))
                if ch in self.awg_channels:
                    self.awg_channels[ch]["frequency"] = freq
                return
            if match := re.match(r"SOUR(\d+):FREQ\s+([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                freq = float(match.group(2))
                if ch in self.awg_channels:
                    self.awg_channels[ch]["frequency"] = freq
                return

            # Amplitude: C1:BSWV AMP,5.0 (Siglent) or SOUR1:VOLT 5.0 (generic)
            if match := re.match(r"C(\d+):BSWV\s+AMP,([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                amp = float(match.group(2))
                if ch in self.awg_channels:
                    self.awg_channels[ch]["amplitude"] = amp
                return
            if match := re.match(r"SOUR(\d+):VOLT\s+([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                amp = float(match.group(2))
                if ch in self.awg_channels:
                    self.awg_channels[ch]["amplitude"] = amp
                return

            # Offset: C1:BSWV OFST,0.5 (Siglent) or SOUR1:VOLT:OFFS 0.5 (generic)
            if match := re.match(r"C(\d+):BSWV\s+OFST,([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                offset = float(match.group(2))
                if ch in self.awg_channels:
                    self.awg_channels[ch]["offset"] = offset
                return
            if match := re.match(r"SOUR(\d+):VOLT:OFFS\s+([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                offset = float(match.group(2))
                if ch in self.awg_channels:
                    self.awg_channels[ch]["offset"] = offset
                return

            # Phase: C1:BSWV PHSE,90 (Siglent) or SOUR1:PHAS 90 (generic)
            if match := re.match(r"C(\d+):BSWV\s+PHSE,([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                phase = float(match.group(2))
                if ch in self.awg_channels:
                    self.awg_channels[ch]["phase"] = phase
                return
            if match := re.match(r"SOUR(\d+):PHAS\s+([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                phase = float(match.group(2))
                if ch in self.awg_channels:
                    self.awg_channels[ch]["phase"] = phase
                return

            # Pulse duty cycle: C1:BSWV DUTY,25 (Siglent) or SOUR1:FUNC:PULS:DCYC 25 (generic)
            if match := re.match(r"C(\d+):BSWV\s+DUTY,([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                duty = float(match.group(2))
                if ch in self.awg_channels:
                    self.awg_channels[ch]["pulse_duty"] = duty
                return
            if match := re.match(r"SOUR(\d+):FUNC:PULS:DCYC\s+([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                duty = float(match.group(2))
                if ch in self.awg_channels:
                    self.awg_channels[ch]["pulse_duty"] = duty
                return

            # Ramp symmetry: C1:BSWV SYM,50 (Siglent) or SOUR1:FUNC:RAMP:SYMM 50 (generic)
            if match := re.match(r"C(\d+):BSWV\s+SYM,([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                symm = float(match.group(2))
                if ch in self.awg_channels:
                    self.awg_channels[ch]["ramp_symmetry"] = symm
                return
            if match := re.match(r"SOUR(\d+):FUNC:RAMP:SYMM\s+([\d.E+\-]+)", command, re.IGNORECASE):
                ch = int(match.group(1))
                symm = float(match.group(2))
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

        # Data acquisition (DAQ) queries
        if self.daq_mode:
            # Return configured readings for any measurement/read/fetch query
            if any(kw in upper for kw in ["READ?", "FETC?", "MEAS:", "R?"]):
                return self.daq_readings

            # Scan list query
            if "ROUT:SCAN?" in upper:
                if self.daq_scan_list:
                    return f"(@{','.join(str(ch) for ch in self.daq_scan_list)})"
                return "(@)"

            # Data points query
            if "DATA:POIN?" in upper:
                return str(len(self.daq_readings.split(",")))

            # Error query
            if "SYST:ERR?" in upper:
                return '+0,"No error"'

        # Function generator (AWG) queries
        if self.awg_mode:
            # Function queries: C1:BSWV? WVTP (Siglent) or SOUR1:FUNC? (generic)
            if match := re.match(r"C(\d+):BSWV\?\s*WVTP", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return self.awg_channels[ch]["function"]
                return "SINE"
            if match := re.match(r"SOUR(\d+):FUNC\?", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return self.awg_channels[ch]["function"]
                return "SINE"

            # Frequency queries: C1:BSWV? FRQ (Siglent) or SOUR1:FREQ? (generic)
            if match := re.match(r"C(\d+):BSWV\?\s*FRQ", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return f"{self.awg_channels[ch]['frequency']:.6f}"
                return "1000.0"
            if match := re.match(r"SOUR(\d+):FREQ\?", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return f"{self.awg_channels[ch]['frequency']:.6f}"
                return "1000.0"

            # Amplitude queries: C1:BSWV? AMP (Siglent) or SOUR1:VOLT? (generic)
            if match := re.match(r"C(\d+):BSWV\?\s*AMP", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return f"{self.awg_channels[ch]['amplitude']:.3f}"
                return "1.0"
            if match := re.match(r"SOUR(\d+):VOLT\?", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return f"{self.awg_channels[ch]['amplitude']:.3f}"
                return "1.0"

            # Offset queries: C1:BSWV? OFST (Siglent) or SOUR1:VOLT:OFFS? (generic)
            if match := re.match(r"C(\d+):BSWV\?\s*OFST", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return f"{self.awg_channels[ch]['offset']:.3f}"
                return "0.0"
            if match := re.match(r"SOUR(\d+):VOLT:OFFS\?", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return f"{self.awg_channels[ch]['offset']:.3f}"
                return "0.0"

            # Phase queries: C1:BSWV? PHSE (Siglent) or SOUR1:PHAS? (generic)
            if match := re.match(r"C(\d+):BSWV\?\s*PHSE", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return f"{self.awg_channels[ch]['phase']:.1f}"
                return "0.0"
            if match := re.match(r"SOUR(\d+):PHAS\?", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return f"{self.awg_channels[ch]['phase']:.1f}"
                return "0.0"

            # Pulse duty cycle queries
            if match := re.match(r"C(\d+):BSWV\?\s*DUTY", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return f"{self.awg_channels[ch]['pulse_duty']:.1f}"
                return "50.0"
            if match := re.match(r"SOUR(\d+):FUNC:PULS:DCYC\?", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return f"{self.awg_channels[ch]['pulse_duty']:.1f}"
                return "50.0"

            # Ramp symmetry queries
            if match := re.match(r"C(\d+):BSWV\?\s*SYM", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return f"{self.awg_channels[ch]['ramp_symmetry']:.1f}"
                return "50.0"
            if match := re.match(r"SOUR(\d+):FUNC:RAMP:SYMM\?", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return f"{self.awg_channels[ch]['ramp_symmetry']:.1f}"
                return "50.0"

            # Output state queries: C1:OUTP? (Siglent) or OUTP1? (generic)
            if match := re.match(r"C(\d+):OUTP\?", upper):
                ch = int(match.group(1))
                if ch in self.awg_channels:
                    return "ON" if self.awg_channels[ch]["enabled"] else "OFF"
                return "OFF"
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
            return _build_ieee_block(MOCK_SCREENSHOT_BMP)

        personality = _PERSONALITIES.get(self.scope_vendor, siglent)
        return personality.build_waveform_response(self)
