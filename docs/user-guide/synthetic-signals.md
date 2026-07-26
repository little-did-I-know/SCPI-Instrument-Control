# Synthetic Signals

Every mock oscilloscope channel now produces a real, parameterized waveform
instead of a fixed byte pattern -- and the same signal engine is available
directly, for generating test data with no instrument (or mock) involved at
all. This guide covers `SignalSpec`, `synthesize()`/`make_waveform()`, and
how `MockConnection` uses them to synthesize state-coupled, trigger-aligned
captures.

## Why

- **Develop and test without hardware.** Write and exercise capture,
  analysis, and reporting code against realistic waveforms -- sine, square,
  triangle, ramp, DC, noise -- before an instrument is available.
- **Reproducible test data.** A seeded `SignalSpec` produces the exact same
  samples every run, which makes it useful for regression tests and
  deterministic examples/demos.
- **A mock that behaves like a scope.** `MockConnection` channels synthesize
  from their current state by default, so SCPI commands that change the
  timebase, voltage scale, or trigger settings visibly change the next
  capture -- the mock reacts the way real hardware would, instead of always
  returning the same bytes.

## `SignalSpec`

`scpi_control.signal_synth.SignalSpec` is a frozen dataclass describing one
signal:

| Field | Default | Meaning |
| --- | --- | --- |
| `kind` | `"sine"` | `"sine"`, `"square"`, `"triangle"`, `"ramp"`, `"dc"`, or `"noise"` |
| `frequency` | `1000.0` | Repetition rate in Hz (periodic kinds only) |
| `amplitude` | `1.0` | Peak amplitude in volts (Vpp = `2 * amplitude`); for `"noise"`, the standard deviation; ignored for `"dc"` |
| `offset` | `0.0` | DC offset in volts, added to every kind (`"dc"` outputs exactly this level) |
| `phase` | `0.0` | Phase in radians (periodic kinds only) |
| `duty` | `0.5` | High fraction of a `"square"` period, `0 < duty < 1` (pulse/PWM) |
| `noise_rms` | `0.0` | Std-dev of additive Gaussian noise laid on top of any kind |
| `seed` | `None` | `None` for fresh randomness on every call; an `int` for reproducible output |
| `drift_amplitude` | `0.0` | Volts of slow baseline wander; `0` (the default) turns drift off |
| `drift_frequency` | `0.1` | Hz of that wander; only used when `drift_amplitude > 0` |
| `glitch_rate` | `0.0` | Mean glitches per second; `0` (the default) turns glitches off |
| `glitch_amplitude` | `0.0` | Volts, peak height of a glitch |
| `ringing_frequency` | `0.0` | Hz of post-edge oscillation; `0` (the default) turns ringing off |
| `ringing_damping` | `0.0` | Decay rate per second of that oscillation |

The last six fields are impairments: default-off knobs that make a signal
imperfect the way a real one is, so measurement and analysis code has
something realistic to face instead of a mathematically clean waveform. All
six are appended at the end of the dataclass and every one defaults to a
value that leaves the signal unaffected, so existing code that constructs a
`SignalSpec` positionally or without these arguments is unaffected.

- **`drift_amplitude`/`drift_frequency`** add slow baseline wander -- a
  sinusoid at `drift_frequency` Hz, `drift_amplitude` volts of amplitude,
  derived from absolute time so it (like ringing, below) stays continuous
  across `stream()` chunks instead of jumping at chunk boundaries.
- **`glitch_rate`/`glitch_amplitude`** add sparse, isolated spikes -- a
  Poisson process at `glitch_rate` events per second, each an instantaneous
  `+/-glitch_amplitude` volt spike on one sample. Glitches draw from their own
  generator (seeded independently from the base signal/noise), so enabling
  them never perturbs `noise_rms`'s samples.
- **`ringing_frequency`/`ringing_damping`** add a damped sinusoid after every
  edge of a periodic signal -- what a real probe/scope front-end does after a
  fast transition, and what gives an overshoot/preshoot measurement something
  genuine to measure. It's an edge impairment, so it is only meaningful on
  signals that actually have edges (`"square"`, or a pulse-like `"ramp"`) --
  applying it to `"sine"` or `"dc"` has no effect, since those kinds have no
  discontinuities for it to trigger on.

```python
from scpi_control.signal_synth import SignalSpec, synthesize

# A 1kHz square wave with all three impairments: slow thermal-style drift on
# the baseline, occasional glitches, and probe-style ringing after every edge
# -- an intentionally imperfect signal for exercising measurement code against
# something closer to what a real instrument would actually capture.
messy = SignalSpec(
    kind="square",
    frequency=1_000.0,
    amplitude=1.0,
    noise_rms=0.02,
    drift_amplitude=0.05,
    drift_frequency=0.2,
    glitch_rate=2.0,
    glitch_amplitude=0.3,
    ringing_frequency=20_000.0,
    ringing_damping=5_000.0,
    seed=42,
)
volts = synthesize(messy, sample_rate=1_000_000.0, n_points=10_000)
```

