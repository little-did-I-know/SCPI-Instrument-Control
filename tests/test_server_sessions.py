"""Worker-thread session core. No FastAPI dependency."""

import concurrent.futures
import threading
import time
from concurrent.futures import Future

import pytest

from scpi_control.connection.mock import MockConnection
from scpi_control.exceptions import SiglentConnectionError, SiglentError
from scpi_control.server.sessions import _STOP, InstrumentSession, SessionError

LEGACY_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"


def make_mock_session(**kwargs):
    conn = MockConnection("mock", idn=LEGACY_IDN, channel_states={1: True}, trigger_status=["Stop"], sample_rate=1_000.0, timebase=1e-3)
    return InstrumentSession.open("bench-1", mock=True, _connection=conn, **kwargs), conn


class TestOpenClose:
    def test_open_connects_and_populates_info(self):
        session, _ = make_mock_session()
        try:
            assert session.state == "connected"
            assert session.model == "SDS1104X-E"
            assert session.dialect == "legacy"
            assert session.num_channels == 4
            assert "SDS1104X-E" in session.idn
            assert session.id
        finally:
            session.close()

    def test_close_is_idempotent_and_sets_state(self):
        session, _ = make_mock_session()
        session.close()
        session.close()
        assert session.state == "closed"

    def test_submit_after_close_raises(self):
        session, _ = make_mock_session()
        session.close()
        with pytest.raises(SessionError):
            session.submit(lambda scope: scope.identify())


class TestSerialization:
    def test_jobs_run_on_one_thread_in_fifo_order(self):
        session, _ = make_mock_session()
        try:
            seen_threads = set()
            order = []

            def job(tag):
                def _run(scope):
                    seen_threads.add(threading.current_thread().name)
                    order.append(tag)
                    return tag

                return _run

            futures = [session.submit(job(i)) for i in range(20)]
            results = [f.result(timeout=5) for f in futures]
            assert results == list(range(20))
            assert order == list(range(20))
            assert len(seen_threads) == 1
            assert threading.current_thread().name not in seen_threads
        finally:
            session.close()

    def test_job_exception_propagates_without_killing_worker(self):
        session, _ = make_mock_session()
        try:

            def boom(scope):
                raise ValueError("nope")

            with pytest.raises(ValueError):
                session.submit(boom).result(timeout=5)
            # worker still alive afterwards:
            assert session.submit(lambda s: s.identify()).result(timeout=5).startswith("Siglent")
        finally:
            session.close()


class FailingMock(MockConnection):
    """Constructs fine, fails at connect — models an unreachable instrument."""

    def connect(self):
        from scpi_control.exceptions import SiglentConnectionError

        raise SiglentConnectionError("boom")


def test_open_failure_raises_and_leaves_no_thread():
    before = threading.active_count()
    conn = FailingMock("mock", idn=LEGACY_IDN)
    with pytest.raises(SiglentError):
        InstrumentSession.open("bad", mock=True, _connection=conn)
    time.sleep(0.1)
    assert threading.active_count() <= before + 1


class GatedConnection(MockConnection):
    """A mock whose connect() blocks on a shared gate until the test releases it.

    Lets a test hold every concurrent InstrumentSession.open() call inside
    connect() at once, so a check-then-register race in SessionManager.create
    can be reproduced deterministically (every worker guaranteed to be
    "inside the window") instead of relying on unlucky thread scheduling.
    """

    def __init__(self, *args, gate, on_enter, **kwargs):
        super().__init__(*args, **kwargs)
        self._gate = gate
        self._on_enter = on_enter

    def connect(self):
        self._on_enter()
        self._gate.wait(timeout=10.0)
        super().connect()


class KillableMock(MockConnection):
    """A mock whose connection can be pulled mid-session, as if the wire dropped."""

    def kill(self):
        # Flip the connected flag; the base query()/write() then raise
        # SiglentConnectionError for every subsequent call, like a dead socket.
        self._connected = False


