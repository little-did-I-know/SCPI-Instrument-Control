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
    # output_dir mode used to return [] unconditionally; it now returns metadata
    # without the bulky arrays, so a caller can see what happened and where.
    assert returned, "output_dir mode must report what it captured"
    assert "waveforms" not in returned[0], "the arrays are on disk, not in the return value"
    assert returned[0]["files"], "each entry must name the files it wrote"
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


def test_the_breaker_stops_a_run_that_cannot_trigger(monkeypatch):
    """The unattended failure this guards: a trigger level the signal never
    crosses times out on EVERY capture. At a 70 s timeout and 100 triggers per
    config that is hours of waiting to collect nothing, previously surfaced only
    as one log line per failure."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, _ = _collector(trigger_status=["Trig'd"] * 5000)
    try:
        results = dc.batch_capture(
            channels=[1],
            timebase_scales=["1us", "10us", "100us"],
            triggers_per_config=10,
            max_consecutive_failures=3,
        )
    finally:
        dc.disconnect()

    assert len(results) == 3, "the run must stop at the third consecutive timeout, not after all 30"
    assert all("error" in entry for entry in results)
    # Everything gathered is still returned rather than discarded.
    assert results[0]["config"]


def test_a_success_resets_the_breaker(monkeypatch):
    """Consecutive, not cumulative: an occasional miss in a long run is not the
    same as a run that cannot trigger at all, and must not stop it."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, _ = _collector()
    real_capture = dc.capture_single
    calls = {"n": 0}

    def flaky_capture(channels, **kwargs):
        calls["n"] += 1
        if calls["n"] % 2 == 0:  # every other capture times out
            raise exceptions.SiglentTimeoutError("no trigger")
        return real_capture(channels, **kwargs)

    monkeypatch.setattr(dc, "capture_single", flaky_capture)
    try:
        results = dc.batch_capture(channels=[1], timebase_scales=["1us"], triggers_per_config=8, max_consecutive_failures=3)
    finally:
        dc.disconnect()

    assert len(results) == 8, "alternating failures never reach 3 in a row, so the run completes"
    assert sum("error" in entry for entry in results) == 4


def test_the_breaker_counts_across_configuration_boundaries(monkeypatch):
    """triggers_per_config=1 would never trip a per-config breaker, which is why
    the count crosses configurations rather than resetting at each one."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, _ = _collector(trigger_status=["Trig'd"] * 5000)
    try:
        results = dc.batch_capture(channels=[1], timebase_scales=["1us", "10us", "100us", "1ms"], triggers_per_config=1, max_consecutive_failures=2)
    finally:
        dc.disconnect()

    assert len(results) == 2, "two configs of one trigger each must trip a threshold of 2"


def test_the_breaker_can_be_disabled(monkeypatch):
    """A run with genuinely sparse triggers can opt out."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, _ = _collector(trigger_status=["Trig'd"] * 5000)
    try:
        results = dc.batch_capture(channels=[1], timebase_scales=["1us"], triggers_per_config=5, max_consecutive_failures=None)
    finally:
        dc.disconnect()

    assert len(results) == 5, "with the breaker disabled every planned capture is attempted"
    assert all("error" in entry for entry in results)


