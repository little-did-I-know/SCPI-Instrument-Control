"""Annotate report plots: text labels, reference lines, shaded spans and captions.

Run:  python examples/report_annotations.py

Writes annotated_report.pdf to the current directory. Requires the
`report-generator` extra:
    pip install -e ".[report-generator]"
"""

from datetime import datetime
from pathlib import Path

import numpy as np

from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator
from scpi_control.report_generator.models.annotations import (
    KIND_HLINE,
    KIND_LABEL,
    KIND_SPAN,
    KIND_VLINE,
    PlotAnnotation,
)
from scpi_control.report_generator.models.report_data import (
    ReportMetadata,
    TestReport,
    TestSection,
    WaveformData,
)


def make_step_response() -> WaveformData:
    """A 3.3 V step with a little ringing, so the annotations have something to point at."""
    t = np.linspace(0, 1e-4, 2000)
    step = np.where(t < 2e-5, 0.0, 3.3)
    ringing = 0.4 * np.exp(-(t - 2e-5) / 5e-6) * np.sin(2 * np.pi * 500_000 * (t - 2e-5))
    voltage = step + np.where(t < 2e-5, 0.0, ringing)
    return WaveformData(channel="C1", time=t, voltage=voltage, sample_rate=2e7, record_length=len(t))


def main() -> int:
    waveform = make_step_response()

    # Coordinates are in DOMAIN units: seconds here, hertz on an FFT plot.
    waveform.annotations = [
        PlotAnnotation(kind=KIND_VLINE, text="edge", x=2e-5),
        PlotAnnotation(kind=KIND_LABEL, text="overshoot", x=2.4e-5, y=3.7, text_dx=0.08, text_dy=0.1),
        PlotAnnotation(kind=KIND_HLINE, text="3.3 V nominal", y=3.3),
        PlotAnnotation(kind=KIND_SPAN, text="settling window", x=2e-5, x_end=4e-5),
    ]
    waveform.caption = "Figure 1: C1 step response, 10x probe, 20 MS/s"

    section = TestSection(title="Step Response", content="Rising edge into a 50 ohm load.", waveforms=[waveform])
    metadata = ReportMetadata(title="Annotated Bench Check", technician="robin", test_date=datetime.now())
    report = TestReport(metadata=metadata, sections=[section])

    output = Path("annotated_report.pdf")
    if not PDFReportGenerator().generate(report, output):
        print("PDF generation failed - is the `report-generator` extra installed?")
        return 1

    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
