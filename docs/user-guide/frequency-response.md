# Frequency Response

`scpi_control.frequency_response` measures a Bode plot: it steps a function
generator across a list of frequencies, captures two oscilloscope channels at
each step, and estimates the gain and phase of whatever sits between them.
This guide covers the two-channel wiring, `sweep()`, what each `ResponsePoint`
diagnostic means, autoranging, the exclusion reasons, and the CSV format --
closing with a clearly-scoped accounting of what has and has not been
validated.

## Wiring

A sweep needs two scope channels and one AWG channel:

- **Reference channel** -- tapped straight off the generator's output, before
  the device under test. This is "what did we actually send."
- **Response channel** -- on the device's output. This is "what came back."

`sweep()` drives the AWG with a sine at `amplitude_vpp`, sweeps its frequency,
and at each step captures both channels and divides response by reference (as
complex amplitudes, so both magnitude and phase come out of one division).
Nothing about the DUT itself is assumed -- the transfer function is measured,
not modeled.

## A Minimal Sweep

```python
from scpi_control.frequency_response import sweep

result = sweep(
    scope,
    awg,
    reference_channel=1,
    response_channel=2,
    start_hz=100.0,
    stop_hz=10_000.0,
    points_per_decade=5,
    amplitude_vpp=2.0,
)

for point in result.usable():
    print(point.frequency_hz, point.gain_db, point.phase_deg)

print(result.cutoff_hz())  # -3 dB corner, interpolated between points
```

`start_hz`/`stop_hz`/`points_per_decade` log-space the sweep for you
(`log_spaced_frequencies()`, also exported); pass an explicit `frequencies=`
list instead if you want particular points, e.g. densely spaced around a
resonance. The AWG channel's prior state (function, frequency, amplitude,
enabled) is restored when `sweep()` returns or raises -- the scope's state is
deliberately left where the sweep ended, so the final ranging is there to
inspect.

Every argument is validated before any wire traffic: a bad channel number or
a non-positive frequency raises `InvalidParameterError` immediately. A
failure mid-sweep raises `FrequencySweepError`, whose `.partial` attribute
holds every point measured before the failure -- on real hardware a sweep can
be a long time on the bench, and a failure at point 30 of 40 should not throw
away the first 30.

