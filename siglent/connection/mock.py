"""Mock connection implementation for deterministic offline SCPI testing."""

from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Union

from siglent import exceptions
from siglent.connection.base import BaseConnection


def _format_scientific(value: float, unit: str) -> str:
    """Format a numeric value with a unit using Siglent-style scientific notation."""
    return f"{value:.2E}{unit}"


class MockConnection(BaseConnection):
    """Mock connection that returns deterministic SCPI responses.

    The mock is designed for offline tests that want to exercise the full
    oscilloscope/automation stack without touching networked hardware. It keeps
    lightweight internal state for common SCPI queries and waveforms.
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
        sample_rate: float = 1_000.0,
        timebase: float = 1e-3,
        trigger_status: Optional[List[str]] = None,
        custom_responses: Optional[Dict[str, Union[str, List[str]]]] = None,
        # Power supply parameters
        psu_mode: bool = False,
        psu_idn: str = "Siglent Technologies,SPD3303X,SPD123456,1.0",
        psu_outputs: Optional[Dict[int, Dict[str, float]]] = None,
    ):
        super().__init__(host, port, timeout)
        channels = channel_states.keys() if channel_states else range(1, 3)

        self.idn = idn
        self._channel_enabled: Dict[int, bool] = {ch: channel_states.get(ch, True) if channel_states else True for ch in channels}
        self._voltage_scales: Dict[int, float] = {ch: voltage_scales.get(ch, 1.0) if voltage_scales else 1.0 for ch in channels}
        self._voltage_offsets: Dict[int, float] = {ch: voltage_offsets.get(ch, 0.0) if voltage_offsets else 0.0 for ch in channels}
        self._waveform_payloads: Dict[int, bytes] = {ch: (waveform_payloads.get(ch, bytes([0, 25, 50, 75])) if waveform_payloads else bytes([0, 25, 50, 75])) for ch in channels}

        self.sample_rate = sample_rate
        self.timebase = timebase
        self.trigger_mode = "STOP"
        self.trigger_type = "EDGE"
        self.trigger_source = "C1"
        self.trigger_level: Dict[int, float] = {ch: 0.0 for ch in channels}
        self.trigger_status: List[str] = trigger_status[:] if trigger_status else ["Stop"]

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

        # Oscilloscope commands
        if command.upper().startswith("TDIV "):
            value = command.split(" ", 1)[1]
            try:
                self.timebase = float(value)
            except ValueError:
                self.timebase = self.timebase
            self.timebase_updates.append(self.timebase)
        elif match := re.match(r"C(\d+):VDIV\s+(.+)", command, re.IGNORECASE):
            channel = int(match.group(1))
            value = float(match.group(2))
            self._voltage_scales[channel] = value
            self.scale_updates.setdefault(channel, []).append(value)
        elif match := re.match(r"C(\d+):OFST\s+(.+)", command, re.IGNORECASE):
            channel = int(match.group(1))
            value = float(match.group(2))
            self._voltage_offsets[channel] = value
        elif match := re.match(r"C(\d+):TRA\s+(ON|OFF)", command, re.IGNORECASE):
            channel = int(match.group(1))
            self._channel_enabled[channel] = match.group(2).upper() == "ON"
        elif command.upper().startswith("TRIG_MODE "):
            self.trigger_mode = command.split(" ", 1)[1].upper()
        elif command.upper().startswith("TRIG_SELECT "):
            _, params = command.split(" ", 1)
            trig_type, _, source = params.split(",")
            self.trigger_type = trig_type.strip().upper()
            self.trigger_source = source.strip().upper()
        elif command.upper() == "ARM":
            # Simulate an acquisition that will eventually stop when no custom sequence is provided
            if len(self.trigger_status) <= 1:
                self.trigger_status = ["Run", "Stop"]
        elif match := re.match(r"C(\d+):TRLV\s+(.+)", command, re.IGNORECASE):
            channel = int(match.group(1))
            self.trigger_level[channel] = float(match.group(2))
        elif match := re.match(r"C(\d+):WF\?", command, re.IGNORECASE):
            channel = int(match.group(1))
            self._last_waveform_channel = channel
            self.waveform_requests.append(channel)

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
            return self.psu_idn if self.psu_mode else self.idn

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
            # MEAS1:VOLT? (generic) or MEASure1:VOLTage? (Siglent)
            if match := re.match(r"MEAS(?:URE)?(\d+):VOLT(?:AGE)?\?", upper):
                ch = int(match.group(1))
                if ch in self.psu_outputs:
                    v = self.psu_outputs[ch]["voltage"]
                    # Add small noise to measurement (0-2mV)
                    noise = 0.001 if v > 0 else 0.0
                    return f"{v + noise:.3f}"
                return "0.000"

            if match := re.match(r"MEAS(?:URE)?(\d+):CURR(?:ENT)?\?", upper):
                ch = int(match.group(1))
                if ch in self.psu_outputs:
                    i = self.psu_outputs[ch]["current"]
                    # Add small noise to measurement (0-2mA)
                    noise = 0.001 if i > 0 else 0.0
                    return f"{i + noise:.3f}"
                return "0.000"

            if match := re.match(r"MEAS(?:URE)?(\d+):POW(?:ER)?\?", upper):
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

        if upper in {":TRIG:STAT?", "TRIG:STAT?"}:
            if len(self.trigger_status) > 1:
                return self.trigger_status.pop(0)
            return self.trigger_status[0]

        if upper == "TRIG_MODE?":
            return self.trigger_mode

        if upper == "TRIG_SELECT?":
            return f"{self.trigger_type},SR,{self.trigger_source}"

        if match := re.match(r"C(\d+):VDIV\?", command, re.IGNORECASE):
            channel = int(match.group(1))
            value = self._voltage_scales.get(channel, 1.0)
            return f"C{channel}:VDIV {_format_scientific(value, 'V')}"

        if match := re.match(r"C(\d+):OFST\?", command, re.IGNORECASE):
            channel = int(match.group(1))
            value = self._voltage_offsets.get(channel, 0.0)
            return f"C{channel}:OFST {_format_scientific(value, 'V')}"

        if match := re.match(r"C(\d+):TRA\?", command, re.IGNORECASE):
            channel = int(match.group(1))
            return "ON" if self._channel_enabled.get(channel, True) else "OFF"

        if match := re.match(r"C(\d+):TRLV\?", command, re.IGNORECASE):
            channel = int(match.group(1))
            return f"C{channel}:TRLV {_format_scientific(self.trigger_level.get(channel, 0.0), 'V')}"

        if upper == "TDIV?":
            return f"TDIV {_format_scientific(self.timebase, 'S')}"

        if upper == "SARA?":
            return f"SARA {_format_scientific(self.sample_rate, 'SA/S')}"

        return ""

    def query_many(self, commands: Iterable[str]) -> List[str]:
        """Convenience helper to query multiple commands sequentially."""
        return [self.query(cmd) for cmd in commands]

    def _build_waveform_block(self, payload: bytes) -> bytes:
        """Construct a minimal Siglent-style block response."""
        length = len(payload)
        length_str = str(length).encode()
        header = b"DESC,#" + str(len(length_str)).encode() + length_str
        return header + payload

    def read_raw(self, size: Optional[int] = None) -> bytes:
        """Return deterministic raw waveform data."""
        if not self._connected:
            raise exceptions.ConnectionError(f"Not connected to oscilloscope at {self.host}:{self.port}")

        channel = self._last_waveform_channel or next(iter(self._waveform_payloads.keys()))
        payload = self._waveform_payloads.get(channel, bytes())
        return self._build_waveform_block(payload)
