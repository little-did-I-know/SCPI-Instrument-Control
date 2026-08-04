"""scope.capabilities derivation (typed-instrument-api Task 6)."""

import dataclasses

import pytest

from scpi_control import exceptions
from scpi_control.oscilloscope import Oscilloscope
from scpi_control.connection.mock import MockConnection
from scpi_control.vocabulary import Coupling, TriggerType

# Copy these two constants from tests/test_dialect_connect.py verbatim.
from tests.test_dialect_connect import MODERN_IDN  # adjust if the constant lives elsewhere in that file


def make_scope(idn, **kwargs):
    conn = MockConnection("mock", idn=idn)
    scope = Oscilloscope("mock", connection=conn, **kwargs)
    scope.connect()
    return scope, conn


def test_capabilities_raise_before_connect():
    scope = Oscilloscope("mock", connection=MockConnection("mock"))
    with pytest.raises(exceptions.SiglentConnectionError):
        scope.capabilities


def test_capabilities_cleared_on_disconnect():
    scope, _ = make_scope(MODERN_IDN)
    assert scope.capabilities is not None
    scope.disconnect()
    with pytest.raises(exceptions.SiglentConnectionError):
        scope.capabilities


def test_modern_capabilities_derive_from_the_tables():
    scope, _ = make_scope(MODERN_IDN)
    caps = scope.capabilities
    assert caps.dialect == "modern"
    assert caps.trigger_types == frozenset({"EDGE", "SLEW", "GLIT", "INTV", "RUNT", "PATTERN"})
    assert caps.trigger_modes == frozenset({"AUTO", "NORM", "SINGLE", "STOP"})
    assert caps.channel_couplings == frozenset({"DC", "AC", "GND"})
    assert caps.trigger_couplings == frozenset({"DC", "AC", "HFREJ", "LFREJ"})
    # Enum membership works because name == value (pinned in test_vocabulary):
    assert TriggerType.GLIT in caps.trigger_types
    assert Coupling.GND in caps.channel_couplings
    # Modern has no legacy-only subsystems:
    assert caps.has_trigger_holdoff is False
    assert caps.has_channel_unit is False
    assert caps.has_measurement_statistics is False
    assert caps.has_probe_ratio is True
    assert caps.max_channels == scope.model_capability.num_channels


def test_tektronix_gaps_are_visible():
    scope, _ = make_scope("TEKTRONIX,MSO24,MOCK0100,FV:1.28")
    caps = scope.capabilities
    assert caps.dialect == "tektronix"
    assert caps.trigger_types == frozenset({"EDGE"})
    assert Coupling.GND not in caps.channel_couplings
    assert "AC" not in caps.trigger_couplings
    assert caps.trigger_sources == frozenset({"C1", "C2", "C3", "C4", "EX"})
    assert caps.has_trigger_holdoff is True
    # MSO24 resolves tek_mso -> badge measurements, not IMMed (CMEAN unmapped):
    assert "CMEAN" not in caps.measurement_types
    assert "PKPK" in caps.measurement_types


def test_capabilities_are_immutable():
    scope, _ = make_scope(MODERN_IDN)
    with pytest.raises(dataclasses.FrozenInstanceError):
        scope.capabilities.dialect = "legacy"
