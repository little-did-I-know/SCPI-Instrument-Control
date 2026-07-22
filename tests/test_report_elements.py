"""New renderable section elements: tables, overlays, manifest, sign-off."""

from datetime import datetime

from scpi_control.report_generator.models.report_data import ReportMetadata, TestSection
from scpi_control.report_generator.models.report_elements import (
    STATUS_FAIL,
    STATUS_PASS,
    ComparisonTable,
    DataManifest,
    ManifestEntry,
    SignoffBlock,
    SignoffRole,
    TableCell,
)


def test_comparison_table_to_dict_round_trips_cells():
    table = ComparisonTable(
        title="Vpp by run",
        headers=["Measurement", "Baseline", "After", "Δ"],
        rows=[[TableCell("vpp"), TableCell("1.00 V"), TableCell("1.10 V", status=STATUS_FAIL), TableCell("+0.10 V")]],
    )
    d = table.to_dict()
    assert d["headers"][1] == "Baseline"
    assert d["rows"][0][2] == {"text": "1.10 V", "status": STATUS_FAIL}
    assert d["rows"][0][0] == {"text": "vpp"}


def test_manifest_and_signoff_to_dict():
    manifest = DataManifest(entries=[ManifestEntry(run_label="before", file_path="a.csv", size_bytes=123, sha256="ab" * 32, capture_timestamp="2026-07-22T10:00:00+00:00", instrument="Siglent SDS824X HD (SN1)")])
    assert manifest.to_dict()["entries"][0]["sha256"] == "ab" * 32
    signoff = SignoffBlock(roles=[SignoffRole(title="Tested by", name="Robin"), SignoffRole(title="Approved by")])
    d = signoff.to_dict()
    assert d["roles"][0] == {"title": "Tested by", "name": "Robin"}
    assert d["roles"][1] == {"title": "Approved by"}


def test_test_section_serializes_new_elements_only_when_set():
    plain = TestSection(title="Plain")
    d = plain.to_dict()
    assert "comparison_table" not in d and "manifest" not in d and "signoff" not in d and "overlay_plots" not in d

    rich = TestSection(title="Rich")
    rich.comparison_table = ComparisonTable(title="t", headers=["h"], rows=[])
    rich.manifest = DataManifest(entries=[])
    rich.signoff = SignoffBlock(roles=[SignoffRole(title="Tested by")])
    d = rich.to_dict()
    assert d["comparison_table"]["title"] == "t"
    assert d["manifest"] == {"entries": []}
    assert d["signoff"]["roles"][0]["title"] == "Tested by"


def test_status_constants_are_pass_fail():
    assert STATUS_PASS == "pass" and STATUS_FAIL == "fail"
