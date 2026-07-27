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
from scpi_control.exceptions import InvalidParameterError
from scpi_control.server.adapters import ADAPTERS, InstrumentAdapter, ScopeAdapter


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
    # Specifically the policy error, not bare Exception: a typo in the call
    # (TypeError) or a missing import (NameError) would satisfy `raises(Exception)`
    # while proving nothing about the policy check surviving the move.
    with pytest.raises(InvalidParameterError) as excinfo:
        adapter.build(address="10.0.0.1", port=9999, mock=False, model=None, allowed_ports=frozenset({5025}), connection=None)
    assert "refusing to connect" in str(excinfo.value)


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


# --- the initial-frame hook: a new kind must not inherit another's frame ----


def test_the_base_adapter_refuses_to_guess_an_initial_frame():
    """The stream handler used to branch on ``session.kind`` to build the
    opening frame, so a third kind would silently have been handed the scope's
    read_state() and blown up deep inside the handler. Declaring the hook on
    the base class means a kind that forgets it fails loudly and by name."""
    with pytest.raises(NotImplementedError):
        InstrumentAdapter().initial_frame(object())


def test_the_scope_initial_frame_matches_what_a_client_expects():
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
        adapter.connect(instrument)
        frame = adapter.initial_frame(instrument)
    finally:
        adapter.close(instrument)
    assert frame["type"] == "state"
    assert "kind" not in frame, "a scope frame carries no kind key -- the client discriminates on shape"
    assert set(frame["state"]) == {"run_state", "timebase", "channels", "trigger"}


def test_the_psu_initial_frame_matches_the_shape_poll_publishes():
    from scpi_control.server.adapters import PsuAdapter

    adapter = PsuAdapter()
    conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,1.0")
    instrument = adapter.build(address=None, port=5025, mock=True, model=None, allowed_ports=None, connection=conn)
    published = []
    try:
        adapter.connect(instrument)
        frame = adapter.initial_frame(instrument)
        adapter.poll(instrument, published.append, 1)
    finally:
        adapter.close(instrument)
    # Same shape at connect and on every tick: a client that discriminates on
    # the frame must not see one thing now and another 250 ms later.
    assert frame["type"] == "state" and frame["kind"] == "psu"
    assert set(frame) == set(published[0])
    assert set(frame["outputs"][0]) == set(published[0]["outputs"][0])


# --- a failed read must read as unknown, never as a confident value ---------


def test_an_unreadable_enable_state_is_unknown_not_off(monkeypatch):
    """The safety invariant's "vice versa" half: an energised output must never
    render as off. An SPD3303X's CH3 has no documented status bit and falls
    through to an OUTP3? the model does not implement, so a False default here
    would silently show a live rail as switched off."""
    from scpi_control.exceptions import SiglentError
    from scpi_control.power_supply_output import PowerSupplyOutput
    from scpi_control.server.adapters import PsuAdapter, read_psu_outputs

    def _unreadable(self):
        raise SiglentError("OUTP3? not supported")

    monkeypatch.setattr(PowerSupplyOutput, "enabled", property(_unreadable))

    adapter = PsuAdapter()
    conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,1.0")
    instrument = adapter.build(address=None, port=5025, mock=True, model=None, allowed_ports=None, connection=conn)
    try:
        adapter.connect(instrument)
        outputs = read_psu_outputs(instrument)
    finally:
        adapter.close(instrument)
    assert outputs, "fixture must produce at least one output"
    assert all(o["enabled"] is None for o in outputs), "an unreadable enable state must be None (unknown), never False"


# --- Minor 9: the measured triplet rides the every-Nth-tick budget ----------


def test_the_psu_adapter_throttles_the_measured_triplet_without_changing_the_frame():
    from scpi_control.server.adapters import MEASUREMENT_EVERY_N_POLLS, PsuAdapter

    adapter = PsuAdapter()
    conn = MockConnection(psu_mode=True, psu_idn="Siglent Technologies,SPD3303X,SPD123456,1.0")
    instrument = adapter.build(address=None, port=5025, mock=True, model=None, allowed_ports=None, connection=conn)
    measure_queries = []
    real_query = conn.query

    def counting_query(command):
        if "MEAS" in command.upper():
            measure_queries.append(command)
        return real_query(command)

    frames = []
    per_tick = []
    try:
        adapter.connect(instrument)
        conn.query = counting_query
        # Ticks 1..4. Tick 1 measures because the cache is empty (a fresh
        # stream must never be briefly blank); ticks 2 and 3 must not; tick 4
        # measures again because 4 % MEASUREMENT_EVERY_N_POLLS == 0.
        for tick in range(1, MEASUREMENT_EVERY_N_POLLS + 1):
            del measure_queries[:]
            adapter.poll(instrument, frames.append, tick)
            per_tick.append(len(measure_queries))
    finally:
        conn.query = real_query
        adapter.close(instrument)

    assert per_tick[0] > 0, "the first tick must measure -- fixture broken if not"
    assert per_tick[1] == 0 and per_tick[2] == 0, "throttled ticks must issue NO measurement queries, got {0}".format(per_tick)
    assert per_tick[3] == per_tick[0], "every Nth tick must measure again, got {0}".format(per_tick)
    # ...and the frame shape is identical on every tick, throttled or not, so
    # the UI never blanks its readings three ticks out of four.
    keys = [set(frame["outputs"][0]) for frame in frames]
    assert all(k == keys[0] for k in keys)
    assert all(frame["outputs"][0]["measured_voltage"] is not None for frame in frames), "throttled ticks must reuse the last known reading"


