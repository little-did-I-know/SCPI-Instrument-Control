"""Unmatched PSU/AWG/DAQ queries must behave like real instruments (audit M9).

The scope path already raises (mock/base.py). PSU/AWG/DAQ returned "", so a
driver bug that misspells a query produced float('') downstream instead of the
timeout a real instrument gives.
"""

import pytest

from scpi_control import exceptions
from scpi_control.connection.mock import MockConnection


def test_unmatched_psu_query_raises_by_default():
    """v5.0.0: strict is now the default, so unmatched queries time out like real hardware."""
    conn = MockConnection(psu_mode=True)
    conn.connect()
    with pytest.raises(exceptions.TimeoutError):
        conn.query("CH1:VOLTAGE?")


def test_unmatched_psu_query_returns_empty_when_lenient():
    """strict=False explicitly restores the pre-5.0.0 lenient "" behavior."""
    conn = MockConnection(psu_mode=True, strict=False)
    conn.connect()
    assert conn.query("CH1:VOLTAGE?") == ""


def test_unmatched_psu_query_times_out_in_strict_mode():
    conn = MockConnection(psu_mode=True, strict=True)
    conn.connect()
    with pytest.raises(exceptions.TimeoutError):
        conn.query("CH1:VOLTAGE?")


def test_matched_psu_query_still_answers_in_strict_mode():
    conn = MockConnection(psu_mode=True, strict=True)
    conn.connect()
    assert conn.query("CH1:VOLT?") == "0.000"


@pytest.mark.parametrize("mode", ["awg_mode", "daq_mode"])
def test_unmatched_awg_and_daq_queries_time_out_in_strict_mode(mode):
    conn = MockConnection(strict=True, **{mode: True})
    conn.connect()
    with pytest.raises(exceptions.TimeoutError):
        conn.query("NOSUCH:COMMAND?")
