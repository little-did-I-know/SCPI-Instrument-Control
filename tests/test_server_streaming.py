"""Streaming poll + state snapshot. No FastAPI dependency."""

import time

import numpy as np
import pytest

from scpi_control import Oscilloscope
from scpi_control.connection.mock import MockConnection
from scpi_control.exceptions import InvalidParameterError
from scpi_control.server.sessions import MAX_FRAME_POINTS, InstrumentSession, SessionError, _waveform_frame, read_state
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

    def get_waveform(self, channel, provenance=True):
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


def test_poll_clears_math_frame_when_disabled():
    session = make_session()  # mock scope, channel 1 enabled
    try:
        # configure math1 = C1 (identity) and enable it
        session.submit(lambda scope: scope.math1.set_expression("C1")).result(timeout=5)
        session.submit(lambda scope: scope.math1.enable()).result(timeout=5)

        got = []

        def cb(msg):
            if msg["type"] == "waveform" and msg["channel"] == "M1":
                got.append(msg)

        unsubscribe = session.subscribe(cb)
        deadline = time.time() + 8.0
        while not any(len(f["points"]) > 0 for f in got) and time.time() < deadline:
            time.sleep(0.02)
        assert any(len(f["points"]) > 0 for f in got), "expected a non-empty M1 frame before disabling"

        session.submit(lambda scope: scope.math1.disable()).result(timeout=5)

        # give it a generous window (poll_interval=0.05 -> many ticks) to observe the clear
        # frame and confirm no further M1 frames arrive afterward.
        time.sleep(0.5)
        unsubscribe()

        # find the index of the first empty-points M1 frame after the disable call
        empty_indices = [i for i, f in enumerate(got) if len(f["points"]) == 0]
        assert empty_indices, "expected exactly one clear (empty-points) M1 frame after disabling"
        assert len(empty_indices) == 1, "expected exactly ONE clear frame, not repeated clears"
        clear_index = empty_indices[0]
        # nothing after the clear frame should be another M1 frame at all
        assert len(got) - 1 == clear_index, "no further M1 frames should be published after the clear"
    finally:
        session.close()


def test_set_measurements_broadcasts_config():
    session = make_session()
    try:
        got = []

        def cb(msg):
            if msg["type"] == "measurements_config":
                got.append(msg)

        unsubscribe = session.subscribe(cb)
        session.set_measurements([(1, "PKPK"), (2, "FREQ")])
        unsubscribe()
        assert got and got[0]["items"] == [{"channel": 1, "mtype": "PKPK"}, {"channel": 2, "mtype": "FREQ"}]
    finally:
        session.close()


def test_poll_publishes_spectrum_frame_when_enabled():
    session = make_session()
    try:
        session.spectrum_config = {**session.spectrum_config, "enabled": True}
        frames = collect(session, "spectrum", n=1, timeout=8.0)
        assert frames, "expected a spectrum frame"
        frame = frames[0]
        assert frame["channel"] == 1 and frame["db"] is True and frame["window"] == "hanning"
        assert 0 < len(frame["points"]) <= 2000
        assert frame["df"] > 0
    finally:
        session.close()


def test_poll_clears_spectrum_frame_when_disabled():
    session = make_session()
    try:
        session.spectrum_config = {**session.spectrum_config, "enabled": True}
        assert collect(session, "spectrum", n=1, timeout=8.0), "expected a live spectrum frame first"
        cleared = []
        unsubscribe = session.subscribe(lambda m: cleared.append(m) if m["type"] == "spectrum" and m["points"] == [] else None)
        session.spectrum_config = {**session.spectrum_config, "enabled": False}
        deadline = time.time() + 8.0
        while not cleared and time.time() < deadline:
            time.sleep(0.02)
        unsubscribe()
        assert cleared, "expected a one-shot empty spectrum frame on disable"
    finally:
        session.close()


def test_poll_publishes_filtered_trace():
    session = make_session()
    try:
        session.filters = {**session.filters, 1: {**session.filters[1], "enabled": True, "cutoff_high": 100.0}}
        frames = collect(session, "waveform", n=6, timeout=8.0)
        f1 = [f for f in frames if f["channel"] == "F1"]
        assert f1, "expected an F1 filtered frame"
        assert 0 < len(f1[0]["points"]) <= 2000
    finally:
        session.close()


def test_poll_clears_filtered_trace_when_disabled():
    session = make_session()
    try:
        session.filters = {**session.filters, 1: {**session.filters[1], "enabled": True, "cutoff_high": 100.0}}
        assert [f for f in collect(session, "waveform", n=6, timeout=8.0) if f["channel"] == "F1"]
        cleared = []
        unsubscribe = session.subscribe(lambda m: cleared.append(m) if m["type"] == "waveform" and m["channel"] == "F1" and m["points"] == [] else None)
        session.filters = {**session.filters, 1: {**session.filters[1], "enabled": False}}
        deadline = time.time() + 8.0
        while not cleared and time.time() < deadline:
            time.sleep(0.02)
        unsubscribe()
        assert cleared, "expected a one-shot empty F1 frame on disable"
    finally:
        session.close()


