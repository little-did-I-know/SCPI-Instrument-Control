"""Modern-dialect :MEASure:SIMPle subsystem (guide p.335-373).

The legacy PAVA? command does not exist on modern instruments -- it appears zero
times in the 855-page modern guide -- so measure() needs a separate wire path.
"""

import pytest

from scpi_control import Oscilloscope
from scpi_control.connection.mock import MockConnection
from scpi_control.measurement import MeasurementType
from scpi_control.scpi_commands import measurement_to_wire
from typing import get_args

MODERN_IDN = "Siglent Technologies,SDS814X HD,MOCK0001,1.0.0.0"


def test_public_wid_maps_to_pwid_not_wid():
    """The trap: modern WID is BURST width (first rising -> last falling edge,
    guide p.345); positive PULSE width is PWID. Our public WID means positive
    pulse width -- it is labelled "Positive Width" in the GUI and the Tektronix
    map already encodes WID -> PWIdth. Mapping WID -> WID returns a
    plausible-looking wrong number on any multi-pulse capture."""
    assert measurement_to_wire("modern", "WID") == "PWID"


def test_negative_width_maps_to_nwid_not_nbwid():
    """NBWID is the negative BURST width (p.345); NWID is the pulse width."""
    assert measurement_to_wire("modern", "NWID") == "NWID"


def test_every_measurement_type_has_a_modern_token():
    """measurement_to_wire raises FeatureNotSupportedError for an unmapped type
    (see _to_wire in scpi_commands.py), so it can never return a falsy token --
    this just checks that every one of the 17 public MeasurementType values
    resolves without raising, i.e. the modern map has no missing entries."""
    for mtype in get_args(MeasurementType):
        token = measurement_to_wire("modern", mtype)
        assert token, "{0} has no modern token".format(mtype)


def _modern_scope():
    scope = Oscilloscope("mock", connection=MockConnection(idn=MODERN_IDN))
    scope.connect()
    return scope


def test_modern_table_renders_the_simple_measure_commands():
    scope = _modern_scope()
    assert scope._get_command("set_measure_state", state="ON") == ":MEASure ON"
    assert scope._get_command("set_simple_source", ch=2) == ":MEASure:SIMPle:SOURce C2"
    assert scope._get_command("set_simple_item", param="PKPK", state="ON") == ":MEASure:SIMPle:ITEM PKPK,ON"
    assert scope._get_command("get_simple_value", param="PKPK") == ":MEASure:SIMPle:VALue? PKPK"


def test_modern_table_no_longer_offers_legacy_pava():
    """PAVA appears zero times in the modern guide; keeping it in the table is
    what let measure() send a nonexistent command."""
    scope = _modern_scope()
    assert not scope._has_command("get_parameter_value")


def test_mock_answers_the_simple_value_query_with_bare_nr3():
    conn = MockConnection(idn=MODERN_IDN)
    conn.connect()
    conn.write(":MEASure ON")
    conn.write(":MEASure:SIMPle:SOURce C1")
    conn.write(":MEASure:SIMPle:ITEM PKPK,ON")
    response = conn.query(":MEASure:SIMPle:VALue? PKPK")
    assert "," not in response, "modern replies are a bare NR3 value (p.369), not <param>,<value>"
    assert float(response) == pytest.approx(2.0)


def test_mock_refuses_the_burst_width_token():
    """WID is burst width (p.345) and the driver must never send it. The mock
    does not implement it, so a regression surfaces as a timeout rather than a
    wrong number."""
    from scpi_control import exceptions

    conn = MockConnection(idn=MODERN_IDN)
    conn.connect()
    conn.write(":MEASure:SIMPle:ITEM WID,ON")
    with pytest.raises(exceptions.SiglentTimeoutError):
        conn.query(":MEASure:SIMPle:VALue? WID")


def test_mock_answers_value_query_without_prior_setup():
    """The corpus drives the mock with a bare documented request and no setup
    writes (test_wire_conformance.py:47-51), so VALue? must answer on its own."""
    conn = MockConnection(idn=MODERN_IDN)
    conn.connect()
    assert conn.query(":MEASure:SIMPle:VALue? PKPK") == "2.000E+00"