def _killable_session():
    conn = KillableMock("mock", idn=LEGACY_IDN, channel_states={1: True}, trigger_status=["Stop"], sample_rate=1_000.0, timebase=1e-3)
    return InstrumentSession.open("bench-1", mock=True, _connection=conn), conn


def _wait_for(predicate, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


class TestErrorState:
    def test_dropped_connection_flips_to_error_and_blocks_mutations(self):
        # Fix 3: a job that fails because the wire dropped must flip the session
        # to "error" and make further submits raise SessionError (-> HTTP 409).
        session, conn = _killable_session()
        try:
            conn.kill()
            with pytest.raises(SiglentError):
                session.submit(lambda scope: scope.identify()).result(timeout=5)
            assert _wait_for(lambda: session.state == "error")
            assert session.state == "error"
            with pytest.raises(SessionError):
                session.submit(lambda scope: scope.identify())
        finally:
            session.close()

    def test_idle_poll_detects_dropped_connection(self):
        # Fix 3: even with no job in flight, the poll loop must notice the drop.
        session, conn = _killable_session()
        try:
            unsubscribe = session.subscribe(lambda msg: None)
            conn.kill()
            assert _wait_for(lambda: session.state == "error")
            assert session.state == "error"
            unsubscribe()
        finally:
            session.close()


class TestCloseDrain:
    def test_close_drains_jobs_stuck_behind_stop(self):
        # Fix 4: a job that lands behind _STOP (submit/close race) must be failed
        # with SessionError on drain, not left to hang forever.
        session, _ = make_mock_session()
        gate = threading.Event()
        started = threading.Event()

        def slow(scope):
            started.set()
            gate.wait(3.0)

        session.submit(slow)
        assert started.wait(2.0)  # worker is now busy holding the slow job
        # Reproduce the race deterministically: _STOP ahead of a still-queued job.
        orphan = Future()
        session._queue.put(_STOP)
        session._queue.put((lambda scope: "never runs", orphan))
        gate.set()  # release the slow job -> worker hits _STOP, then drains
        done, _ = concurrent.futures.wait([orphan], timeout=5)
        assert orphan in done, "orphaned future hung instead of being drained"
        with pytest.raises(SessionError):
            orphan.result()
        session.close()


class TestCloseNotifiesStreams:
    def test_close_publishes_closed_message(self):
        # Fix 5 (sessions half): close() tells subscribers the session is gone.
        session, _ = make_mock_session()
        seen = []
        session.subscribe(seen.append)
        session.close()
        assert any(m.get("type") == "closed" for m in seen)


def test_open_connect_timeout_raises_connection_error(monkeypatch):
    # Fix 8: a connect that never completes surfaces as SiglentConnectionError.
    conn = MockConnection("mock", idn=LEGACY_IDN, channel_states={1: True}, trigger_status=["Stop"], sample_rate=1_000.0, timebase=1e-3)

    def fake_result(self, timeout=None):
        raise concurrent.futures.TimeoutError()

    monkeypatch.setattr(concurrent.futures.Future, "result", fake_result)
    with pytest.raises(SiglentConnectionError):
        InstrumentSession.open("t", mock=True, _connection=conn)


from scpi_control.server.sessions import SessionManager


class _StallingLock:
    """Wraps a real threading.Lock; on its Nth release, blocks the releasing
    thread until a gate opens.

    Lets a test stall SessionManager.create() at an exact lock hand-off
    (rather than relying on sleep-based timing) so a gap between two
    separate ``with self._lock:`` blocks can be reproduced deterministically.
    The real lock is released before the stall, so other threads are free to
    acquire it while the stalled thread is paused -- exactly the residual
    over-admission window under test.
    """

    def __init__(self, stall_after_release, on_stall, proceed_gate):
        self._real = threading.Lock()
        self._release_count = 0
        self._stall_after_release = stall_after_release
        self._on_stall = on_stall
        self._proceed_gate = proceed_gate
        self._stalled_once = False

    def __enter__(self):
        self._real.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._real.release()
        self._release_count += 1
        if self._release_count == self._stall_after_release and not self._stalled_once:
            self._stalled_once = True
            self._on_stall()
            self._proceed_gate.wait(timeout=10.0)


class TestSessionManager:
    def _manager_with_one(self):
        manager = SessionManager()
        conn = MockConnection("mock", idn=LEGACY_IDN, channel_states={1: True}, trigger_status=["Stop"], sample_rate=1_000.0, timebase=1e-3)
        session = manager.create("bench-1", mock=True, _connection=conn)
        return manager, session

    def test_create_registers_and_get_returns_it(self):
        manager, session = self._manager_with_one()
        try:
            assert manager.get(session.id) is session
            assert manager.list() == [session]
        finally:
            manager.close_all()

    def test_delete_closes_and_removes(self):
        manager, session = self._manager_with_one()
        assert manager.delete(session.id) is True
        assert session.state == "closed"
        assert manager.get(session.id) is None
        assert manager.delete("nope") is False

    def test_failed_create_registers_nothing(self):
        manager = SessionManager()
        conn = FailingMock("mock", idn=LEGACY_IDN)  # FailingMock defined above in this file
        with pytest.raises(SiglentError):
            manager.create("bad", mock=True, _connection=conn)
        assert manager.list() == []

    def test_failed_create_releases_its_reservation(self):
        # A failed attempt must not leak its cap reservation -- otherwise the
        # cap permanently shrinks by one per failure until restart.
        manager = SessionManager(max_sessions=2)
        for _ in range(3):
            conn = FailingMock("mock", idn=LEGACY_IDN)
            with pytest.raises(SiglentError):
                manager.create("bad", mock=True, _connection=conn)
        try:
            for i in range(2):
                conn = MockConnection("mock", idn=LEGACY_IDN, channel_states={1: True}, trigger_status=["Stop"], sample_rate=1_000.0, timebase=1e-3)
                assert manager.create("ok-{0}".format(i), mock=True, _connection=conn) is not None
            with pytest.raises(SessionError):
                manager.create("over", mock=True, _connection=MockConnection("mock", idn=LEGACY_IDN))
        finally:
            manager.close_all()

    def test_concurrent_create_never_exceeds_the_cap(self):
        # TOCTOU regression: SessionManager.create used to check the cap and
        # release the lock before InstrumentSession.open() ran, so N
        # concurrent callers could all observe room and all proceed. Force
        # the race deterministically by gating every connect() behind a
        # threading.Event: no create() call can register a session until the
        # gate opens, so every worker is guaranteed to have made (or been
        # denied) its cap check before any of them can succeed -- regardless
        # of scheduling order.
        cap = 3
        workers = 9
        manager = SessionManager(max_sessions=cap)
        gate = threading.Event()
        state_lock = threading.Lock()
        counters = {"entered": 0, "finished": 0}

        def on_enter():
            with state_lock:
                counters["entered"] += 1

        def make_conn():
            return GatedConnection("mock", idn=LEGACY_IDN, channel_states={1: True}, trigger_status=["Stop"], sample_rate=1_000.0, timebase=1e-3, gate=gate, on_enter=on_enter)

        outcomes = []
        outcomes_lock = threading.Lock()

        def worker(i):
            try:
                session = manager.create("bench-{0}".format(i), mock=True, _connection=make_conn())
                with outcomes_lock:
                    outcomes.append(session)
            except SessionError:
                pass
            finally:
                with state_lock:
                    counters["finished"] += 1

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(worker, i) for i in range(workers)]
                # Quiescence point: every worker is either blocked in connect()
                # (having already passed the cap check) or has already been
                # rejected by it. No thread can register while the gate is
                # shut, so this condition is reachable regardless of whether
                # the fix is present -- it never depends on beating a race.
                reached = _wait_for(lambda: counters["entered"] + counters["finished"] >= workers, timeout=5.0)
                gate.set()  # always release, even on a timed-out wait, to avoid hanging workers
                assert reached, "workers did not reach the gate/rejection quiescence point in time"
                done, not_done = concurrent.futures.wait(futures, timeout=10.0)
                assert not not_done, "a worker did not finish after the gate opened"

            assert len(outcomes) == cap, "successful creations ({0}) did not match the cap ({1})".format(len(outcomes), cap)
        finally:
            gate.set()
            manager.close_all()

    def test_no_over_admission_window_between_pending_release_and_registration(self):
        # MEDIUM 1: the reservation used to be decremented (under the lock),
        # the lock released, and only then re-acquired to register the
        # session -- a gap during which the slot is counted by neither
        # self._sessions nor self._pending. Stall a creator exactly there
        # (after the pending-decrement release, before the register
        # acquire) via a lock wrapper that blocks on its Nth release, and
        # prove a concurrent create() is wrongly admitted while cap=1.
        manager = SessionManager(max_sessions=1)
        stalled = threading.Event()
        proceed = threading.Event()
        # Release #1 is the initial check+reserve block; release #2 is the
        # pending-decrement block that runs right after InstrumentSession.open
        # returns. Stalling there -- before the registration block's own
        # acquire -- lands the stalled thread exactly in the window under test.
        manager._lock = _StallingLock(stall_after_release=2, on_stall=stalled.set, proceed_gate=proceed)

        result = {}

        def first():
            conn = MockConnection("mock", idn=LEGACY_IDN, channel_states={1: True}, trigger_status=["Stop"], sample_rate=1_000.0, timebase=1e-3)
            result["first"] = manager.create("first", mock=True, _connection=conn)

        t = threading.Thread(target=first)
        t.start()
        try:
            assert stalled.wait(timeout=5.0), "first creator never reached the post-decrement window"
            conn2 = MockConnection("mock", idn=LEGACY_IDN, channel_states={1: True}, trigger_status=["Stop"], sample_rate=1_000.0, timebase=1e-3)
            with pytest.raises(SessionError):
                manager.create("second", mock=True, _connection=conn2)
        finally:
            proceed.set()
            t.join(timeout=5.0)
            manager.close_all()

    def test_open_never_called_when_cap_already_full(self, monkeypatch):
        # MEDIUM 2: the cap check must run BEFORE InstrumentSession.open --
        # open() spawns a worker thread and blocks on a 30s connect, so
        # checking afterwards would let a full-cap caller pay that cost (and
        # tie up a threadpool worker) anyway. Only ordering in create()
        # enforces this; spy on open() to prove it is never reached once the
        # cap is full, rather than just checking the resulting session count.
        manager = SessionManager(max_sessions=1)
        conn = MockConnection("mock", idn=LEGACY_IDN, channel_states={1: True}, trigger_status=["Stop"], sample_rate=1_000.0, timebase=1e-3)
        manager.create("first", mock=True, _connection=conn)

        calls = []
        original_open = InstrumentSession.open

        def spy(*args, **kwargs):
            calls.append((args, kwargs))
            return original_open(*args, **kwargs)

        monkeypatch.setattr(InstrumentSession, "open", spy)
        try:
            conn2 = MockConnection("mock", idn=LEGACY_IDN, channel_states={1: True}, trigger_status=["Stop"], sample_rate=1_000.0, timebase=1e-3)
            with pytest.raises(SessionError):
                manager.create("second", mock=True, _connection=conn2)
            assert calls == [], "InstrumentSession.open must not be called once the cap is already full"
        finally:
            manager.close_all()

    @pytest.mark.parametrize("max_sessions", [0, -1])
    def test_rejects_non_positive_max_sessions(self, max_sessions):
        # LOW 5: max_sessions < 1 yields a gateway that refuses every create()
        # with a 409 -- a footgun that looks like a crash. Reject it eagerly.
        with pytest.raises(ValueError):
            SessionManager(max_sessions=max_sessions)

    def test_create_with_an_unknown_kind_fails_cleanly(self):
        # The guard in InstrumentSession.open checks `kind not in ADAPTERS`
        # before ADAPTERS[kind]() is ever evaluated, so a garbage kind must
        # raise SessionError (-> HTTP 409), not a bare KeyError (-> HTTP 500).
        # No connection/hardware needed: the check fires before build() runs.
        manager = SessionManager()
        try:
            with pytest.raises(SessionError):
                manager.create("x", kind="bogus", mock=True)
            assert manager.list() == []
        finally:
            manager.close_all()


