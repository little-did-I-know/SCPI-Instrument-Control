"""capture_single must wait for the acquisition, not for a fixed 0.5 seconds.

It armed a single acquisition then slept a flat 0.5 s and read whatever was
there, while TriggerWaitCollector.wait_for_trigger in the same file polls
acquisition_status() correctly. On a slow timebase the read landed before the
sweep finished, so batch_capture recorded the PREVIOUS config's waveform under
the new config's label -- wrong data, correctly formatted, no warning.

FakeTime is used throughout so the timeout tests cost no wall-clock time.
"""

import numpy as np
import pytest

from scpi_control import exceptions
from scpi_control.automation import DataCollector
from scpi_control.connection.mock import MockConnection
from tests.test_automation import FakeTime


def _collector(**kwargs):
    conn = MockConnection(channel_states={1: True, 2: False}, sample_rate=1_000.0, timebase=1e-3, **kwargs)
    dc = DataCollector("mock", connection=conn)
    dc.connect()
    return dc, conn


def test_capture_single_waits_for_the_acquisition_to_finish(monkeypatch):
    """Three statuses queued: the poll must consume the two busy ones before
    reading. A fixed sleep would read immediately, at status 'Trig'd'."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, conn = _collector(trigger_status=["Trig'd", "Trig'd", "Stop"])
    try:
        waveforms = dc.capture_single([1])
    finally:
        dc.disconnect()
    assert list(waveforms.keys()) == [1]
    # The queue is drained down to its final repeating element, proving the loop
    # polled rather than slept.
    assert conn.trigger_status == ["Stop"]


def test_capture_single_times_out_instead_of_reading_stale_data(monkeypatch):
    """A status that never reaches STOP must raise, not return the previous
    acquisition. A long queue is required: TRIG_MODE SINGLE resets a
    single-element queue to ['Ready', 'Stop'] (mock/siglent.py:131-133)."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, _ = _collector(trigger_status=["Trig'd"] * 200)
    try:
        with pytest.raises(exceptions.SiglentTimeoutError) as excinfo:
            dc.capture_single([1], max_wait=1.0)
    finally:
        dc.disconnect()
    message = str(excinfo.value)
    # acquisition_status() normalizes across dialects, so the last status is the
    # canonical "TRIGD" token, not the mock's raw "Trig'd".
    assert "TRIGD" in message
    assert "1.00" in message


def test_normal_trigger_mode_completes_on_trigd(monkeypatch):
    """In NORM the scope re-arms after every trigger and never reports STOP, so
    a naive `while status != 'STOP'` loop always times out. wait_for_trigger
    already carries this branch; capture_single must too."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, conn = _collector(trigger_status=["Ready", "Ready", "Trig'd", "Trig'd"])
    dc.scope.trigger.mode = "NORM"
    try:
        waveforms = dc.capture_single([1], max_wait=5.0)
    finally:
        dc.disconnect()
    assert list(waveforms.keys()) == [1]


def test_an_explicit_max_wait_is_honoured(monkeypatch):
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, _ = _collector(trigger_status=["Trig'd"] * 200)
    try:
        with pytest.raises(exceptions.SiglentTimeoutError) as excinfo:
            dc.capture_single([1], max_wait=0.5)
    finally:
        dc.disconnect()
    assert "0.5" in str(excinfo.value)


def test_the_default_timeout_scales_with_the_timebase(monkeypatch):
    """A 100 ms/div sweep takes 1.4 s; a 2 s floor alone would time out on it."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, _ = _collector()
    try:
        dc.scope.timebase = 0.1
        assert dc._acquisition_timeout() == pytest.approx(14 * 0.1 * 5)
        dc.scope.timebase = 1e-6
        assert dc._acquisition_timeout() == pytest.approx(2.0)  # floor
    finally:
        dc.disconnect()


def test_norm_mode_is_not_re_armed(monkeypatch):
    """capture_single must not force a single-shot when the scope is already in
    NORM: doing so would stomp the user's configured mode (and, incidentally,
    defeat _wait_for_acquisition's own NORM branch, since it reads the mode
    after this write). Pinned via the raw commands sent to the mock rather
    than behaviour alone, so removing the guard fails this test even though
    the capture still completes."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, conn = _collector(trigger_status=["Ready", "Ready", "Trig'd", "Trig'd"])
    dc.scope.trigger.mode = "NORM"
    try:
        dc.capture_single([1], max_wait=5.0)
    finally:
        dc.disconnect()
    assert not any("TRIG_MODE SINGLE" in w.upper() for w in conn.writes)


def test_default_mode_is_armed_single_shot(monkeypatch):
    """Companion to the NORM test above: in the default (non-NORM) mode,
    capture_single must still arm a single acquisition as before."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, conn = _collector(trigger_status=["Trig'd", "Trig'd", "Stop"])
    try:
        dc.capture_single([1])
    finally:
        dc.disconnect()
    assert any("TRIG_MODE SINGLE" in w.upper() for w in conn.writes)


