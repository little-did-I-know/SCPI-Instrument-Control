"""BrandingTemplate applies to / captures from a ReportMetadata. Pure model, no Qt, no reportlab."""

from datetime import datetime

from scpi_control.report_generator.models.report_data import ReportMetadata
from scpi_control.report_generator.models.template import BrandingTemplate


def bare_metadata():
    return ReportMetadata(title="Bench", technician="robin", test_date=datetime(2026, 7, 17))


def test_apply_to_metadata_sets_all_branding_fields():
    branding = BrandingTemplate(company_name="ACME", header_text="H", footer_text="F")
    md = bare_metadata()
    branding.apply_to_metadata(md)
    assert md.company_name == "ACME"
    assert md.header_text == "H"
    assert md.footer_text == "F"


def test_apply_to_metadata_does_not_overwrite_with_empty_branding():
    """A branding with no company_name must not wipe an existing one."""
    md = bare_metadata()
    md.company_name = "Existing Co"
    BrandingTemplate(company_name=None, header_text="H").apply_to_metadata(md)
    assert md.company_name == "Existing Co"  # preserved
    assert md.header_text == "H"  # applied


def test_from_metadata_captures_text_and_colors():
    md = bare_metadata()
    md.company_name = "ACME"
    md.header_text = "H"
    branding = BrandingTemplate.from_metadata(md, colors={"primary_color": "#ff0000", "failure_color": "#00ff00"})
    assert branding.company_name == "ACME"
    assert branding.header_text == "H"
    assert branding.primary_color == "#ff0000"
    assert branding.failure_color == "#00ff00"
    # unspecified colors keep the defaults
    assert branding.secondary_color == "#ff7f0e"


def test_apply_capture_round_trips():
    original = BrandingTemplate(company_name="ACME", footer_text="F", primary_color="#123456")
    md = bare_metadata()
    original.apply_to_metadata(md)
    recaptured = BrandingTemplate.from_metadata(md, colors={"primary_color": original.primary_color})
    assert recaptured.company_name == original.company_name
    assert recaptured.footer_text == original.footer_text
    assert recaptured.primary_color == original.primary_color