class TestKindMismatchGuard:
    def test_a_misreporting_instrument_is_rejected(self):
        # The kind-mismatch guard in _connect_job compares classify(self.model)
        # against self.kind for any non-mock session. Reachable without real
        # hardware by constructing InstrumentSession directly (bypassing
        # .open()/adapter.build()) with mock=False and a PowerSupply wrapping a
        # MockConnection(psu_mode=True, ...): the instrument genuinely reports
        # "SPD3303X" via *IDN?, which classify() resolves to "psu", while the
        # session's own `kind` (left at the InstrumentSession.__init__ default
        # of "scope" since open() was bypassed) says otherwise -- the exact
        # "instrument silently misreports its own kind" case the guard exists for.
        from scpi_control.power_supply import PowerSupply
        from scpi_control.server.adapters import PsuAdapter

        conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,1.0")
        instrument = PowerSupply("mock", connection=conn)
        session = InstrumentSession("bench-1", instrument, False, "10.0.0.5", 0.25, PsuAdapter())
        assert session.kind == "scope"  # the untouched __init__ default
        with pytest.raises(SessionError):
            session._connect_job(instrument)

    def test_an_unregistered_scope_model_still_connects(self):
        # The guard must reject a POSITIVE identification as another kind, not
        # whitelist MODEL_REGISTRY. classify() answers "unknown" for every
        # model outside the registry's 22 entries -- a Rigol DS1054Z, a Tek
        # TBS1052B, an unlisted Siglent -- and all of those connected fine via
        # the generic/legacy dialect fallback before the per-kind split. If the
        # guard compares `detected != self.kind` they all start failing with
        # "connected instrument is a unknown, not a scope", which would be a
        # breaking change to the pre-existing scope path.
        #
        # Non-mock (mock=True skips the guard entirely) and constructed
        # directly so no socket is opened, same technique as the test above.
        from scpi_control.oscilloscope import Oscilloscope
        from scpi_control.server.adapters import ScopeAdapter
        from scpi_control.server.discovery import classify

        conn = MockConnection("mock", idn="RIGOL TECHNOLOGIES,DS1054Z,DS1ZA000000000,00.04.04", channel_states={1: True}, trigger_status=["Stop"], sample_rate=1_000.0, timebase=1e-3)
        instrument = Oscilloscope("mock", connection=conn)
        session = InstrumentSession("bench-1", instrument, False, "10.0.0.5", 0.25, ScopeAdapter())
        session._connect_job(instrument)
        assert session.model == "DS1054Z"
        assert classify(session.model) == "unknown", "fixture no longer exercises the unregistered-model path"
        assert session.state == "connected"


