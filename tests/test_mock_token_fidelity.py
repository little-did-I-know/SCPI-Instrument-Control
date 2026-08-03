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
