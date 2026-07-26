"""capture_single must wait for the acquisition, not for a fixed 0.5 seconds.

It armed a single acquisition then slept a flat 0.5 s and read whatever was
there, while TriggerWaitCollector.wait_for_trigger in the same file polls
acquisition_status() correctly. On a slow timebase the read landed before the
sweep finished, so batch_capture recorded the PREVIOUS config's waveform under
the new config's label -- wrong data, correctly formatted, no warning.

FakeTime is used throughout so the timeout tests cost no wall-clock time.
"""

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
