"""Instrument session layer: one worker thread per instrument.

All SCPI I/O for a session happens on its single worker thread (FIFO job
queue), so compound operations are atomic and the non-thread-safe connection
is never shared across threads (AUDIT.md C2). This module is FastAPI-free:
the API layer adapts the returned concurrent.futures.Future to asyncio.
"""

import queue
import threading
import time
import uuid
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any, Callable, Dict, List, Optional, Tuple

from scpi_control import Oscilloscope
from scpi_control.connection.mock import MockConnection
from scpi_control.exceptions import InvalidParameterError, SiglentConnectionError, SiglentError
from scpi_control.server import compute
from scpi_control.server.recorder import TrendRecorder

MAX_FRAME_POINTS = 2000
MEASUREMENT_EVERY_N_POLLS = 4


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


_STOP = object()

DEFAULT_MOCK_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"


class SessionError(RuntimeError):
    """Session is not in a state that can accept jobs (maps to HTTP 409)."""


def _make_mock_connection(model: Optional[str]) -> MockConnection:
    idn = DEFAULT_MOCK_IDN if model is None else "Siglent Technologies,{0},MOCK0001,1.0.0.0".format(model)
    # No explicit waveform_payloads: channels serve state-coupled synthesized
    # signals (connection/mock/synth.py). 1 MSa/s x 14 div x 1 ms/div = 14k points.
    return MockConnection("mock", idn=idn, channel_states={1: True, 2: False, 3: False, 4: False}, trigger_status=["Stop"], sample_rate=1_000_000.0, timebase=1e-3)


