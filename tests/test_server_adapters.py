"""The per-kind adapter seam.

InstrumentSession used to be an Oscilloscope session: submit() was typed to it
and the poll loop read waveforms directly. Adding a second instrument kind meant
either branching a 500-line file or subclassing threading code that should have
exactly one implementation. The adapter owns what varies -- build, connect, poll,
and kind-specific state -- and the session owns what does not.

These tests exercise adapters with NO server and no HTTP, which is the whole
point of the seam: the expensive parts of a session are not needed to check that
an instrument kind is wired up correctly.
"""

import pytest

from scpi_control.connection.mock import MockConnection
from scpi_control.server.adapters import ADAPTERS, ScopeAdapter


def test_the_registry_exposes_the_scope_adapter():
    assert ADAPTERS["scope"].kind == "scope"


def test_the_scope_adapter_builds_and_connects_a_mock():
    adapter = ScopeAdapter()
    conn = MockConnection(
        "mock",
        idn="Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0",
        channel_states={1: True, 2: False, 3: False, 4: False},
        trigger_status=["Stop"],
        sample_rate=1_000_000.0,
        timebase=1e-3,
    )
    instrument = adapter.build(address=None, port=5025, mock=True, model=None, allowed_ports=None, connection=conn)
    try:
        identity = adapter.connect(instrument)
        assert identity["idn"].startswith("Siglent")
        assert identity["num_channels"] == 4
        assert identity["dialect"]
    finally:
        adapter.close(instrument)


def test_the_scope_adapter_publishes_frames_when_polled():
    """poll() is the contract the session's tick depends on: it must publish
    through the callback rather than returning, because a scope emits several
    messages per tick (a frame per channel, math, filters, spectrum)."""
    adapter = ScopeAdapter()
    conn = MockConnection(
        "mock",
        idn="Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0",
        channel_states={1: True, 2: False, 3: False, 4: False},
        trigger_status=["Stop"],
        sample_rate=1_000_000.0,
        timebase=1e-3,
    )
    instrument = adapter.build(address=None, port=5025, mock=True, model=None, allowed_ports=None, connection=conn)
    published = []
    try:
        adapter.connect(instrument)
        adapter.poll(instrument, published.append, 1)
    finally:
        adapter.close(instrument)
    assert published, "a connected scope with an enabled channel must publish at least one frame"
    assert any(message.get("type") == "frame" or "points" in message for message in published)


def test_a_non_mock_build_validates_the_target():
    """The network policy check must not be lost in the move: an address outside
    the allowed set is refused before any socket is opened."""
    adapter = ScopeAdapter()
    with pytest.raises(Exception):
        adapter.build(address="10.0.0.1", port=9999, mock=False, model=None, allowed_ports=frozenset({5025}), connection=None)
