"""Instrument session layer: one worker thread per instrument.

All SCPI I/O for a session happens on its single worker thread (FIFO job
queue), so compound operations are atomic and the non-thread-safe connection
is never shared across threads (AUDIT.md C2). This module is FastAPI-free:
the API layer adapts the returned concurrent.futures.Future to asyncio.
"""

import queue
import threading
import uuid
from concurrent.futures import Future
from typing import Any, Callable, Dict, List, Optional, Tuple

from scpi_control import Oscilloscope
from scpi_control.connection.mock import MockConnection
from scpi_control.exceptions import SiglentError

MAX_FRAME_POINTS = 2000
MEASUREMENT_EVERY_N_POLLS = 4


def _safe(fn, default=None):
    try:
        return fn()
    except SiglentError:
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


def _waveform_frame(scope: Oscilloscope, channel: int) -> Dict[str, Any]:
    data = scope.get_waveform(channel)
    voltage = data.voltage
    step = max(1, len(voltage) // MAX_FRAME_POINTS)
    points = voltage[::step]
    t0 = float(data.time[0]) if len(data.time) else 0.0
    dt = float(data.time[1] - data.time[0]) * step if len(data.time) > 1 else 1.0
    return {"type": "waveform", "channel": channel, "t0": t0, "dt": dt, "points": [float(v) for v in points]}


_STOP = object()

DEFAULT_MOCK_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"


class SessionError(RuntimeError):
    """Session is not in a state that can accept jobs (maps to HTTP 409)."""


def _make_mock_connection(model: Optional[str]) -> MockConnection:
    idn = DEFAULT_MOCK_IDN if model is None else "Siglent Technologies,{0},MOCK0001,1.0.0.0".format(model)
    return MockConnection("mock", idn=idn, channel_states={1: True}, trigger_status=["Stop"], sample_rate=1_000.0, timebase=1e-3)


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
            callback(message)

    def set_measurements(self, items: List[Tuple[int, str]]) -> None:
        self.measurements = list(items)

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
        self._poll_count += 1
        scope = self._scope
        try:
            for n in scope.supported_channels:
                ch = scope.get_channel(n)
                if ch is not None and _safe(lambda: ch.enabled, default=False):
                    self.publish(_waveform_frame(scope, n))
            if self.measurements and self._poll_count % MEASUREMENT_EVERY_N_POLLS == 0:
                values = []
                for channel, mtype in self.measurements:
                    value = _safe(lambda: scope.measurement.measure(mtype, channel))
                    values.append({"channel": channel, "mtype": mtype, "value": value})
                self.publish({"type": "measurements", "values": values})
        except SiglentError as exc:
            self.error_detail = str(exc)
            self.publish({"type": "error", "detail": str(exc)})
            if not scope.is_connected:
                self.state = "error"
