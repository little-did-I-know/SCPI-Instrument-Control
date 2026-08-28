"""value + unit (+ optional uncertainty), via pint + uncertainties.

Pure-CPU, no instrument. Requires the `uncertainty` extra -- skipped cleanly
if it isn't installed, matching this repo's other optional-dependency tests.
"""

import pytest

pint = pytest.importorskip("pint")
pytest.importorskip("uncertainties")

from scpi_control.quantities import format_quantity, quantity


def test_quantity_plain_value_has_a_float_magnitude():
    q = quantity(1.234, "V")
    assert q.magnitude == 1.234
    assert str(q.units) == "volt"


def test_quantity_with_uncertainty_carries_a_ufloat_magnitude():
    q = quantity(1.234, "V", uncertainty=0.012)
    assert q.magnitude.nominal_value == pytest.approx(1.234)
    assert q.magnitude.std_dev == pytest.approx(0.012)


def test_mismatched_dimension_addition_raises():
    volts = quantity(1.0, "V")
    seconds = quantity(1.0, "s")
    with pytest.raises(pint.errors.DimensionalityError):
        volts + seconds


def test_format_quantity_without_uncertainty_uses_compact_si_prefix():
    assert format_quantity(quantity(0.012, "V")) == "12 mV"


def test_format_quantity_with_uncertainty():
    assert format_quantity(quantity(1.234, "V", uncertainty=0.012)) == "1.23 ± 0.012 V"


def test_format_quantity_compacts_a_small_time_with_uncertainty():
    assert format_quantity(quantity(12.34e-9, "s", uncertainty=0.12e-9)) == "12.3 ± 0.12 ns"


def test_format_quantity_percent_unit():
    assert format_quantity(quantity(50.0, "percent")) == "50 %"
