"""PDFReportGenerator threads a template's brand colors into its styles; a
no-branding generator keeps today's defaults. Needs reportlab (skips in CI)."""

import pytest

pytest.importorskip("reportlab")

from reportlab.lib import colors  # noqa: E402

from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator  # noqa: E402
from scpi_control.report_generator.models.template import BrandingTemplate  # noqa: E402


def test_branding_colors_reach_the_styles():
    branding = BrandingTemplate(primary_color="#010203", secondary_color="#040506", success_color="#070809", failure_color="#0a0b0c")
    gen = PDFReportGenerator(branding=branding)
    assert gen.styles["ReportTitle"].textColor == colors.HexColor("#010203")  # primary
    assert gen.styles["SectionHeading"].textColor == colors.HexColor("#010203")  # primary
    assert gen.styles["SubsectionHeading"].textColor == colors.HexColor("#070809")  # success
    assert gen.styles["Heading4"].textColor == colors.HexColor("#040506")  # secondary
    assert gen.styles["ResultPass"].textColor == colors.HexColor("#070809")  # success
    assert gen.styles["ResultFail"].textColor == colors.HexColor("#0a0b0c")  # failure


def test_no_branding_keeps_todays_default_colors():
    gen = PDFReportGenerator()  # no branding
    assert gen.styles["ReportTitle"].textColor == colors.HexColor("#1f77b4")
    assert gen.styles["Heading4"].textColor == colors.HexColor("#ff7f0e")  # secondary default, now live
    assert gen.styles["ResultFail"].textColor == colors.HexColor("#d62728")
