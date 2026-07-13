"""Tests for dialect-routed scope-level operations and status polling."""

import pytest

from scpi_control import Oscilloscope
from scpi_control.connection.mock import MockConnection

LEGACY_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"


def make_scope(**mock_kwargs):
    conn = MockConnection("mock", idn=LEGACY_IDN, **mock_kwargs)
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    return scope, conn


def test_acquisition_status_uses_sast_on_legacy():
    scope, conn = make_scope(trigger_status=["Ready", "Trig'd"])
    assert scope.acquisition_status() == "READY"
    assert scope.acquisition_status() == "TRIGD"
    assert "SAST?" in conn.queries
    assert ":TRIG:STAT?" not in conn.queries
    scope.disconnect()


def test_run_stop_single_route_through_table():
    scope, conn = make_scope()
    scope.run()
    scope.stop()
    scope.trigger_single()
    assert "TRIG_MODE AUTO" in conn.writes
    assert "STOP" in conn.writes
    assert "TRIG_MODE SINGLE" in conn.writes
    assert "ARM" in conn.writes
    scope.disconnect()


def test_get_error_raises_not_implemented():
    scope, conn = make_scope()
    with pytest.raises(NotImplementedError):
        scope.get_error()
    scope.disconnect()


def test_timebase_setter_routes():
    scope, conn = make_scope()
    scope.timebase = 0.001
    assert "TDIV 0.001" in conn.writes
    scope.disconnect()
