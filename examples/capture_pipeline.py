"""Capture-to-report pipeline: single-run and batch/comparison paths, end to end.

Demonstrates `scpi_control.pipeline.run_capture_pipeline` -- the single entry
point connecting live/mock oscilloscope capture to the report_generator
package -- covering both invocation shapes it routes between automatically:

1. A single-run capture (no timebase/voltage sweep, one trigger) with a
   `CriteriaSet` that PASSES for the known signal.
2. A batch capture (multiple triggers, two channels) with a `CriteriaSet`
   where one channel's signal FAILS, so the example shows both the passing
   and the failing report path.

Requirements: none by default -- runs against the built-in mock scope. Pass
--host <ip> to drive a real oscilloscope on the network. Sticks to Markdown
output (no `reportlab` needed), matching batch_report.py's precedent.

Expected output: printed overall_result for each run (plus the batch's
yield), and Markdown reports written under
'capture_pipeline_output/single/' and 'capture_pipeline_output/batch/'.
"""

import argparse
from datetime import datetime

from scpi_control.automation import DataCollector
from scpi_control.connection import MockConnection
from scpi_control.pipeline import run_capture_pipeline
from scpi_control.report_generator.models.comparison import MODE_BATCH
from scpi_control.report_generator.models.criteria import ComparisonType, CriteriaSet, MeasurementCriteria
from scpi_control.report_generator.models.report_data import ReportMetadata
from scpi_control.signal_synth import SignalSpec

# Square wave vpp = 2 * amplitude. Channel 1 is comfortably inside the
# criteria window on both runs; channel 2 (batch demo only) is deliberately
# out of spec so the batch report demonstrates a FAIL.
_FREQUENCY_HZ = 1_000.0
_PASSING_AMPLITUDE_V = 1.0  # vpp ~2.0 V
_FAILING_AMPLITUDE_V = 0.3  # vpp ~0.6 V -- outside the [1.5, 2.5] V window


def _connect_single(host: str):
    """Mock connection for the single-run demo, or None for real hardware."""
    if host != "mock":
        return None
    return MockConnection(
        channel_states={1: True},
        signals={1: SignalSpec(kind="square", frequency=_FREQUENCY_HZ, amplitude=_PASSING_AMPLITUDE_V, noise_rms=0.0, seed=1)},
        sample_rate=100_000.0,
        timebase=1e-3,
    )


def _connect_batch(host: str):
    """Mock connection for the batch demo, or None for real hardware."""
    if host != "mock":
        return None
    return MockConnection(
        channel_states={1: True, 2: True},
        signals={
            1: SignalSpec(kind="square", frequency=_FREQUENCY_HZ, amplitude=_PASSING_AMPLITUDE_V, noise_rms=0.0, seed=2),
            2: SignalSpec(kind="square", frequency=_FREQUENCY_HZ, amplitude=_FAILING_AMPLITUDE_V, noise_rms=0.0, seed=3),
        },
        sample_rate=100_000.0,
        timebase=1e-3,
    )


def _vpp_criteria(name: str) -> CriteriaSet:
    """A single critical criterion: vpp must land within [1.5, 2.5] V."""
    criteria = CriteriaSet(name=name, description="Peak-to-peak voltage acceptance window")
    criteria.add_criteria(
        MeasurementCriteria(
            measurement_name="vpp",
            comparison_type=ComparisonType.RANGE,
            min_value=1.5,
            max_value=2.5,
            description="Vpp within spec",
            severity="critical",
        )
    )
    return criteria


def run_single_run_demo(host: str) -> None:
    """One capture, one report -- `run_capture_pipeline` routes here whenever
    a capture produces exactly one result (no sweep, default
    `triggers_per_config=1`)."""
    print("-" * 60)
    print("Single-run demo (1 channel, 1 trigger)")
    print("-" * 60)

    with DataCollector(host, connection=_connect_single(host)) as collector:
        result = run_capture_pipeline(
            collector,
            channels=[1],
            output_dir="capture_pipeline_output/single",
            metadata=ReportMetadata(title="Single-Run Capture", technician="example", test_date=datetime.now()),
            criteria_set=_vpp_criteria("Single-run vpp acceptance"),
        )

    print(f"Overall result: {result.report.overall_result}")
    for report_format, path in result.report_paths.items():
        print(f"  [{report_format}] {path}")


def run_batch_demo(host: str) -> None:
    """Multiple triggers across two channels -- `run_capture_pipeline` routes
    here whenever a capture produces 2+ results. Channel 2's signal is
    out-of-spec, so this run demonstrates the FAIL path."""
    print("-" * 60)
    print("Batch demo (2 channels, 3 triggers each -- one channel out of spec)")
    print("-" * 60)

    with DataCollector(host, connection=_connect_batch(host)) as collector:
        result = run_capture_pipeline(
            collector,
            channels=[1, 2],
            output_dir="capture_pipeline_output/batch",
            metadata=ReportMetadata(title="Batch Capture Comparison", technician="example", test_date=datetime.now()),
            criteria_set=_vpp_criteria("Batch vpp acceptance"),
            triggers_per_config=3,
            mode=MODE_BATCH,
        )

    print(f"Overall result: {result.report.overall_result}")
    if result.comparison is not None:
        print(f"Yield: {result.comparison.yield_passed}/{result.comparison.yield_total} runs passed")
    for report_format, path in result.report_paths.items():
        print(f"  [{report_format}] {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="mock", help="Instrument hostname/IP, or 'mock' for the built-in mock scope (default: mock)")
    args = parser.parse_args()

    run_single_run_demo(args.host)
    run_batch_demo(args.host)


if __name__ == "__main__":
    main()
