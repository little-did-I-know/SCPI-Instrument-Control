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
VDIV over SCPI to show the capture's length and clipping respond, (3) saves
one synthesized capture and reloads it with load_waveform() to show the chain
composes, (4) synthesizes a multitone and compares its measured THD to the
analytically expected value, (5) synthesizes a chirp and measures its
start/end frequency from zero crossings, and (6) synthesizes a sine with
known timing jitter and compares its measured period jitter to the injected
value.

Requirements: SCPI-Instrument-Control (core install) -- runs entirely against
a mock connection, no instrument needed.
"""

from pathlib import Path

import numpy as np

from scpi_control.analysis import FFTAnalyzer
from scpi_control.connection import MockConnection
from scpi_control.oscilloscope import Oscilloscope
from scpi_control.report_generator.utils.waveform_analyzer import WaveformAnalyzer
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


def demo_multitone() -> None:
    """Synthesize a multitone and compare its measured THD to the analytic value.

    harmonics gives the relative amplitudes of the 2nd, 3rd, ... harmonic of a
    coherent series riding on the fundamental, so THD comes out to exactly
    sqrt(sum(h**2)) -- independent of amplitude, frequency, and phase.
    """
    print()
    print("=== Part 4: multitone -- measured vs. expected THD ===")
    harmonics = (0.1, 0.05)
    spec = SignalSpec(kind="multitone", frequency=1_000.0, amplitude=1.0, harmonics=harmonics)
    waveform = make_waveform(spec, sample_rate=100_000.0, n_points=100_000)
    measured_thd = FFTAnalyzer.thd_of_waveform(waveform)
    expected_thd = 100.0 * float(np.sqrt(np.sum(np.square(harmonics))))
    print(f"multitone: measured THD = {measured_thd:.3f}%  " f"expected THD (100*sqrt(sum(h**2))) = {expected_thd:.3f}%")


def _zero_crossing_freq(time_s: np.ndarray, voltage: np.ndarray, from_end: bool) -> float:
    """Estimate instantaneous frequency from one pair of rising zero crossings.

    Linear interpolation between the two bracketing samples locates each
    crossing sub-sample; the reciprocal of the gap between one crossing and
    the next is a local frequency estimate -- accurate near the start or end
    of a sweep, where the chirp's instantaneous frequency is nearly constant
    over a single cycle.
    """
    rising = np.flatnonzero((voltage[:-1] <= 0.0) & (voltage[1:] > 0.0))
    pair = rising[-2:] if from_end else rising[:2]

    def _crossing_time(i: int) -> float:
        t0, t1 = time_s[i], time_s[i + 1]
        v0, v1 = voltage[i], voltage[i + 1]
        return float(t0 + (0.0 - v0) * (t1 - t0) / (v1 - v0))

    return 1.0 / (_crossing_time(pair[1]) - _crossing_time(pair[0]))


def demo_chirp() -> None:
    """Synthesize a chirp and measure its start/end frequency from zero crossings."""
    print()
    print("=== Part 5: chirp -- measured start/end frequency ===")
    spec = SignalSpec(kind="chirp")  # defaults: 1 kHz -> 10 kHz over 10 ms, then it retraces
    sample_rate = 1_000_000.0
    n_points = int(round(sample_rate * spec.sweep_time))
    waveform = make_waveform(spec, sample_rate=sample_rate, n_points=n_points)
    start_freq = _zero_crossing_freq(waveform.time, waveform.voltage, from_end=False)
    end_freq = _zero_crossing_freq(waveform.time, waveform.voltage, from_end=True)
    print(f"chirp: configured {spec.frequency:.1f} Hz -> {spec.end_frequency:.1f} Hz over {spec.sweep_time * 1000:.1f} ms")
    print(f"chirp: measured start = {start_freq:.1f} Hz  measured end = {end_freq:.1f} Hz")


def demo_jitter() -> None:
    """Synthesize a jittered sine and compare its measured period jitter to
    the injected jitter_rms, via the same WaveformAnalyzer call path the
    tests use.

    jitter_rms is per-kind-calibrated (see
    docs/superpowers/specs/2026-08-28-signal-timing-jitter-design.md's Model
    section): a kind whose measured rising edge sits exactly at a cycle
    boundary -- sine, square, multitone, pulse -- measures close to the
    nominal value, as demonstrated here. triangle/ramp measure a smaller,
    but stable and documented, fraction of it (~0.66x and ~0.5x
    respectively) because their measured edge sits mid-cycle, where
    neighboring cycles' jitter draws partially cancel.
    """
    print()
    print("=== Part 6: jitter -- measured vs. injected period jitter (sine) ===")
    jitter_rms = 3e-6  # seconds
    spec = SignalSpec(kind="sine", frequency=10_000.0, amplitude=1.0, jitter_rms=jitter_rms, seed=21)
    waveform = make_waveform(spec, sample_rate=1_000_000.0, n_points=50_000)
    measured_jitter = WaveformAnalyzer.calculate_quality_stats(waveform)["jitter"]
    print(f"jitter: injected jitter_rms = {jitter_rms * 1e6:.2f} us  " f"measured = {measured_jitter * 1e6:.2f} us")


def main() -> None:
    demo_make_waveform()
    demo_mock_session()
    demo_reload()
    demo_multitone()
    demo_chirp()
    demo_jitter()


if __name__ == "__main__":
    main()
