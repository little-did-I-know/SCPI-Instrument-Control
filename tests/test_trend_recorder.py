"""TrendRecorder unit tests. No FastAPI or instrument dependency."""

from scpi_control.server.recorder import MAX_LOG_ROWS, TrendRecorder


def test_defaults_are_idle_and_empty():
    recorder = TrendRecorder()
    assert recorder.state == "idle"
    assert recorder.started_at is None
    assert recorder.status() == {"state": "idle", "started_at": None, "columns": [], "row_count": 0, "max_rows": MAX_LOG_ROWS}


def test_start_freezes_columns_and_clears_previous_rows():
    recorder = TrendRecorder()
    recorder.start([(1, "PKPK")], 100.0)
    recorder.append(101.0, [1.0])
    recorder.start([(2, "FREQ"), (1, "PKPK")], 200.0)
    status = recorder.status()
    assert status["state"] == "recording"
    assert status["started_at"] == 200.0
    assert status["columns"] == [{"channel": 2, "mtype": "FREQ"}, {"channel": 1, "mtype": "PKPK"}]
    assert status["row_count"] == 0  # previous rows cleared


def test_append_is_gated_by_state():
    recorder = TrendRecorder()
    recorder.append(1.0, [1.0])  # idle: ignored
    assert recorder.status()["row_count"] == 0
    recorder.start([(1, "PKPK")], 0.0)
    recorder.append(1.0, [1.0])
    recorder.stop()
    recorder.append(2.0, [2.0])  # stopped: ignored
    assert recorder.status()["row_count"] == 1  # stop keeps recorded data


def test_none_values_are_preserved():
    recorder = TrendRecorder()
    recorder.start([(1, "PKPK"), (2, "FREQ")], 0.0)
    recorder.append(1.0, [1.5, None])
    assert recorder.rows_since() == [[1.0, 1.5, None]]


def test_ring_buffer_caps_rows_dropping_oldest():
    recorder = TrendRecorder(max_rows=3)
    recorder.start([(1, "PKPK")], 0.0)
    for i in range(5):
        recorder.append(float(i), [float(i)])
    rows = recorder.rows_since()
    assert len(rows) == 3
    assert [r[0] for r in rows] == [2.0, 3.0, 4.0]
    assert recorder.status()["max_rows"] == 3


def test_rows_since_filters_strictly_greater():
    recorder = TrendRecorder()
    recorder.start([(1, "PKPK")], 0.0)
    recorder.append(1.0, [1.0])
    recorder.append(2.0, [2.0])
    assert [r[0] for r in recorder.rows_since(1.0)] == [2.0]
    assert [r[0] for r in recorder.rows_since()] == [1.0, 2.0]


def test_stop_is_idempotent_and_started_at_survives():
    recorder = TrendRecorder()
    recorder.start([(1, "PKPK")], 42.0)
    recorder.stop()
    recorder.stop()
    assert recorder.state == "idle"
    assert recorder.started_at == 42.0  # export availability marker
