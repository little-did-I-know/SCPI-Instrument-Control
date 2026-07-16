"""Badge measurement pool: allocation, reuse, no-clobber, and cleanup."""

import pytest

from scpi_control import Oscilloscope, exceptions
from scpi_control.connection.mock import MockConnection

MSO58_IDN = "TEKTRONIX,MSO58,MOCK0300,CF:91.1CT FV:2.0"


def _mso_scope(**kwargs):
    conn = MockConnection("mock", idn=MSO58_IDN, channel_states={i: True for i in range(1, 9)}, **kwargs)
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    return scope, conn


def test_first_measure_allocates_and_configures_a_badge():
    scope, conn = _mso_scope()
    assert scope.measurement.measure_vpp(1) == pytest.approx(2.0)
    assert "MEASUrement:LIST?" in conn.queries
    assert 'MEASUrement:ADDNew "MEAS1"' in conn.writes
    assert "MEASUrement:MEAS1:TYPe PK2Pk" in conn.writes
    assert "MEASUrement:MEAS1:SOUrce CH1" in conn.writes
    assert "MEASUrement:MEAS1:RESUlts:CURRentacq:MEAN?" in conn.queries
    scope.disconnect()


def test_repeat_measure_reuses_the_badge_with_one_query():
    scope, conn = _mso_scope()
    scope.measurement.measure_vpp(1)
    writes_before = len(conn.writes)
    queries_before = len(conn.queries)

    assert scope.measurement.measure_vpp(1) == pytest.approx(2.0)

    # The whole point of the pool: no re-configuration, exactly one result query.
    assert len(conn.writes) == writes_before
    assert len(conn.queries) == queries_before + 1
    scope.disconnect()


def test_distinct_measurements_get_distinct_slots():
    scope, conn = _mso_scope()
    scope.measurement.measure_vpp(1)
    assert scope.measurement.measure_frequency(2) == pytest.approx(1000.0)
    assert 'MEASUrement:ADDNew "MEAS2"' in conn.writes
    assert "MEASUrement:MEAS2:TYPe FREQUENCY" in conn.writes
    assert "MEASUrement:MEAS2:SOUrce CH2" in conn.writes
    scope.disconnect()


def test_same_type_on_another_channel_gets_its_own_slot():
    scope, conn = _mso_scope()
    scope.measurement.measure_vpp(1)
    scope.measurement.measure_vpp(8)
    assert "MEASUrement:MEAS2:SOUrce CH8" in conn.writes
    scope.disconnect()


def test_user_badges_are_never_reused_or_deleted():
    # Seed a user badge on MEAS2, not MEAS1, so lowest-free-slot allocation
    # (which should land on MEAS1) is distinguishable from a naive max+1
    # strategy (which would land on MEAS3, not colliding) and from a
    # count+1 strategy (which would land on MEAS2, colliding with the
    # user's badge). This also covers the case where the user's badges
    # don't start at MEAS1.
    scope, conn = _mso_scope(tek_badges={2: {"type": "FREQUENCY", "source": "CH1"}})
    scope.measurement.measure_vpp(1)

    assert 'MEASUrement:ADDNew "MEAS1"' in conn.writes  # took the lowest free slot
    assert 'MEASUrement:ADDNew "MEAS2"' not in conn.writes  # skipped the user's slot

    scope.disconnect()
    assert 'MEASUrement:DELete "MEAS1"' in conn.writes  # ours is removed
    assert 'MEASUrement:DELete "MEAS2"' not in conn.writes  # theirs survives
    assert 2 in conn.badges


def test_disconnect_removes_every_badge_we_created():
    scope, conn = _mso_scope()
    scope.measurement.measure_vpp(1)
    scope.measurement.measure_frequency(2)
    scope.disconnect()
    assert 'MEASUrement:DELete "MEAS1"' in conn.writes
    assert 'MEASUrement:DELete "MEAS2"' in conn.writes
    assert conn.badges == {}


def test_badge_created_but_not_configured_is_still_cleaned_up(monkeypatch):
    scope, conn = _mso_scope()
    # Fail the TYPe write so the badge exists on the instrument (ADDNew already
    # went through) but was never configured -- this must not leak.
    real_write = scope.write

    def flaky_write(command):
        if ":TYPe " in command:
            raise exceptions.CommandError("simulated link glitch")
        return real_write(command)

    monkeypatch.setattr(scope, "write", flaky_write)
    with pytest.raises(exceptions.CommandError):
        scope.measurement.measure_vpp(1)
    monkeypatch.setattr(scope, "write", real_write)

    scope.disconnect()
    assert 'MEASUrement:DELete "MEAS1"' in conn.writes  # created -> cleaned up
    assert conn.badges == {}


def test_retry_after_failed_type_write_reconfigures_a_fresh_slot(monkeypatch):
    # The half-configured MEAS1 from the failed attempt must never be handed
    # back out and read as-is -- that would silently return a value for a
    # badge whose type was never set. The retry must configure a new slot.
    scope, conn = _mso_scope()
    real_write = scope.write
    state = {"failed_once": False}

    def flaky_write(command):
        if ":TYPe " in command and not state["failed_once"]:
            state["failed_once"] = True
            raise exceptions.CommandError("simulated link glitch")
        return real_write(command)

    monkeypatch.setattr(scope, "write", flaky_write)
    with pytest.raises(exceptions.CommandError):
        scope.measurement.measure_vpp(1)

    # Retry: should succeed by configuring a fresh slot, not by reading the
    # unconfigured MEAS1 as if it were already set up.
    assert scope.measurement.measure_vpp(1) == pytest.approx(2.0)
    monkeypatch.setattr(scope, "write", real_write)

    assert 'MEASUrement:ADDNew "MEAS2"' in conn.writes
    assert "MEASUrement:MEAS2:TYPe PK2Pk" in conn.writes

    scope.disconnect()
    assert 'MEASUrement:DELete "MEAS1"' in conn.writes  # leaked half-configured slot, cleaned up
    assert 'MEASUrement:DELete "MEAS2"' in conn.writes  # fully-configured slot, cleaned up
    assert conn.badges == {}


def test_non_numeric_result_reports_the_acquisition_caveat():
    scope, conn = _mso_scope()
    scope.measurement.measure_vpp(1)  # allocate the badge
    conn.custom_responses["MEASUrement:MEAS1:RESUlts:CURRentacq:MEAN?"] = "----"
    with pytest.raises(exceptions.CommandError, match="running acquisition"):
        scope.measurement.measure_vpp(1)
    scope.disconnect()


def test_types_without_a_badge_token_gate_cleanly():
    scope, conn = _mso_scope()
    # CMEAN has no badge token in either manual; ACRMS is AC-coupled RMS, not
    # cycle RMS, so CRMS stays unmapped rather than mapped to a lie.
    for mtype in ("CMEAN", "CRMS"):
        with pytest.raises(exceptions.FeatureNotSupportedError):
            scope.measurement.measure(mtype, 1)
    scope.disconnect()


def test_top_and_base_measure_via_badges():
    # Both MSO2 and 4/5/6 list TOP and BASE as badge types.
    scope, conn = _mso_scope()
    assert scope.measurement.measure("TOP", 1) == pytest.approx(1.0)
    assert "MEASUrement:MEAS1:TYPe TOP" in conn.writes
    scope.disconnect()


def test_no_badge_traffic_when_no_measurement_was_taken():
    scope, conn = _mso_scope()
    scope.disconnect()
    assert "MEASUrement:LIST?" not in conn.queries
    assert not [w for w in conn.writes if "ADDNew" in w or "DELete" in w]
