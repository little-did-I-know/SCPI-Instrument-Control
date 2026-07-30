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
    adapter = ScopeAdapter()
    scope = _FakeScope(_RaisingChannel())
    with caplog.at_level(logging.INFO, logger=ADAPTERS_LOGGER):
        caplog.clear()
        adapter.poll(scope, lambda frame: None, 1)  # fail
        adapter.poll(scope, lambda frame: None, 2)  # fail (steady state, no new log)
        scope.channel = _OkChannel()
        adapter.poll(scope, lambda frame: None, 3)  # recover

    warnings = _adapter_records(caplog, logging.WARNING)
    all_records = [r for r in caplog.records if r.name == ADAPTERS_LOGGER]
    recoveries = [r for r in all_records if r.levelno < logging.WARNING]

    assert len(warnings) == 1, "the failure must still log exactly once: {0}".format(warnings)
    # Without a recovery line, a reader of the log has no way to tell whether
    # an outage that shows up as a WARNING is still ongoing.
    assert len(recoveries) == 1, "a failure->success transition must log a recovery record: {0}".format(all_records)
    assert "channel 1" in recoveries[0].getMessage(), "the recovery record must name the operation that recovered"


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
