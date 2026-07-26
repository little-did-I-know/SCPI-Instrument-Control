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


def test_the_psu_adapter_builds_and_connects_a_mock():
    from scpi_control.server.adapters import PsuAdapter

    adapter = PsuAdapter()
    conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,1.0")
    instrument = adapter.build(address=None, port=5025, mock=True, model=None, allowed_ports=None, connection=conn)
    try:
        identity = adapter.connect(instrument)
        assert "SPD3303X" in identity["idn"]
        assert identity["num_channels"] >= 1, "num_channels carries the PSU's OUTPUT count"
    finally:
        adapter.close(instrument)


def test_the_psu_adapter_publishes_measured_values():
    from scpi_control.server.adapters import PsuAdapter

    adapter = PsuAdapter()
    conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,1.0")
    instrument = adapter.build(address=None, port=5025, mock=True, model=None, allowed_ports=None, connection=conn)
    published = []
    try:
        adapter.connect(instrument)
        adapter.poll(instrument, published.append, 1)
    finally:
        adapter.close(instrument)
    assert len(published) == 1, "a PSU emits one state message per tick, unlike a scope's frame-per-channel"
    state = published[0]
    assert state["kind"] == "psu"
    first = state["outputs"][0]
    assert {"output", "voltage", "current", "enabled", "measured_voltage", "measured_current", "measured_power"} <= set(first)


def test_the_psu_adapter_has_no_scope_state():
    """The point of moving state onto adapters: a PSU session must not carry a
    spectrum config or a filter bank it can never use."""
    from scpi_control.server.adapters import PsuAdapter

    adapter = PsuAdapter()
    for scope_only in ("measurements", "spectrum_config", "filters", "active_reference", "recorder"):
        assert not hasattr(adapter, scope_only), f"{scope_only} is scope-only and must not be on the PSU adapter"
