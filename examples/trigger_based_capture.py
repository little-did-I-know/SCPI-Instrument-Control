"""Trigger-based event capture.

This example demonstrates how to wait for specific trigger conditions
and capture waveforms when they occur. This is useful for capturing
sporadic events or signals that meet specific criteria.

Requirements: none by default -- runs against the built-in mock scope, seeded
so its trigger status already reads "stopped" and both waits resolve
immediately. The mock cannot represent a genuinely sporadic/untriggered
event, so this only exercises the wait/capture code paths, not real waiting.
Pass --host <ip> to drive a real oscilloscope on the network.

Expected output: a single trigger wait (up to 30s) that saves to
'trigger_captures/' if it fires, followed by up to 10 polled trigger events
saved to 'multi_trigger_captures/' in the current directory.
"""

import argparse
import time
from pathlib import Path

from scpi_control.automation import DataCollector, TriggerWaitCollector
from scpi_control.connection import MockConnection
from scpi_control.signal_synth import SignalSpec


def _connect(host):
    """Return a mock connection for --host mock, or None to use a real socket."""
    if host != "mock":
        return None
    return MockConnection(
        "mock",
        channel_states={1: True},
        signals={1: SignalSpec(kind="square", frequency=1000.0, amplitude=1.65, offset=1.65)},
        sample_rate=20e6,
        timebase=500e-6,
        trigger_status=["Stop"],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="mock", help="Instrument hostname/IP, or 'mock' for the built-in mock scope (default: mock)")
    args = parser.parse_args()

    # Example 1: Wait for a single trigger event
    print("Example 1: Waiting for trigger event...")
    with TriggerWaitCollector(args.host, connection=_connect(args.host)) as tc:
        # Configure trigger: Channel 1, Rising edge, 1V threshold
        tc.collector.scope.trigger.set_source(1)
        tc.collector.scope.trigger.set_slope("POS")  # Rising edge
        tc.collector.scope.trigger.set_level(1, 1.0)  # 1V threshold

        print("Trigger configured:")
        print("  Source: Channel 1")
        print("  Edge: Rising")
        print("  Level: 1.0V")
        print("\nWaiting for trigger (max 30 seconds)...")

        # wait_for_trigger(save_on_trigger=True) writes into output_dir without
        # creating it first, so it must already exist.
        Path("trigger_captures").mkdir(exist_ok=True)

        # Wait for trigger
        waveforms = tc.wait_for_trigger(channels=[1, 2], max_wait=30.0, save_on_trigger=True, output_dir="trigger_captures")

        if waveforms:
            print("\nTrigger captured successfully!")
            for ch, waveform in waveforms.items():
                print(f"Channel {ch}: {len(waveform.voltage)} samples")
        else:
            print("\nNo trigger detected within timeout period")

    # Example 2: Capture multiple trigger events
    print("\n" + "=" * 60)
    print("Example 2: Capturing 10 trigger events...")

    with DataCollector(args.host, connection=_connect(args.host)) as collector:
        # Configure trigger
        collector.scope.trigger.set_source(1)
        collector.scope.trigger.set_slope("POS")
        collector.scope.trigger.set_level(1, 2.0)  # 2V threshold
        collector.scope.trigger.set_mode("NORM")  # Normal trigger mode

        print("Trigger configured:")
        print("  Source: Channel 1")
        print("  Edge: Rising")
        print("  Level: 2.0V")
        print("\nCapturing 10 trigger events...")

        captures = []
        for i in range(10):
            # Trigger single acquisition
            collector.scope.trigger_single()

            # Wait for trigger (simple polling). Uses the dialect-normalized
            # acquisition_status() rather than a raw ":TRIG:STAT?" query --
            # that literal command is modern-dialect only and times out
            # against a legacy-dialect scope (mock or real).
            timeout = 5.0
            start = time.time()
            while (time.time() - start) < timeout:
                status = collector.scope.acquisition_status()
                if status == "STOP":
                    # Capture waveform
                    waveforms = collector.capture_single([1, 2])
                    captures.append(waveforms)
                    print(f"  Captured event {i+1}/10")
                    break
                time.sleep(0.05)
            else:
                print(f"  Event {i+1} timed out")

        if captures:
            print(f"\nCaptured {len(captures)} events")

            # Save all captures. save_data() writes into the given directory
            # without creating it first, so it must already exist.
            print("Saving captures to 'multi_trigger_captures/'...")
            Path("multi_trigger_captures").mkdir(exist_ok=True)
            for i, waveforms in enumerate(captures):
                collector.save_data(waveforms, f"multi_trigger_captures/event_{i+1:03d}", format="npz")

            print("Done!")


if __name__ == "__main__":
    main()
