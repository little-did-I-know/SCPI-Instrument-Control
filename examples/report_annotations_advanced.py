"""Every plot-annotation surface: region zooms, FFT, overlays, styling and sidecars.

The companion to report_annotations.py, which covers the four annotation kinds on a
single waveform plot. This one exercises the surfaces beyond that:

  * annotations on all four plot types -- waveform, region zoom, FFT, comparison overlay
  * per-annotation overrides (own colour, own size, no arrow) next to PlotStyle defaults
  * a region zoom inheriting the parent's annotations, clipped to the region window
  * FFT annotations, whose coordinates are HERTZ rather than seconds
  * saving to and restoring from a <source>.annotations.json sidecar
  * the anchor list the GUI's Annotate... dialog offers

Run:  python examples/report_annotations_advanced.py [--out DIR]

Writes annotated_report.pdf, annotated_report.md + plots/, and capture.npz with its
annotation sidecar. Requires the `report-generator` extra:
    pip install -e ".[report-generator]"
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np

from scpi_control.report_generator.generators.markdown_generator import MarkdownReportGenerator
from scpi_control.report_generator.generators.pdf_generator import PDFReportGenerator
from scpi_control.report_generator.models.annotations import (
    KIND_HLINE,
    KIND_LABEL,
    KIND_SPAN,
    KIND_VLINE,
    PlotAnnotation,
)
from scpi_control.report_generator.models.plot_style import PlotStyle
from scpi_control.report_generator.models.report_data import ReportMetadata, TestReport, TestSection, WaveformData
from scpi_control.report_generator.models.report_elements import OverlayPlotSpec, OverlayTrace
from scpi_control.report_generator.utils.anchors import build_anchor_choices
from scpi_control.report_generator.utils.annotation_store import (
    load_annotations_into,
    load_fft_annotations_into,
    save_annotations,
)

EDGE = 1e-3  # rising edge, seconds
SETTLED = 2e-3  # settling complete, seconds
NOMINAL = 3.3  # rail voltage


def make_step_response(source_file: Path, droop: float = 0.0) -> WaveformData:
    """A 3.3 V step at 1 ms with ring-down, over a 5 ms window. `droop` sags the
    plateau so the two overlay traces differ."""
    time = np.linspace(0, 5e-3, 2000)
    after = time >= EDGE
    ringing = 0.45 * np.exp(-(time - EDGE) / 150e-6) * np.sin(2 * np.pi * 8e3 * (time - EDGE))
    voltage = np.where(after, NOMINAL + ringing - droop * (time - EDGE) / 4e-3, 0.0)
    return WaveformData(
        channel="C1",
        time=time,
        voltage=voltage,
        sample_rate=4e5,
        record_length=len(time),
        source_file=source_file,
        probe_ratio=10.0,
        coupling="DC",
    )


def make_spectrum():
    """(frequency_hz, magnitude_db) for the FFT plot: a 1 MHz square wave's harmonics."""
    time = np.linspace(0, 1e-4, 4000)
    signal = np.sign(np.sin(2 * np.pi * 1e6 * time))
    spectrum = np.abs(np.fft.rfft(signal * np.hanning(time.size)))
    frequency = np.fft.rfftfreq(time.size, d=time[1] - time[0])
    magnitude_db = 20 * np.log10(np.maximum(spectrum / spectrum.max(), 1e-6))
    keep = frequency <= 6e6
    return frequency[keep], magnitude_db[keep]


def waveform_annotations():
    """All four kinds in DOMAIN units (seconds), two of them overriding the style."""
    return [
        PlotAnnotation(kind=KIND_VLINE, text="trigger / rising edge", x=EDGE),
        PlotAnnotation(kind=KIND_LABEL, text="overshoot", x=EDGE + 30e-6, y=3.75, text_dx=0.06, text_dy=0.08),
        # Per-annotation overrides beat the PlotStyle defaults: own colour, own
        # size, and no arrow. Keep the offsets small without an arrow -- nothing
        # then links the text back to the point it describes.
        PlotAnnotation(kind=KIND_LABEL, text="first undershoot", x=EDGE + 95e-6, y=2.95, text_dx=0.03, text_dy=-0.08, arrow=False, color="#1a7f37", fontsize=10),
        PlotAnnotation(kind=KIND_HLINE, text=f"{NOMINAL} V nominal", y=NOMINAL),
        # Deliberately wider than the region below, to show the span arriving in
        # the region zoom clamped to the window rather than dropped.
        PlotAnnotation(kind=KIND_SPAN, text="settling window", x=EDGE, x_end=SETTLED + 1.5e-3),
        # Outside the region window, so the zoom drops this one entirely.
        PlotAnnotation(kind=KIND_LABEL, text="steady state", x=4.2e-3, y=NOMINAL, text_dx=-0.18, text_dy=0.06),
    ]


def fft_annotations():
    """FFT coordinates are HERTZ (y is dB); the renderer scales x for the MHz axis."""
    return [
        PlotAnnotation(kind=KIND_VLINE, text="fundamental 1 MHz", x=1e6),
        PlotAnnotation(kind=KIND_LABEL, text="3rd harmonic", x=3e6, y=-10.0, text_dx=0.05, text_dy=-0.10),
        PlotAnnotation(kind=KIND_HLINE, text="-60 dB floor", y=-60.0),
        PlotAnnotation(kind=KIND_SPAN, text="band of interest", x=2.5e6, x_end=3.5e6),
    ]