def test_measure_returns_a_real_value_for_every_type_on_modern():
    """The load-bearing net. Before this change every one of these raised
    SiglentTimeoutError because measure() sent legacy PAVA? on modern."""
    scope = _modern_scope()
    for mtype in get_args(MeasurementType):
        value = scope.measurement.measure(mtype, 1)
        assert isinstance(value, float), "{0} returned {1!r}".format(mtype, value)


def test_measure_on_modern_emits_the_documented_sequence():
    """Also the "did we enable the item" check -- the mock deliberately does not
    require enablement (it would break the corpus), so the sequence is asserted here."""
    scope = _modern_scope()
    conn = scope._connection
    conn.writes.clear()
    scope.measurement.measure("WID", 2)
    written = [c for c in conn.writes if "MEAS" in c.upper()]
    assert written == [
        ":MEASure ON",
        ":MEASure:MODE SIMPle",
        ":MEASure:SIMPle:SOURce C2",
        ":MEASure:SIMPle:ITEM PWID,ON",
    ], written


def test_measure_agrees_across_dialects_for_the_same_signal():
    """Guarantees only that legacy and modern mocks describe the same synthesized
    signal -- the mock fixtures for both dialects were authored to mirror each
    other, so this does NOT catch a token swap (e.g. WID <-> NWID): both are
    "5.000E-04" here, so a swap would silently agree instead of failing. That
    class of regression is what test_measure_on_modern_emits_the_documented_
    sequence checks, by asserting the literal wire tokens sent."""
    legacy = Oscilloscope("mock", connection=MockConnection(idn="Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"))
    legacy.connect()
    modern = _modern_scope()
    for mtype in ("PKPK", "FREQ", "WID", "NWID", "DUTY"):
        assert modern.measurement.measure(mtype, 1) == pytest.approx(legacy.measurement.measure(mtype, 1)), mtype


def test_a_measurement_the_instrument_cannot_compute_is_reported_as_unavailable():
    """MEASURED on a real SDS824X HD (fw 3.8.12.1.1.3.6), 2026-07-30: with
    PKPK/MAX/MIN/MEAN all enabled on a live channel, MEAN answered
    "1.45474E+00" while PKPK, MAX and MIN each answered the literal "****" --
    the instrument's marker for "no value for this item right now".

    p.369 documents the reply as a bare NR3 and says nothing about "****", so
    measure() did float("****") and raised "Failed to parse measurement" -- a
    normal, transient, expected condition surfacing as a parse failure. In the
    gateway that reaches _safe(), which logs "poll query failed, degrading to
    a default" at WARNING, so an ordinary unavailable reading looked like an
    instrument fault in the log.

    It stays an exception (measure() returns float, and inventing a None
    return would push the check onto every caller), but a DISTINGUISHABLE one,
    so a caller can tell "not available yet" from "the wire is broken".
    """
    from scpi_control.exceptions import CommandError, MeasurementUnavailableError

    conn = MockConnection("mock", idn=MODERN_IDN, custom_responses={":MEASure:SIMPle:VALue? PKPK": "****"})
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()

    with pytest.raises(MeasurementUnavailableError) as excinfo:
        scope.measurement.measure("PKPK", 1)

    message = str(excinfo.value)
    assert "PKPK" in message
    assert "parse" not in message.lower(), "an unavailable reading is not a parse failure: {0}".format(message)
    assert isinstance(excinfo.value, CommandError), "must stay a CommandError subclass so existing handlers keep catching it"
    scope.disconnect()


def test_a_genuinely_unparseable_measurement_still_fails_as_before():
    # The '****' handling must not swallow real wire corruption.
    from scpi_control.exceptions import CommandError, MeasurementUnavailableError

    conn = MockConnection("mock", idn=MODERN_IDN, custom_responses={":MEASure:SIMPle:VALue? PKPK": "garbage"})
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()

    with pytest.raises(CommandError) as excinfo:
        scope.measurement.measure("PKPK", 1)
    assert not isinstance(excinfo.value, MeasurementUnavailableError)
    scope.disconnect()
