"""Template fields for sign-off and raw-data appendix, with backward compat."""

from scpi_control.report_generator.models.template import ReportTemplate


def test_defaults():
    t = ReportTemplate(name="t")
    assert t.include_signoff is False
    assert t.signoff_roles == ["Tested by", "Reviewed by", "Approved by"]
    assert t.signoff_names == {}
    assert t.include_raw_data_appendix is False


def test_round_trip():
    t = ReportTemplate(name="t", include_signoff=True, signoff_roles=["QA"], signoff_names={"QA": "Robin"}, include_raw_data_appendix=True)
    t2 = ReportTemplate.from_dict(t.to_dict())
    assert t2.include_signoff is True
    assert t2.signoff_roles == ["QA"]
    assert t2.signoff_names == {"QA": "Robin"}
    assert t2.include_raw_data_appendix is True


def test_old_template_json_without_fields_loads():
    t = ReportTemplate(name="old")
    data = t.to_dict()
    for key in ("include_signoff", "signoff_roles", "signoff_names", "include_raw_data_appendix"):
        data.pop(key, None)
    t2 = ReportTemplate.from_dict(data)
    assert t2.include_signoff is False and t2.signoff_roles == ["Tested by", "Reviewed by", "Approved by"]


def test_default_lists_are_not_shared_between_instances():
    a, b = ReportTemplate(name="a"), ReportTemplate(name="b")
    a.signoff_roles.append("Extra")
    assert "Extra" not in b.signoff_roles
