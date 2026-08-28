"""Synthetic signal generation: parameterized waveforms as numpy arrays or WaveformData.

Public API for users who want synthetic data for testing and analysis, and the
engine behind MockConnection's state-coupled waveform synthesis. Kinds live in a
dispatch table of generator functions -- adding a kind is one new generator plus
docs and tests; the mock coupling and code-conversion layers are kind-agnostic.
"""

import time
from dataclasses import dataclass, replace
from typing import Callable, Dict, Iterator, Optional, Tuple, Union

import numpy as np

from scpi_control import exceptions


@dataclass(frozen=True)
class SignalSpec:
    """Parameters of one synthetic signal.

    Attributes:
        kind: One of "sine", "square", "triangle", "ramp", "dc", "noise",
            "chirp", "exponential", "pulse", "multitone".
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
        ringing_frequency: Hz of post-edge oscillation (0 = off). Ringing is
            an EDGE impairment: it is PHYSICALLY meaningful on kinds with fast
            edges ("square", "pulse", or a pulse-like "ramp"). It is not,
            however, a no-op elsewhere -- edges are found as any nonzero
            sample-to-sample change, not only as a discontinuity, so on a
            continuous kind ("sine", "chirp", "exponential", "multitone") it
            acts as a derivative-weighted filter whose magnitude scales with
            the signal's slew rate: measurable, but usually small. Only "dc",
            whose sample-to-sample differences are all zero, is a true no-op.
        ringing_damping: Decay rate per second of that oscillation; only used
            when ringing_frequency > 0. Defaults away from 0 for the same
            reason drift_frequency does: undamped ringing (decay rate 0)
            never actually decays, so the kernel would run for the entire
            buffer on every edge -- quadratic in the number of edges once
            ringing_frequency is switched on the most natural way, by setting
            only that field.
        end_frequency: "chirp" sweep stop frequency in Hz.
        sweep_time: "chirp" seconds per sweep, after which it retraces.
        sweep_log: "chirp" sweeps logarithmically rather than linearly.
        tau: "exponential" RC time constant in seconds.
        pulse_width: "pulse" 50%-to-50% width in seconds (FWHM), matching the
            instrument convention and the threshold the repo's timing analyzer
            measures at. The flat top therefore runs for pulse_width -
            edge_time. "pulse" ignores `duty`.
        edge_time: "pulse" 0-to-100% transition time in seconds; 0 gives an
            ideal instantaneous edge.
        harmonics: "multitone" relative amplitudes of the 2nd, 3rd, ...
            harmonic. `amplitude` is the FUNDAMENTAL's amplitude, so the peak
            of the sum is higher; that is deliberate, since normalizing would
            make the THD of a multitone depend on its harmonic set.
        jitter_rms: Std-dev of period-to-period timing jitter, in seconds (0 =
            off). PERIODIC_KINDS only (sine, square, triangle, ramp,
            multitone, exponential, pulse): "dc"/"noise" have no cycle
            structure and "chirp" has no stable period, so on those three
            kinds this field is a no-op rather than an error. Each cycle
            BOUNDARY gets its own independent Gaussian time-shift, and every
            sample's shift is the LINEAR INTERPOLATION between the two
            boundaries straddling it -- a continuous warp, not a per-cycle
            hard step -- so an enabled `ringing_frequency` keys on the actual
            jittered edge, not the nominal one, with no special-casing needed.

            What you actually measure back depends on WHERE your kind's
            measurable edge sits within its cycle, because the interpolation
            blends less of the "wrong" neighbor the closer the edge sits to a
            boundary. Let f be that edge's fractional position in [0, 1)
            (f=0 is the cycle boundary itself; _cycle_fraction computes the
            same fraction for the underlying generator):
              - An edge AT the cycle boundary (f=0 -- the ascending v50
                crossing of "sine", "square", "multitone", and "pulse" (whose
                edge sits within edge_time/2 of the boundary) at their default
                phase=0.0) gets the full, unblended shift from the boundary on
                each side, so period[n] = T + delta[n+1] - delta[n] exactly as
                a per-cycle-constant model would give: measures `jitter_rms`
                almost exactly (verified empirically: ratio 0.94-1.08 across
                trials at 1-5% of the period).
              - An edge at some other in-cycle fraction f gets a BLENDED shift
                and measures LESS. Two verified examples: "triangle"'s
                ascending crossing sits at f=0.25 (ratio measured ~0.66-0.68,
                close to the 0.6614 the formula below predicts); "ramp"'s
                zero crossing -- despite the ramp's own discontinuity sitting
                at the boundary -- is itself a continuous ramp, so its v50
                crossing actually sits at f=0.5, cycle CENTER, the point of
                MAXIMUM attenuation (ratio measured ~0.50-0.52, matching the
                formula's minimum of 0.5 almost exactly).
              Both are consistent with
              Var(period)/jitter_rms**2 = 0.5*[(1-2f)**2 + f**2 + (1-f)**2],
              which is 1.0 at f=0 and a minimum of 0.25 (ratio 0.5) at f=0.5.
            The internal per-boundary draw uses sigma = jitter_rms / sqrt(2),
            which is what keeps the common f=0 case exactly calibrated. See
            docs/superpowers/specs/2026-08-28-signal-timing-jitter-design.md
            for the full derivation. stream() chunk-boundary continuity: a
            cycle straddling a stream() chunk boundary now draws the SAME
            deltas regardless of which chunk's call renders it -- see
            `jitter_seed` below and
            docs/superpowers/specs/2026-08-28-jitter-stream-continuity-design.md.
        jitter_seed: Decouples jitter's per-boundary randomness from `seed`.
            None (the default) falls back to `seed`, so a one-shot
            `synthesize()`/`make_waveform()` call behaves exactly as if this
            field didn't exist. `stream()` auto-fills it with the ORIGINAL,
            pre-chunk-bump `seed` on every chunk whose spec left it None --
            `seed` itself keeps bumping per chunk (so noise/glitches keep
            varying chunk-to-chunk, unaffected), but every chunk of one
            stream() run now shares the same jitter entropy source, which is
            what makes a cycle straddling a chunk boundary resolve to
            identical boundary deltas no matter which chunk renders it. Set
            explicitly on a spec passed to `stream()` to opt out of the
            auto-fill and choose jitter's entropy source independently of
            `seed`.
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
    ringing_frequency: float = 0.0  # Hz of post-edge oscillation (0 = off); an edge impairment -- physically meaningful on "square"/"pulse"; on continuous kinds a small derivative filter, not a no-op
    ringing_damping: float = 5_000.0  # decay rate per second (M8: nonzero default, same reason as drift_frequency -- damping=0 never decays, making the kernel run the whole buffer on every edge)
    # Kind-specific parameters, appended at the END for the same reason the
    # impairments above were: inserting them beside the fields they read best
    # next to would reorder positional construction and break callers. Every
    # default is chosen so SignalSpec(kind=X) alone yields a sensible signal at
    # the default 1 kHz frequency, the property the original six kinds have.
    end_frequency: float = 10_000.0  # "chirp": sweep stop frequency, Hz
    sweep_time: float = 0.01  # "chirp": seconds per sweep, then it retraces
    sweep_log: bool = False  # "chirp": log rather than linear sweep
    tau: float = 1e-4  # "exponential": RC time constant, s (5 tau per half period at 1 kHz)
    pulse_width: float = 2e-4  # "pulse": 50%-to-50% width, s (20% duty at 1 kHz)
    edge_time: float = 1e-5  # "pulse": 0->100% transition time, s
    harmonics: Tuple[float, ...] = (
        0.1,
        0.05,
    )  # "multitone": relative amplitudes of the 2nd, 3rd, ... harmonic; non-empty by default so SignalSpec(kind="multitone") is not a bit-identical duplicate of "sine"
    # Appended after harmonics -- the last of the kind-specific fields -- for the
    # same don't-reorder-positional-construction reason as every field above it,
    # NOT next to the other impairments where it reads better.
    jitter_rms: float = 0.0  # seconds of period-to-period timing jitter (0 = off); PERIODIC_KINDS only -- see the docstring above for the model and the sqrt(2) calibration
    # Appended after jitter_rms -- the current last field -- for the same
    # don't-reorder-positional-construction reason as every field above it.
    jitter_seed: Optional[int] = None  # decouples jitter's boundary RNG from `seed`; None falls back to `seed`. stream() auto-fills this with the pre-bump `seed` per chunk -- see the docstring above


# How close to a whole cycle a sample may sit and still count as landing exactly
# on the boundary. In ULPs so it scales with the magnitude of the cycle count --
# see _cycle_fraction for why this exists at all.
_CYCLE_BOUNDARY_ULPS = 4


def _cycle_fraction(spec: SignalSpec, t: np.ndarray) -> np.ndarray:
    """Position within the current cycle, in [0, 1).

    The near-integer snap is load-bearing, not defensive. `synthesize` builds
    `t = t0 + i / sample_rate`, and for an arbitrary t0 -- a trigger crossing, a
    free-run drift offset, a DUT's lead-in -- that sum cannot land exactly on a
    whole number of periods. The product then comes out an ULP *below* an
    integer and `%` maps it to 0.9999999999999991 rather than 0.0.

    On a continuous kind that is invisible. On one that is discontinuous at the
    wrap it inverts a sample: "square" reads its low level at the instant it
    should switch high, and "ramp" resets a sample early. In a mock capture that
    is a full-amplitude artifact -- about 50 int8 codes -- on an otherwise
    correct trace, which reads as a broken instrument model rather than as
    arithmetic.

    Snapping cannot do harm larger than it repairs: it moves the cycle position
    by at most _CYCLE_BOUNDARY_ULPS ULPs, below the resolution of every consumer.
    A legitimate sample would have to fall within a few ULP of a boundary to be
    touched -- adjacent samples are frequency/sample_rate apart, many orders of
    magnitude more -- and a sample that close to a boundary belongs on it. A
    sweep of 3000 random specs (1 Hz to 10 MHz, 1 kSa/s to 1 GSa/s, arbitrary t0
    and phase) snapped nothing at all.

    KNOWN RESIDUAL: this fixes the wrap at fraction 0, not the other decision
    points. `_square` compares against `duty`, `_pulse` against its edge and
    width, `_exponential` against its high-phase length; a sample landing on one
    of those thresholds is subject to the same float error, which moves that edge
    by one sample. Strictly smaller than an inverted sample, and closing it means
    making every threshold comparison in every generator boundary-aware. See
    tests/test_cycle_boundary.py, which pins the current behaviour so the gap is
    visible.
    """
    cycles = spec.frequency * t + spec.phase / (2.0 * np.pi)
    nearest = np.round(cycles)
    cycles = np.where(np.abs(cycles - nearest) <= _CYCLE_BOUNDARY_ULPS * np.spacing(np.abs(cycles)), nearest, cycles)
    return cycles % 1.0


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


def _multitone(spec: SignalSpec, t: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """A fundamental plus a coherent harmonic series -- a distorted sine.

    Harmonic k rides at k*theta, so its phase advances with the fundamental's
    rather than drifting against it. That makes THD exactly sqrt(sum(h**2)),
    independent of amplitude, frequency and phase, which is the whole point:
    it gives the repo's THD code a signal with a known correct answer.
    """
    theta = 2.0 * np.pi * spec.frequency * t + spec.phase
    samples = np.sin(theta)
    for order, relative in enumerate(spec.harmonics, start=2):
        if relative:
            samples = samples + relative * np.sin(order * theta)
    return spec.amplitude * samples


def _exponential(spec: SignalSpec, t: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """A square wave through an RC network, at its PERIODIC STEADY STATE.

    Solved in closed form rather than integrated forward: stream() re-enters
    synthesize() per chunk with a new t0, so anything that had to settle in over
    the first few cycles would restart its settling at every chunk boundary.
    Requiring the trace to repeat exactly gives two linear equations in the two
    phase-start levels; `duty` splits the period, the waveform charges toward
    +amplitude and discharges toward -amplitude with time constant `tau`.

    Both branch boundaries evaluate to the same level (the high branch at t_high
    equals low_start; the low branch at t_low equals high_start), so the result
    is continuous everywhere -- there is no jump for a probe's edge response to
    key on. (Not the same as ringing being a no-op here: it keys on any
    sample-to-sample change, so it still filters this kind slightly. See
    SignalSpec.ringing_frequency.)
    """
    period = 1.0 / spec.frequency
    t_high = spec.duty * period
    t_low = period - t_high
    a = np.exp(-t_high / spec.tau)
    b = np.exp(-t_low / spec.tau)
    # expm1 form throughout: the algebraic result is (2b - 1 - ab)/(1 - ab), but
    # as tau grows both numerator and denominator become differences of
    # near-equal numbers and lose every significant digit -- at tau=1e12 the
    # naive form divides by zero. -expm1(-period/tau) IS 1 - a*b, computed
    # accurately.
    denom = -np.expm1(-period / spec.tau)
    high_start = spec.amplitude * (np.expm1(-t_low / spec.tau) - b * np.expm1(-t_high / spec.tau)) / denom
    low_start = spec.amplitude * (a * np.expm1(-t_low / spec.tau) - np.expm1(-t_high / spec.tau)) / denom
    within = _cycle_fraction(spec, t) * period
    rising = within < t_high
    decay = np.exp(-np.where(rising, within, within - t_high) / spec.tau)
    return np.where(rising, spec.amplitude + (high_start - spec.amplitude) * decay, -spec.amplitude + (low_start + spec.amplitude) * decay)


def _pulse(spec: SignalSpec, t: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """A trapezoid whose width and edge rate are independent of the period.

    That independence is the whole reason this kind exists alongside "square",
    whose only shape control is `duty` -- which this kind therefore ignores.
    `pulse_width` is the 50%-to-50% width: the 50% level sits at the midpoint of
    each linear ramp, so the crossings land at edge_time/2 and
    pulse_width + edge_time/2, exactly pulse_width apart.
    """
    within = _cycle_fraction(spec, t) / spec.frequency
    high = spec.amplitude
    low = -spec.amplitude
    if spec.edge_time <= 0:
        return np.where(within < spec.pulse_width, high, low)
    span = high - low
    rise = low + span * (within / spec.edge_time)
    fall = high - span * ((within - spec.pulse_width) / spec.edge_time)
    return np.where(within < spec.edge_time, rise, np.where(within < spec.pulse_width, high, np.where(within < spec.pulse_width + spec.edge_time, fall, low)))


def _chirp_phase(spec: SignalSpec, x: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
    """Phase accumulated from the start of a sweep to `x` seconds into it."""
    f0 = spec.frequency
    f1 = spec.end_frequency
    span = spec.sweep_time
    if spec.sweep_log:
        ratio = f1 / f0
        if ratio == 1.0:
            # The limit of the log form as f1 -> f0: a constant-frequency tone.
            # Taken here rather than raising, because log(1) == 0 would divide by
            # zero on a spec that is degenerate but perfectly sane.
            return 2.0 * np.pi * f0 * x
        return 2.0 * np.pi * f0 * span / np.log(ratio) * (np.power(ratio, x / span) - 1.0)
    return 2.0 * np.pi * (f0 * x + (f1 - f0) * x * x / (2.0 * span))


def _chirp(spec: SignalSpec, t: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """A repeating frequency sweep, with phase accumulated across retraces.

    Phase is n * PHI(sweep_time) + PHI(position within this sweep), not merely
    the latter: resetting phase at each retrace would put a step discontinuity
    every sweep_time, which the ringing impairment would then treat as a real
    edge. np.floor (not int truncation) gives the sweep index, because t is
    routinely negative -- the mock free-runs from a negative t0 and ringing
    renders samples before t0.
    """
    sweep = np.floor(t / spec.sweep_time)
    within = t - sweep * spec.sweep_time
    phase = sweep * _chirp_phase(spec, spec.sweep_time) + _chirp_phase(spec, within)
    return spec.amplitude * np.sin(phase + spec.phase)


_GENERATORS: Dict[str, Callable[[SignalSpec, np.ndarray, np.random.Generator], np.ndarray]] = {
    "sine": _sine,
    "square": _square,
    "triangle": _triangle,
    "ramp": _ramp,
    "dc": _dc,
    "noise": _noise,
    "multitone": _multitone,
    "exponential": _exponential,
    "pulse": _pulse,
    "chirp": _chirp,
}

PERIODIC_KINDS = ("sine", "square", "triangle", "ramp", "multitone", "exponential", "pulse")

# Hard cap on the ringing decay kernel's length in samples, independent of
# n_points (I3) or sample_rate. This is a backstop against a user-supplied
# ringing_damping near zero making `5 / damping` samples unboundedly long --
# not the normal control on cost, which is ringing_damping's own sensible
# nonzero default (M8).
_MAX_RINGING_KERNEL_SAMPLES = 200_000


def _validate(spec: SignalSpec, sample_rate: float, n_points: int) -> None:
    if spec.kind not in _GENERATORS:
        raise exceptions.InvalidParameterError(f"Unknown signal kind: {spec.kind!r}. Supported: {', '.join(sorted(_GENERATORS))}")
    if sample_rate <= 0:
        raise exceptions.InvalidParameterError(f"sample_rate must be positive: {sample_rate}")
    if n_points < 1:
        raise exceptions.InvalidParameterError(f"n_points must be at least 1: {n_points}")
    if spec.kind in PERIODIC_KINDS and spec.frequency <= 0:
        raise exceptions.InvalidParameterError(f"frequency must be positive for {spec.kind!r}: {spec.frequency}")
    if spec.kind in ("square", "exponential") and not 0.0 < spec.duty < 1.0:
        raise exceptions.InvalidParameterError(f"duty must be strictly between 0 and 1: {spec.duty}")
    # np.isfinite on every kind-specific scalar below, not just a sign check: nan
    # passes BOTH sides of an ordering comparison, so `tau <= 0` and
    # `pulse_width <= edge_time` silently let it through -- and a nan pulse_width
    # is the worst of them, since it yields a finite but wrong waveform with no
    # tell-tale in the output. tau=inf passes `tau <= 0` too, and produces an
    # all-nan trace plus a RuntimeWarning, though the documented tau -> inf limit
    # is the DC average amplitude*(2*duty - 1).
    if spec.kind == "exponential" and not (np.isfinite(spec.tau) and spec.tau > 0):
        raise exceptions.InvalidParameterError(f"tau must be a positive, finite number for 'exponential': {spec.tau}")
    if spec.kind == "multitone":
        try:
            relatives = list(spec.harmonics)
        except TypeError:
            raise exceptions.InvalidParameterError(f"harmonics must be a sequence of relative amplitudes: {spec.harmonics!r}") from None
        for order, relative in enumerate(relatives, start=2):
            # The guard has to cover the ELEMENT test too, not just list(): on a
            # non-numeric element np.isfinite raises a raw "ufunc 'isfinite' not
            # supported" TypeError, and on a complex one the `>= 0` does --
            # either would escape this module's contract that every bad
            # parameter surfaces as InvalidParameterError.
            try:
                acceptable = bool(np.isfinite(relative)) and relative >= 0
            except TypeError:
                acceptable = False
            if not acceptable:
                raise exceptions.InvalidParameterError(f"harmonics[{order - 2}] (harmonic order {order}) must be a non-negative finite number: {relative!r}")
    if spec.kind == "pulse":
        if not np.isfinite(spec.edge_time) or spec.edge_time < 0:
            raise exceptions.InvalidParameterError(f"edge_time must be a non-negative, finite number: {spec.edge_time}")
        if not np.isfinite(spec.pulse_width):
            raise exceptions.InvalidParameterError(f"pulse_width must be a finite number: {spec.pulse_width}")
        if spec.pulse_width <= spec.edge_time:
            raise exceptions.InvalidParameterError(f"pulse_width (50%-to-50%) must exceed edge_time, or the pulse never reaches its top: {spec.pulse_width} <= {spec.edge_time}")
        if spec.pulse_width + spec.edge_time > 1.0 / spec.frequency:
            raise exceptions.InvalidParameterError(f"the trapezoid must fit in one period: pulse_width + edge_time = {spec.pulse_width + spec.edge_time} > {1.0 / spec.frequency}")
    if spec.kind == "chirp":
        # chirp is deliberately outside PERIODIC_KINDS (no stable period, so the
        # mock must free-run it rather than align it to a trigger), which means
        # the shared positive-frequency check above does not cover it.
        if spec.frequency <= 0:
            raise exceptions.InvalidParameterError(f"frequency must be positive for 'chirp': {spec.frequency}")
        if not (np.isfinite(spec.end_frequency) and spec.end_frequency > 0):
            raise exceptions.InvalidParameterError(f"end_frequency must be a positive, finite number for 'chirp': {spec.end_frequency}")
        if not (np.isfinite(spec.sweep_time) and spec.sweep_time > 0):
            raise exceptions.InvalidParameterError(f"sweep_time must be a positive, finite number for 'chirp': {spec.sweep_time}")
    if spec.noise_rms < 0:
        raise exceptions.InvalidParameterError(f"noise_rms must be non-negative: {spec.noise_rms}")
    if spec.drift_amplitude < 0:
        raise exceptions.InvalidParameterError(f"drift_amplitude must be non-negative: {spec.drift_amplitude}")
    if spec.drift_amplitude > 0 and spec.drift_frequency <= 0:
        # M3: drift_frequency itself was never validated, so drift_frequency=0.0
        # (with drift enabled) silently produced NO drift at all -- sin(0*t) is
        # always 0 -- and a negative value merely inverted phase, both surprising
        # and undocumented. Only checked when drift is actually enabled: a
        # disabled drift_frequency default/leftover value is never used.
        raise exceptions.InvalidParameterError(f"drift_frequency must be positive when drift_amplitude > 0: {spec.drift_frequency}")
    if spec.glitch_rate < 0:
        raise exceptions.InvalidParameterError(f"glitch_rate must be non-negative: {spec.glitch_rate}")
    if spec.glitch_amplitude < 0:
        raise exceptions.InvalidParameterError(f"glitch_amplitude must be non-negative: {spec.glitch_amplitude}")
    if spec.ringing_frequency < 0:
        raise exceptions.InvalidParameterError(f"ringing_frequency must be non-negative: {spec.ringing_frequency}")
    if spec.ringing_damping < 0:
        raise exceptions.InvalidParameterError(f"ringing_damping must be non-negative: {spec.ringing_damping}")
    if not np.isfinite(spec.jitter_rms) or spec.jitter_rms < 0:
        raise exceptions.InvalidParameterError(f"jitter_rms must be a non-negative, finite number: {spec.jitter_rms}")


def _impairment_rng(seed: Optional[int], stream_index: int) -> np.random.Generator:
    """An independent, seed-reproducible generator per impairment.

    Drawing impairments from synthesize()'s shared `rng` would make enabling one
    impairment change another's samples and the base noise, so a test asserting on
    noise would break merely because drift was switched on.
    """
    if seed is None:
        return np.random.default_rng()
    return np.random.default_rng([seed, stream_index])


def _jitter_cycle_rng(seed: Optional[int], boundary_index: int) -> np.random.Generator:
    """An independent, seed-reproducible generator per jittered cycle-BOUNDARY.

    Keyed by BOUNDARY INDEX rather than by _impairment_rng's stream position: a
    given boundary's time-shift must come out identically no matter which
    buffer observes it -- in particular, ringing's extended lookback window
    (t_ext, which starts decay_len samples before t0) must see the SAME delta
    for a boundary that the plain (non-extended) buffer would have drawn for
    it, or the two would disagree about where an edge near that boundary sits.
    "2" is a fixed namespace tag distinguishing this from the module's other
    seeded streams (the bare `rng` in synthesize() is seeded directly off
    spec.seed; _impairment_rng's glitch stream uses index 1), so a jitter draw
    can never collide with another impairment's draw under the same seed.

    Named "_cycle_rng" (not "_boundary_rng") for continuity with existing
    callers/tests: a boundary index IS a cycle index -- boundary n is simply
    the point in time cycle n begins -- this function's contract (one
    reproducible draw per integer index) hasn't changed, only how
    _apply_jitter combines two adjacent draws.
    """
    if seed is None:
        return np.random.default_rng()
    # boundary_index can be negative: ringing's extended lookback window
    # renders samples before t0, and t0 itself can be negative (a free-running
    # mock's trigger-relative time base). SeedSequence entries must be
    # non-negative, so reinterpret the signed 64-bit index as its unsigned bit
    # pattern -- a bijection, so distinct boundaries (negative or not) still
    # get distinct, deterministic seeds.
    boundary_component = int(np.uint64(np.int64(boundary_index)))
    return np.random.default_rng([seed, 2, boundary_component])


def _apply_jitter(spec: SignalSpec, t: np.ndarray) -> np.ndarray:
    """Warp a time array by linearly interpolating a jittered delta between
    cycle-BOUNDARY control points, so every sample's shift varies continuously
    (no hard steps) instead of jumping once per cycle.

    Model: boundary n (the instant cycle n begins) gets its own Gaussian
    time-shift d[n] ~ N(0, sigma). For a sample at continuous cycle position
    `pos = frequency*t + phase/2pi`, let n = floor(pos) and frac = pos - n in
    [0, 1). The sample's delta is the linear blend of the two boundaries that
    straddle it: delta(t) = d[n]*(1-frac) + d[n+1]*frac, and
    t_effective = t - delta(t).

    This replaces an earlier hard-step model (delta = d[cycle_index(t)], a
    per-cycle constant) that was found to make t_effective NON-MONOTONIC --
    going backward in time -- whenever |d[n+1]-d[n]| exceeded one sample
    interval dt, which happens at ordinary jitter values and corrupted edge
    detection (spurious double-edges, 10-30x measurement inflation) on 5 of
    7 PERIODIC_KINDS. The interpolated model is C0-continuous everywhere, so
    t_effective stays monotonic as long as |d[n+1]-d[n]| < T (one period) --
    verified empirically to hold at the jitter magnitudes this feature
    targets, a vastly higher bar than the old model's < dt.

    Calibration is now EDGE-POSITION DEPENDENT, not a single constant. An
    edge sitting exactly at a cycle boundary (frac=0, e.g. sine/square/
    multitone/pulse's ascending v50 crossing at the default phase=0.0) gets
    the full, unblended d[n] shift on one side and d[n+1] on the other, so
    period[n] = T + d[n+1] - d[n] exactly as under the old model:
    std(period) = sigma*sqrt(2) = jitter_rms, unchanged (verified empirically:
    ratio 0.94-1.08 at 1-5% of the period). An edge at some other in-cycle
    fraction f gets a BLENDED shift and consecutive such edges are no longer
    independent; verified empirically at two more points --
    Var(period)/jitter_rms**2 = 0.5*[(1-2f)**2 + f**2 + (1-f)**2] -- "triangle"
    (f=0.25, measured ratio ~0.66-0.68 vs. the formula's 0.6614) and "ramp"
    (whose v50 crossing, despite the RAMP's own hard discontinuity sitting at
    the boundary, is itself continuous and actually sits at f=0.5, cycle
    center: measured ratio ~0.50-0.52 vs. the formula's minimum of 0.5).
    Using sigma = jitter_rms / sqrt(2) here keeps the frac=0 case exactly
    calibrated, which is the common case (every PERIODIC_KINDS default phase
    puts its edge at or within edge_time/2 of a boundary, except "triangle"
    at f=0.25 and "ramp" at f=0.5). See SignalSpec.jitter_rms for the
    caller-facing summary and
    docs/superpowers/specs/2026-08-28-signal-timing-jitter-design.md for the
    full derivation.

    A no-op (returns `t` unchanged, same object) when jitter_rms is 0 or the
    kind has no stable period -- PERIODIC_KINDS excludes "dc", "noise" (no
    cycle structure) and "chirp" (frequency sweeps, so "cycle index" is
    undefined). That fast path is also what keeps a disabled jitter_rms
    byte-identical to this feature never having existed: the generator sees
    the exact same time array it always did.
    """
    if spec.jitter_rms <= 0 or spec.kind not in PERIODIC_KINDS:
        return t
    pos = spec.frequency * t + spec.phase / (2.0 * np.pi)
    n = np.floor(pos).astype(np.int64)
    frac = pos - n
    sigma = spec.jitter_rms / np.sqrt(2.0)
    # One generator per UNIQUE boundary index needed by this buffer -- the
    # boundary before (n) and after (n + 1) each sample -- not one per sample:
    # this buffer's ringing extended-window call included, a typical buffer
    # spans hundreds to low thousands of cycles, not samples.
    boundary_indices, inverse = np.unique(np.concatenate([n, n + 1]), return_inverse=True)
    jitter_seed = spec.jitter_seed if spec.jitter_seed is not None else spec.seed
    boundary_deltas = np.array([_jitter_cycle_rng(jitter_seed, idx).normal(0.0, sigma) for idx in boundary_indices])
    half = n.size
    d_before = boundary_deltas[inverse[:half]]
    d_after = boundary_deltas[inverse[half:]]
    delta = d_before * (1.0 - frac) + d_after * frac
    return t - delta


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
    # `t` stays the NOMINAL time array all the way through this function --
    # drift below is deliberately a function of absolute time, unwarped. Jitter
    # (_apply_jitter) is applied only at the two _GENERATORS[...] call sites
    # below (the plain one and, inside the ringing branch, the extended-window
    # one), so ringing's own edge detection sees the jittered edge position,
    # not the nominal one.
    t = t0 + np.arange(n_points) / sample_rate
    if spec.ringing_frequency > 0:
        # A damped sinusoid triggered at each edge. Real probe/scope front-ends
        # ring after a fast transition; this is what gives overshoot/preshoot
        # measurements something real to measure. Applied to the base signal
        # BEFORE drift and glitches: ringing is part of the signal's own edge
        # response, not a baseline wander or an additive event.
        #
        # I3: this must be a function of ABSOLUTE TIME, like drift, not of the
        # current buffer alone -- np.diff() cannot see an edge across a
        # stream() chunk boundary, so an edge landing right at a boundary used
        # to get no ringing at all, and one near a chunk's end had its ring
        # truncated. Fixed the same way drift is continuous: render
        # `decay_len` extra samples BEFORE t0, detect edges (and let their
        # ringing spill forward) across that whole extended window, then slice
        # the prepended samples back off. The generator is called exactly
        # once (over the extended window) rather than once for the plain
        # buffer and again for the extended one, so a stochastic kind (e.g.
        # "noise") does not draw from `rng` twice.
        decay_len = min(_MAX_RINGING_KERNEL_SAMPLES, max(1, int(sample_rate / max(spec.ringing_damping, 1e-9) * 5)))
        # Built as t0 + (index - decay_len) / sample_rate, NOT (t0 - decay_len /
        # sample_rate) + index / sample_rate -- the two are mathematically equal
        # but round differently in float64. With the latter, this chunk's t0
        # (itself computed elsewhere as start_time + produced / sample_rate) and
        # this expression's own "t0 - decay_len/sample_rate" partial sum
        # accumulate rounding error differently than a neighboring chunk's
        # equivalent sample does, so the same absolute instant can land a few
        # ULP apart depending on which chunk computed it -- enough to flip which
        # side of a razor's-edge comparison (e.g. square wave's `< duty`) a
        # sample falls on, right when frequency and chunk_size divide evenly
        # (verified: this happened at every chunk boundary in the drift-style
        # continuity test below until reordered this way).
        t_ext = t0 + (np.arange(n_points + decay_len) - decay_len) / sample_rate
        samples_ext = _GENERATORS[spec.kind](spec, _apply_jitter(spec, t_ext), rng) + spec.offset
        # ANY nonzero sample-to-sample change is an edge here, not just a
        # discontinuity: on a continuous kind every sample qualifies, so this
        # becomes a derivative-weighted filter rather than a no-op. That is
        # defensible as a band-limited edge response and is documented as such
        # on SignalSpec.ringing_frequency -- it is not a special case to strip.
        edges = np.flatnonzero(np.diff(samples_ext))
        if edges.size:
            # 5 time constants of decay, in samples. `max(spec.ringing_damping, 1e-9)`
            # only guards the division against damping == 0 (undamped ringing) --
            # it must NOT clamp small-but-nonzero damping up to some larger floor,
            # or slow decay would be truncated before it actually decays, showing
            # up as a discontinuity where the kernel window ends. `max(1, ...)`
            # then guards int() truncating to 0 for very heavy damping.
            # `_MAX_RINGING_KERNEL_SAMPLES` is a defensive backstop, not the
            # normal control on cost -- M8 gives ringing_damping a sensible
            # nonzero default so ordinary use never approaches it; it only
            # bounds the (user-opted-into) case of an explicit near-zero
            # damping, which would otherwise make the kernel unboundedly long.
            total = n_points + decay_len
            tail = np.arange(decay_len) / sample_rate
            kernel = np.sin(2 * np.pi * spec.ringing_frequency * tail) * np.exp(-spec.ringing_damping * tail)
            response = np.zeros(total)
            for edge in edges:
                step = samples_ext[edge + 1] - samples_ext[edge]
                end = min(total, edge + 1 + decay_len)
                response[edge + 1 : end] += 0.5 * step * kernel[: end - edge - 1]
            samples = samples_ext[decay_len:] + response[decay_len:]
        else:
            samples = samples_ext[decay_len:]
    else:
        samples = _GENERATORS[spec.kind](spec, _apply_jitter(spec, t), rng) + spec.offset
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
            if spec.seed is None:
                chunk_spec = spec
            else:
                # jitter_seed=spec.seed (the pre-bump value) only when the caller
                # left it None -- so every chunk of this run shares the same
                # jitter entropy source (closing the stream()-chunk-boundary
                # discontinuity, see SignalSpec.jitter_seed) while `seed` itself
                # keeps bumping per chunk, unchanged, so noise/glitches keep
                # their existing non-repeating-across-chunks behavior. A caller
                # who set jitter_seed explicitly keeps their own choice.
                jitter_seed = spec.jitter_seed if spec.jitter_seed is not None else spec.seed
                chunk_spec = replace(spec, seed=spec.seed + index, jitter_seed=jitter_seed)
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