def test_the_breaker_defaults_on(monkeypatch):
    """The run worth protecting is the one where nobody thought to pass the
    parameter, so the default must not be None."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, _ = _collector(trigger_status=["Trig'd"] * 5000)
    try:
        results = dc.batch_capture(channels=[1], timebase_scales=["1us"], triggers_per_config=50)
    finally:
        dc.disconnect()

    assert len(results) == 3, "the default threshold is 3, so a doomed run stops at the third failure"
    assert all("error" in entry for entry in results)


@pytest.mark.parametrize("bad", [0, -1])
def test_an_invalid_breaker_threshold_is_rejected(bad):
    dc, _ = _collector()
    try:
        with pytest.raises(exceptions.InvalidParameterError):
            dc.batch_capture(channels=[1], timebase_scales=["1us"], max_consecutive_failures=bad)
    finally:
        dc.disconnect()


def test_an_interrupted_run_keeps_what_it_collected(monkeypatch):
    """Ctrl-C on a run the operator can see is doomed must not throw away the
    captures already taken. start_continuous_capture already behaved this way;
    batch_capture had no handler at all, so the whole run was lost."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, _ = _collector()
    real_capture = dc.capture_single
    calls = {"n": 0}

    def interrupt_on_third(channels, **kwargs):
        calls["n"] += 1
        if calls["n"] == 3:
            raise KeyboardInterrupt
        return real_capture(channels, **kwargs)

    monkeypatch.setattr(dc, "capture_single", interrupt_on_third)
    try:
        results = dc.batch_capture(channels=[1], timebase_scales=["1us"], triggers_per_config=10)
    finally:
        dc.disconnect()

    assert len(results) == 2, "the two completed captures must survive the interrupt"
    assert all(entry["waveforms"] for entry in results)
    # Note on this test's failure mode: without the handler the KeyboardInterrupt
    # escapes into pytest, which aborts the whole SESSION ("!!! KeyboardInterrupt
    # !!!") rather than reporting one red test. If the handler is ever removed the
    # signal is a dead suite, not a failing test -- worth knowing before hunting it.


def test_a_dropped_connection_mid_run_does_not_discard_the_captures(monkeypatch):
    """A dropped link is the other likely unattended failure. Catching only
    SiglentTimeoutError let it propagate and discard every capture already taken
    -- the exact loss the error-entry path exists to prevent. It counts toward
    the breaker too: a scope that stopped answering is what a breaker is for."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, _ = _collector()
    real_capture = dc.capture_single
    calls = {"n": 0}

    def drop_after_two(channels, **kwargs):
        calls["n"] += 1
        if calls["n"] > 2:
            raise exceptions.SiglentConnectionError("connection reset by peer")
        return real_capture(channels, **kwargs)

    monkeypatch.setattr(dc, "capture_single", drop_after_two)
    try:
        results = dc.batch_capture(channels=[1], timebase_scales=["1us"], triggers_per_config=20, max_consecutive_failures=3)
    finally:
        dc.disconnect()

    assert len(results) == 5, "two successes, then three failures trip the breaker"
    assert all(entry["waveforms"] for entry in results[:2])
    assert all("error" in entry for entry in results[2:])


def test_an_interrupt_between_configs_also_keeps_the_captures(monkeypatch):
    """The window the first version missed: Ctrl-C during the config-apply block
    (set_timebase / set_scale / the settle sleep) rather than during a capture.
    Guarding only the capture discarded the whole run for a keypress one
    statement earlier."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, _ = _collector()
    real_set = dc.scope.set_timebase
    calls = {"n": 0}

    def interrupt_on_second_config(value):
        calls["n"] += 1
        if calls["n"] == 2:
            raise KeyboardInterrupt
        return real_set(value)

    monkeypatch.setattr(dc.scope, "set_timebase", interrupt_on_second_config)
    try:
        results = dc.batch_capture(channels=[1], timebase_scales=["1us", "10us"], triggers_per_config=2)
    finally:
        dc.disconnect()

    assert len(results) == 2, "the first config's captures must survive an interrupt in the second's setup"


def test_an_instrument_error_while_applying_a_config_keeps_the_captures(monkeypatch):
    """Same window, non-interrupt cause: the scope stops answering between
    configs. Previously this propagated and discarded the run."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime())
    dc, _ = _collector()
    real_set = dc.scope.set_timebase
    calls = {"n": 0}

    def die_on_second_config(value):
        calls["n"] += 1
        if calls["n"] == 2:
            raise exceptions.SiglentConnectionError("scope stopped answering")
        return real_set(value)

    monkeypatch.setattr(dc.scope, "set_timebase", die_on_second_config)
    try:
        results = dc.batch_capture(channels=[1], timebase_scales=["1us", "10us"], triggers_per_config=2)
    finally:
        dc.disconnect()

    assert len(results) == 2, "the first config's captures must survive the instrument dying"
def test_a_doomed_save_configuration_fails_fast_instead_of_writing_nothing(monkeypatch, tmp_path):
    """The defect this replaced: a rejected file_format failed identically on
    every iteration for the run's whole duration, each failure swallowed by the
    loop's broad except, and the function returned an empty list. An overnight
    run produced an empty directory and no signal at all.

    'parquet' is not a supported format, so the FIRST save raises and nothing is
    ever written -- configuration, not a transient hiccup."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime(step=0.01))
    # A dedicated subdirectory, not tmp_path itself: a conftest fixture puts a
    # 'fake-home' directory in tmp_path, so tmp_path is never empty.
    output_dir = tmp_path / "captures"
    dc, _ = _collector()
    try:
        with pytest.raises(exceptions.SiglentError) as excinfo:
            dc.start_continuous_capture(channels=[1], duration=10.0, interval=0.02, output_dir=output_dir, file_format="parquet")
    finally:
        dc.disconnect()

    message = str(excinfo.value)
    assert "parquet" in message, "the error must name the format that was rejected"
    assert "no file was written" in message
    assert sorted(output_dir.iterdir()) == [], "nothing should have been written"
    # The cause is chained rather than discarded, so the underlying reason survives.
    assert isinstance(excinfo.value.__cause__, exceptions.InvalidParameterError)


