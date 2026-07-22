"""Markdown generator renders comparison tables, overlays, manifest, sign-off."""

from datetime import datetime

from scpi_control.report_generator.generators.markdown_generator import MarkdownReportGenerator
from scpi_control.report_generator.models.report_data import ReportMetadata, TestReport, TestSection
from scpi_control.report_generator.models.report_elements import (
    STATUS_FAIL,
    STATUS_PASS,
    ComparisonTable,
    DataManifest,
    ManifestEntry,
    OverlayPlotSpec,
    OverlayTrace,
    SignoffBlock,
    SignoffRole,
    TableCell,
)


def _report(section):
    return TestReport(metadata=ReportMetadata(title="T", technician="R", test_date=datetime(2026, 7, 22)), sections=[section])


def _generate(tmp_path, section, include_plots=False):
    out = tmp_path / "report.md"
    assert MarkdownReportGenerator(include_plots=include_plots).generate(_report(section), out)
    return out.read_text(encoding="utf-8")


def test_comparison_table_rendered_with_status_marks(tmp_path):
    section = TestSection(title="Comparison Results")
    section.comparison_table = ComparisonTable(
        title="Vs baseline",
        headers=["Measurement", "before", "after"],
        rows=[[TableCell("vpp"), TableCell("2.0 V", status=STATUS_PASS), TableCell("3.0 V", status=STATUS_FAIL)]],
    )
    text = _generate(tmp_path, section)
    assert "| Measurement | before | after |" in text
    assert "| vpp | 2.0 V ✅ | 3.0 V ❌ |" in text


def test_manifest_rendered(tmp_path):
    section = TestSection(title="Raw Data Appendix")
    section.manifest = DataManifest(entries=[ManifestEntry(run_label="before", file_path="a.csv", size_bytes=1234, sha256="ab" * 32, capture_timestamp="2026-07-22T10:00:00+00:00", instrument="Siglent SDS824X HD (SN1)")])
    text = _generate(tmp_path, section)
    assert "SHA-256" in text
    assert ("ab" * 32)[:16] in text  # hash shown (possibly truncated to >=16 chars)
    assert "Siglent SDS824X HD (SN1)" in text


def test_signoff_rendered_with_lines(tmp_path):
    section = TestSection(title="Sign-Off")
    section.signoff = SignoffBlock(roles=[SignoffRole(title="Tested by", name="Robin"), SignoffRole(title="Approved by")])
    text = _generate(tmp_path, section)
    assert "**Tested by:** Robin" in text
    assert "**Approved by:**" in text
    assert text.count("Signature: ") == 2 and text.count("Date: ") == 2


def test_overlay_plot_written_and_referenced(tmp_path):
    import numpy as np

    from scpi_control.report_generator.models.report_data import WaveformData

    def wf(label):
        t = np.linspace(0, 1e-3, 100)
        return WaveformData(channel=label, time=t, voltage=np.sin(2 * np.pi * 1000 * t), sample_rate=100_000.0, record_length=100)

    section = TestSection(title="Waveform Overlays")
    section.overlay_plots = [OverlayPlotSpec(channel_label="1", traces=[OverlayTrace("before", wf("1"), "#1f77b4"), OverlayTrace("after", wf("1"), "#ff7f0e")])]
    text = _generate(tmp_path, section, include_plots=True)
    assert "![Overlay: 1](plots/" in text
    assert (tmp_path / "plots").exists() and any((tmp_path / "plots").iterdir())
