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
from collections import Counter
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any, Callable, Dict, List, Optional

from scpi_control.exceptions import SiglentConnectionError, SiglentError
from scpi_control.server.adapters import ADAPTERS, MAX_FRAME_POINTS, _waveform_frame, read_state  # noqa: F401  (re-exported: stream.py/api/scope.py and tests import these from here)
from scpi_control.server.adapters import make_mock_scope_connection as _make_mock_connection  # noqa: F401  (re-exported for backward compatibility)

_STOP = object()


class SessionError(RuntimeError):
    """Session is not in a state that can accept jobs (maps to HTTP 409)."""


class InstrumentSession:
    def __init__(self, label: str, instrument: Any, mock: bool, address: Optional[str], poll_interval: float, adapter: Any):
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
        self.adapter = adapter
        self._instrument = instrument
        self._poll_interval = poll_interval
        self._queue: "queue.Queue" = queue.Queue()
        self._closed = threading.Event()
        self._thread = threading.Thread(target=self._worker, name="scpi-session-{0}".format(self.id), daemon=True)
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []
        self._subscribers_lock = threading.Lock()
        self._poll_count = 0
        self.owner = ""
        self.owner_last_active = time.monotonic()
        # Live stream watchers, keyed by identity (not by "is this the
        # owner"): a Counter rather than a set because the same identity may
        # open two tabs and close one, so a plain membership test would drop
        # the identity on the first close while the second tab is still live.
        self._watchers: "Counter[str]" = Counter()

    def touch(self) -> None:
        """Record owner activity; feeds the abandoned-session claim rule."""
        self.owner_last_active = time.monotonic()

    def owner_watching(self) -> bool:
        """True while at least one live stream opened by the current owner is connected.

        Evaluated at check time against the *current* owner and the live
        per-identity watcher counts (see mark_owner_watching) -- never a
        snapshot taken when some stream connected. Ownership can change
        mid-stream via claim() or an explicit handoff, so "is the owner
        watching" must always be asked fresh: a snapshot fails open (a
        non-owner who claims the session while already watching would not
        be protected) and also sticks stale (a former owner's lingering
        socket would keep blocking claims after handoff).

        A watching owner is never idle even though only writes touch()
        owner_last_active -- the claim rule refuses outright while this is
        true, regardless of the idle threshold.
        """
        return bool(self.owner) and self._watchers[self.owner] > 0

    def mark_owner_watching(self, identity: str) -> Callable[[], None]:
        """Register that ``identity`` opened the live stream; returns an unmark callback.

        Tracks the watching identity itself, not whether it happened to be
        the owner at connect time -- owner_watching() does that comparison
        later, at check time, against whoever owns the session *then*. The
        returned callback decrements exactly once no matter how many times
        it is called, so it is safe to invoke unconditionally from a
        ``finally`` block on any disconnect path (clean close, error, or
        cancellation).
        """
        self._watchers[identity] += 1
        released = False

        def unmark() -> None:
            nonlocal released
            if not released:
                released = True
                self._watchers[identity] -= 1
                if self._watchers[identity] <= 0:
                    del self._watchers[identity]

        return unmark

    @classmethod
    def open(
        cls,
        label: str,
        *,
        kind: str = "scope",
        address: Optional[str] = None,
        port: int = 5025,
        mock: bool = False,
        model: Optional[str] = None,
        poll_interval: float = 0.25,
        owner: str = "",
        allowed_ports: Optional[frozenset] = None,
        _connection=None,
    ) -> "InstrumentSession":
        adapter = ADAPTERS[kind]()
        instrument = adapter.build(address=address, port=port, mock=mock, model=model, allowed_ports=allowed_ports, connection=_connection)
        session = cls(label, instrument, mock, address, poll_interval, adapter)
        session.owner = owner
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

    @property
    def _scope(self) -> Any:
        """Alias kept for the mechanical Task 3 rename; use ``_instrument``."""
        return self._instrument

    def _connect_job(self, instrument: Any) -> None:
        info = self.adapter.connect(instrument)
        self.idn = info["idn"]
        self.model = info["model"]
        self.dialect = info["dialect"]
        self.num_channels = info["num_channels"]
        self.state = "connected"

    def submit(self, fn: Callable[[Any], Any]) -> "Future":
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
        if not self._instrument.is_connected:
            # The wire dropped while idle (no job in flight to surface it).
            self._enter_error_state("connection lost")
            return
        self._poll_count += 1
        try:
            self.adapter.poll(self._instrument, self.publish, self._poll_count)
        except SiglentError as exc:
            self.error_detail = str(exc)
            self.publish({"type": "error", "detail": str(exc)})
            if not self._instrument.is_connected:
                self.state = "error"


