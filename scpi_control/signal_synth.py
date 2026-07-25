"""Synthetic signal generation: parameterized waveforms as numpy arrays or WaveformData.

Public API for users who want synthetic data for testing and analysis, and the
engine behind MockConnection's state-coupled waveform synthesis. Kinds live in a
dispatch table of generator functions -- adding a kind is one new generator plus
docs and tests; the mock coupling and code-conversion layers are kind-agnostic.
"""

import time
from dataclasses import dataclass, replace
from typing import Callable, Dict, Iterator, Optional

import numpy as np

from scpi_control import exceptions


@dataclass(frozen=True)
class SignalSpec:
    """Parameters of one synthetic signal.

    Attributes:
        kind: One of "sine", "square", "triangle", "ramp", "dc", "noise".
        frequency: Repetition rate in Hz (periodic kinds only).
        amplitude: Peak amplitude in volts (Vpp = 2*amplitude); for "noise",
            the standard deviation. Ignored for "dc".
        offset: DC offset in volts, added to every kind ("dc" outputs exactly
            this level).
        phase: Phase in radians (periodic kinds only).
        duty: High fraction of a "square" period, 0 < duty < 1 (pulse/PWM).
        noise_rms: Std-dev of additive Gaussian noise laid on any kind.
        seed: None for fresh randomness per call; an int for reproducibility.
        drift_amplitude: Volts of slow baseline wander (0 = off).
        drift_frequency: Hz of that wander; only used when drift_amplitude > 0.
        glitch_rate: Mean glitches per second (0 = off).
        glitch_amplitude: Volts, peak height of a glitch.
        ringing_frequency: Hz of post-edge oscillation (0 = off).
        ringing_damping: Decay rate per second of that oscillation.
    """

    kind: str = "sine"
    frequency: float = 1_000.0
    amplitude: float = 1.0
    offset: float = 0.0
    phase: float = 0.0
    duty: float = 0.5
    noise_rms: float = 0.0
    seed: Optional[int] = None
    # Impairments, all default-off. Appended at the END of the dataclass
    # deliberately: inserting them next to noise_rms, where they read better,
    # would reorder positional construction and break callers.
    drift_amplitude: float = 0.0  # volts of slow baseline wander (0 = off)
    drift_frequency: float = 0.1  # Hz of that wander; only used when drift_amplitude > 0
    glitch_rate: float = 0.0  # mean glitches per second (0 = off)
    glitch_amplitude: float = 0.0  # volts, peak height of a glitch
    ringing_frequency: float = 0.0  # Hz of post-edge oscillation (0 = off)
    ringing_damping: float = 0.0  # decay rate per second of that oscillation


def _cycle_fraction(spec: SignalSpec, t: np.ndarray) -> np.ndarray:
    return (spec.frequency * t + spec.phase / (2.0 * np.pi)) % 1.0


