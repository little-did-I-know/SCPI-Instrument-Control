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
    scope, conn = _mso_scope(tek_badges={1: {"type": "FREQUENCY", "source": "CH1"}})
    scope.measurement.measure_vpp(1)

    assert 'MEASUrement:ADDNew "MEAS1"' not in conn.writes  # skipped the user's slot
    assert 'MEASUrement:ADDNew "MEAS2"' in conn.writes

    scope.disconnect()
    assert 'MEASUrement:DELete "MEAS2"' in conn.writes  # ours is removed
    assert 'MEASUrement:DELete "MEAS1"' not in conn.writes  # theirs survives
    assert 1 in conn.badges


def test_disconnect_removes_every_badge_we_created():
    scope, conn = _mso_scope()
    scope.measurement.measure_vpp(1)
    scope.measurement.measure_frequency(2)
    scope.disconnect()
    assert 'MEASUrement:DELete "MEAS1"' in conn.writes
    assert 'MEASUrement:DELete "MEAS2"' in conn.writes
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