class SessionManager:
    """Registry of live sessions. create() connects before registering."""

    def __init__(self, allowed_ports: Optional[frozenset] = None, max_sessions: int = 8) -> None:
        if max_sessions < 1:
            # A cap below 1 doesn't disable the gateway -- it silently makes
            # every create() a 409 "session limit reached (0)", which reads
            # like a bug rather than a configuration mistake. Reject eagerly
            # here (the library boundary) rather than relying solely on the
            # CLI to catch it, since SessionManager is also constructed
            # directly by embedders and tests.
            raise ValueError("max_sessions must be at least 1 (got {0})".format(max_sessions))
        self._sessions: Dict[str, InstrumentSession] = {}
        self._lock = threading.Lock()
        self.allowed_ports = allowed_ports
        self.max_sessions = max_sessions
        # Slots claimed by an in-flight create() that hasn't registered yet.
        # Counted alongside len(self._sessions) under the same lock as the
        # cap check so the check and the reservation are one atomic step --
        # see create() for why that matters.
        self._pending = 0

    def create(self, label: str, *, address: Optional[str] = None, port: int = 5025, mock: bool = False, model: Optional[str] = None, owner: str = "", _connection=None) -> InstrumentSession:
        # Checked BEFORE InstrumentSession.open: opening spawns a worker thread
        # and blocks on a connect with a 30s timeout, so checking the cap after
        # the fact would let concurrent requests past the cap occupy every
        # threadpool worker anyway -- the exact exhaustion this guards against.
        #
        # The check alone isn't enough under concurrency: the lock used to be
        # released between the check and registration, so N concurrent callers
        # could all observe room and all proceed (TOCTOU) -- with a cap of 8
        # and 100 concurrent requests, all 100 pass. Reserving a slot in
        # self._pending under the SAME lock acquisition as the check closes
        # that window: each successful check immediately claims capacity, so
        # the next concurrent caller sees it.
        #
        # The reservation is released and the session registered in a SINGLE
        # lock acquisition (below), not two: releasing the lock after
        # decrementing self._pending and only later re-acquiring it to insert
        # into self._sessions would reopen the same race one step later -- in
        # that gap the slot is counted by neither self._pending nor
        # self._sessions, so a concurrent caller's check can pass when it
        # shouldn't. The `registered` flag lets the `finally` tell success
        # from failure: on success the reservation was already released
        # inside the try (alongside registration), so `finally` must not
        # double-decrement; on any failure -- open() raising from a connect
        # timeout, validate_target's policy rejection, or anything else --
        # `registered` is still False and `finally` releases the reservation,
        # so a failed attempt can never leak a slot and permanently shrink
        # the cap.
        with self._lock:
            if len(self._sessions) + self._pending >= self.max_sessions:
                raise SessionError("session limit reached ({0}); close a session first".format(self.max_sessions))
            self._pending += 1
        registered = False
        try:
            session = InstrumentSession.open(label, address=address, port=port, mock=mock, model=model, owner=owner, allowed_ports=self.allowed_ports, _connection=_connection)
            with self._lock:
                self._pending -= 1
                self._sessions[session.id] = session
                registered = True
        finally:
            if not registered:
                with self._lock:
                    self._pending -= 1
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
