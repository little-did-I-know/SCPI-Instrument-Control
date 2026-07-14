"""Worker-thread session core. No FastAPI dependency."""

import threading
import time

import pytest

from scpi_control.connection.mock import MockConnection
from scpi_control.exceptions import SiglentError
from scpi_control.server.sessions import InstrumentSession, SessionError

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
