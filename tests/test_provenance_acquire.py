"""Acquire attaches provenance; hot paths and failures skip it safely."""

import logging
from unittest.mock import patch

import pytest

from scpi_control.connection import MockConnection
from scpi_control.oscilloscope import Oscilloscope


@pytest.fixture
def mock_scope():
    conn = MockConnection(
        "mock",
        idn="Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0",
        channel_states={1: True, 2: False, 3: False, 4: False},
        trigger_status=["Stop"],
        sample_rate=1_000.0,
        timebase=1e-3,
        waveform_payloads={1: bytes(range(256))},
    )
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    yield scope
    scope.disconnect()


def test_acquire_attaches_provenance(mock_scope):
    data = mock_scope.get_waveform(1)
    assert data.provenance is not None
    assert data.provenance.instrument.model == "SDS1104X-E"
    assert 1 in data.provenance.channels
    assert data.provenance.acquired_at


def test_acquire_provenance_false_skips_snapshot(mock_scope):
    data = mock_scope.get_waveform(1, provenance=False)
    assert data.provenance is None


def test_snapshot_failure_never_breaks_acquire(mock_scope, caplog):
    with patch("scpi_control.waveform.AcquisitionProvenance.from_scope", side_effect=RuntimeError("boom")):
        with caplog.at_level(logging.WARNING):
            data = mock_scope.get_waveform(1)
    assert data.provenance is None
    assert len(data.voltage) > 0
    assert any("provenance" in r.message.lower() for r in caplog.records)