class InstrumentSession:
    def __init__(self, label: str, scope: Oscilloscope, mock: bool, address: Optional[str], poll_interval: float):
        self.id = uuid.uuid4().hex[:8]
        self.label = label
        self.mock = mock
        self.address = address
        self.state = "connecting"
        self.idn = ""
        self.model = ""
        self.dialect = ""
        self.num_channels = 0
        self.error_detail: Optional[str] = None
        self._scope = scope
        self._poll_interval = poll_interval
        self._queue: "queue.Queue" = queue.Queue()
        self._closed = threading.Event()
        self._thread = threading.Thread(target=self._worker, name="scpi-session-{0}".format(self.id), daemon=True)
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []
        self._subscribers_lock = threading.Lock()
        self.measurements: List[Tuple[int, str]] = []
        self._poll_count = 0
        # Server-owned analysis config. Request coroutines swap these whole
        # dicts atomically (never mutate in place); the worker thread only reads.
        self.spectrum_config: Dict[str, Any] = {"enabled": False, "channel": 1, "window": "hanning", "db": True}
        self.filters: Dict[int, Dict[str, Any]] = {n: {"source": 1, "kind": "lowpass", "cutoff_low": None, "cutoff_high": None, "order": 5, "enabled": False} for n in (1, 2)}
        self.active_reference: Optional[Dict[str, Any]] = None  # {"name", "channel", "data": {"time","voltage",...}}
        self._shown: set = set()  # trace keys (M1/M2/F1/F2/SPEC) live on subscribers' canvases; worker-thread-only
        self.recorder = TrendRecorder()  # internally locked: worker appends, request threads control/read

    @classmethod
    def open(
        cls,
        label: str,
        *,
        address: Optional[str] = None,
        port: int = 5025,
        mock: bool = False,
        model: Optional[str] = None,
        poll_interval: float = 0.25,
        _connection=None,
    ) -> "InstrumentSession":
        if mock:
            conn = _connection if _connection is not None else _make_mock_connection(model)
            scope = Oscilloscope("mock", connection=conn)
        else:
            if not address:
                raise ValueError("address is required for a non-mock session")
            scope = Oscilloscope(address, port=port)
        session = cls(label, scope, mock, address, poll_interval)
        session._thread.start()
        try:
            session.submit(session._connect_job).result(timeout=30)
        except FuturesTimeoutError:
            # A hung connect leaves a worker parked on the socket; close then
            # surface it as a domain error rather than a bare futures timeout.
            session.close()
            raise SiglentConnectionError("connect timed out")
        except BaseException:
            session.close()
            raise
        return session

    def _connect_job(self, scope: Oscilloscope) -> None:
        scope.connect()
        self.idn = scope.identify()
        info = scope.device_info or {}
        self.model = info.get("model", "")
        self.dialect = scope.dialect or ""
        self.num_channels = len(scope.supported_channels)
        self.state = "connected"

    def submit(self, fn: Callable[[Oscilloscope], Any]) -> "Future":
        if self._closed.is_set() or self.state == "error":
            # spec: mutations on a dead session are 409 until it is deleted
            raise SessionError("session {0} is {1}".format(self.id, self.state))
        future: Future = Future()
        self._queue.put((fn, future))
        return future

    def close(self, timeout: float = 10.0) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        self._queue.put(_STOP)
        self._thread.join(timeout=timeout)
        self.state = "closed"
        # Tell any live streams the session is gone. Publishing from the closing
        # thread is safe: subscribers only schedule via call_soon_threadsafe.
        self.publish({"type": "closed"})

    @property
    def viewers(self) -> int:
        with self._subscribers_lock:
            return len(self._subscribers)

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> Callable[[], None]:
        with self._subscribers_lock:
            self._subscribers.append(callback)

        def unsubscribe() -> None:
            with self._subscribers_lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)

        return unsubscribe

    def publish(self, message: Dict[str, Any]) -> None:
        with self._subscribers_lock:
            subscribers = list(self._subscribers)
        for callback in subscribers:
            try:
                callback(message)
            except Exception:  # a broken subscriber must not kill the worker thread
                continue

    def set_measurements(self, items: List[Tuple[int, str]]) -> None:
        self.measurements = list(items)
        self.publish({"type": "measurements_config", "items": [{"channel": c, "mtype": m} for c, m in self.measurements]})

    def start_recording(self) -> Dict[str, Any]:
        if self.recorder.state == "recording":
            raise SessionError("already recording")
        if not self.measurements:
            raise InvalidParameterError("no measurements selected")
        self.recorder.start(list(self.measurements), time.time())
        self._publish_log_status()
        return self.recorder.status()

    def stop_recording(self) -> Dict[str, Any]:
        self.recorder.stop()
        self._publish_log_status()
        return self.recorder.status()

    def _publish_log_status(self) -> None:
        status = self.recorder.status()
        self.publish({"type": "log_status", "state": status["state"], "started_at": status["started_at"], "row_count": status["row_count"], "columns": status["columns"]})

    def reference_overlay(self) -> Dict[str, Any]:
        active = self.active_reference
        if active is None:
            return {"name": None, "channel": None, "t0": 0.0, "dt": 1.0, "points": []}
        frame = _decimate_frame(active["channel"], active["data"]["time"], active["data"]["voltage"])
        return {"name": active["name"], "channel": active["channel"], "t0": frame["t0"], "dt": frame["dt"], "points": frame["points"]}

    def set_active_reference(self, name: Optional[str], channel: Optional[int], data: Optional[Dict[str, Any]]) -> None:
        self.active_reference = None if name is None else {"name": name, "channel": channel, "data": data}
        self.publish({"type": "reference", **self.reference_overlay()})

    def _enter_error_state(self, detail: str) -> None:
        """Flip to the terminal error state and tell the streams once."""
        self.state = "error"
        self.error_detail = detail
        self.publish({"type": "error", "detail": detail})

    def _worker(self) -> None:
        while True:
            try:
                item = self._queue.get(timeout=self._poll_interval)
            except queue.Empty:
                self._poll_tick()
                continue
            if item is _STOP:
                break
            fn, future = item
            if not future.set_running_or_notify_cancel():
                continue
            try:
                future.set_result(fn(self._scope))
            except BaseException as exc:  # propagate everything to the caller
                future.set_exception(exc)
                # A SiglentError from a dropped wire is a session-fatal event:
                # flip to "error" so REST mutations start returning 409.
                if isinstance(exc, SiglentError) and not self._scope.is_connected:
                    self._enter_error_state(str(exc))
        # Drain jobs that raced in behind _STOP so their callers get a clean 409
        # instead of an await that never resolves.
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            if item is _STOP:
                continue
            fn, future = item
            if not future.set_running_or_notify_cancel():
                continue
            future.set_exception(SessionError("session {0} is closed".format(self.id)))
        try:
            self._scope.disconnect()
        except SiglentError:
            pass

    def _poll_tick(self) -> None:
        with self._subscribers_lock:
            if not self._subscribers:
                return
        if self.state != "connected":
            return
        if not self._scope.is_connected:
            # The wire dropped while idle (no job in flight to surface it).
            self._enter_error_state("connection lost")
            return
        self._poll_count += 1
        scope = self._scope
        try:
            acquired = {}
            for n in scope.supported_channels:
                ch = scope.get_channel(n)
                if ch is not None and _safe(lambda: ch.enabled, default=False):
                    data = scope.get_waveform(n, provenance=False)
                    acquired["C{0}".format(n)] = data
                    self.publish(_decimate_frame(n, data.time, data.voltage))
            shown_now = set()
            for label, math in (("M1", scope.math1), ("M2", scope.math2)):
                result = None
                if math is not None and _safe(lambda: math.enabled, default=False):
                    result = _safe(lambda: math.compute(acquired))
                if result is not None:
                    self.publish(_decimate_frame(label, result.time, result.voltage))
                    shown_now.add(label)
                elif label in self._shown:
                    self.publish(_decimate_frame(label, [], []))  # one-shot clear on transition
            for n in sorted(self.filters):
                config = self.filters[n]
                label = "F{0}".format(n)
                result = _quiet(lambda: compute.filtered_waveform(config, acquired)) if config["enabled"] else None
                if result is not None:
                    self.publish(_decimate_frame(label, result.time, result.voltage))
                    shown_now.add(label)
                elif label in self._shown:
                    self.publish(_decimate_frame(label, [], []))
            spectrum_config = self.spectrum_config  # snapshot: request threads swap the dict atomically
            frame = _quiet(lambda: compute.spectrum_frame(spectrum_config, acquired)) if spectrum_config["enabled"] else None
            if frame is not None:
                self.publish(frame)
                shown_now.add("SPEC")
            elif "SPEC" in self._shown:
                self.publish(compute.empty_spectrum_frame(spectrum_config))
            self._shown = shown_now
            if self._poll_count % MEASUREMENT_EVERY_N_POLLS == 0:
                if self.measurements:
                    now = time.time()
                    values = []
                    for channel, mtype in self.measurements:
                        value = _safe(lambda: scope.measurement.measure(mtype, channel))
                        values.append({"channel": channel, "mtype": mtype, "value": value})
                    self.publish({"type": "measurements", "values": values, "timestamp": now})
                    self.recorder.append(now, [entry["value"] for entry in values])
                reference = self.active_reference  # snapshot for thread safety
                if reference is not None:
                    self.publish(compute.reference_stats(reference, acquired))
        except SiglentError as exc:
            self.error_detail = str(exc)
            self.publish({"type": "error", "detail": str(exc)})
            if not scope.is_connected:
                self.state = "error"


class SessionManager:
    """Registry of live sessions. create() connects before registering."""

    def __init__(self) -> None:
        self._sessions: Dict[str, InstrumentSession] = {}
        self._lock = threading.Lock()

    def create(self, label: str, *, address: Optional[str] = None, port: int = 5025, mock: bool = False, model: Optional[str] = None, _connection=None) -> InstrumentSession:
        session = InstrumentSession.open(label, address=address, port=port, mock=mock, model=model, _connection=_connection)
        with self._lock:
            self._sessions[session.id] = session
        return session

    def list(self) -> List[InstrumentSession]:
        with self._lock:
            return list(self._sessions.values())

    def get(self, session_id: str) -> Optional[InstrumentSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        session.close()
        return True

    def close_all(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.close()
