"""Trigger *type* selection per dialect -- backend review 2026-07-31, finding High-2.

The public vocabulary (EDGE/SLEW/GLIT/INTV/RUNT/PATTERN) is the legacy TRSE one.
Modern scopes spell these :TRIGger:TYPE {EDGE|PULSE|SLOPe|INTerval|RUNT|PATTern}
(SDS800X HD guide p.485); before this fix the legacy tokens were sent verbatim and
the scope silently stayed on EDGE. Tek families only share EDGE (TBS p.161 has
{EDGe|PULSe}, MSO2/MSO456 use WIDth) -> everything else gates loudly.
"""

import pytest

from scpi_control import exceptions
from scpi_control.connection.mock import MockConnection
from scpi_control.oscilloscope import Oscilloscope
from scpi_control.scpi_commands import trigger_type_from_wire, trigger_type_to_wire

MODERN_IDN = "Siglent Technologies,SDS824X HD,SDS08A0X804831,3.8.12.1.1.3.6"


def modern_scope():
    conn = MockConnection(idn=MODERN_IDN)
    scope = Oscilloscope(connection=conn, host="mock")
    scope.connect()
    return scope, conn


def test_modern_setter_sends_manual_tokens():
    scope, conn = modern_scope()
    scope.trigger.trigger_type = "SLEW"
    assert conn.writes[-1] == ":TRIGger:TYPE SLOPe"
    scope.trigger.trigger_type = "GLIT"
    assert conn.writes[-1] == ":TRIGger:TYPE PULSE"
    scope.trigger.trigger_type = "INTV"
    assert conn.writes[-1] == ":TRIGger:TYPE INTerval"


def test_modern_round_trip_returns_public_vocabulary():
    scope, _ = modern_scope()
    scope.trigger.trigger_type = "SLEW"
    assert scope.trigger.trigger_type == "SLEW"


def test_modern_getter_passes_through_unsettable_types():
    # A scope can sit in VIDeo (front panel); reads must not explode a snapshot.
    assert trigger_type_from_wire("modern", "VIDeo") == "VIDEO"


def test_tektronix_gates_everything_but_edge():
    assert trigger_type_to_wire("tektronix", "EDGE") == "EDGE"
    for t in ("SLEW", "GLIT", "INTV", "RUNT", "PATTERN"):
        with pytest.raises(exceptions.FeatureNotSupportedError):
            trigger_type_to_wire("tektronix", t)


def test_unknown_public_token_raises_value_error():
    with pytest.raises(ValueError):
        trigger_type_to_wire("modern", "BOGUS")


def test_mock_rejects_invalid_modern_type_like_hardware():
    # Measured 2026-07-31: invalid parameter queues -224, setting unchanged.
    scope, conn = modern_scope()
    scope.trigger.trigger_type = "EDGE"
    conn.write(":TRIGger:TYPE NONSENSE")
    assert conn.error_queue and conn.error_queue[0][0] == -224
    assert scope.trigger.trigger_type == "EDGE"
