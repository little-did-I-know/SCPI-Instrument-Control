"""Debug script to test channel state and capture functionality."""

import logging
import pytest

pytest.skip("Interactive debug helper; skipped in automated CI runs", allow_module_level=True)

import sys

# Configure detailed logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)

from siglent import Oscilloscope


def test_channel_state(scope_ip: str):
    """Test channel enabled state detection.

    Args:
        scope_ip: IP address of oscilloscope
    """
    print("\n" + "=" * 60)
    print("Channel State Debug Test")
    print("=" * 60)

    try:
        print(f"\n1. Connecting to oscilloscope at {scope_ip}...")
        scope = Oscilloscope(scope_ip)
        scope.connect()
        print(f"   Connected to: {scope.device_info.get('model', 'Unknown')}")

        print("\n2. Checking channel states BEFORE enabling...")
        for ch_num in range(1, 5):
            try:
                channel = getattr(scope, f"channel{ch_num}")
                is_enabled = channel.enabled
                print(f"   Channel {ch_num}: {'ENABLED' if is_enabled else 'DISABLED'}")
            except Exception as e:
                print(f"   Channel {ch_num}: ERROR - {e}")

        print("\n3. Enabling Channel 1...")
        scope.channel1.enable()
        print("   Command sent")

        # Wait a bit
        import time

        time.sleep(0.2)

        print("\n4. Checking channel states AFTER enabling Channel 1...")
        for ch_num in range(1, 5):
            try:
                channel = getattr(scope, f"channel{ch_num}")
                is_enabled = channel.enabled
                print(f"   Channel {ch_num}: {'ENABLED' if is_enabled else 'DISABLED'}")
            except Exception as e:
                print(f"   Channel {ch_num}: ERROR - {e}")

        print("\n5. Testing waveform capture from Channel 1...")
        try:
            waveform = scope.get_waveform(1)
            if waveform:
                print(f"   SUCCESS! Captured waveform:")
                print(f"     - Samples: {len(waveform.voltage)}")
                print(f"     - Time range: {waveform.time[0]:.6e} to {waveform.time[-1]:.6e} s")
                print(f"     - Voltage range: {waveform.voltage.min():.3f} to {waveform.voltage.max():.3f} V")
            else:
                print(f"   FAILED - No waveform data returned")
        except Exception as e:
            print(f"   FAILED - {e}")
            import traceback

            traceback.print_exc()

        print("\n6. Disconnecting...")
        scope.disconnect()
        print("   Disconnected")

        print("\n" + "=" * 60)
        print("Test Complete")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_capture_debug.py <scope_ip>")
        print("Example: python test_capture_debug.py 192.168.1.207")
        sys.exit(1)

    scope_ip = sys.argv[1]
    test_channel_state(scope_ip)