`"square"`'s `duty` is the fraction of each period spent high, so a
`SignalSpec(kind="square", duty=0.2)` is a 20%-duty pulse/PWM waveform, not
just a symmetric square wave. `"dc"` ignores `amplitude` entirely and always
outputs `offset`. `"noise"` uses `amplitude` as the Gaussian standard
deviation rather than a peak value. An invalid `kind` or an out-of-range
parameter (non-positive `frequency` on a periodic kind, `duty` outside
`(0, 1)`, negative `noise_rms`, a negative `drift_amplitude`/`glitch_rate`/
`glitch_amplitude`/`ringing_frequency`/`ringing_damping`, or a non-positive
`drift_frequency` while `drift_amplitude > 0`) raises `InvalidParameterError`
-- no partial or silently-clamped signal is ever returned.

## Generating Signals Directly

```python
from scpi_control.signal_synth import SignalSpec, synthesize, make_waveform

spec = SignalSpec(kind="sine", frequency=1_000.0, amplitude=0.8, noise_rms=0.02, seed=42)

# Raw voltage samples, as a numpy array
volts = synthesize(spec, sample_rate=100_000.0, n_points=1_000)

# A full WaveformData, ready for analysis, saving, or the report generator
waveform = make_waveform(spec, sample_rate=100_000.0, n_points=1_000, channel=1)
waveform.voltage, waveform.time, waveform.sample_rate
```

`synthesize()` returns a `float64` array of `n_points` voltage samples;
`t0` shifts the start time, which matters for periodic kinds (it's how the
mock aligns a capture to a trigger crossing -- see below). `make_waveform()`
wraps the same samples in a `WaveformData` with a matching `time` axis, so it
composes directly with the rest of the library:

```python
waveform = make_waveform(SignalSpec(kind="square", frequency=1_000.0, amplitude=1.0), sample_rate=1_000_000.0, n_points=10_000)
# waveform.voltage / waveform.time feed analysis, plotting, or a report exactly
# like a captured waveform would -- see docs/report-generator/ for the reporting
# side of that chain.
```

Two calls with `seed=None` (the default) produce different noise and, for
`"noise"` itself, different signal on every call. Pass an `int` seed to get
byte-identical output across runs.

## Streaming

`synthesize()` and `make_waveform()` generate one fixed-length block. For
continuous or live simulation -- feeding a loop, a plot, or a network socket
indefinitely -- `stream()` does the same phase-continuous generation without
hand-rolling the `t0` bookkeeping yourself:

```python
def stream(
    spec: SignalSpec,
    sample_rate: float,
    chunk_size: int,
    *,
    start_time: float = 0.0,
    duration: Optional[float] = None,
    realtime: bool = False,
) -> Iterator[np.ndarray]
```

It returns an iterator of `float64` voltage chunks, each `chunk_size`
samples long, where every chunk picks up exactly where the previous one left
off -- no phase discontinuity at chunk boundaries. Validation errors (the
same ones `SignalSpec` and `synthesize()` raise) happen at call time, before
the first chunk is produced.

A minimal continuous loop:

```python
from scpi_control.signal_synth import SignalSpec, stream

spec = SignalSpec(kind="sine", frequency=1_000.0, amplitude=1.0, noise_rms=0.02)
for chunk in stream(spec, sample_rate=1_000_000.0, chunk_size=10_000):
    process(chunk)  # phase-continuous float64 volts; break when done
```

By default `stream()` yields chunks as fast as the consumer pulls them. With
`duration=None` (the default) it streams forever -- `break` out of the loop
to stop. Passing a positive `duration` bounds the stream to
`round(duration * sample_rate)` total samples, truncating the final chunk to
fit; `start_time` shifts the time of the very first sample, the same way
`t0` does for `synthesize()`.

Set `realtime=True` to pace chunks at wall-clock rate: chunk `k` is withheld
until `k * chunk_size / sample_rate` seconds after the first chunk was
produced. Scheduling is absolute (measured from the start, not
chunk-to-chunk), so timing error never accumulates across a long stream, and
a consumer slower than real time simply never waits -- it just gets chunks
later than it asked for them.

Seeding follows the same rule the mock uses per acquisition: `seed=None`
re-rolls fresh noise on every chunk, while a seeded spec advances the seed
per chunk (`seed + chunk_index`) so the whole stream is reproducible
run-to-run without repeating the same noise block over and over.

