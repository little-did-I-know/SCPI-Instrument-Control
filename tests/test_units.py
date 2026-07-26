"""Parsing human-written SI quantity strings.

batch_capture documents its scales as strings ('1us', '500mV') and its example
copies those verbatim, but the apply path never parsed them -- the documented
call raised TypeError. These tests pin the parser that fixes it, including the
one rule that is easy to get backwards: 'm' is milli, 'M' is mega.
"""

import pytest

from scpi_control import exceptions
from scpi_control.units import parse_si_value


@pytest.mark.parametrize(
    "text,expected",
    [
        ("1us", 1e-6),
        ("500mV", 0.5),
        ("2.5V", 2.5),
        ("1e-6", 1e-6),
        ("100 ns", 1e-7),
        ("1s", 1.0),
        ("1M", 1e6),
        ("1m", 1e-3),
        ("1k", 1e3),
        ("1K", 1e3),
        ("1G", 1e9),
        ("1p", 1e-12),
        ("1MHz", 1e6),
        ("1Hz", 1.0),
        ("-2.5mV", -2.5e-3),
        ("+1u", 1e-6),
        ("  1us  ", 1e-6),
        ("1µs", 1e-6),
        ("1μs", 1e-6),
    ],
)
def test_parses_si_strings(text, expected):
    assert parse_si_value(text, "test quantity") == pytest.approx(expected)


def test_milli_and_mega_are_distinguished_by_case():
    """The load-bearing pair. A case-insensitive parser silently turns a 1 mV
    scale into a 1 MV scale -- nine orders of magnitude, no error."""
    assert parse_si_value("1m", "scale") == pytest.approx(1e-3)
    assert parse_si_value("1M", "scale") == pytest.approx(1e6)


@pytest.mark.parametrize("value,expected", [(1e-6, 1e-6), (0.5, 0.5), (2, 2.0), (-3, -3.0)])
def test_numbers_pass_through_untouched(value, expected):
    """What makes this change purely additive: callers already passing floats
    keep working, so batch_capture accepts both spellings."""
    result = parse_si_value(value, "scale")
    assert isinstance(result, float)
    assert result == pytest.approx(expected)


def test_an_unknown_unit_is_accepted_not_guessed_at():
    """Units are deliberately unvalidated: the first suffix character is checked
    against the prefix table and everything else is treated as a unit. Rejecting
    unknown units would mean maintaining a list of every unit an instrument
    might use."""
    assert parse_si_value("1x", "scale") == pytest.approx(1.0)


@pytest.mark.parametrize("bad", ["", "   ", "abc", "mV", None, [], True, False])
def test_rejects_values_with_no_usable_number(bad):
    """True/False are rejected on purpose despite bool subclassing int -- reading
    True as 1.0 would silently accept a caller's mistake."""
    with pytest.raises(exceptions.InvalidParameterError):
        parse_si_value(bad, "test quantity")


@pytest.mark.parametrize("bad", ["1,000us", "1_000", "1..5", "5 000"])
def test_rejects_a_suffix_that_swallowed_part_of_the_number(bad):
    """The counterpart to the unvalidated-unit rule above, and the same
    silent-wrong-value class this parser exists to eliminate.

    The regex captures a leading number and treats the rest as a unit, so
    '1,000us' -- an operator writing 1 ms -- parsed to 1.0 and set a timebase
    1000x off, recorded under the label '1.0' so nothing downstream could tell.
    An unknown unit discards nothing; a dropped numeric remainder discards
    everything after it.
    """
    with pytest.raises(exceptions.InvalidParameterError):
        parse_si_value(bad, "timebase scale")


def test_an_exponent_beyond_the_decimal_range_is_a_parameter_error():
    """Decimal.scaleb raises Overflow, which is NOT a subclass of
    InvalidOperation, so the original guard let a raw decimal exception escape
    a module that promises InvalidParameterError for every bad input."""
    with pytest.raises(exceptions.InvalidParameterError):
        parse_si_value("1e999995G", "scale")


def test_the_error_names_the_quantity_and_the_value():
    with pytest.raises(exceptions.InvalidParameterError) as excinfo:
        parse_si_value("wat", "timebase scale")
    message = str(excinfo.value)
    assert "timebase scale" in message
    assert "wat" in message


@pytest.mark.parametrize(
    "text,expected",
    [
        ("10us", 1e-5),
        ("100ns", 1e-7),
        ("10mV", 1e-2),
        ("100us", 1e-4),
        ("1e6m", 1e3),
    ],
)
def test_parsed_values_are_canonical_floats(text, expected):
    """Exact equality, NOT pytest.approx -- that is the whole point.

    parse_si_value used to compute float(number) * scale, and float
    multiplication is not correctly rounded the way parsing a decimal literal
    is: float("10") * 1e-6 is 9.999999999999999e-06 while 10e-6 is 1e-05. The
    parsed value is formatted straight into a SCPI command, so the difference
    reached the wire as "TDIV 9.999999999999999e-06".
    """
    assert parse_si_value(text, "scale") == expected


def test_a_parsed_scale_formats_to_a_canonical_scpi_value():
    """The wire-level consequence, pinned directly."""
    assert "{0}".format(parse_si_value("10us", "timebase scale")) == "1e-05"
