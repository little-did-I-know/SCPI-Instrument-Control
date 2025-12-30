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

    def connect(self) -> None:
        """Mark the connection as established."""
        self._connected = True

    def disconnect(self) -> None:
        """Mark the connection as closed."""
        self._connected = False

    def write(self, command: str) -> None:
        """Record the command and update simple internal state."""
        if not self._connected:
            raise exceptions.ConnectionError(f"Not connected to oscilloscope at {self.host}:{self.port}")

        command = command.strip()
        self.writes.append(command)

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
            return self.idn

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
