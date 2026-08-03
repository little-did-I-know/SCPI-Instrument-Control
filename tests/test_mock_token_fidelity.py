"""Mock accept-sets derive from the shared token tables (Task 8)."""

import pytest

from scpi_control import scpi_commands as sc
from scpi_control.connection.mock import MockConnection
from scpi_control.oscilloscope import Oscilloscope

from tests.test_dialect_connect import LEGACY_IDN, MODERN_IDN  # same import note as Task 6


def make_scope(idn):
    conn = MockConnection("mock", idn=idn)
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    return scope, conn


@pytest.mark.parametrize("idn", [MODERN_IDN, LEGACY_IDN])
def test_mock_accepts_every_public_coupling_the_driver_can_send(idn):
    scope, conn = make_scope(idn)
    for token in sorted(sc.supported_couplings(scope.dialect)):
        scope.channel1.coupling = token
        assert scope.channel1.coupling == token
        assert conn.error_queue == []


def test_mock_rejects_an_undocumented_coupling_token_like_hardware():
    scope, conn = make_scope(MODERN_IDN)
    scope.channel1.coupling = "AC"  # known-good baseline
    conn.write(":CHANnel1:COUPling BOGUS")  # bypass driver validation
    assert conn.error_queue == [(-224, "Illegal parameter value")]
    assert scope.channel1.coupling == "AC"  # state unchanged


def test_mock_rejects_an_undocumented_trigger_mode():
    scope, conn = make_scope(MODERN_IDN)
    conn.write(":TRIGger:MODE SOMETIMES")
    assert conn.error_queue == [(-224, "Illegal parameter value")]


def test_mock_acceptance_derives_from_the_shared_table(monkeypatch):
    # MUTATION GUARD (mutation-test-the-guard-tests): mutate the shared table
    # and prove the mock MOVES WITH the driver -- accepting the new wire token
    # and rejecting the old one. If the mock kept a private copy, this fails.
    scope, conn = make_scope(MODERN_IDN)
    monkeypatch.setitem(sc._COUPLING_TO_WIRE["modern"], "DC", "DCX")
    scope.channel1.coupling = "DC"  # driver now sends DCX
    assert conn.error_queue == []
    conn.write(":CHANnel1:COUPling DC")  # the OLD token is now foreign
    assert conn.error_queue == [(-224, "Illegal parameter value")]


def test_mock_rejects_an_undocumented_legacy_trigger_mode():
    scope, conn = make_scope(LEGACY_IDN)
    scope.trigger.mode = "AUTO"  # known-good baseline
    conn.write("TRIG_MODE BOGUS")  # bypass driver validation
    assert conn.error_queue == [(-224, "Illegal parameter value")]
    assert scope.trigger.mode == "AUTO"  # state unchanged


def test_mock_rejects_an_undocumented_legacy_trigger_slope():
    scope, conn = make_scope(LEGACY_IDN)
    scope.trigger.slope = "POS"  # known-good baseline
    conn.write("C1:TRSL BOGUS")  # bypass driver validation
    assert conn.error_queue == [(-224, "Illegal parameter value")]
    assert scope.trigger.slope == "POS"  # state unchanged


def test_mock_accepts_every_legacy_trigger_mode_the_driver_sends_via_trig_mode():
    # STOP is excluded: the driver's mode setter diverts it to the separate
    # bare "STOP" command (self._cmd("stop")), never to TRIG_MODE, so it
    # never reaches this guard -- AUTO/NORM/SINGLE are the tokens TRIG_MODE
    # actually carries for the legacy dialect.
    scope, conn = make_scope(LEGACY_IDN)
    for mode in sorted(sc.supported_trigger_modes("legacy") - {"STOP"}):
        scope.trigger.mode = mode
        assert scope.trigger.mode == mode
        assert conn.error_queue == []


def test_mock_accepts_every_legacy_trigger_slope_the_driver_can_send():
    scope, conn = make_scope(LEGACY_IDN)
    for slope in sorted(sc.supported_trigger_slopes("legacy")):
        scope.trigger.slope = slope
        assert scope.trigger.slope == slope
        assert conn.error_queue == []


def test_legacy_run_sends_trig_mode_auto_without_error():
    # run() is the OTHER call site that writes TRIG_MODE AUTO directly
    # (scpi_commands.py's legacy "run" template), not through Trigger.mode --
    # confirm the guard doesn't clip it.
    scope, conn = make_scope(LEGACY_IDN)
    scope.run()
    assert "TRIG_MODE AUTO" in conn.writes
    assert conn.error_queue == []
