"""The mock's SCPI error queue.

Real instruments accept a bad command, ignore it, and queue an error for later
collection. The mock used to answer '+0,"No error"' unconditionally, so
FunctionGenerator.get_error() and DataLogger.get_error() could only ever report
perfect health and no caller-side error handling was reachable in tests.
"""

import pytest

from scpi_control.connection.mock import MockConnection

NO_ERROR = '+0,"No error"'


def _conn(**kwargs):
    conn = MockConnection(**kwargs)
    conn.connect()
    return conn


@pytest.mark.parametrize("mode", ["daq_mode", "awg_mode", "psu_mode"])
def test_empty_queue_reports_no_error(mode):
    """All three instrument classes that expose get_error() must be able to ask.
    Only daq_mode answered before -- awg_mode and psu_mode timed out, so
    FunctionGenerator.get_error() and PowerSupply.get_error() were unusable
    against the mock entirely."""
    assert _conn(**{mode: True}).query("SYST:ERR?") == NO_ERROR


def test_errors_pop_oldest_first_then_drain_to_no_error():
    conn = _conn(awg_mode=True)
    conn.push_error(-222, "Data out of range")
    conn.push_error(-113, "Undefined header")

    assert conn.query("SYST:ERR?") == '-222,"Data out of range"'
    assert conn.query("SYST:ERR?") == '-113,"Undefined header"'
    assert conn.query("SYST:ERR?") == NO_ERROR


def test_cls_clears_the_queue():
    """*CLS is the standard way to clear status; the mock ignored it entirely."""
    conn = _conn(awg_mode=True)
    conn.push_error(-222, "Data out of range")
    conn.write("*CLS")
    assert conn.query("SYST:ERR?") == NO_ERROR


def test_scope_mode_still_has_no_error_query():
    """Scopes deliberately have no get_error -- scope.get_error() raises
    NotImplementedError and test_scpi_command_tables.py:38 asserts the command's
    absence. Adding a wire-level accessor here would quietly undo that gating, so
    scope mode must keep timing out. The queue itself still works; it just has no
    SCPI accessor, which matches the library's model."""
    from scpi_control import exceptions

    conn = _conn()  # default = scope mode
    with pytest.raises(exceptions.SiglentTimeoutError):
        conn.query("SYST:ERR?")
