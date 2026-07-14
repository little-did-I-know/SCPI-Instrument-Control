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
