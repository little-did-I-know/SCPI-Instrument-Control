"""ReportTemplate.create_probe_calibration_template ships a valid,
round-trippable probe-comp preset: probe_calibration test type,
percentage pass/fail limits, four sections, FFT off. Pure model, no Qt."""

from scpi_control.report_generator.models.template import ReportTemplate


def test_probe_calibration_template_config_and_round_trip():
    t = ReportTemplate.create_probe_calibration_template()

    # Linked to the existing probe_calibration test type, FFT off.
    assert t.default_test_type == "probe_calibration"
    assert t.include_fft_analysis is False
    assert len(t.sections) == 4

    # Ships the compensation limits, keyed by measurement name.
    assert t.criteria_set is not None
    limits = {c.measurement_name: c for c in t.criteria_set.criteria_list}
    assert set(limits) == {"Overshoot", "Undershoot", "Top Flatness"}
    assert limits["Overshoot"].max_value == 5.0
    assert limits["Undershoot"].max_value == 5.0
    assert limits["Top Flatness"].max_value == 2.0

    # Survives the library save/load path (to_dict -> from_dict).
    restored = ReportTemplate.from_dict(t.to_dict())
    assert restored.default_test_type == "probe_calibration"
    assert restored.include_fft_analysis is False
    assert len(restored.sections) == 4
    assert restored.criteria_set is not None
    assert len(restored.criteria_set.criteria_list) == 3
