"""MeasurementCriteria.validate: half-open RANGE is enforced; unspecified criteria are not-evaluable."""

from scpi_control.report_generator.models.criteria import ComparisonType, MeasurementCriteria


def test_range_min_only_is_enforced():
    c = MeasurementCriteria("vpp", ComparisonType.RANGE, min_value=4.5)  # no max
    assert c.validate(4.0).passed is False  # below min -> FAIL (was True)
    assert c.validate(5.0).passed is True


def test_range_max_only_is_enforced():
    c = MeasurementCriteria("vpp", ComparisonType.RANGE, max_value=5.5)  # no min
    assert c.validate(6.0).passed is False  # above max -> FAIL (was True)
    assert c.validate(5.0).passed is True


def test_range_no_bounds_is_not_evaluable():
    assert MeasurementCriteria("vpp", ComparisonType.RANGE).validate(1.0).passed is None


def test_min_only_unspecified_is_not_evaluable():
    assert MeasurementCriteria("vpp", ComparisonType.MIN_ONLY).validate(1.0).passed is None


def test_range_full_still_works():
    c = MeasurementCriteria("vpp", ComparisonType.RANGE, min_value=1.0, max_value=2.0)
    assert c.validate(1.5).passed is True
    assert c.validate(3.0).passed is False
