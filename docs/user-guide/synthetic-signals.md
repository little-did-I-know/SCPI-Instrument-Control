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
  triangle, ramp, DC, noise, chirp, exponential, pulse, multitone -- before
  an instrument is available.
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
| `kind` | `"sine"` | `"sine"`, `"square"`, `"triangle"`, `"ramp"`, `"dc"`, `"noise"`, `"chirp"`, `"exponential"`, `"pulse"`, or `"multitone"` |
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
| `ringing_damping` | `5000.0` | Decay rate per second of that oscillation; only used when `ringing_frequency > 0` |

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
  genuine to measure. It's an edge impairment, so it is *physically*
  meaningful on signals that actually have fast edges (`"square"` and
  `"pulse"`, or a pulse-like `"ramp"`). On the continuous kinds (`"sine"`,
  `"chirp"`, `"exponential"`, `"multitone"`) it is **not** a no-op, though:
  edges are found as any nonzero sample-to-sample change rather than as a
  discontinuity, so every sample of a continuous signal qualifies and the
  impairment becomes a derivative-weighted filter. Its magnitude scales with
  the signal's slew rate -- measurable, but usually far smaller than on a real
  edge (at `sample_rate=1e6`, `amplitude=1.0`,
  `ringing_frequency=50_000`: about 0.10 V on `"chirp"`, 0.056 V on
  `"exponential"`, 0.013 V on `"multitone"` and 0.010 V on `"sine"`, against
  0.90 V on `"square"`). `"dc"`, whose sample-to-sample differences are all
  zero, is the only kind ringing genuinely leaves untouched.

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

### Kind-specific parameters

Seven more fields exist purely to parameterize the four newer kinds; each is
ignored by every other kind, and every default is chosen so
`SignalSpec(kind=X)` alone works at the default 1 kHz `frequency`:

| Field | Read by | Default | Meaning |
| --- | --- | --- | --- |
| `end_frequency` | `"chirp"` | `10_000.0` | Sweep stop frequency in Hz |
| `sweep_time` | `"chirp"` | `0.01` | Seconds per sweep, after which it retraces |
| `sweep_log` | `"chirp"` | `False` | Sweep logarithmically (equal time per octave) instead of linearly |
| `tau` | `"exponential"` | `1e-4` | RC time constant in seconds |
| `pulse_width` | `"pulse"` | `2e-4` | 50%-to-50% width (FWHM) in seconds |
| `edge_time` | `"pulse"` | `1e-5` | 0-to-100% transition time in seconds; `0` gives an ideal instantaneous edge |
| `harmonics` | `"multitone"` | `(0.1, 0.05)` | Relative amplitudes of the 2nd, 3rd, ... harmonic |

Three things are easy to get wrong here:

- **`pulse_width` is the 50%-to-50% width (FWHM)**, not the flat-top
  duration -- it matches the instrument convention
  (`SOUR{ch}:FUNC:PULS:WIDT`) and the threshold the repo's timing analyzer
  measures at. The flat top itself runs for `pulse_width - edge_time`.
  `"pulse"` also **ignores `duty`** entirely; independence from the period is
  the whole reason it exists alongside `"square"`, whose only shape control
  *is* `duty`.
- **For `"multitone"`, `amplitude` is the fundamental's amplitude, not the
  peak of the sum.** It is deliberately not normalized against the harmonics,
  because normalizing would make THD depend on which harmonics are present;
  as generated, THD is exactly `sqrt(sum(h**2))` for `harmonics = (h2, h3,
  ...)`.