def test_batch_capture_accepts_its_own_documented_string_scales(monkeypatch):
    """The docstring documents timebase_scales=['1us','10us'] and
    voltage_scales={1:['1V','2V']} and its example copies them verbatim -- then
    the apply path passed them to set_scale() unparsed and raised TypeError,
    losing every capture taken so far."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, conn = _collector()
    try:
        results = dc.batch_capture(
            channels=[1],
            timebase_scales=["1us", "10us"],
            voltage_scales={1: ["1V", "500mV"]},
            triggers_per_config=1,
        )
    finally:
        dc.disconnect()
    assert len(results) == 4
    assert conn.timebase_updates == [1e-6, 1e-6, 1e-5, 1e-5]
    assert conn.scale_updates[1] == [1.0, 0.5, 1.0, 0.5]


def test_batch_capture_still_accepts_numeric_scales(monkeypatch):
    """Purely additive: callers already passing floats keep working."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, conn = _collector()
    try:
        results = dc.batch_capture(channels=[1], timebase_scales=[1e-3], voltage_scales={1: [0.5]}, triggers_per_config=1)
    finally:
        dc.disconnect()
    assert len(results) == 1
    assert conn.timebase_updates == [1e-3]


def test_batch_capture_rejects_an_unparseable_scale_before_capturing(monkeypatch):
    """Fail on the argument, not 40 captures in."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, conn = _collector()
    try:
        with pytest.raises(exceptions.InvalidParameterError):
            dc.batch_capture(channels=[1], timebase_scales=["banana"], triggers_per_config=1)
        assert conn.waveform_requests == []
    finally:
        dc.disconnect()


def test_a_timed_out_capture_becomes_a_visible_failed_entry(monkeypatch):
    """The run continues and the failure is in the returned data, not only in a
    log line. Previously the slot held the PREVIOUS config's waveform."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, _ = _collector(trigger_status=["Trig'd"] * 500)
    try:
        results = dc.batch_capture(channels=[1], timebase_scales=["1us", "10us"], triggers_per_config=1)
    finally:
        dc.disconnect()
    assert len(results) == 2, "the run must continue past a timeout"
    for entry in results:
        assert entry["waveforms"] == {}
        assert "error" in entry
        assert entry["config"]
    # Nothing already captured is lost, and no entry claims a waveform it lacks.


def test_start_continuous_capture_writes_files_with_its_default_format(monkeypatch, tmp_path):
    """The regression that actually shipped, pinned at the caller level.

    start_continuous_capture's default file_format is 'npz', which was valid as
    a filename EXTENSION and rejected as a format ARGUMENT, so every save raised
    -- swallowed by the loop's broad except, leaving an empty output directory
    and a log line. The alias fix is covered at unit level; this covers the path
    that failed, including the filename/extension interaction, end to end.
    """
    monkeypatch.setattr("scpi_control.automation.time", FakeTime(step=0.01))
    dc, _ = _collector()
    try:
        returned = dc.start_continuous_capture(channels=[1], duration=0.1, interval=0.02, output_dir=tmp_path)
    finally:
        dc.disconnect()

    written = sorted(tmp_path.glob("*.npz"))
    assert written, "the default file_format must produce files, not a silently empty directory"
    assert returned == [], "with output_dir set, captures go to disk rather than the returned list"
    # Loading proves a real npz was written, not an empty or mis-formatted file.
    with np.load(str(written[0])) as archive:
        assert len(archive["voltage"]) > 0


def test_capture_single_rejects_a_non_positive_max_wait(monkeypatch):
    """max_wait=0 skipped the poll loop without a single status read and raised
    'last status: unknown', which reads like an instrument fault rather than the
    bad argument it is."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, conn = _collector()
    try:
        for bad in (0, -1.0):
            with pytest.raises(exceptions.InvalidParameterError) as excinfo:
                dc.capture_single([1], max_wait=bad)
            assert repr(bad) in str(excinfo.value)
        assert conn.waveform_requests == []
    finally:
        dc.disconnect()


def test_duplicate_configs_are_numbered_by_position_not_by_value(monkeypatch):
    """'1us' and '1000ns' are the same timebase, so after parsing both configs
    are the identical dict {'timebase': 1e-06}. configs.index(config) matched
    the first one for both and reported 'Config 1/2' twice."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, _ = _collector()
    statuses = []
    try:
        dc.batch_capture(
            channels=[1],
            timebase_scales=["1us", "1000ns"],
            triggers_per_config=1,
            progress_callback=lambda current, total, status: statuses.append(status),
        )
    finally:
        dc.disconnect()
    assert [s.split(",")[0] for s in statuses] == ["Config 1/2", "Config 2/2"]


def test_successful_entries_carry_no_error_key(monkeypatch):
    """Existing consumers reading config/waveforms/trigger_num are unaffected."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, _ = _collector()
    try:
        results = dc.batch_capture(channels=[1], timebase_scales=["1us"], triggers_per_config=1)
    finally:
        dc.disconnect()
    assert results and "error" not in results[0]
    assert results[0]["waveforms"]
