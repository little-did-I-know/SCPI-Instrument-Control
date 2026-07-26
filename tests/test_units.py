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


def test_the_error_names_the_quantity_and_the_value():
    with pytest.raises(exceptions.InvalidParameterError) as excinfo:
        parse_si_value("wat", "timebase scale")
    message = str(excinfo.value)
    assert "timebase scale" in message
    assert "wat" in message
