"""DAQ mock dispatch and write handling (audit M7, M8)."""

import pytest

from scpi_control.connection.mock import MockConnection


@pytest.fixture
def daq():
    conn = MockConnection(daq_mode=True, daq_readings="1.234,2.345,3.456")
    conn.connect()
    return conn


def test_error_query_is_not_hijacked_by_the_readings_matcher(daq):
    """'R?' as a substring matched SYST:ERR? and returned measurement data."""
    assert daq.query("SYST:ERR?") == '+0,"No error"'


def test_trigger_source_query_is_not_hijacked(daq):
    assert daq.query("TRIG:SOUR?") != daq.daq_readings


def test_read_query_still_returns_readings(daq):
    assert daq.query("READ?") == "1.234,2.345,3.456"


def test_scan_list_round_trips(daq):
    """set then get must reflect the write -- round-trip verification code
    concluded configuration had failed on a healthy instrument (M8)."""
    daq.write("ROUT:SCAN (@101,102)")
    assert daq.query("ROUT:SCAN?") == "(@101,102)"


def test_trigger_source_default_is_immediate(daq):
    assert daq.query("TRIG:SOUR?") == "IMM"


def test_trigger_source_write_round_trips(daq):
    daq.write("TRIG:SOUR BUS")
    assert daq.query("TRIG:SOUR?") == "BUS"


def test_error_query_still_answers_in_strict_mode():
    """Reordering must not push handled queries past the strict-mode raise."""
    conn = MockConnection(daq_mode=True, strict=True)
    conn.connect()
    assert conn.query("SYST:ERR?") == '+0,"No error"'
    assert conn.query("TRIG:SOUR?") == "IMM"
