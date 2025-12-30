"""Trigger-based event capture.

This example demonstrates how to wait for specific trigger conditions
and capture waveforms when they occur. This is useful for capturing
sporadic events or signals that meet specific criteria.
"""

from siglent.automation import DataCollector, TriggerWaitCollector

# Replace with your oscilloscope's IP address
SCOPE_IP = "192.168.1.100"


def main():
    # Example 1: Wait for a single trigger event
    print("Example 1: Waiting for trigger event...")
    with TriggerWaitCollector(SCOPE_IP) as tc:
        # Configure trigger: Channel 1, Rising edge, 1V threshold
        tc.collector.scope.trigger.set_source(1)
        tc.collector.scope.trigger.set_slope("POS")  # Rising edge
        tc.collector.scope.trigger.set_level(1, 1.0)  # 1V threshold

        print("Trigger configured:")
        print("  Source: Channel 1")
        print("  Edge: Rising")
        print("  Level: 1.0V")
        print("\nWaiting for trigger (max 30 seconds)...")

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

    with DataCollector(SCOPE_IP) as collector:
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

            # Wait for trigger (simple polling)
            import time

            timeout = 5.0
            start = time.time()
            while (time.time() - start) < timeout:
                status = collector.scope.query(":TRIG:STAT?").strip()
                if status == "Stop":
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

            # Save all captures
            print("Saving captures to 'multi_trigger_captures/'...")
            for i, waveforms in enumerate(captures):
                collector.save_data(waveforms, f"multi_trigger_captures/event_{i+1:03d}", format="npz")

            print("Done!")


if __name__ == "__main__":
    main()
