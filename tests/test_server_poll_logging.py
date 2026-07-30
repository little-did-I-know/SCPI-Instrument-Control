"""A poll-path query failure must stop being silent.

The incident: a scope's channel-enabled query started raising SiglentError,
_safe() swallowed it with no log line, and the channel silently read as "off"
-- no frames, no error, no clue. Diagnosing the frozen live view took an hour
of ruling out the transport, the bundle, auth, and the frontend, because
nothing in the gateway ever said a query had failed.

The fix must not become the next incident in the other direction: logging
every tick of a persistent failure would write four lines a second at the
0.25s poll interval and bury every other line in the log. So the discipline
is once per transition -- one WARNING when a query starts failing, one
recovery record when it starts succeeding again, nothing in between.

These tests build the failing query with a fake scope whose channel accessor
raises, rather than by monkeypatching _safe -- so the real _safe/poll() path
is what's under test.
"""

import logging

from scpi_control.exceptions import SiglentError
from scpi_control.server.adapters import ScopeAdapter

ADAPTERS_LOGGER = "scpi_control.server.adapters"


class _RaisingChannel:
    """A channel whose display query (the `.enabled` accessor) always fails,
    exactly like the incident's channel-enabled read."""

    @property
    def enabled(self):
        raise SiglentError("C1:TRA? timed out")


class _OkChannel:
    enabled = True


class _FakeWaveform:
    time = [0.0, 1.0]
    voltage = [0.0, 1.0]


class _FakeScope:
    """Just enough surface for ScopeAdapter.poll(): one channel, no math, a
    gate that always says "go", and a waveform read that never fails -- the
    only thing under test is what happens when the channel accessor raises.
    """

    supported_channels = [1]
    math1 = None
    math2 = None

    def __init__(self, channel):
        self.channel = channel

    def new_acquisition_ready(self):
        return True

    def record_length(self):
        return 2

    def waveform_max_points(self):
        return 1000

    def get_channel(self, n):
        return self.channel

    def get_waveform(self, channel, provenance=False, stride=None):
        return _FakeWaveform()


def _adapter_records(caplog, level=logging.WARNING):
    """Records from OUR logger only, at-or-above `level`. Filtering by logger
    name (not just clearing caplog) keeps these assertions robust to any
    unrelated warning some other module happens to log during the same tick.
    """
    return [r for r in caplog.records if r.name == ADAPTERS_LOGGER and r.levelno >= level]


def test_a_failed_poll_query_is_logged_once_per_transition(caplog):
    adapter = ScopeAdapter()
    scope = _FakeScope(_RaisingChannel())
    with caplog.at_level(logging.WARNING, logger=ADAPTERS_LOGGER):
        caplog.clear()
        adapter.poll(scope, lambda frame: None, 1)
        adapter.poll(scope, lambda frame: None, 2)

    warnings = _adapter_records(caplog, logging.WARNING)
    # One per tick would bury the log: at 0.25s a persistent failure would
    # write four lines a second.
    assert len(warnings) == 1, "a persistent failure must log once, not once per tick: {0}".format(warnings)
    assert "channel 1" in warnings[0].getMessage(), "the warning must name the failing operation"


def test_recovery_is_logged_so_the_log_shows_the_end_of_the_outage(caplog):
    """The recovery record must be a WARNING, not a quieter level: an
    operator or alerting pipeline filtering at WARNING -- the level the
    onset failure logs at -- must see the outage both begin AND end, or the
    log is exactly as ambiguous as it was before this fix for that reader.
    A level-agnostic "a recovery record exists somewhere" assertion cannot
    tell that design apart from a design that quietly logs recovery at INFO,
    so this asserts the level explicitly.
    """
    adapter = ScopeAdapter()
    scope = _FakeScope(_RaisingChannel())
    with caplog.at_level(logging.WARNING, logger=ADAPTERS_LOGGER):
        caplog.clear()
        adapter.poll(scope, lambda frame: None, 1)  # fail
        adapter.poll(scope, lambda frame: None, 2)  # fail (steady state, no new log)
        scope.channel = _OkChannel()
        adapter.poll(scope, lambda frame: None, 3)  # recover

    all_records = _adapter_records(caplog, logging.WARNING)
    failures = [r for r in all_records if "failed" in r.getMessage()]
    recoveries = [r for r in all_records if "recovered" in r.getMessage()]

    assert len(failures) == 1, "the failure must still log exactly once: {0}".format(all_records)
    # Without a recovery line, a reader of the log has no way to tell whether
    # an outage that shows up as a WARNING is still ongoing.
    assert len(recoveries) == 1, "a failure->success transition must log a recovery record: {0}".format(all_records)
    assert recoveries[0].levelno == logging.WARNING, "the recovery record must be WARNING, matching the failure's level"
    assert "channel 1" in recoveries[0].getMessage(), "the recovery record must name the operation that recovered"


def test_a_query_that_degrades_inside_the_accessor_is_silent_by_design(caplog):
    """Final-review fix (cheap 1): poll() passed label="acquisition ready
    check" (and labels for record length / waveform max points) to _safe, but
    all three accessors catch their own query failure and return None -- so
    _safe never sees an exception from them and its logging branch is
    unreachable. The labels promised log lines that could never be written.

    A modern-dialect mock is exactly that situation for real: it has no
    response for INR? or :ACQuire:POINts?, so both queries genuinely fail and
    both accessors genuinely degrade to None. The tick must still publish a
    frame (a gate we cannot read is "no gate", not "not ready") and must stay
    silent, since nothing was swallowed at this level.
    """
    from scpi_control.connection.mock import MockConnection
    from scpi_control.oscilloscope import Oscilloscope

    conn = MockConnection("mock", idn="Siglent Technologies,SDS824X HD,MOCK0001,1.0.0.0", channel_states={1: True, 2: False, 3: False, 4: False}, sample_rate=1_000_000.0, timebase=1e-3)
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    assert scope.dialect == "modern"
    assert scope.new_acquisition_ready() is None, "fixture broken: the modern mock is expected to fail INR?, degrading the gate to None"
    assert scope.record_length() is None, "fixture broken: the modern mock is expected to fail :ACQuire:POINts?"

    adapter = ScopeAdapter()
    published = []
    with caplog.at_level(logging.WARNING, logger=ADAPTERS_LOGGER):
        caplog.clear()
        adapter.poll(scope, published.append, 1)

    assert any(frame.get("type") == "waveform" for frame in published), "an unreadable gate must not stall the live view"
    assert _adapter_records(caplog, logging.WARNING) == [], "these three queries degrade inside the accessor -- the adapter has nothing to report"


def test_a_healthy_poll_logs_nothing(caplog):
    adapter = ScopeAdapter()
    scope = _FakeScope(_OkChannel())
    with caplog.at_level(logging.INFO, logger=ADAPTERS_LOGGER):
        caplog.clear()
        adapter.poll(scope, lambda frame: None, 1)

    # Filtered by logger name and level, not "caplog is entirely empty": that
    # keeps this test robust to an unrelated record some other module logs.
    at_or_above_warning = _adapter_records(caplog, logging.WARNING)
    assert at_or_above_warning == [], "a normal tick must not log at WARNING or above: {0}".format(at_or_above_warning)
