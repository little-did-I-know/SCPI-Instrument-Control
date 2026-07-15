"""Streaming poll + state snapshot. No FastAPI dependency."""

import time

import numpy as np
import pytest

from scpi_control import Oscilloscope
from scpi_control.connection.mock import MockConnection
from scpi_control.server.sessions import MAX_FRAME_POINTS, InstrumentSession, _waveform_frame, read_state
from scpi_control.waveform import WaveformData

LEGACY_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"
MODERN_IDN = "Siglent Technologies,SDS824X HD,MOCK0002,3.8.12"


def make_session(poll_interval=0.05, **conn_kwargs):
    defaults = dict(idn=LEGACY_IDN, channel_states={1: True}, trigger_status=["Stop"], sample_rate=1_000.0, timebase=1e-3)
    defaults.update(conn_kwargs)
    conn = MockConnection("mock", **defaults)
    return InstrumentSession.open("s", mock=True, _connection=conn, poll_interval=poll_interval)


def collect(session, wanted_type, n=1, timeout=5.0):
    got = []

    def cb(msg):
        if msg["type"] == wanted_type:
            got.append(msg)

    unsubscribe = session.subscribe(cb)
    deadline = time.time() + timeout
    while len(got) < n and time.time() < deadline:
        time.sleep(0.02)
    unsubscribe()
    return got


def test_read_state_snapshot_shape():
    conn = MockConnection("mock", idn=LEGACY_IDN, channel_states={1: True}, trigger_status=["Stop"], sample_rate=1_000.0, timebase=1e-3)
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    try:
        state = read_state(scope)
        assert state["run_state"] in ("ARM", "READY", "AUTO", "TRIGD", "STOP", "ROLL")
        assert isinstance(state["timebase"], float)
        assert set(state["channels"]) == {1, 2, 3, 4}
        ch1 = state["channels"][1]
        assert ch1["enabled"] is True
        assert isinstance(ch1["voltage_scale"], float)
        assert state["trigger"]["mode"] in ("AUTO", "NORM", "SINGLE", "STOP")
    finally:
        scope.disconnect()


def test_poll_publishes_waveform_frames_for_enabled_channels():
    session = make_session()
    try:
        frames = collect(session, "waveform", n=2)
        assert len(frames) >= 2
        frame = frames[0]
        assert frame["channel"] == 1
        assert 0 < len(frame["points"]) <= 2000
        assert isinstance(frame["points"][0], float)
        assert frame["dt"] > 0
    finally:
        session.close()


def test_no_poll_without_subscribers():
    session = make_session()
    try:
        writes_before = len(session._scope._connection.queries)
        time.sleep(0.3)
        assert len(session._scope._connection.queries) == writes_before
    finally:
        session.close()


def test_measurement_poll_reports_none_on_timeout():
    # PAVA? is legacy-only; on a modern-dialect mock it still has no response ->
    # SiglentTimeoutError -> value None. (The legacy mock now answers PAVA?, so a
    # modern scope is used here to keep exercising the graceful-timeout path.)
    session = make_session(idn=MODERN_IDN)
    try:
        session.set_measurements([(1, "PKPK")])
        msgs = collect(session, "measurements", n=1, timeout=8.0)
        assert msgs, "expected a measurements message"
        entry = msgs[0]["values"][0]
        assert entry["channel"] == 1 and entry["mtype"] == "PKPK"
        assert entry["value"] is None
    finally:
        session.close()


def test_user_job_still_runs_promptly_while_streaming():
    session = make_session()
    try:
        unsubscribe = session.subscribe(lambda m: None)
        start = time.time()
        assert session.submit(lambda s: s.identify()).result(timeout=5)
        assert time.time() - start < 2.0
        unsubscribe()
    finally:
        session.close()


class _StubScope:
    def __init__(self, n):
        self._data = WaveformData(time=np.linspace(0.0, 1.0, n), voltage=np.zeros(n), channel=1)

    def get_waveform(self, channel):
        return self._data


@pytest.mark.parametrize("n", [1999, 2000, 2001, 4001, 14001])
def test_waveform_frame_never_exceeds_cap(n):
    frame = _waveform_frame(_StubScope(n), 1)
    assert len(frame["points"]) <= MAX_FRAME_POINTS


def test_raising_subscriber_does_not_kill_worker():
    session = make_session()
    try:
        good = []

        def bad(msg):
            raise RuntimeError("boom")

        unsubscribe_bad = session.subscribe(bad)
        unsubscribe_good = session.subscribe(good.append)
        deadline = time.time() + 5
        while not good and time.time() < deadline:
            time.sleep(0.02)
        assert good, "worker died or good subscriber starved"
        assert session.submit(lambda s: s.identify()).result(timeout=5)
        unsubscribe_bad()
        unsubscribe_good()
    finally:
        session.close()


def test_poll_publishes_math_frame_when_enabled():
    session = make_session()  # mock scope, channel 1 enabled
    try:
        # configure math1 = C1 (identity) and enable it
        session.submit(lambda scope: scope.math1.set_expression("C1")).result(timeout=5)
        session.submit(lambda scope: scope.math1.enable()).result(timeout=5)
        frames = collect(session, "waveform", n=4, timeout=8.0)
        math_frames = [f for f in frames if f["channel"] == "M1"]
        assert math_frames, "expected an M1 math frame"
        assert 0 < len(math_frames[0]["points"]) <= 2000
    finally:
        session.close()