def test_the_awg_adapter_builds_and_connects_a_mock():
    from scpi_control.server.adapters import AwgAdapter

    adapter = AwgAdapter()
    conn = MockConnection("mock", awg_mode=True, awg_idn="Siglent Technologies,SDG1032X,SDG1XXXXX,2.01.01.37R1")
    instrument = adapter.build(address=None, port=5025, mock=True, model=None, allowed_ports=None, connection=conn)
    try:
        identity = adapter.connect(instrument)
        assert "SDG1032X" in identity["idn"]
        assert identity["num_channels"] >= 1, "num_channels carries the AWG's channel count"
    finally:
        adapter.close(instrument)


def test_the_awg_adapter_publishes_channel_state():
    from scpi_control.server.adapters import AwgAdapter

    adapter = AwgAdapter()
    conn = MockConnection("mock", awg_mode=True, awg_idn="Siglent Technologies,SDG1032X,SDG1XXXXX,2.01.01.37R1")
    instrument = adapter.build(address=None, port=5025, mock=True, model=None, allowed_ports=None, connection=conn)
    published = []
    try:
        adapter.connect(instrument)
        adapter.poll(instrument, published.append, 1)
    finally:
        adapter.close(instrument)
    assert len(published) == 1, "an AWG emits one state message per tick, like a PSU and unlike a scope's frame-per-channel"
    state = published[0]
    assert state["kind"] == "awg"
    first = state["channels"][0]
    assert {"channel", "function", "frequency", "amplitude", "offset", "phase", "enabled", "duty_cycle", "symmetry"} <= set(first)


def test_the_awg_initial_frame_matches_the_polled_shape():
    """A client that discriminates on frame shape must not see one thing at
    connect and another a quarter-second later."""
    from scpi_control.server.adapters import AwgAdapter

    adapter = AwgAdapter()
    conn = MockConnection("mock", awg_mode=True, awg_idn="Siglent Technologies,SDG1032X,SDG1XXXXX,2.01.01.37R1")
    instrument = adapter.build(address=None, port=5025, mock=True, model=None, allowed_ports=None, connection=conn)
    published = []
    try:
        adapter.connect(instrument)
        adapter.poll(instrument, published.append, 1)
        opening = adapter.initial_frame(instrument)
    finally:
        adapter.close(instrument)
    assert set(opening) == set(published[0])
    assert set(opening["channels"][0]) == set(published[0]["channels"][0])


def test_the_awg_adapter_has_no_scope_or_psu_state():
    from scpi_control.server.adapters import AwgAdapter

    adapter = AwgAdapter()
    for foreign in ("measurements", "spectrum_config", "filters", "active_reference", "recorder", "_measured"):
        assert not hasattr(adapter, foreign), "{0} belongs to another kind and must not be on the AWG adapter".format(foreign)


def test_the_awg_reader_skips_shape_parameters_that_do_not_apply():
    """pulse_duty_cycle logs a warning on every read when the function is not
    PULSE (awg_output.py:281). At four polls a second that is a warning flood,
    so the reader must not ask for a parameter the current function ignores."""
    from scpi_control.server.adapters import read_awg_channels
    from scpi_control import FunctionGenerator

    conn = MockConnection("mock", awg_mode=True, awg_idn="Siglent Technologies,SDG1032X,SDG1XXXXX,2.01.01.37R1")
    awg = FunctionGenerator("mock", connection=conn)
    awg.connect()
    try:
        channel = awg.get_channel(1)
        channel.function = "SINE"
        rows = read_awg_channels(awg)
        assert rows[0]["duty_cycle"] is None, "duty cycle is meaningless for SINE and must not be read"
        assert rows[0]["symmetry"] is None, "symmetry is meaningless for SINE and must not be read"

        channel.function = "PULSE"
        rows = read_awg_channels(awg)
        assert rows[0]["duty_cycle"] is not None, "duty cycle must be read when the function IS PULSE"
        assert rows[0]["symmetry"] is None

        channel.function = "RAMP"
        rows = read_awg_channels(awg)
        assert rows[0]["symmetry"] is not None, "symmetry must be read when the function IS RAMP"
        assert rows[0]["duty_cycle"] is None
    finally:
        awg.disconnect()
