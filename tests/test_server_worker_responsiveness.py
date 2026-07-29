"""The regression test this whole sub-project exists for, and its backoff.

InstrumentSession._worker is one loop per session: while the job queue is
empty it waits ``timeout=poll_interval`` and then runs a poll tick -- and a
poll tick that blocks inside a waveform read (a real Siglent at a slow
timebase can take well over a second) leaves the worker unable to service
ANY queued job for as long as the read takes. Every control in the web UI --
a channel toggle, Run/Stop, ``/scope/state`` -- hangs for the length of the
capture.

Task 4's readiness gate (ScopeAdapter.poll: ``new_acquisition_ready()``) fixes
this by never STARTING the blocking read on a tick that has nothing new to
report. The test below proves that: a scope reporting "no new acquisition"
must let a queued job run promptly, and the read that would have starved it
must be the one thing standing between "prompt" and "starved" -- not a race
against how fast the test happens to submit the job.

``MockConnection(waveform_gate=...)`` (Task 2) is what makes the would-be
blocking read reproducible without sleeping: the read blocks until the test
releases the gate.
"""

import threading

import pytest

from scpi_control.connection.mock import MockConnection
from scpi_control.server.adapters import ADAPTERS
from scpi_control.server.sessions import InstrumentSession

# A dialect new_acquisition_ready() can actually answer (Task 1): the modern
# SDS824X HD, whose INR? bit 0 the gate reads. The legacy dialect has no such
# command and new_acquisition_ready() always returns None there, which would
# make `ready=False` impossible to construct.
MODERN_IDN = "Siglent Technologies,SDS824X HD,SDS08A0X804831,3.8.12.1.1.3.6"


def _mock_session(waveform_gate, ready, poll_interval=0.05):
    """A connected mock scope session whose waveform-data read blocks on
    ``waveform_gate`` and whose ``new_acquisition_ready()`` answers a fixed
    ``ready`` forever (a constant scalar in MockConnection.custom_responses,
    not a list, so every INR? query gets the same reply).
    """
    conn = MockConnection(
        "mock",
        idn=MODERN_IDN,
        channel_states={1: True, 2: False, 3: False, 4: False},
        trigger_status=["Stop"],
        sample_rate=1_000_000.0,
        timebase=1e-3,
        custom_responses={"INR?": "1" if ready else "0"},
        waveform_gate=waveform_gate,
    )
    return InstrumentSession.open("bench-1", mock=True, _connection=conn, poll_interval=poll_interval)


def test_a_user_job_is_not_starved_by_a_long_acquisition(monkeypatch):
    # Before the gate, the worker sat inside a blocking waveform read for the
    # whole acquisition and never looked at the job queue, so every control in
    # the UI hung for the length of the capture.
    gate = threading.Event()
    session = _mock_session(waveform_gate=gate, ready=False)
    try:
        # Simulate a live view already well into its stream (NOT the very
        # first tick): ScopeAdapter.poll() always fetches unconditionally on
        # the first-ever tick, gate or no gate, so it can show a scope's
        # last-known frame instead of a blank canvas. That exemption is
        # Task 4's OTHER behaviour and is not what this test is about -- the
        # bug this test guards is a *later* tick stalling an ongoing stream.
        session.adapter._published_a_frame = True

        # Wait for a real poll tick to actually reach the readiness check
        # before submitting the job. Without this, the job can win a race
        # against the very first tick (submitted before any tick has run at
        # all) and the test would pass whether or not the gate works --
        # exactly the "passes for the wrong reason" trap the brief warns
        # about. new_acquisition_ready() is called unconditionally, before
        # the (possibly mutated-away) early-return, so wrapping it is a
        # mutation-proof synchronization point.
        tick_reached_readiness_check = threading.Event()
        real_ready = session._instrument.new_acquisition_ready

        def _signal_then_answer():
            tick_reached_readiness_check.set()
            return real_ready()

        monkeypatch.setattr(session._instrument, "new_acquisition_ready", _signal_then_answer)

        session.subscribe(lambda message: None)
        assert tick_reached_readiness_check.wait(timeout=2.0), "no poll tick ever reached the readiness check"

        result = session.submit(lambda scope: "job ran")
        assert result.result(timeout=2.0) == "job ran"
    finally:
        # Always release the gate, even if an assertion above failed, so a
        # broken gate cannot leave the worker thread blocked forever.
        gate.set()
        session.close()


def test_the_poll_backs_off_to_the_duration_of_the_last_poll(monkeypatch):
    # Belt and braces beside the readiness gate: if a gate ever misreports (or
    # is unavailable, as on a non-Siglent dialect), a slow scope must degrade
    # to a lower poll rate rather than piling up back-to-back tick attempts
    # (and the blocking reads that go with them) the moment it recovers.
    #
    # This drives InstrumentSession._poll_if_due() directly and single
    # threaded -- no InstrumentSession.open(), no worker thread started -- so
    # injecting a fake `time.monotonic` schedule cannot race a real tick.
    # `_poll_tick()` itself is a no-op here (no subscribers, state is still
    # "connecting"), which is fine: the schedule is a function of the
    # injected clock, not of what the tick actually did.
    adapter = ADAPTERS["scope"]()
    session = InstrumentSession("bench", instrument=object(), mock=True, address=None, poll_interval=0.1, adapter=adapter)

    # First call: start=100.0, end=105.0 -> a poll "measured" at 5s, far
    # longer than poll_interval (0.1s).
    clock = iter([100.0, 105.0])
    monkeypatch.setattr("scpi_control.server.sessions.time.monotonic", lambda: next(clock))
    session._poll_if_due()

    assert session.poll_log[-1][1] == 5.0
    assert session._next_poll_at == 110.0  # 105.0 + max(0.1, 5.0)

    # Second call: the schedule says wait until 110.0. A clock reading before
    # that must skip the tick entirely -- no new log entry.
    logged_before = len(session.poll_log)
    monkeypatch.setattr("scpi_control.server.sessions.time.monotonic", lambda: 108.0)
    session._poll_if_due()
    assert len(session.poll_log) == logged_before, "a tick ran before its scheduled time"

    # Third call: past the schedule -> the tick runs again.
    clock = iter([110.0, 110.2])
    monkeypatch.setattr("scpi_control.server.sessions.time.monotonic", lambda: next(clock))
    session._poll_if_due()
    assert len(session.poll_log) == logged_before + 1
    assert session.poll_log[-1][1] == pytest.approx(0.2)
    assert session._next_poll_at == pytest.approx(110.4)  # 110.2 + max(0.1, 0.2)