def test_set_active_reference_broadcasts_overlay_and_clear():
    session = make_session()
    try:
        got = []
        unsubscribe = session.subscribe(lambda m: got.append(m) if m["type"] == "reference" else None)
        data = session.submit(lambda scope: scope.get_waveform(1)).result(timeout=5)
        session.set_active_reference("golden", 1, {"time": data.time, "voltage": data.voltage})
        session.set_active_reference(None, None, None)
        unsubscribe()
        assert got[0]["name"] == "golden" and got[0]["channel"] == 1
        assert 0 < len(got[0]["points"]) <= 2000
        assert got[1]["name"] is None and got[1]["points"] == []
    finally:
        session.close()


def test_poll_publishes_reference_stats_for_active_reference():
    # An explicit payload (rather than the default state-coupled synthesis, which
    # varies each acquisition) keeps the mock replaying the same record every
    # tick, so the self-compare below is deterministic.
    session = make_session(waveform_payloads={1: bytes([0, 25, 50, 75])})
    try:
        data = session.submit(lambda scope: scope.get_waveform(1)).result(timeout=5)
        session.set_active_reference("golden", 1, {"time": data.time, "voltage": data.voltage})
        msgs = collect(session, "reference_stats", n=1, timeout=8.0)
        assert msgs, "expected a reference_stats message"
        assert msgs[0]["correlation"] is not None and msgs[0]["correlation"] > 0.99
        assert msgs[0]["max_deviation"] is not None
    finally:
        session.close()


def test_poll_survives_unexpected_analysis_exception(monkeypatch):
    # An unexpected (non-Siglent) error in analysis compute must never kill
    # the worker: the tick degrades that trace and keeps publishing channels.
    from scpi_control.server import compute

    def boom(config, acquired):
        raise RuntimeError("unexpected numpy edge case")

    monkeypatch.setattr(compute, "filtered_waveform", boom)
    monkeypatch.setattr(compute, "spectrum_frame", boom)
    session = make_session()
    try:
        session.filters = {**session.filters, 1: {**session.filters[1], "enabled": True, "cutoff_high": 100.0}}
        session.spectrum_config = {**session.spectrum_config, "enabled": True}
        # n=8: this mock's default enables all 4 channels, so one healthy tick
        # already yields 4 "waveform" messages; require two full ticks' worth
        # so the assertion actually distinguishes "died after tick 1" from
        # "kept polling."
        frames = collect(session, "waveform", n=8, timeout=8.0)
        channel_frames = [f for f in frames if f["channel"] == 1]
        assert len(channel_frames) >= 2, "worker must keep polling after an analysis exception"
    finally:
        session.close()


def test_measurements_message_carries_timestamp():
    session = make_session()
    try:
        session.set_measurements([(1, "PKPK")])
        before = time.time()
        msgs = collect(session, "measurements", n=1, timeout=8.0)
        assert msgs, "expected a measurements message"
        assert isinstance(msgs[0]["timestamp"], float)
        assert before - 1.0 <= msgs[0]["timestamp"] <= time.time() + 1.0
    finally:
        session.close()


def test_recorder_accumulates_rows_while_recording():
    session = make_session()
    try:
        session.set_measurements([(1, "PKPK")])
        session.start_recording()
        msgs = collect(session, "measurements", n=2, timeout=12.0)
        assert msgs
        status = session.recorder.status()
        assert status["row_count"] >= 1
        rows = session.recorder.rows_since()
        assert len(rows[0]) == 2  # [timestamp, one column value]
        assert rows[0][0] == msgs[0]["timestamp"]  # same clock stamp feeds both
    finally:
        session.close()


def test_recorder_ignores_measurements_when_idle():
    session = make_session()
    try:
        session.set_measurements([(1, "PKPK")])
        assert collect(session, "measurements", n=1, timeout=8.0)
        assert session.recorder.status()["row_count"] == 0
    finally:
        session.close()


def test_start_and_stop_recording_broadcast_log_status():
    session = make_session()
    try:
        got = []
        unsubscribe = session.subscribe(lambda m: got.append(m) if m["type"] == "log_status" else None)
        session.set_measurements([(1, "PKPK")])
        session.start_recording()
        session.stop_recording()
        unsubscribe()
        assert [m["state"] for m in got] == ["recording", "idle"]
        assert got[0]["started_at"] is not None and got[0]["row_count"] == 0
        assert got[0]["columns"] == [{"channel": 1, "mtype": "PKPK"}]
    finally:
        session.close()


def test_start_recording_requires_a_selection():
    session = make_session()
    try:
        with pytest.raises(InvalidParameterError):
            session.start_recording()
    finally:
        session.close()


def test_double_start_recording_raises_session_error():
    session = make_session()
    try:
        session.set_measurements([(1, "PKPK")])
        session.start_recording()
        with pytest.raises(SessionError):
            session.start_recording()
    finally:
        session.close()