class TestBackwardCompatibleScopeSurface:
    """5.8.0 moved scope-only state onto ScopeAdapter. It must stay reachable.

    ``set_measurements``/``start_recording``/``stop_recording``/``recorder``/
    ``measurements``/``spectrum_config``/``filters``/``active_reference``/
    ``reference_overlay``/``set_active_reference`` were public names on a
    public class in 5.7.1 -- the shipped trend-logging example used four of
    them. Removing them would make this release a MAJOR, so they survive as
    thin delegations to the adapter.
    """

    def test_the_v5_7_1_scope_surface_still_works(self):
        session, _ = make_mock_session()
        try:
            session.set_measurements([(1, "PKPK"), (1, "FREQ")])
            assert session.measurements == [(1, "PKPK"), (1, "FREQ")]
            assert session.recorder is session.adapter.recorder
            assert session.start_recording()["state"] == "recording"
            assert session.stop_recording()["state"] == "idle"
            assert session.recorder.rows_since() == []
            assert session.reference_overlay()["name"] is None
            session.set_active_reference("golden", 1, {"time": [0.0, 1.0], "voltage": [0.5, 1.5]})
            assert session.active_reference["name"] == "golden"
            assert session.reference_overlay()["name"] == "golden"
            assert session.spectrum_config["enabled"] is False
            session.spectrum_config = {**session.spectrum_config, "enabled": True}
            assert session.spectrum_config["enabled"] is True
            assert sorted(session.filters) == [1, 2]
            session.filters = {**session.filters, 1: {**session.filters[1], "enabled": True}}
            assert session.filters[1]["enabled"] is True
        finally:
            session.close()

    def test_the_shims_delegate_and_keep_no_state_on_the_session(self):
        # A shim that stored its own copy would undo the point of the move: a
        # PSU session would carry scope state again, and the two copies would
        # drift the moment a route wrote through session.adapter (which every
        # /scope/ route does). Assert the write lands on the ADAPTER and that
        # the session's own __dict__ never grows the attribute.
        session, _ = make_mock_session()
        try:
            session.set_measurements([(2, "RMS")])
            session.spectrum_config = {**session.spectrum_config, "channel": 3}
            for name in ("measurements", "spectrum_config", "filters", "active_reference", "recorder"):
                assert name not in vars(session), "{0} must live on the adapter, not on the session".format(name)
            assert session.adapter.measurements == [(2, "RMS")]
            assert session.adapter.spectrum_config["channel"] == 3
            # And the read side really is the adapter's object, not a copy.
            assert session.measurements is session.adapter.measurements
            assert session.filters is session.adapter.filters
        finally:
            session.close()

    def test_the_adapter_argument_is_optional(self):
        # The pre-5.8 constructor took five positional arguments. Anyone who
        # built a session by hand must not have to learn about adapters.
        conn = MockConnection("mock", idn=LEGACY_IDN, channel_states={1: True}, trigger_status=["Stop"], sample_rate=1_000.0, timebase=1e-3)
        from scpi_control.oscilloscope import Oscilloscope

        session = InstrumentSession("bench-1", Oscilloscope("mock", connection=conn), True, None, 0.25)
        assert session.adapter.kind == "scope"
        assert session.kind == "scope"


