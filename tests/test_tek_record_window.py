"""A Tektronix capture must return the full record, not whatever window was left behind.

Backend review 2026-07-31. WFMOutpre:NR_Pt? is window-relative -- MSO4/5/6
programmer manual p.2-1461: "returns the number of points for the DATa:SOUrce
waveform that will be transmitted in response to a CURVe? query" (the manual's
own example on p.2-1455 shows a 1250-point record reporting NR_PT 1000). The old
code queried NR_Pt? FIRST and then wrote DATa:STOP back to that same number, so a
narrow window left by a prior script or a recalled setup truncated every capture
forever, unrecoverably.

The fix is the manual's own instruction, p.2-341/2-342: "Changes to the record
length value are not automatically reflected in the data:stop value... If you
always want to transfer complete waveforms, set DATa:STARt to 1 and DATa:STOP to
the maximum record length, or larger." Widening FIRST needs no record-length
query, so it works on every Tek family (only the MSO4/5/6 manual is available
here; HORizontal:RECOrdlength?'s spelling is unverified for TBS1000/MSO2).
"""

from scpi_control.connection.mock import MockConnection
from scpi_control.oscilloscope import Oscilloscope

TEK_IDN = "TEKTRONIX,MSO46,C012345,CF:91.1CT FV:1.20.3"


def _scope(**kwargs):
    # sample_rate/timebase give a 14,000-point full record (14 divisions x
    # 1e6 Sa/s x 1ms/div, matching the defaults used elsewhere for Tek/LeCroy
    # synthesis, e.g. test_mock_synthesis.py) -- large enough that the
    # manual's own Appendix D scenario (p.D-2: "a previous session left
    # DATa:STOP at 25 on a 10000-point record") and a full capture are
    # unmistakably different sizes.
    kwargs.setdefault("sample_rate", 1_000_000.0)
    kwargs.setdefault("timebase", 1e-3)
    conn = MockConnection(idn=TEK_IDN, **kwargs)
    scope = Oscilloscope(connection=conn, host="mock")
    scope.connect()
    return scope, conn


def test_stale_narrow_window_does_not_truncate_the_capture():
    # Seed the exact hazard: a previous session left DATa:STOP at 25 on a
    # much larger record (the manual's own Appendix D scenario, p.D-2).
    scope, conn = _scope(data_stop=25)
    wf = scope.get_waveform(1)
    assert len(wf.voltage) > 25


def test_acquire_widens_the_window_before_asking_how_many_points():
    scope, conn = _scope(data_stop=25)
    scope.get_waveform(1)
    # Ordering is the whole point: measuring first and writing the measured
    # value back is what made the truncation permanent. conn.writes and
    # conn.queries (connection/mock/base.py) are each append-only to their
    # OWN list, so neither alone can show a write's position relative to a
    # query -- conn.command_log is a combined, call-order trace of both
    # (added alongside this test) that makes the ordering observable.
    log = [c.upper() for c in conn.command_log]
    widen = [i for i, c in enumerate(log) if "DATA:STAR" in c or "DATA:STOP" in c]
    measure = [i for i, c in enumerate(log) if "NR_PT" in c]
    assert widen, f"no DATa:STARt/STOP write observed in {log}"
    assert measure, f"no NR_Pt? query observed in {log}"
    assert max(widen) < min(measure), f"window was measured before it was widened: {log}"


def test_mock_nr_pt_is_window_relative():
    # Wire-level pin of the manual's semantics. This is the mock half: if
    # NR_PT? ever goes back to ignoring the window, the driver test above
    # stops being able to detect the bug.
    _, conn = _scope(data_stop=25)
    assert int(float(conn.query("WFMOUTPRE:NR_PT?"))) == 25
