"""Golden-reference comparison: save a known-good capture and compare later ones.

Stores a captured waveform as a named reference, then scores a later capture
against it with a correlation coefficient and a point-by-point difference --
the shape of a pass/fail bench check.

Requirements: none by default -- runs against the built-in mock scope. Pass
--host <ip> to drive a real oscilloscope on the network.

Expected output: correlation and peak-difference figures printed to the
console. References are written to a temporary directory that is removed on
exit; pass --storage-dir to keep them.
"""

import argparse
import shutil
import tempfile

from scpi_control import Oscilloscope
from scpi_control.connection import MockConnection
from scpi_control.reference_waveform import ReferenceWaveform
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
    parser = argparse.ArgumentParser(description="Save and compare against a golden reference waveform")
    parser.add_argument("--host", default="mock", help="Instrument hostname/IP, or 'mock' (default: mock)")
    parser.add_argument("--storage-dir", default=None, help="Where to keep references (default: a temp dir, deleted on exit)")
    args = parser.parse_args()

    storage = args.storage_dir or tempfile.mkdtemp()
    scope = Oscilloscope(args.host, connection=_connect(args.host))
    scope.connect()
    try:
        store = ReferenceWaveform(storage_dir=storage)

        golden = scope.get_waveform(channel=1)
        store.save_reference(golden, "baseline")
        print(f"Saved reference 'baseline' ({len(golden.time)} samples)")

        # load_reference returns a dict -- calculate_correlation needs that dict,
        # not the reference's name.
        reference = store.load_reference("baseline")

        later = scope.get_waveform(channel=1)
        correlation = store.calculate_correlation(later, reference)
        difference = store.calculate_difference(later, reference)

        print(f"Correlation with baseline: {correlation:.6f}")
        print(f"Peak absolute difference:  {abs(difference).max():.3e} V")
        print(f"References on file: {[r['name'] for r in store.list_references()]}")
    finally:
        scope.disconnect()
        if args.storage_dir is None:
            shutil.rmtree(storage, ignore_errors=True)


if __name__ == "__main__":
    main()
