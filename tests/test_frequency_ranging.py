"""Table tests for the 1-2-5 ranging choices (scpi_control/frequency_response/ranging.py)."""

import pytest

from scpi_control import exceptions
from scpi_control.frequency_response.ranging import choose_timebase, choose_volts_per_div, round_125_up


@pytest.mark.parametrize(
    "value,expected",
    [
        (0.9, 1.0),
        (1.0, 1.0),
        (1.1, 2.0),
        (2.0, 2.0),
        (2.1, 5.0),
        (5.0, 5.0),
        (5.1, 10.0),
        (12.0, 20.0),
        (0.03, 0.05),
        (0.0004, 0.0005),
        (1e-3, 1e-3),
        (1.0 / 3000.0, 5e-4),
    ],
)
def test_round_125_up_lands_on_the_sequence(value, expected):
    assert round_125_up(value) == pytest.approx(expected, rel=1e-9)


@pytest.mark.parametrize("bad", [0.0, -1.0])
def test_round_125_up_rejects_non_positive(bad):
    with pytest.raises(exceptions.InvalidParameterError):
        round_125_up(bad)


@pytest.mark.parametrize(
    "frequency,expected",
    [(100.0, 1e-2), (1000.0, 1e-3), (3000.0, 5e-4), (10000.0, 1e-4)],
)
def test_choose_timebase_rounds_up_so_the_window_gains_cycles(frequency, expected):
    # Rounding 1/f UP buys cycles; rounding down would lose them to leakage.
    assert choose_timebase(frequency) == pytest.approx(expected, rel=1e-9)


@pytest.mark.parametrize(
    "peak_to_peak,expected",
    [(2.0, 0.5), (1.0, 0.2), (0.199, 0.05), (12.0, 2.0)],
)
def test_choose_volts_per_div_targets_six_divisions(peak_to_peak, expected):
    assert choose_volts_per_div(peak_to_peak) == pytest.approx(expected, rel=1e-9)


@pytest.mark.parametrize("nothing", [0.0, -0.5])
def test_choose_volts_per_div_returns_none_when_there_is_no_signal(nothing):
    # A flat trace gives no scale to aim at; the caller keeps what the scope has
    # and the floor rule reports the point as unmeasurable.
    assert choose_volts_per_div(nothing) is None
