"""Batch report across five synthesized DUTs, one of them an outlier.

Synthesizes five "DUT" captures (four within spec, one with a high outlier
amplitude), runs them through the comparison pipeline in batch mode
(MODE_BATCH), and builds a report showing per-DUT pass/fail, cross-run
aggregate statistics (mean/std/min/max), and a yield figure that lands in the
executive summary -- e.g. "Yield: 4/5 passed (80%)".

No real oscilloscope required -- every DUT capture is fully synthetic.

Requirements: SCPI-Instrument-Control[report-generator] -- no hardware needed.

Expected output: 'batch_report_output/batch_report.md' (plus a 'plots'
subdirectory with the overlay image).
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from scpi_control.provenance import AcquisitionProvenance, InstrumentInfo
from scpi_control.report_generator.analysis.comparison_analyzer import ComparisonAnalyzer
from scpi_control.report_generator.comparison_report_builder import build_comparison_report
from scpi_control.report_generator.generators.markdown_generator import MarkdownReportGenerator
from scpi_control.report_generator.models.comparison import MODE_BATCH, Run, RunMetadata, RunSet
from scpi_control.report_generator.models.criteria import ComparisonType, CriteriaSet, MeasurementCriteria
from scpi_control.report_generator.models.report_data import ReportMetadata
from scpi_control.signal_synth import SignalSpec, make_waveform
from scpi_control.waveform import Waveform

OUTPUT_DIR = Path("batch_report_output")

# Nominal amplitude is 1.0 V (Vpp ~2.0 V); DUT-04 is a deliberate outlier.
DUT_AMPLITUDES = [1.0, 1.02, 0.98, 1.35, 1.01]


def _save_capture(name: str, amplitude: float, seed: int) -> Path:
    """Synthesize one sine capture and save it as CSV, provenance attached.

    save_waveform() only writes the channel header line on plain CSV when
    waveform.provenance is set -- see scpi_control/waveform.py.
    """
    waveform = make_waveform(SignalSpec(kind="sine", frequency=1_000.0, amplitude=amplitude, noise_rms=0.02, seed=seed), sample_rate=100_000.0, n_points=2_000)
    waveform.provenance = AcquisitionProvenance(instrument=InstrumentInfo(manufacturer="Siglent", model="SDS1104X-E"))
    path = OUTPUT_DIR / name
    Waveform(Mock()).save_waveform(waveform, str(path), format="CSV")
    return path


def build_runset() -> RunSet:
    """Five DUT runs, one with an out-of-spec amplitude."""
    runs = []
    for i, amplitude in enumerate(DUT_AMPLITUDES, start=1):
        dut_id = f"DUT-{i:02d}"
        capture_file = _save_capture(f"{dut_id.lower()}.csv", amplitude=amplitude, seed=100 + i)
        runs.append(Run(label=dut_id, files=[capture_file], metadata=RunMetadata(dut_id=dut_id)))

    # Vpp must land within 1.8-2.2 V; DUT-04's higher amplitude (Vpp ~2.7 V) fails.
    criteria = CriteriaSet(name="Vpp acceptance", description="Output amplitude acceptance window")
    criteria.add_criteria(MeasurementCriteria(measurement_name="vpp", comparison_type=ComparisonType.RANGE, min_value=1.8, max_value=2.2, description="Peak-to-peak within spec", severity="critical"))

    return RunSet(runs=runs, mode=MODE_BATCH, criteria_set=criteria)


def main() -> None:
    print("=" * 60)
    print("Batch report demo")
    print("=" * 60)

    OUTPUT_DIR.mkdir(exist_ok=True)

    runset = build_runset()
    result = ComparisonAnalyzer.analyze(runset)

    print(f"Yield: {result.yield_passed}/{result.yield_total} DUTs passed")

    metadata = ReportMetadata(
        title="Production Batch Test",
        technician="Lab Tech",
        test_date=datetime.now(),
        equipment_model="SDS1104X-E",
    )
    # build_comparison_report() includes the raw-data appendix (SHA-256
    # manifest) and a sign-off block by default -- pass include_appendix=False
    # / include_signoff=False, or a ReportTemplate, to change that.
    report = build_comparison_report(result, metadata)

    print(f"Overall result: {report.overall_result}")
    print(f"Executive summary: {report.executive_summary}")

    md_path = OUTPUT_DIR / "batch_report.md"
    if MarkdownReportGenerator().generate(report, md_path):
        print(f"  [OK] {md_path}")
    else:
        print("  [FAILED] Markdown report generation failed")

    # For a PDF instead (or in addition), install the optional dependency and swap in
    # PDFReportGenerator: pip install "SCPI-Instrument-Control[report-generator]"
    #   from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator
    #   PDFReportGenerator().generate(report, OUTPUT_DIR / "batch_report.pdf")

    print("=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
