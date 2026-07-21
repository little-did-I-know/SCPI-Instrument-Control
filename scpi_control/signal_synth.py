"""Synthetic signal generation: parameterized waveforms as numpy arrays or WaveformData.

Public API for users who want synthetic data for testing and analysis, and the
engine behind MockConnection's state-coupled waveform synthesis. Kinds live in a
dispatch table of generator functions -- adding a kind is one new generator plus
docs and tests; the mock coupling and code-conversion layers are kind-agnostic.
"""

from dataclasses import dataclass
from typing import Callable, Dict, Optional

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
    """

    kind: str = "sine"
    frequency: float = 1_000.0
    amplitude: float = 1.0
    offset: float = 0.0
    phase: float = 0.0
    duty: float = 0.5
    noise_rms: float = 0.0
    seed: Optional[int] = None


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
    if spec.noise_rms > 0:
        samples = samples + rng.normal(0.0, spec.noise_rms, n_points)
    return samples


def make_waveform(spec: SignalSpec, sample_rate: float, n_points: int, channel: int = 1):
    """Generate a WaveformData ready for analysis, saving, or reporting."""
    # Function-level import: keeps `import scpi_control.connection` (which pulls
    # the mock package, which pulls this module) from importing waveform.py
    # mid-initialization.
    from scpi_control.waveform import WaveformData

    voltage = synthesize(spec, sample_rate, n_points)
    time = np.arange(n_points) / sample_rate
    return WaveformData(time=time, voltage=voltage, channel=channel, sample_rate=sample_rate)