def _sine(spec: SignalSpec, t: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    return spec.amplitude * np.sin(2.0 * np.pi * spec.frequency * t + spec.phase)


def _square(spec: SignalSpec, t: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    return np.where(_cycle_fraction(spec, t) < spec.duty, spec.amplitude, -spec.amplitude)


def _triangle(spec: SignalSpec, t: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    return spec.amplitude * (1.0 - 4.0 * np.abs(_cycle_fraction(spec, t) - 0.5))


def _ramp(spec: SignalSpec, t: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    return spec.amplitude * (2.0 * _cycle_fraction(spec, t) - 1.0)


def _dc(spec: SignalSpec, t: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    return np.zeros_like(t)


def _noise(spec: SignalSpec, t: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    return rng.normal(0.0, spec.amplitude, t.shape)


_GENERATORS: Dict[str, Callable[[SignalSpec, np.ndarray, np.random.Generator], np.ndarray]] = {
    "sine": _sine,
    "square": _square,
    "triangle": _triangle,
    "ramp": _ramp,
    "dc": _dc,
    "noise": _noise,
}

PERIODIC_KINDS = ("sine", "square", "triangle", "ramp")


def _validate(spec: SignalSpec, sample_rate: float, n_points: int) -> None:
    if spec.kind not in _GENERATORS:
        raise exceptions.InvalidParameterError(f"Unknown signal kind: {spec.kind!r}. Supported: {', '.join(sorted(_GENERATORS))}")
    if sample_rate <= 0:
        raise exceptions.InvalidParameterError(f"sample_rate must be positive: {sample_rate}")
    if n_points < 1:
        raise exceptions.InvalidParameterError(f"n_points must be at least 1: {n_points}")
    if spec.kind in PERIODIC_KINDS and spec.frequency <= 0:
        raise exceptions.InvalidParameterError(f"frequency must be positive for {spec.kind!r}: {spec.frequency}")
    if spec.kind == "square" and not 0.0 < spec.duty < 1.0:
        raise exceptions.InvalidParameterError(f"duty must be strictly between 0 and 1: {spec.duty}")
    if spec.noise_rms < 0:
        raise exceptions.InvalidParameterError(f"noise_rms must be non-negative: {spec.noise_rms}")
    if spec.drift_amplitude < 0:
        raise exceptions.InvalidParameterError(f"drift_amplitude must be non-negative: {spec.drift_amplitude}")
    if spec.glitch_rate < 0:
        raise exceptions.InvalidParameterError(f"glitch_rate must be non-negative: {spec.glitch_rate}")
    if spec.glitch_amplitude < 0:
        raise exceptions.InvalidParameterError(f"glitch_amplitude must be non-negative: {spec.glitch_amplitude}")
    if spec.ringing_frequency < 0:
        raise exceptions.InvalidParameterError(f"ringing_frequency must be non-negative: {spec.ringing_frequency}")
    if spec.ringing_damping < 0:
        raise exceptions.InvalidParameterError(f"ringing_damping must be non-negative: {spec.ringing_damping}")


def _impairment_rng(seed: Optional[int], stream_index: int) -> np.random.Generator:
    """An independent, seed-reproducible generator per impairment.

    Drawing impairments from synthesize()'s shared `rng` would make enabling one
    impairment change another's samples and the base noise, so a test asserting on
    noise would break merely because drift was switched on.
    """
    if seed is None:
        return np.random.default_rng()
    return np.random.default_rng([seed, stream_index])


def synthesize(spec: SignalSpec, sample_rate: float, n_points: int, t0: float = 0.0) -> np.ndarray:
    """Generate voltage samples for a signal spec.

    Args:
        spec: Signal parameters.
        sample_rate: Samples per second.
        n_points: Number of samples.
        t0: Time of the first sample in seconds (shifts periodic signals).

    Returns:
        float64 voltage array of length n_points.
    """
    _validate(spec, sample_rate, n_points)
    rng = np.random.default_rng(spec.seed)
    t = t0 + np.arange(n_points) / sample_rate
    samples = _GENERATORS[spec.kind](spec, t, rng) + spec.offset
    if spec.ringing_frequency > 0:
        # A damped sinusoid triggered at each edge. Real probe/scope front-ends
        # ring after a fast transition; this is what gives overshoot/preshoot
        # measurements something real to measure. Deterministic and edge-local,
        # so it needs no generator and is automatically continuous across
        # stream() chunks. Applied to the base signal BEFORE drift and glitches:
        # ringing is part of the signal's own edge response, not a baseline
        # wander or an additive event.
        edges = np.flatnonzero(np.diff(samples))
        if edges.size:
            # 5 time constants of decay, in samples. `max(spec.ringing_damping, 1e-9)`
            # only guards the division against damping == 0 (undamped ringing) --
            # it must NOT clamp small-but-nonzero damping up to some larger floor,
            # or slow decay would be truncated before it actually decays, showing
            # up as a discontinuity where the kernel window ends. `max(1, ...)`
            # then guards int() truncating to 0 for very heavy damping. Both are
            # capped by n_points, since the kernel can never need to run longer
            # than the buffer itself.
            decay_len = min(n_points, max(1, int(sample_rate / max(spec.ringing_damping, 1e-9) * 5)))
            tail = np.arange(decay_len) / sample_rate
            kernel = np.sin(2 * np.pi * spec.ringing_frequency * tail) * np.exp(-spec.ringing_damping * tail)
            response = np.zeros(n_points)
            for edge in edges:
                step = samples[edge + 1] - samples[edge]
                end = min(n_points, edge + 1 + decay_len)
                response[edge + 1 : end] += 0.5 * step * kernel[: end - edge - 1]
            samples = samples + response
    if spec.drift_amplitude > 0:
        # Time-based, NOT a random walk: stream() re-seeds per chunk, so a walk
        # would reset at every chunk boundary and a live view would show sawtooth
        # jumps. Deriving drift from absolute time keeps it continuous for free.
        samples = samples + spec.drift_amplitude * np.sin(2 * np.pi * spec.drift_frequency * t)
    if spec.glitch_rate > 0 and spec.glitch_amplitude > 0:
        glitch_rng = _impairment_rng(spec.seed, 1)
        expected = spec.glitch_rate * n_points / sample_rate
        count = glitch_rng.poisson(expected)
        if count:
            positions = glitch_rng.integers(0, n_points, size=count)
            signs = glitch_rng.choice(np.array([-1.0, 1.0]), size=count)
            samples = samples.copy()
            # np.add.at, NOT samples[positions] += ... -- fancy-index += applies
            # only ONCE per repeated index, so duplicate glitch positions would be
            # silently dropped and the glitch rate would come out low.
            np.add.at(samples, positions, signs * spec.glitch_amplitude)
    if spec.noise_rms > 0:
        samples = samples + rng.normal(0.0, spec.noise_rms, n_points)
    return samples


def stream(
    spec: SignalSpec,
    sample_rate: float,
    chunk_size: int,
    *,
    start_time: float = 0.0,
    duration: Optional[float] = None,
    realtime: bool = False,
) -> Iterator[np.ndarray]:
    """Yield phase-continuous voltage chunks for live/continuous simulation.

    Args:
        spec: Signal parameters. A seeded spec uses seed + chunk_index per
            chunk (reproducible run-to-run, non-repeating across chunks);
            seed=None re-rolls noise freshly every chunk.
        sample_rate: Samples per second.
        chunk_size: Samples per yielded chunk.
        start_time: Time of the very first sample in seconds.
        duration: None streams forever (stop by breaking out); a positive
            number bounds the stream to round(duration * sample_rate) samples,
            truncating the final chunk.
        realtime: When True, chunks arrive at wall-clock rate (chunk k is
            withheld until k * chunk_size / sample_rate seconds after the
            first chunk); scheduling is absolute, so timing error never
            accumulates, and a consumer slower than real time simply never
            waits.

    Returns:
        Iterator of float64 voltage arrays. Validation errors raise at call
        time, before the first chunk.
    """
    _validate(spec, sample_rate, chunk_size)
    if duration is not None and duration <= 0:
        raise exceptions.InvalidParameterError(f"duration must be positive: {duration}")
    total = None if duration is None else int(round(duration * sample_rate))

    def _chunks() -> Iterator[np.ndarray]:
        produced = 0
        index = 0
        wall_start = None
        while total is None or produced < total:
            n = chunk_size if total is None else min(chunk_size, total - produced)
            chunk_spec = spec if spec.seed is None else replace(spec, seed=spec.seed + index)
            chunk = synthesize(chunk_spec, sample_rate, n, t0=start_time + produced / sample_rate)
            if realtime:
                if wall_start is None:
                    wall_start = time.monotonic()
                else:
                    delay = wall_start + produced / sample_rate - time.monotonic()
                    if delay > 0:
                        time.sleep(delay)
            yield chunk
            produced += n
            index += 1

    return _chunks()


def make_waveform(spec: SignalSpec, sample_rate: float, n_points: int, channel: int = 1):
    """Generate a WaveformData ready for analysis, saving, or reporting."""
    # Function-level import: keeps `import scpi_control.connection` (which pulls
    # the mock package, which pulls this module) from importing waveform.py
    # mid-initialization.
    from scpi_control.waveform import WaveformData

    voltage = synthesize(spec, sample_rate, n_points)
    time = np.arange(n_points) / sample_rate
    return WaveformData(time=time, voltage=voltage, channel=channel, sample_rate=sample_rate)