def test_a_later_save_failure_is_counted_without_aborting_the_run(monkeypatch, tmp_path):
    """Once one file has landed the configuration is proven, so a transient
    failure must not throw away a long unattended run."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime(step=0.01))
    dc, _ = _collector()
    real_save = dc.scope.waveform.save_waveform
    calls = {"n": 0}

    def flaky_save(waveform, filename, format=None, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:  # first one succeeds, proving the configuration
            raise OSError("transient disk hiccup")
        return real_save(waveform, filename, format=format, **kwargs)

    monkeypatch.setattr(dc.scope.waveform, "save_waveform", flaky_save)
    try:
        returned = dc.start_continuous_capture(channels=[1], duration=0.2, interval=0.02, output_dir=tmp_path)
    finally:
        dc.disconnect()

    assert calls["n"] > 2, "the run must continue past the failed save"
    assert len(returned) > 1, "captures after the failure must still be reported"
    assert sorted(tmp_path.glob("*.npz")), "the successful saves must still be on disk"


def test_in_memory_mode_still_returns_the_waveforms(monkeypatch):
    """Without output_dir nothing changed: the arrays come back in the result."""
    monkeypatch.setattr("scpi_control.automation.time", FakeTime(step=0.01))
    dc, _ = _collector()
    try:
        returned = dc.start_continuous_capture(channels=[1], duration=0.1, interval=0.02, output_dir=None)
    finally:
        dc.disconnect()

    assert returned
    assert "waveforms" in returned[0]
    assert "files" not in returned[0]


def test_a_run_that_saves_nothing_at_all_still_says_so(caplog, tmp_path):
    """The other route to an empty output directory: no save ever FAILS because
    no save is ever attempted. Every capture yields no waveforms (the channel is
    disabled, or acquire() raises and the inner handler logs and continues), so
    the save counters stay at zero and nothing would otherwise signal it."""
    import logging

    conn = MockConnection(channel_states={1: False}, sample_rate=1_000.0, timebase=1e-3)
    dc = DataCollector("mock", connection=conn)
    dc.connect()
    try:
        with caplog.at_level(logging.WARNING, logger="scpi_control.automation"):
            returned = dc.start_continuous_capture(channels=[1], duration=0.05, interval=0.01, output_dir=tmp_path / "captures")
    finally:
        dc.disconnect()

    assert returned, "captures still happened, they just produced nothing to save"
    assert all(entry["files"] == [] for entry in returned)
    assert any("wrote no files" in record.message for record in caplog.records), "a run that writes nothing must say so"


def test_the_fatal_error_keeps_its_original_exception_type(tmp_path):
    """A caller catching InvalidParameterError must still catch it. Wrapping in a
    plain SiglentError would flatten the type and silently break that."""
    conn = MockConnection(channel_states={1: True}, sample_rate=1_000.0, timebase=1e-3)
    dc = DataCollector("mock", connection=conn)
    dc.connect()
    try:
        with pytest.raises(exceptions.InvalidParameterError):
            dc.start_continuous_capture(channels=[1], duration=0.05, interval=0.01, output_dir=tmp_path / "captures", file_format="parquet")
    finally:
        dc.disconnect()