- **`"chirp"` retraces every `sweep_time`**, with phase carried across the
  retrace rather than reset, so there is no discontinuity at a sweep
  boundary. Because it has no stable period, `"chirp"` is deliberately not in
  `PERIODIC_KINDS`: it is the one kind the mock free-runs rather than
  trigger-aligns (see [Trigger alignment](#state-coupling) below).

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
  another channel's crossing) between channels. `"chirp"` is not in
  `PERIODIC_KINDS` (it has no stable period), so it always free-runs -- never
  trigger-aligned, even when the configured trigger level/slope is otherwise
  attainable.

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

## AWG to Scope Loopback

Every example so far has one mock instrument synthesizing from its own state.
`AwgLoopback` (`scpi_control.connection.mock.loopback`) patches a second mock
instrument's state into that synthesis, so a mock scope can capture whatever a
mock AWG is currently outputting -- two separate `MockConnection` objects, one
virtual cable between them:

```python
from scpi_control.connection import MockConnection
from scpi_control.connection.mock.loopback import AwgLoopback
from scpi_control.dut import RCLowPass
from scpi_control.oscilloscope import Oscilloscope

awg = MockConnection("mock", awg_mode=True)
scope_conn = MockConnection("mock", signals={1: AwgLoopback(awg, awg_channel=1, dut=RCLowPass(cutoff_hz=2_000))})
scope = Oscilloscope("mock", connection=scope_conn)
```

### `signals=` as a callable

`signals={channel: ...}` now accepts a callable that returns a `SignalSpec`,
not just a static `SignalSpec` instance -- and unlike a static spec, which is
read once, a callable is invoked at **every acquisition**. That is what makes
the loopback live: `AwgLoopback` is such a callable, and each call re-reads
the AWG connection's current channel state, so a `C1:BSWV` write on the AWG
changes the very next scope capture. This is a general extension point, not
specific to AWGs -- anything with a `() -> SignalSpec` signature works.

### Function mapping

`AwgLoopback` translates the AWG channel's live state into a `SignalSpec` on
every call:

| AWG `WVTP` | `SignalSpec.kind` |
| --- | --- |
| `SINE` | `sine` |
| `SQUARE` | `square` |
| `NOISE` | `noise` |
| `DC` | `dc` |
| `PULSE` | `pulse` |
| `RAMP` | `triangle` if symmetry is within 1 percentage point of 50 (i.e. 49 to 51), otherwise `ramp` |
| `ARB` | `sine`, with a logged warning (the mock stores no arbitrary sample data) |

Two unit conversions happen on the way in, because the AWG and `SignalSpec`
don't speak the same units for the same quantity:

- **Amplitude.** An AWG's `AMP` is peak-to-peak; `SignalSpec.amplitude` is
  peak. `AwgLoopback` halves it, so an AWG set to 2.0 Vpp arrives as a 2.0 V
  peak-to-peak capture, not 4.0. **`NOISE` is the exception**, because
  `SignalSpec.amplitude` is a standard deviation for that kind rather than a
  peak: Gaussian noise has no true peak, so `AwgLoopback` maps the AWG's `AMP`
  on the usual convention that a quoted peak-to-peak is the +/-3 sigma span
  (99.7% of samples), i.e. `sigma = Vpp / 6`. An AWG set to 2.0 Vpp of noise
  therefore arrives as a sigma = 0.333 V trace, whose measured peak-to-peak is
  approximately -- but, being random, never exactly -- 2.0 V.
- **Phase.** An AWG's `PHSE` is in degrees; `SignalSpec.phase` is in radians.
  `AwgLoopback` converts.

An output with `enabled=False` reads flat -- like a disconnected input, not a
zero-amplitude waveform at some frequency.

### Duty is clamped, not validated

`SignalSpec` requires strictly `0 < duty < 1` and raises `InvalidParameterError`
outside that range, but a real AWG accepts `DUTY,0` and `DUTY,100` without
complaint. `AwgLoopback` clamps the converted duty into `SignalSpec`'s legal
range instead of propagating the AWG's value verbatim, because a mock
instrument should not raise where a real one would simply output something
(a very narrow pulse, or one at the opposite rail) and keep going.

### The DUT: `RCLowPass`

`AwgLoopback` accepts an optional `dut=` -- a device model sitting between
the AWG and the scope, exactly where a real device under test would
physically sit. That's why the DUT lives on the loopback rather than on the
scope's `MockConnection`: it belongs to the cable run connecting the two
instruments, not to either instrument itself.

`scpi_control.dut.RCLowPass(cutoff_hz=...)` is a first-order RC low-pass. It
is stateful -- unlike every generator in `signal_synth`, which is closed-form
specifically so consecutive captures and streamed chunks join seamlessly --
so filtering a bare capture would start from `y = 0` and put a settling
transient at the head of every acquisition. To avoid that, the filter is
applied to a lead-in rendered *before* the capture window and then discarded,
the same fix `signal_synth`'s ringing impairment uses for the same reason: a
capture is in steady state from its very first sample, with no transient at
the head.

**Known simplification:** trigger alignment (see [State
coupling](#state-coupling) above) searches for the trigger-level crossing on
the *unfiltered* signal, so where a capture triggers does not depend on the
DUT's filter state -- only the sample values within the window do.

**Quantization caveat:** a legacy-dialect mock capture is quantized to int8
codes at 25 codes/division (see [State coupling](#state-coupling) above), so a
voltage difference smaller than one code -- 0.04 V at the default 1 V/div --
cannot be resolved in a capture, no matter how gently the DUT is filtering. The
modern dialect's `:WAVeform:WIDTh WORD` path is 256x finer (6400 codes/division,
0.15625 mV/LSB), and since both paths share the same synthesis it is the WORD
grid, not int8, that the filter's lead-in depth is sized against
(`dut._WARMUP_TIME_CONSTANTS`, 12 time constants: `e^-12` leaves under 0.05 WORD
LSB un-settled at the head of the window). A
comparison that leans on fine amplitude detail (e.g. a raw sample-to-sample
step height at a gentle cutoff) will end up measuring the code grid rather
than the filter. Either widen the effect until it clears one code, or measure
a time-domain property such as rise time instead, which isn't limited by the
code grid -- see `examples/awg_scope_loopback.py`, which does exactly that.

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
- `examples/awg_scope_loopback.py` for a runnable walkthrough of the AWG to
  scope loopback, including the `RCLowPass` DUT
