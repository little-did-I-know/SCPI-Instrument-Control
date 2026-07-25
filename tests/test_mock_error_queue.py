"""The mock's SCPI error queue.

Real instruments accept a bad command, ignore it, and queue an error for later
collection. The mock used to answer '+0,"No error"' unconditionally, so
FunctionGenerator.get_error() and DataLogger.get_error() could only ever report
perfect health and no caller-side error handling was reachable in tests.
"""

import pytest

from scpi_control.connection.mock import MockConnection

NO_ERROR = '+0,"No error"'


def _conn(**kwargs):
    conn = MockConnection(**kwargs)
    conn.connect()
    return conn


@pytest.mark.parametrize("mode", ["daq_mode", "awg_mode", "psu_mode"])
def test_empty_queue_reports_no_error(mode):
    """All three instrument classes that expose get_error() must be able to ask.
    Only daq_mode answered before -- awg_mode and psu_mode timed out, so
    FunctionGenerator.get_error() and PowerSupply.get_error() were unusable
    against the mock entirely."""
    assert _conn(**{mode: True}).query("SYST:ERR?") == NO_ERROR


def test_errors_pop_oldest_first_then_drain_to_no_error():
    conn = _conn(awg_mode=True)
    conn.push_error(-222, "Data out of range")
    conn.push_error(-113, "Undefined header")

    assert conn.query("SYST:ERR?") == '-222,"Data out of range"'
    assert conn.query("SYST:ERR?") == '-113,"Undefined header"'
    assert conn.query("SYST:ERR?") == NO_ERROR


def test_cls_clears_the_queue():
    """*CLS is the standard way to clear status; the mock ignored it entirely."""
    conn = _conn(awg_mode=True)
    conn.push_error(-222, "Data out of range")
    conn.write("*CLS")
    assert conn.query("SYST:ERR?") == NO_ERROR


def test_scope_mode_still_has_no_error_query():
    """Scopes deliberately have no get_error -- scope.get_error() raises
    NotImplementedError and test_scpi_command_tables.py:38 asserts the command's
    absence. Adding a wire-level accessor here would quietly undo that gating, so
    scope mode must keep timing out. The queue itself still works; it just has no
    SCPI accessor, which matches the library's model."""
    from scpi_control import exceptions

    conn = _conn()  # default = scope mode
    with pytest.raises(exceptions.SiglentTimeoutError):
        conn.query("SYST:ERR?")


import math

from scpi_control import exceptions

LEGACY_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"


@pytest.mark.parametrize(
    "value",
    [1e9, -5.0, 0.0, float("nan"), float("inf")],
    ids=["absurd", "negative", "zero", "nan", "inf"],
)
def test_invalid_voltage_scale_is_rejected_and_queued(value):
    conn = _conn(idn=LEGACY_IDN)
    before = conn._voltage_scales.get(1)

    conn.write("C1:VDIV {0}".format(value))

    assert conn._voltage_scales.get(1) == before, "a rejected command must not change state"
    # Scope mode has no SYST:ERR? accessor (scopes expose no get_error), so assert
    # on the queue attribute directly rather than over the wire.
    assert conn.error_queue == [(-222, "Data out of range")]


def test_valid_voltage_scale_is_accepted_and_queues_nothing():
    conn = _conn(idn=LEGACY_IDN)
    conn.write("C1:VDIV 0.5")
    assert conn._voltage_scales[1] == 0.5
    assert conn.error_queue == []


MODERN_IDN = "Siglent Technologies,SDS824X HD,MOCK0002,3.8.12"


@pytest.mark.parametrize(
    "value",
    [-5.0, 0.0, float("nan"), float("inf")],
    ids=["negative", "zero", "nan", "inf"],
)
def test_invalid_probe_attenuation_is_rejected_and_queued(value):
    conn = _conn(idn=LEGACY_IDN)
    before = conn.probe_ratios.get(1)

    conn.write("C1:ATTN {0}".format(value))

    assert conn.probe_ratios.get(1) == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range")]


def test_valid_probe_attenuation_is_accepted_and_queues_nothing():
    conn = _conn(idn=LEGACY_IDN)
    conn.write("C1:ATTN 10")
    assert conn.probe_ratios[1] == 10.0
    assert conn.error_queue == []


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf")],
    ids=["nan", "inf"],
)
def test_invalid_legacy_trigger_level_is_rejected_and_queued(value):
    conn = _conn(idn=LEGACY_IDN)
    before = conn.trigger_level.get(1)

    conn.write("C1:TRLV {0}".format(value))

    assert conn.trigger_level.get(1) == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range")]


def test_valid_negative_legacy_trigger_level_is_accepted_and_queues_nothing():
    """positive=False must still be honored -- a legitimately negative trigger
    level must NOT be rejected. Getting this backwards would be a worse bug
    than the one being fixed."""
    conn = _conn(idn=LEGACY_IDN)
    conn.write("C1:TRLV -0.5")
    assert conn.trigger_level[1] == -0.5
    assert conn.error_queue == []


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf")],
    ids=["nan", "inf"],
)
def test_invalid_modern_trigger_level_is_rejected_and_queued(value):
    conn = _conn(idn=MODERN_IDN)
    before = conn.trigger_level.get(1)

    conn.write(":TRIGger:EDGE:LEVel {0}".format(value))

    assert conn.trigger_level.get(1) == before, "a rejected command must not change state"
    assert conn.error_queue == [(-222, "Data out of range")]


def test_valid_negative_modern_trigger_level_is_accepted_and_queues_nothing():
    """positive=False must still be honored -- a legitimately negative trigger
    level must NOT be rejected. Getting this backwards would be a worse bug
    than the one being fixed."""
    conn = _conn(idn=MODERN_IDN)
    conn.write(":TRIGger:EDGE:LEVel -0.5")
    assert conn.trigger_level[1] == -0.5
    assert conn.error_queue == []


def test_unimplemented_command_still_times_out_rather_than_queueing():
    """The strict-mode boundary. An UNIMPLEMENTED command must keep failing
    loudly -- that is what forces every new command to earn a wire-form corpus
    entry. Only IMPLEMENTED commands with bad parameters queue an error."""
    conn = _conn(idn=LEGACY_IDN)
    with pytest.raises(exceptions.SiglentTimeoutError):
        conn.query("C1:NOSUCHQUERY?")
    assert conn.error_queue == [], "a timeout must not also queue an error"