## Mock Oscilloscope Synthesis

`MockConnection` synthesizes each channel's waveform from its current state
at every acquisition, instead of returning fixed bytes -- unless that channel
has an explicit payload (see [Precedence](#precedence-vs-waveform_payloads)
below).

### Per-channel defaults

If a channel has no `signals=` entry, it falls back to a built-in default:

| Channel | Kind | Frequency | Amplitude | Noise (RMS) |
| --- | --- | --- | --- | --- |
| 1 | square | 1 kHz | 2 Vpp (`amplitude=1.0`) | 0.01 |
| 2 | sine | 2 kHz | 1 Vpp (`amplitude=0.5`) | 0.01 |
| 3 | sine | 5 kHz | 0.5 Vpp (`amplitude=0.25`) | 0.01 |
| 4 | sine | 10 kHz | 0.25 Vpp (`amplitude=0.125`) | 0.01 |

Any channel number outside 1-4 that still needs synthesis falls back to a
1 kHz, 1 V-amplitude sine with `noise_rms=0.01`.

### Choosing signals with `signals=`

Pass a `signals={channel: SignalSpec(...)}` dict to `MockConnection` to
override the defaults for specific channels; channels you don't mention keep
their built-in default:

```python
from scpi_control.connection import MockConnection
from scpi_control.oscilloscope import Oscilloscope
from scpi_control.signal_synth import SignalSpec

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
waveform = scope.get_waveform(1)
scope.disconnect()
```

### State coupling

The next capture reflects the mock's *current* SCPI state, so writes made
before an acquisition change what comes back:

- **Capture length.** The window is 14 divisions times the timebase; the
  point count is `round(sample_rate * window)`, clamped to `[2, 14000]`.
  `scope.write("TDIV 1e-4")` shrinks the window (and therefore the point
  count) on the next capture.
- **Clipping.** Samples are converted to int8 codes at 25 codes/division and
  clipped at +/-127 -- an 8-bit ADC over-ranging exactly like real hardware.
  `scope.write("C1:VDIV 0.1")` narrows the voltage range a division
  represents, so a signal whose amplitude no longer fits clips at the new
  ceiling (`127 * vdiv / 25` volts).
- **Trigger alignment.** For periodic kinds, the mock finds where the ideal
  signal crosses the configured trigger level in the trigger's slope
  direction and places that crossing at the center of the capture window --
  the same edge a real scope would trigger on. A **triggered, noise-free**
  capture is therefore bit-identical across repeated acquisitions at
  unchanged settings. If the configured trigger level/slope combination is
  unattainable for the signal (e.g. a level outside its range), the mock
  free-runs instead: each acquisition's window drifts forward by a fixed
  fraction of the window, so consecutive captures visibly shift rather than
  repeating. Each channel aligns to its own trigger level and signal; the
  mock does not model `trigger_source` routing (triggering one channel off
  another channel's crossing) between channels.

### Precedence vs. `waveform_payloads`

`waveform_payloads={channel: bytes}` bypasses synthesis entirely for that
channel -- if a channel has an explicit payload, those bytes are always
returned regardless of `signals=` or SCPI state, which keeps existing
byte-identical tests unaffected by this feature.

### Seeding rules

- `seed=None` (the default): every acquisition re-rolls fresh noise (and,
  for `"noise"`, a fresh signal).
- `seed=<int>`: the *first* acquisition for that channel uses exactly that
  seed; each subsequent acquisition on the same channel advances the seed by
  one (`seed + 1`, `seed + 2`, ...), so repeated captures are each
  individually reproducible but not identical to one another -- matching how
  a real, noisy instrument produces a different (but statistically
  consistent) trace on every trigger.

### Web gateway default

Mock sessions created through the web gateway now default to
`sample_rate=1_000_000.0`, so a default mock session's captures are 14,000
points long (14 divisions x 1 ms/div timebase) instead of the fixed 256-byte
explicit ramp payloads earlier sessions served.

## Extensibility

Signal kinds live in a small dispatch table (`kind -> generator function`)
inside `scpi_control/signal_synth.py`. The mock's state-coupling and
volts-to-codes conversion are kind-agnostic, so adding a new kind is: one new
generator function, a table entry, and matching docs/tests -- no changes to
`MockConnection` or the waveform code path.

## See Also

- [Data Provenance](data-provenance.md) for what gets attached to a saved
  waveform (including one synthesized by the mock) and how to read it back
- `examples/synthetic_signals.py` for a runnable, hardware-free walkthrough
  of `make_waveform()`, a mock session reacting to SCPI writes, and the
  save/reload round trip
