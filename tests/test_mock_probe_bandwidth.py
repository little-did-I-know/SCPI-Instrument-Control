"""Probe ratio and bandwidth limit must answer on a legacy mock (audit L3).

gui/widgets/channel_control.py reads channel.probe_ratio and
channel.bandwidth_limit on every refresh (channel_control.py:239,244); with no
mock handler for either query on a legacy Siglent scope, the read raised
TimeoutError and the GUI showed an error. Task 14 adds mock state/handlers for
both, using the documented wire forms (RC01020-E01C p.22 ATTN, p.27 BWL) --
not the invented per-channel "C{ch}:BWL?" form the driver used to send.
"""

import pytest

from scpi_control.connection.mock import MockConnection
from scpi_control.oscilloscope import Oscilloscope

LEGACY_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"


@pytest.fixture
def scope():
    s = Oscilloscope(connection=MockConnection(idn=LEGACY_IDN), host="mock")
    s.connect()
    return s


def test_probe_ratio_round_trips(scope):
    scope.channel1.probe_ratio = 10.0
    assert scope.channel1.probe_ratio == pytest.approx(10.0)


def test_probe_ratio_default_reads_without_timeout(scope):
    """A fresh mock (no prior write) must still answer -- this is the GUI's
    default-refresh path (audit L3): construct + read, no write in between."""
    assert scope.channel1.probe_ratio == pytest.approx(1.0)


def test_bandwidth_limit_round_trips(scope):
    scope.channel1.bandwidth_limit = "ON"
    assert scope.channel1.bandwidth_limit == "ON"

    scope.channel1.bandwidth_limit = "OFF"
    assert scope.channel1.bandwidth_limit == "OFF"


def test_bandwidth_limit_default_reads_without_timeout(scope):
    """Same default-refresh path as probe_ratio above, for bandwidth_limit."""
    assert scope.channel1.bandwidth_limit == "OFF"


def test_bare_bwl_query_returns_all_channel_pairs(scope):
    """BWL? is documented as a GLOBAL query returning every channel's mode as
    <channel>,<mode> pairs (RC01020-E01C p.27) -- never a per-channel query."""
    scope.channel1.bandwidth_limit = "ON"
    response = scope._connection.query("BWL?")
    assert response.startswith("BWL ")
    assert "C1,ON" in response


def test_channel_control_read_path_does_not_time_out(scope):
    """Mirrors gui/widgets/channel_control.py's refresh: construct a Channel
    and read both properties back-to-back with no prior write (audit L3)."""
    probe = scope.channel1.probe_ratio
    bw = scope.channel1.bandwidth_limit
    assert isinstance(probe, float)
    assert bw in ("ON", "OFF")
