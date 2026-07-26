"""Per-kind adapters: what differs between instrument kinds in a session.

InstrumentSession owns everything shared -- the worker thread, the job queue,
pub/sub, viewers, ownership, the error state machine. An adapter owns the four
things that actually vary by kind, plus any state only that kind needs.

Keeping the lifecycle in ONE implementation is deliberate. It is threading code,
and a subclass that overrides part of a thread or error path by accident is a
much worse failure than a little indirection.
"""

import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from scpi_control import Oscilloscope
from scpi_control.connection.mock import MockConnection
from scpi_control.exceptions import InvalidParameterError, SiglentError
from scpi_control.server import compute
from scpi_control.server.netpolicy import validate_target
from scpi_control.server.recorder import TrendRecorder

MAX_FRAME_POINTS = 2000
MEASUREMENT_EVERY_N_POLLS = 4

DEFAULT_MOCK_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"


def _safe(fn, default=None):
    try:
        return fn()
    except SiglentError:
        return default


def _quiet(fn, default=None):
    """Like _safe, but for analysis compute: ANY exception degrades to default.

    The poll tick is the session heartbeat; a numpy edge case in analysis
    must never kill the worker thread.
    """
    try:
        return fn()
    except Exception:
        return default


def read_state(scope: Oscilloscope) -> Dict[str, Any]:
    channels: Dict[int, Dict[str, Any]] = {}
    for n in scope.supported_channels:
        ch = scope.get_channel(n)
        channels[n] = {
            "enabled": ch.enabled,
            "voltage_scale": ch.voltage_scale,
            "voltage_offset": ch.voltage_offset,
            "coupling": ch.coupling,
            "probe_ratio": _safe(lambda: ch.probe_ratio),
        }
    trig = scope.trigger
    return {
        "run_state": scope.acquisition_status(),
        "timebase": scope.timebase,
        "channels": channels,
        "trigger": {
            "mode": trig.mode,
            "source": _safe(lambda: trig.source),
            "level": _safe(lambda: trig.level),
            "slope": _safe(lambda: trig.slope),
            "coupling": _safe(lambda: trig.coupling),
        },
    }


