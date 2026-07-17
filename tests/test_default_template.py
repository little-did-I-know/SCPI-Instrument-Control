"""ReportTemplate.create_default_template ships a valid, round-trippable starter
template with branding and 6 sections. Pure model, no Qt, no reportlab."""

from scpi_control.report_generator.models.template import BrandingTemplate, ReportTemplate


def test_default_template_has_branding_and_six_sections():
    t = ReportTemplate.create_default_template()
    assert isinstance(t.branding, BrandingTemplate)
    assert len(t.sections) == 6
    assert t.name  # named


def test_default_template_round_trips():
    t = ReportTemplate.create_default_template()
    restored = ReportTemplate.from_dict(t.to_dict())
    assert restored.name == t.name
    assert len(restored.sections) == 6
    assert restored.branding.primary_color == t.branding.primary_color
