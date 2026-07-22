"""Before/after comparison report: two synthetic captures, one comparison report.

Synthesizes a "before" and an "after" capture with make_waveform() (the "after"
capture has higher amplitude and more noise), saves each as CSV, then runs the
new comparison pipeline: RunSet -> ComparisonAnalyzer -> build_comparison_report().
A vpp CriteriaSet marks the amplitude regression as a failure, and the rendered
Markdown report includes the overlay plot, a Delta/Delta% table vs baseline, a
SHA-256 raw-data manifest, and a sign-off block (both on by default for
comparison reports).

No real oscilloscope required -- both captures are fully synthetic.

Requirements: SCPI-Instrument-Control[report-generator] -- no hardware needed.

Expected output: 'comparison_report_output/comparison_report.md' (plus a
'plots' subdirectory with the overlay image).
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from scpi_control.provenance import AcquisitionProvenance, InstrumentInfo
from scpi_control.report_generator.analysis.comparison_analyzer import ComparisonAnalyzer
from scpi_control.report_generator.comparison_report_builder import build_comparison_report
from scpi_control.report_generator.generators.markdown_generator import MarkdownReportGenerator
from scpi_control.report_generator.models.comparison import Run, RunMetadata, RunSet
from scpi_control.report_generator.models.criteria import ComparisonType, CriteriaSet, MeasurementCriteria
from scpi_control.report_generator.models.report_data import ReportMetadata
from scpi_control.signal_synth import SignalSpec, make_waveform
from scpi_control.waveform import Waveform

OUTPUT_DIR = Path("comparison_report_output")


def _save_capture(name: str, amplitude: float, noise_rms: float) -> Path:
    """Synthesize one sine capture and save it as CSV, provenance attached.

    save_waveform() only writes the channel header line on plain CSV when
    waveform.provenance is set -- without it every plain CSV round-trips as
    channel "1" regardless of the synthesized channel, which is harmless here
    (a single channel per run) but matches the convention used elsewhere.
    """
    waveform = make_waveform(SignalSpec(kind="sine", frequency=1_000.0, amplitude=amplitude, noise_rms=noise_rms, seed=42), sample_rate=100_000.0, n_points=2_000)
    waveform.provenance = AcquisitionProvenance(instrument=InstrumentInfo(manufacturer="Siglent", model="SDS1104X-E"))
    path = OUTPUT_DIR / name
    Waveform(Mock()).save_waveform(waveform, str(path), format="CSV")
    return path


def build_runset() -> RunSet:
    """Two runs: a clean 'before' capture and a noisier, higher-amplitude 'after'."""
    before_file = _save_capture("before.csv", amplitude=1.0, noise_rms=0.02)
    after_file = _save_capture("after.csv", amplitude=1.3, noise_rms=0.06)

    # Vpp is expected to stay within 1.8-2.2 V; the "after" run's higher
    # amplitude (Vpp ~2.6 V) will fail this and show up as a delta and a FAIL.
    criteria = CriteriaSet(name="Vpp stability", description="Output amplitude must not drift")
    criteria.add_criteria(MeasurementCriteria(measurement_name="vpp", comparison_type=ComparisonType.RANGE, min_value=1.8, max_value=2.2, description="Peak-to-peak within spec", severity="critical"))

    return RunSet(
        runs=[
            Run(label="before", files=[before_file], metadata=RunMetadata(condition="Before firmware update")),
            Run(label="after", files=[after_file], metadata=RunMetadata(condition="After firmware update")),
        ],
        criteria_set=criteria,
        # mode defaults to MODE_COMPARISON; baseline_index defaults to 0 ("before").
    )


def main() -> None:
    print("=" * 60)
    print("Comparison report demo")
    print("=" * 60)

    OUTPUT_DIR.mkdir(exist_ok=True)

    runset = build_runset()
    result = ComparisonAnalyzer.analyze(runset)

    metadata = ReportMetadata(
        title="Firmware Update Regression Check",
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

    md_path = OUTPUT_DIR / "comparison_report.md"
    if MarkdownReportGenerator().generate(report, md_path):
        print(f"  [OK] {md_path}")
    else:
        print("  [FAILED] Markdown report generation failed")

    # For a PDF instead (or in addition), install the optional dependency and swap in
    # PDFReportGenerator: pip install "SCPI-Instrument-Control[report-generator]"
    #   from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator
    #   PDFReportGenerator().generate(report, OUTPUT_DIR / "comparison_report.pdf")

    print("=" * 60)
    print("Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
