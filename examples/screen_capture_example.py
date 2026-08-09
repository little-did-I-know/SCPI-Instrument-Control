"""Pulling a screenshot off the instrument's display.

Requirements: none by default -- runs against the built-in mock scope. Pass
--host <ip> to drive a real oscilloscope on the network.

Note: the mock answers SCDP? with a minimal but valid 1x1-pixel BMP (58
bytes), not the instrument's actual framebuffer, so a mock run demonstrates
the transfer and the file write, not a picture worth looking at. It decodes
as a real (if tiny) image -- it is not a fake/placeholder byte string.
Against real hardware the same call returns the scope's actual screen
contents.

Expected output: the byte count printed to the console and 'screenshot.bmp'
written to the current directory. The scope returns BMP, not PNG -- use
ScreenCapture.get_screenshot_pil() (requires Pillow) if you want PNG.
"""

import argparse
import sys

from scpi_control import Oscilloscope
from scpi_control.connection import MockConnection
from scpi_control.screen_capture import ScreenCapture
from scpi_control.signal_synth import SignalSpec


def _connect(host):
    if host != "mock":
        return None
    return MockConnection(
        "mock",
        channel_states={1: True},
        signals={1: SignalSpec(kind="sine", frequency=1000.0, amplitude=1.0)},
        sample_rate=1e6,
        timebase=1e-3,
    )


def main():
    parser = argparse.ArgumentParser(description="Capture the instrument's screen")
    parser.add_argument("--host", default="mock", help="Instrument hostname/IP, or 'mock' (default: mock)")
    parser.add_argument("--output", default="screenshot.bmp", help="Where to write the BMP screenshot (default: screenshot.bmp)")
    args = parser.parse_args()

    scope = Oscilloscope(args.host, connection=_connect(args.host))
    scope.connect()
    try:
        camera = ScreenCapture(scope)
        data = camera.capture_screenshot()
        if not data:
            print("No screenshot returned by the instrument.", file=sys.stderr)
            raise SystemExit(1)
        with open(args.output, "wb") as handle:
            handle.write(data)
        print(f"Wrote {len(data)} bytes to {args.output}")
    finally:
        scope.disconnect()


if __name__ == "__main__":
    main()