class TestAdapterLifecycleHooks:
    def test_worker_teardown_goes_through_the_adapters_close_hook(self):
        # _worker used to call self._scope.disconnect() directly. Identical
        # behaviour for the two kinds that exist -- both adapters only
        # disconnect -- but it left InstrumentAdapter.close() dead, so a kind
        # whose teardown needs more (an AWG de-energising before disconnect)
        # would silently skip it.
        session, _ = make_mock_session()
        closed = []
        real_close = session.adapter.close

        def recording_close(instrument):
            closed.append(instrument)
            real_close(instrument)

        session.adapter.close = recording_close
        session.close()
        assert closed == [session._instrument], "teardown must call adapter.close(), not the instrument's disconnect() directly"

    def test_a_non_siglent_error_from_poll_becomes_a_visible_error_state(self):
        # _poll_tick only caught SiglentError, so anything else out of
        # adapter.poll escaped _worker: the thread died, no error frame was
        # ever published, and the session read "connected" forever behind a
        # stream that had simply gone quiet.
        session, _ = make_mock_session()
        frames = []
        try:
            session.subscribe(frames.append)  # _poll_tick is a no-op with no subscribers

            def _boom(_instrument, _publish, _tick):
                raise ValueError("a numpy edge case, not a wire problem")

            session.adapter.poll = _boom
            assert _wait_for(lambda: session.state == "error"), "a poll failure must surface as an error state, not a dead worker thread"
            assert any(m.get("type") == "error" for m in frames), "the streams must be told, not just session.state"
            assert session._thread.is_alive(), "the worker must survive to report the failure"
        finally:
            session.close()
