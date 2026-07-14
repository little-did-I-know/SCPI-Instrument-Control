"""Streaming poll + state snapshot. No FastAPI dependency."""

import time

from scpi_control import Oscilloscope
from scpi_control.connection.mock import MockConnection
from scpi_control.server.sessions import InstrumentSession, read_state

LEGACY_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"


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
    # MockConnection has no PAVA? response by default -> SiglentTimeoutError -> value None
    session = make_session()
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
