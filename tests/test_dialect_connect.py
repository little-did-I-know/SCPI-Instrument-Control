"""Tests for connect-time dialect resolution and CHDR OFF."""

import pytest

from scpi_control import Oscilloscope
from scpi_control.connection.mock import MockConnection

LEGACY_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"
MODERN_IDN = "Siglent Technologies,SDS824X HD,MOCK0002,3.8.12"


def make_scope(idn, **kwargs):
    conn = MockConnection("mock", idn=idn)
    scope = Oscilloscope("mock", connection=conn, **kwargs)
    scope.connect()
    return scope, conn


def test_legacy_scope_resolves_legacy_and_sends_chdr_off():
    scope, conn = make_scope(LEGACY_IDN)
    assert scope.dialect == "legacy"
    assert "CHDR OFF" in conn.writes
    scope.disconnect()


def test_modern_scope_resolves_modern_and_skips_chdr():
    scope, conn = make_scope(MODERN_IDN)
    assert scope.dialect == "modern"
    assert "CHDR OFF" not in conn.writes
    assert scope._scpi_commands.dialect == "modern"
    scope.disconnect()


def test_dialect_override_forces_legacy_on_modern_scope():
    scope, conn = make_scope(MODERN_IDN, dialect="legacy")
    assert scope.dialect == "legacy"
    assert "CHDR OFF" in conn.writes
    scope.disconnect()


def test_invalid_dialect_rejected_at_init():
    with pytest.raises(Exception):
        Oscilloscope("mock", dialect="klingon")


def test_dialect_is_none_before_connect():
    scope = Oscilloscope("mock", connection=MockConnection("mock"))
    assert scope.dialect is None