def annotated_style() -> PlotStyle:
    """Non-default annotation styling, applied report-wide. Compare the Markdown
    plots against the PDF, which uses the defaults."""
    return PlotStyle(
        annotation_color="#0b5394",
        annotation_fontsize=10,
        annotation_line_color="#6a3d9a",
        annotation_line_style="-.",
        annotation_span_color="#33a02c",
        annotation_span_alpha=0.15,
    )


def build_report(out: Path):
    """A two-section report covering all four annotated plot types."""
    source_file = out / "capture.npz"
    waveform = make_step_response(source_file)
    # A real file on disk, so the sidecar written later sits beside its capture
    # exactly as it would after a GUI import.
    np.savez(source_file, time=waveform.time, voltage=waveform.voltage)

    waveform.annotations = waveform_annotations()
    waveform.caption = "Figure 1: C1 step response into 50 ohm, 10x probe"
    # The zoom of this region carries the parent's annotations, clipped to
    # 0.9-2.2 ms. Region plots have no annotations or caption of their own.
    waveform.add_region(0.9e-3, 2.2e-3, label="Settling", region_type="transient", description="Ring-down after the rising edge.")

    frequency, magnitude = make_spectrum()
    step_section = TestSection(
        title="Step Response",
        content="Rising edge into a 50 ohm load.",
        waveforms=[waveform],
        include_fft=True,
        fft_frequency=frequency,
        fft_magnitude=magnitude,
        # Required for the sidecar to restore FFT annotations: they hang off the
        # section, so the loader needs to be told which channel they belong to.
        fft_channel=waveform.channel,
        fft_annotations=fft_annotations(),
        fft_caption="Figure 2: C1 spectrum, Hann window, normalised to the fundamental",
    )

    overlay_section = TestSection(
        title="Run Comparison",
        content="Overlay annotations are set in Python and are not persisted to a sidecar.",
        overlay_plots=[
            OverlayPlotSpec(
                channel_label="C1",
                traces=[
                    OverlayTrace(run_label="run 1", waveform=waveform, color="#1f77b4"),
                    OverlayTrace(run_label="run 2", waveform=make_step_response(out / "capture_run2.npz", droop=0.35), color="#d62728"),
                ],
                annotations=[
                    PlotAnnotation(kind=KIND_VLINE, text="edge", x=EDGE),
                    PlotAnnotation(kind=KIND_SPAN, text="spec window", x=EDGE, x_end=SETTLED),
                    PlotAnnotation(kind=KIND_LABEL, text="run 2 droops", x=3.5e-3, y=3.05, text_dx=-0.20, text_dy=-0.10),
                ],
                caption="Figure 3: C1 across both runs",
            )
        ],
        order=1,
    )

    metadata = ReportMetadata(
        title="Annotated Bench Check",
        technician="robin",
        test_date=datetime.now(),
        equipment_model="SDS824X HD",
    )
    return TestReport(metadata=metadata, sections=[step_section, overlay_section]), waveform, step_section


def show_persistence(waveform: WaveformData, section: TestSection) -> None:
    """Save to the sidecar, then restore into fresh objects -- twice, to show that
    a repeat import does not duplicate anything."""
    path = save_annotations([waveform], fft={waveform.channel: (section.fft_caption, section.fft_annotations)})
    entry = json.loads(path.read_text(encoding="utf-8"))["waveforms"][waveform.channel]
    print(f"\nSidecar: {path.name}")
    print(f"  {len(entry['annotations'])} waveform + {len(entry['fft']['annotations'])} FFT annotations, caption {entry['caption']!r}")
    print(f"  fields left at their default are omitted: {json.dumps(entry['annotations'][0])}")

    reloaded = make_step_response(waveform.source_file)
    reloaded_section = TestSection(title="Reloaded", fft_channel=reloaded.channel)
    applied = load_annotations_into([reloaded])
    fft_applied = load_fft_annotations_into(reloaded_section, [reloaded])
    print(f"  restored {applied} waveform + {fft_applied} FFT annotations; identical to the originals: {reloaded.annotations == waveform.annotations}")

    again = load_annotations_into([reloaded]) + load_fft_annotations_into(reloaded_section, [reloaded])
    print(f"  loading the same sidecar again applied {again} more (loading is idempotent)")


def show_anchors(waveform: WaveformData) -> None:
    """The anchor list behind the Annotate... dialog's dropdown: five waveform
    features plus start/mid/end for every region."""
    print("\nAnchor choices offered for this waveform:")
    for label, x, y in build_anchor_choices(waveform):
        print(f"  {label:<24} x = {x * 1e3:7.3f} ms   y = {'—' if y is None else f'{y:+.3f} V'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Annotate report plots: every surface.")
    parser.add_argument("--out", type=Path, default=Path.cwd(), help="output directory (default: current directory)")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    report, waveform, section = build_report(args.out)

    pdf_path = args.out / "annotated_report.pdf"
    if not PDFReportGenerator().generate(report, pdf_path):
        print("PDF generation failed - is the `report-generator` extra installed?")
        return 1
    print(f"Wrote {pdf_path.name} (default annotation styling)")

    md_path = args.out / "annotated_report.md"
    if not MarkdownReportGenerator(plot_style=annotated_style()).generate(report, md_path):
        print("Markdown generation failed")
        return 1
    plots = sorted(p.name for p in (args.out / "plots").glob("*.png"))
    print(f"Wrote {md_path.name} (custom annotation styling) with {len(plots)} plots: {', '.join(plots)}")

    show_persistence(waveform, section)
    show_anchors(waveform)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
