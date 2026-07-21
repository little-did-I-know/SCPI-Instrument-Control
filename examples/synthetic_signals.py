"""Synthetic signal generation: parameterized test waveforms, and the mock
oscilloscope's state-coupled synthesis.

scpi_control.signal_synth.SignalSpec describes a waveform (kind, frequency,
amplitude, offset, phase, duty, additive noise, and an optional seed for
reproducibility); synthesize()/make_waveform() turn a spec into a numpy array
or a full WaveformData ready for analysis, saving, or the report generator.
The same engine powers MockConnection: channels without an explicit
waveform_payloads entry synthesize live from the mock's current state, so
SCPI commands that change the timebase or voltage scale visibly change the
next capture -- exactly like a real scope.

This example (1) generates a few signal kinds directly and prints basic
stats, (2) opens a mock oscilloscope session, acquires, then changes TDIV and
VDIV over SCPI to show the capture's length and clipping respond, and (3)
saves one synthesized capture and reloads it with load_waveform() to show the
chain composes.

Requirements: SCPI-Instrument-Control (core install) -- runs entirely against
a mock connection, no instrument needed.
"""

from pathlib import Path

from scpi_control.connection import MockConnection
from scpi_control.oscilloscope import Oscilloscope
from scpi_control.signal_synth import SignalSpec, make_waveform
from scpi_control.waveform_io import load_waveform

OUTPUT_DIR = Path.cwd()
NPZ_PATH = OUTPUT_DIR / "synthetic_demo.npz"

# 8-bit code path constants the mock synthesizer uses internally
# (scpi_control/connection/mock/synth.py) -- reused here only to predict the
# voltage ceiling a given V/div setting clips at.
CODES_PER_DIV = 25
CODE_LIMIT = 127


def _print_stats(label: str, voltage) -> None:
    vpp = float(voltage.max() - voltage.min())
    print(f"{label:12s}: Vpp={vpp:.4f} V  mean={voltage.mean():.4f} V  std={voltage.std():.4f} V  n={len(voltage)}")


def demo_make_waveform() -> None:
    """Generate a few signal kinds directly and print basic stats."""
    print("=== Part 1: make_waveform() -- basic stats per kind ===")
    kinds = [
        ("square", SignalSpec(kind="square", frequency=1_000.0, amplitude=1.0, duty=0.5)),
        ("sine", SignalSpec(kind="sine", frequency=1_000.0, amplitude=1.0)),
        ("noisy sine", SignalSpec(kind="sine", frequency=1_000.0, amplitude=1.0, noise_rms=0.05, seed=7)),
    ]
    for label, spec in kinds:
        waveform = make_waveform(spec, sample_rate=100_000.0, n_points=1_000)
        _print_stats(label, waveform.voltage)


def demo_mock_session() -> None:
    """Open a mock scope session and show SCPI writes change the next capture."""
    print()
    print("=== Part 2: mock oscilloscope session -- state-coupled synthesis ===")
    conn = MockConnection(
        "mock",
        idn="Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0",
        channel_states={1: True, 2: False, 3: False, 4: False},
        trigger_status=["Stop"],
        sample_rate=1_000_000.0,
        timebase=1e-3,
        signals={1: SignalSpec(kind="sine", frequency=2_000.0, amplitude=0.8, noise_rms=0.02, seed=42)},
    )
    scope = Oscilloscope("mock", connection=conn)
    scope.connect()
    try:
        waveform = scope.get_waveform(1, provenance=False)
        print(f"Initial capture (TDIV=1e-3, C1:VDIV=1.0): {len(waveform.voltage)} points, " f"Vpp={float(waveform.voltage.max() - waveform.voltage.min()):.3f} V")

        # Shrinking the timebase shrinks the acquisition window (14 divisions
        # x timebase), so fewer points come back at the same sample rate.
        scope.write("TDIV 1e-4")
        shorter = scope.get_waveform(1, provenance=False)
        print(f"After TDIV 1e-4: {len(shorter.voltage)} points (window shrank from 14 ms to 1.4 ms)")

        # Tightening the voltage scale below the signal's amplitude clips the
        # capture, just like an 8-bit scope's ADC would over-range.
        scope.write("C1:VDIV 0.1")
        clipped = scope.get_waveform(1, provenance=False)
        clip_ceiling = CODE_LIMIT * 0.1 / CODES_PER_DIV
        peak = float(max(abs(clipped.voltage.max()), abs(clipped.voltage.min())))
        print(f"After C1:VDIV 0.1: peak |V| = {peak:.3f} V (signal amplitude is 0.8 V, " f"but the 8-bit code path ceilings at ~{clip_ceiling:.3f} V for this V/div)")

        print()
        print("=== Part 3: save + load_waveform() -- the chain composes ===")
        final = scope.get_waveform(1, provenance=True)
        scope.waveform.save_waveform(final, str(NPZ_PATH))
        print(f"Saved {NPZ_PATH.name} ({len(final.voltage)} points)")
    finally:
        scope.disconnect()


def demo_reload() -> None:
    """Reload the saved capture and show the raw data survives the round trip."""
    loaded = load_waveform(NPZ_PATH)
    print(f"Reloaded {NPZ_PATH.name} ({loaded.source_format}): {len(loaded.voltage)} points, " f"channel {loaded.channel}, sample_rate {loaded.sample_rate}")
    print(f"First 5 samples (V): {loaded.voltage[:5].tolist()}")


def main() -> None:
    demo_make_waveform()
    demo_mock_session()
    demo_reload()


if __name__ == "__main__":
    main()