See `examples/frequency_response_sweep.py` for a complete, runnable version
of the above, including the analytic comparison used in this page's
[Accuracy and limits](#accuracy-and-limits) section.

## Reading a `ResponsePoint`

Each point carries its diagnostics alongside its answer, so you don't have to
take a gain or phase number on faith:

| Field | Meaning |
| --- | --- |
| `frequency_hz` | The frequency this point asked the generator for. |
| `gain_db` | Response/reference magnitude ratio, in dB. `None` if the point was excluded. |
| `phase_deg` | Response phase relative to the reference, in degrees. `None` if excluded. |
| `reference_vpp` / `response_vpp` | Raw peak-to-peak volts of each capture -- useful for spotting clipping or a flat trace at a glance. |
| `cycles_in_window` | How many drive-frequency cycles the capture's time axis actually spans, measured from the returned samples (not assumed from the requested timebase). More cycles means less spectral leakage in the gain/phase estimate. |
| `samples_per_cycle` | Samples per drive-frequency cycle, likewise measured. Below 20 (`MIN_SAMPLES_PER_CYCLE`), the point is still kept, but the library logs a warning that its phase is coarse -- worth checking `samples_per_cycle` yourself near the top of a sweep. |
| `volts_per_div` | The response channel's vertical scale for the accepted capture -- what autoranging landed on. |
| `excluded_reason` | `None` when `gain_db` is present; otherwise a string explaining why the point has no answer. The two are never both set and never both unset -- `ResponsePoint` enforces the pairing at construction. |

A `ResponsePoint` is never a guess wearing an answer's clothes: if the
library could not trust the numbers, `gain_db`/`phase_deg` are `None` and
`excluded_reason` says why, rather than a value that happens to be wrong.

## Autoranging

Real vertical resolution is finite -- 8-bit ADC codes on a legacy capture, a
wider but still finite grid on a modern one -- so a response that's too small
for the current scale is unreadable, and one that's too large is clipped.
`sweep(..., autorange=True)` (the default) handles this per point:

1. Capture both channels at the current scale.
2. If the response's measured peak-to-peak doesn't already fill about 6 of
   the 8 vertical divisions, compute a better vertical scale and recapture.
3. **Only at the very first point**, do the same check for the reference
   channel. The reference is the drive amplitude, which is constant by
   construction, so re-ranging it every point would spend a capture to reach
   the same answer every time.

Chosen scales are rounded onto the 1-2-5 sequence (`0.1, 0.2, 0.5, 1.0, 2.0,
...` V/div) -- the sequence real oscilloscope firmware is believed to coerce
vertical (and horizontal) settings onto, though that belief itself is
unverified against real firmware (see [Accuracy and
limits](#accuracy-and-limits)).

That makes the **capture cost of a point at most two acquisitions -- both
channels together each time -- and at most three at the first point**: the
initial capture, a response rescale if the response didn't already fill the
screen, and, only at point zero, a reference rescale too. It is never three
after the first point, because the reference is never re-ranged again.

**Why it matters:** a fixed vertical scale is wrong at both ends of a wide
sweep, and the two failure modes are different in their consequences. On the
RC low-pass this project measures against, holding the scale fixed cost
0.885 dB of error at 10 kHz -- a small-looking response squeezed into too few
ADC codes, quietly wrong rather than absent. Earlier in this project's
development, the same fixed-scale setup at 100 kHz produced a reported gain
of 0 dB with nothing to flag it -- a plausible-looking number for a point
that had, in fact, measured nothing. That gap is exactly why `ResponsePoint`
carries `volts_per_div` and why an unmeasurable point returns
`excluded_reason` instead of a number today: running that same 100 kHz,
fixed-1V/div, autorange-disabled case now correctly returns
`excluded_reason="response below vertical resolution"` rather than a
number, because the response capture's peak-to-peak comes back at `0.0` V
(quantized flat) instead of a plausible-looking level. A reader who can see
the scale a point was measured at, or see that it was refused outright, has
a chance to catch what a bare number never shows.

## Exclusion Reasons

When a point's diagnostics say it can't be trusted, `excluded_reason` is one
of the following. `gain_db`/`phase_deg` are `None` in every case.

| `excluded_reason` | What happened | What to do |
| --- | --- | --- |
| `capture failed for channel {N}` / `capture failed for channels {a, b}` | The scope did not return usable data for that channel on that acquisition (link error, timeout, etc.). | Check the connection/log for the underlying error. A single isolated occurrence may be transient; the sweep continues past it. Persistent failures on one channel usually mean it isn't actually enabled or connected. |
| `reference below vertical resolution — source connected?` | The reference channel's capture is at or below the quantization floor. | Check that the generator is actually connected to the reference channel and that `amplitude_vpp` matches what you expect the generator to output. Because the reference is only autoranged once, at the very first point, a wrong amplitude assumption here can affect the whole sweep. |
| `response reaches beyond ±4 divisions (clipped or off screen)` | The response left the visible vertical range (clipped or drawn past the graticule) on the scale it was captured at, with no autorange left to try (either it's disabled, or it already tried once and the result still didn't fit). | Check whether the DUT has more gain than expected, or lower `amplitude_vpp`. If autoranging is enabled, remember it attempts only one rescale per point, so a DUT with a very large, frequency-dependent gain swing can still outrun it at some points. |
| `response below vertical resolution` | The response is too small to resolve on the scale it was captured at (again, with no further autorange available). | Expected deep in a filter's stopband, far past the corner -- there may simply be very little signal left to measure. If it happens close to or before where you expect the passband, check wiring and DUT assumptions; a single autorange attempt may not be enough for a very sharp roll-off, and denser `points_per_decade` near the corner can help. |
| `reference carries no energy at the drive frequency` | The reference passed the floor/off-screen checks, but the single-frequency estimate at the drive tone came back exactly zero. | Rare; usually means the generator isn't actually outputting the requested frequency. Verify the AWG connection and that its output is enabled. |
| `response carries no energy at the drive frequency` | Same as above, for the response channel. | Same as above. |

## The CSV Format

`result.to_csv("frequency_response.csv")` writes a `#`-commented metadata
header (instrument identity, firmware, library version, acquisition time,
channel/settings summary, and how many of the requested points were
measured), followed by plain CSV: one header row naming the same fields as
`ResponsePoint`, then one row per point. An excluded point's numeric fields
are **empty**, not a sentinel like `-999` or `nan` written as text -- an
empty field is unambiguous, while a sentinel can be silently misread as a
real number.

That choice has a consequence worth knowing about before you reach for
numpy:

- **`pandas.read_csv("frequency_response.csv", comment="#")` reads the file
  correctly, unaided.** Measured, not assumed.
- **`numpy.genfromtxt(..., names=True, comments="#")` does NOT**, even
  though it looks like it should. `names=True` always takes the *first
  line* of the input as the header, whether or not that line starts with
  `#` -- `comments="#"` only affects how later lines are parsed, not which
  line is treated as the header. Handed the raw file, `genfromtxt` reads the
  first metadata line as if it were the column names. Also measured.

  Drop the `#` lines yourself before they reach `genfromtxt` -- either a
  filtering generator:

  ```python
  import numpy as np

  with open("frequency_response.csv") as handle:
      rows = (line for line in handle if not line.startswith("#"))
      data = np.genfromtxt(rows, delimiter=",", names=True, dtype=None, encoding="utf-8")
  ```

  or `skip_header=` with the exact number of metadata lines the header
  currently writes (fragile if that count ever changes -- the filtering
  generator above doesn't share that fragility).

An empty numeric field read by either library comes back as `NaN`, not `0`
or some other plausible-looking value -- an excluded point stays visibly
missing all the way through, rather than being mistaken for a real
measurement of zero gain.

## Accuracy and limits

- **Everything measured here is against a mock instrument and an analytic
  model, not real hardware.** The worst-case error against a closed-form
  first-order RC low-pass (`RCLowPass`, `cutoff_hz=1000`) over a 21-point,
  100 Hz-10 kHz sweep on a 1 MSa/s mock was **0.020 dB and 1.798 degrees**.
  **No real function generator was involved in validating any of this** --
  there isn't one on the development bench, so nothing here has been checked
  against real firmware.
- The phase worst case sits at the *top* of the swept range, where the
  mock's fixed 1 MSa/s sample rate leaves only about 100 samples per cycle
  at 10 kHz. A real scope raises its sample rate as the timebase shrinks, so
  a real instrument would very likely do *better* there than the mock does
  -- the mock's own geometry is the pessimistic case, not the measured
  numbers' ceiling.
- More generally, **the mock's fixed horizontal geometry shapes every
  accuracy figure in this section**: 14 divisions, capped at 14,000 points a
  capture, so at 1 MSa/s the capture window never exceeds 14 ms -- only about
  1.4 cycles at 100 Hz, the low end of the sweep above. A real scope's
  sample rate follows its timebase instead of staying fixed, which is why
  the mock is pessimistic (the safe direction) rather than optimistic at
  both ends of the range, but it also means these figures describe *this*
  mock's geometry, not a hardware guarantee.
- **The 1-2-5 vertical and horizontal scale coercion (`round_125_up`,
  behind both `choose_timebase()` and autoranging) is unverified against
  real firmware.** The mock stores whatever scale value it's handed, so
  agreement between the mock and this rounding logic proves the two are
  internally consistent with each other, not that real instrument firmware
  coerces to the same values this library assumes.
- **`cutoff_hz()` cannot be more precise than the point spacing.** It finds
  where the response first crosses `level_db` below the sweep's peak by
  linearly interpolating in log-frequency between the two bracketing
  measured points -- a real, sharper corner between those two points is
  invisible to it. Denser `points_per_decade` narrows the gap; it cannot
  close it to zero.
- **A capture costs at most two acquisitions per point, three at the very
  first point** -- see [Autoranging](#autoranging) above. This replaces an
  earlier, less precise claim of "at most two," which did not account for
  the response and reference rescales both being able to fire at point
  zero.

## See Also

- [Synthetic Signals](synthetic-signals.md) for `AwgLoopback` and `RCLowPass`,
  the mock machinery this feature is built and measured on
- [Data Provenance](data-provenance.md) for what the CSV metadata header's
  instrument/firmware/library fields actually mean and where they come from
- `examples/frequency_response_sweep.py` for a runnable, hardware-free sweep
  against an `RCLowPass` DUT, including the analytic comparison