def _decimate_frame(channel, time_axis, voltage) -> Dict[str, Any]:
    step = max(1, -(-len(voltage) // MAX_FRAME_POINTS))  # ceiling division keeps len(points) <= cap
    points = voltage[::step]
    t0 = float(time_axis[0]) if len(time_axis) else 0.0
    dt = float(time_axis[1] - time_axis[0]) * step if len(time_axis) > 1 else 1.0
    return {"type": "waveform", "channel": channel, "t0": t0, "dt": dt, "points": [float(v) for v in points]}


def _waveform_frame(scope: Oscilloscope, channel: int) -> Dict[str, Any]:
    data = scope.get_waveform(channel, provenance=False)
    return _decimate_frame(channel, data.time, data.voltage)


def make_mock_scope_connection(model: Optional[str]) -> MockConnection:
    idn = DEFAULT_MOCK_IDN if model is None else "Siglent Technologies,{0},MOCK0001,1.0.0.0".format(model)
    # No explicit waveform_payloads: channels serve state-coupled synthesized
    # signals (connection/mock/synth.py). 1 MSa/s x 14 div x 1 ms/div = 14k points.
    return MockConnection("mock", idn=idn, channel_states={1: True, 2: False, 3: False, 4: False}, trigger_status=["Stop"], sample_rate=1_000_000.0, timebase=1e-3)


class InstrumentAdapter:
    """What a session needs to know about one kind of instrument."""

    kind = ""

    def build(self, address, port, mock, model, allowed_ports, connection) -> Any:
        raise NotImplementedError

    def connect(self, instrument) -> Dict[str, Any]:
        """Connect, then return {"idn", "model", "dialect", "num_channels"}."""
        raise NotImplementedError

    def poll(self, instrument, publish: Callable[[Dict[str, Any]], None], tick: int) -> None:
        """Publish whatever this kind emits per tick. Called on the worker thread."""
        raise NotImplementedError

    def close(self, instrument) -> None:
        raise NotImplementedError


class ScopeAdapter(InstrumentAdapter):
    kind = "scope"

    def __init__(self) -> None:
        self.measurements: List[Tuple[int, str]] = []
        # Server-owned analysis config. Request coroutines swap these whole
        # dicts atomically (never mutate in place); the worker thread only reads.
        self.spectrum_config: Dict[str, Any] = {"enabled": False, "channel": 1, "window": "hanning", "db": True}
        self.filters: Dict[int, Dict[str, Any]] = {n: {"source": 1, "kind": "lowpass", "cutoff_low": None, "cutoff_high": None, "order": 5, "enabled": False} for n in (1, 2)}
        self.active_reference: Optional[Dict[str, Any]] = None  # {"name", "channel", "data": {"time","voltage",...}}
        self._shown: set = set()  # trace keys (M1/M2/F1/F2/SPEC) live on subscribers' canvases; worker-thread-only
        self.recorder = TrendRecorder()  # internally locked: worker appends, request threads control/read

    def build(self, address, port, mock, model, allowed_ports, connection):
        if mock:
            conn = connection if connection is not None else make_mock_scope_connection(model)
            return Oscilloscope("mock", connection=conn)
        if not address:
            raise ValueError("address is required for a non-mock session")
        validate_target(address, port, allowed_ports=allowed_ports)
        return Oscilloscope(address, port=port)

    def connect(self, instrument):
        instrument.connect()
        info = instrument.device_info or {}
        return {
            "idn": instrument.identify(),
            "model": info.get("model", ""),
            "dialect": instrument.dialect or "",
            "num_channels": len(instrument.supported_channels),
        }

    def poll(self, instrument, publish, tick):
        scope = instrument
        shown = self._shown
        acquired = {}
        for n in scope.supported_channels:
            ch = scope.get_channel(n)
            if ch is not None and _safe(lambda: ch.enabled, default=False):
                data = scope.get_waveform(n, provenance=False)
                acquired["C{0}".format(n)] = data
                publish(_decimate_frame(n, data.time, data.voltage))
        shown_now = set()
        for label, math in (("M1", scope.math1), ("M2", scope.math2)):
            result = None
            if math is not None and _safe(lambda: math.enabled, default=False):
                result = _safe(lambda: math.compute(acquired))
            if result is not None:
                publish(_decimate_frame(label, result.time, result.voltage))
                shown_now.add(label)
            elif label in shown:
                publish(_decimate_frame(label, [], []))  # one-shot clear on transition
        filters = self.filters
        for n in sorted(filters):
            config = filters[n]
            label = "F{0}".format(n)
            result = _quiet(lambda: compute.filtered_waveform(config, acquired)) if config["enabled"] else None
            if result is not None:
                publish(_decimate_frame(label, result.time, result.voltage))
                shown_now.add(label)
            elif label in shown:
                publish(_decimate_frame(label, [], []))
        spectrum_config = self.spectrum_config
        frame = _quiet(lambda: compute.spectrum_frame(spectrum_config, acquired)) if spectrum_config["enabled"] else None
        if frame is not None:
            publish(frame)
            shown_now.add("SPEC")
        elif "SPEC" in shown:
            publish(compute.empty_spectrum_frame(spectrum_config))
        self._shown = shown_now
        if tick % MEASUREMENT_EVERY_N_POLLS == 0:
            if self.measurements:
                now = time.time()
                values = []
                for channel, mtype in self.measurements:
                    value = _safe(lambda: scope.measurement.measure(mtype, channel))
                    values.append({"channel": channel, "mtype": mtype, "value": value})
                publish({"type": "measurements", "values": values, "timestamp": now})
                self.recorder.append(now, [entry["value"] for entry in values])
            reference = self.active_reference  # snapshot for thread safety
            if reference is not None:
                publish(compute.reference_stats(reference, acquired))

    def close(self, instrument):
        instrument.disconnect()

    def set_measurements(self, items: List[Tuple[int, str]], publish: Callable[[Dict[str, Any]], None]) -> None:
        self.measurements = list(items)
        publish({"type": "measurements_config", "items": [{"channel": c, "mtype": m} for c, m in self.measurements]})

    def start_recording(self, publish: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
        # Local import: sessions.py imports this module at top level, so a
        # module-level import of SessionError back from sessions.py here would
        # be circular. By call time sessions.py is fully loaded.
        from scpi_control.server.sessions import SessionError

        if self.recorder.state == "recording":
            raise SessionError("already recording")
        if not self.measurements:
            raise InvalidParameterError("no measurements selected")
        self.recorder.start(list(self.measurements), time.time())
        self._publish_log_status(publish)
        return self.recorder.status()

    def stop_recording(self, publish: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
        self.recorder.stop()
        self._publish_log_status(publish)
        return self.recorder.status()

    def _publish_log_status(self, publish: Callable[[Dict[str, Any]], None]) -> None:
        status = self.recorder.status()
        publish({"type": "log_status", "state": status["state"], "started_at": status["started_at"], "row_count": status["row_count"], "columns": status["columns"]})

    def reference_overlay(self) -> Dict[str, Any]:
        active = self.active_reference
        if active is None:
            return {"name": None, "channel": None, "t0": 0.0, "dt": 1.0, "points": []}
        frame = _decimate_frame(active["channel"], active["data"]["time"], active["data"]["voltage"])
        return {"name": active["name"], "channel": active["channel"], "t0": frame["t0"], "dt": frame["dt"], "points": frame["points"]}

    def set_active_reference(self, name: Optional[str], channel: Optional[int], data: Optional[Dict[str, Any]], publish: Callable[[Dict[str, Any]], None]) -> None:
        self.active_reference = None if name is None else {"name": name, "channel": channel, "data": data}
        publish({"type": "reference", **self.reference_overlay()})


ADAPTERS: Dict[str, type] = {"scope": ScopeAdapter}
