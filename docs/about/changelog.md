# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### ⚠️ Breaking Changes

- A token name is now an identity rather than a unique credential. `scpi-web token add <name>`
  no longer fails when that name already exists — it mints an additional token, so one person can
  hold several devices, and `scpi-web token revoke <name>` cuts off every one of them at once.
  Anything that relied on the duplicate-name error to detect an existing name should call
  `TokenStore.names()` instead.
- `DuplicateTokenName` has been removed from `scpi_control.server.auth`. It can no longer be
  raised, so any `except DuplicateTokenName` clause is now an `ImportError` waiting to happen.
- `TokenStore.names()` now returns distinct names, sorted. It previously returned one entry per
  token, which is one entry per device under the new model.
- A fresh gateway no longer mints an identity called `default`, and no longer prints a
  `?token=…` bootstrap URL on first start. Instead it opens a host-only admin panel and asks
  what to call you, so the first identity is a real person rather than an anonymous credential
  that ends up owning every session it creates. Existing installations are unaffected — this
  changes only what happens when the token store is empty.
- Revoking an identity now also closes that identity's live streams and releases the sessions
  they owned. A revoked colleague mid-capture loses their view, and their session becomes
  immediately claimable. The revoke route's response code has changed from 204 to 200 with a
  body carrying `{"devices", "streams", "sessions"}` counts — a wire-visible change for anyone
  scripting against it.

### Added

- Handing out gateway access no longer means sending someone a permanent secret. `scpi-web invite
  <name>` prints a link and a six-digit code for the same ten-minute invitation: send the link, or
  read the code down the phone. Either one is exchanged in the browser for a real token, so a
  scientist never sees an `scpi_…` string and a leaked chat message stops working in minutes. The
  same command is how you get someone back in after they clear their browser or switch laptops.
  The sign-in screen now asks for a join code first, with the raw-token field kept for scripts and
  CI.
- `scpi-web token list` now shows how many devices each identity holds and when it was last used.
- The SCPI terminal now works for any connected instrument, not just oscilloscopes. It moved out
  of the oscilloscope's control rail (eight tabs down to seven) into a drawer across the bottom of
  the window, opened from a Terminal button in the header and closed with Escape, so a power
  supply session can be driven by raw SCPI for anything its panel doesn't expose.
  `POST /api/sessions/{id}/command` is the new kind-agnostic route behind it; the older
  `/scope/command` is unchanged and still refuses a non-scope session, and both now delegate to
  one shared implementation of what a command does.
- A power supply session now has a readout strip like an oscilloscope's: one card per output
  showing measured voltage, current and power, and whether that rail is live. Unreadable values
  still show as `--.--`, and an output whose on/off state the supply will not report still shows
  as unknown rather than a confident off.
- Internally, which view a session shows is now decided by a per-kind registry instead of a chain
  of `session.kind` checks in the app shell. No visible change on its own, but it's what makes the
  next instrument kind a single registry entry instead of another branch threaded through the
  shell.
- The gateway can now host a function generator (SDG series) alongside oscilloscopes and power
  supplies. Connect one discovered on the network from the home screen, set each channel's
  waveform, frequency, amplitude, offset and phase, switch outputs on and off, and kill every
  output with one button. Duty cycle appears for a pulse and symmetry for a ramp, only where they
  apply. The home screen's "Connect manually" panel gained a one-click mock generator button
  alongside the mock scope and mock power supply, so an AWG session is reachable with no hardware
  and no direct API call.
- The readout strip shows what the generator reports back rather than what was sent — an AWG
  clamps amplitude against its load setting and snaps frequency to its resolution — and every
  channel appears, including disabled ones, so which outputs are live is answerable at a glance. A
  value the instrument will not report shows as `--.--`, and an output whose state it will not
  report shows as unknown rather than off.
- `POST /api/sessions` accepts `kind: "awg"`, and the new `/api/sessions/{id}/awg/...` routes read
  and control the channels.
- A session that fails now says why. A dropped stream or an error from the instrument shows as a
  banner under the header carrying the detail, instead of only turning the status dot red.
  Dismissing the banner clears the message but does not change what the status dot reports — the
  connection state is the instrument's to report, not a side effect of closing a notification.
- Any session can be disconnected from the header. Disconnect moved out of the oscilloscope
  toolbar, so a power supply or function generator session no longer has to be left by reloading
  the page.
- A non-owner is now told, in session, that it's read-only and who owns it, with the same Claim
  action the home screen offers. Previously they found out by having a write rejected.
- The gateway now serves an admin panel on the machine it runs on, at `http://127.0.0.1:8766/`.
  It lists who has access with device counts and last-seen, issues an invitation showing the
  link and code together with a countdown, cancels one sent to the wrong person, and revokes
  someone with a confirmation that names how many devices it signs out. There is no sign-in,
  and three independent things stand in for one: the listener binds loopback, so the operating
  system refuses every non-local connection; requests must carry a `Host` of `127.0.0.1` or
  `localhost`, which is what stops a DNS-rebound page the bind would let through; and any
  request carrying a foreign `Origin` is refused, which is what stops an ordinary cross-origin
  page that satisfies both of the others.
  `--admin-port` moves it; `--no-admin` switches it off. There is deliberately no flag to bind
  it to another address.
- Cancelling a pending invitation is new — previously the only remedy for one sent to the wrong
  person was waiting ten minutes for it to expire.
- A Sessions screen in the admin panel lists every open session with its owner, viewer count and
  idle time. Release clears the owner, making the session immediately claimable by anyone, with
  no confirmation. Close ends the session after confirming, and warns when that session is
  recording so an active capture is not lost accidentally.
- The admin panel gained a page header.
- The live-session list in the Sessions screen now displays readable right-aligned numeric columns
  for Viewers and Idle time.
- A Horizontal panel in the oscilloscope controls, containing a new timebase stepper that steps
  in a 1-2-5 ladder (1 ms → 2 ms → 5 ms → 10 ms) with engineering-unit labels, making both slow
  sweeps and sub-microsecond settings easily reachable.
- `capture.csv` gained an optional `max_points` parameter for parity with the JSON export,
  allowing an oversized record to be trimmed to a smaller sample count before export.

### Changed

- On modern Siglent instruments, the gateway now asks the instrument to thin the waveform record
  to the points the display needs, rather than transferring everything and discarding most of it
  client-side — no change to what you see on screen. Dialects without the interval command
  continue to transfer the full record and thin on the server.
- The CSV and JSON exports now stream instead of loading into memory; when a waveform is too large
  to export safely, the endpoints return an error naming the actual point count and showing how to
  proceed with `max_points`. On dialects that cannot report record length in advance, the export
  proceeds unguarded and logs a warning if it oversizes — nothing is ever silently truncated or
  decimated.

### Fixed

- The gateway no longer freezes while a long capture is in progress. The oscilloscope poll
  previously fetched a waveform on a timer without checking whether the instrument had finished
  acquiring — at slow sweep rates this meant requesting much faster than the scope could produce
  frames, blocking the read until the acquisition was complete, and freezing every control in the
  web UI (since the session's only worker thread also services commands). On modern Siglent
  instruments, the poll now checks whether a new acquisition has landed before fetching; other
  dialects use adaptive timing-based backoff to prevent the freeze.
- On modern Siglent instruments, the live view updates once per completed acquisition. At slow
  sweep rates, a single update every 14 seconds (at 1 s/div, for example) is expected behaviour —
  it matches the instrument's own display rate — and is not a defect or regression.
- A channel whose display query failed is now logged instead of silently failing. Previously a
  poll-path failure made a channel appear 'off': no waveform, no error message, a gateway that
  appeared healthy and did nothing.
- A thinned live view on a modern Siglent instrument no longer reports a time axis that is too
  short by the thinning factor. When the live view asks the scope for every Nth point, the
  instrument keeps reporting the *acquisition's* sample spacing rather than the spacing between
  the points it actually sends — so a trace thinned 7:1 claimed to cover a seventh of the sweep
  it really covered, with `sample_rate` wrong by the same factor. Measurements and exports were
  never affected (they are never thinned); the live view's x-axis was. Verified against an
  SDS824X HD.
- A thinned read that comes back short now fails loudly instead of returning a truncated trace
  scaled onto a time axis that looks correct, and a deep record that fits comfortably once
  thinned is no longer refused as too large for one transfer.
- The timebase control's stepper no longer moves in 0.1 s jumps or hides sub-microsecond sweeps
  under a six-decimal display. It previously lived in the Trigger panel with 100 ms increments —
  one click from 1 ms/div landed on 0.101 s/div — and made sub-microsecond sweeps effectively
  unreachable.
- Revoking a token now takes effect immediately. The gateway reloads its token store when the file
  changes, so `scpi-web token revoke` no longer requires restarting the server to lock someone out
  — which meant the documented remedy for a leaked credential silently did nothing until someone
  remembered to restart.
- The token store is now written atomically, so a crash or a concurrent read during a write can no
  longer leave a `tokens.json` that the gateway refuses to start from.
- An AWG channel whose waveform the instrument will not report now shows the same `--.--` marker
  every other unreadable field uses, instead of a blank dropdown.
- The home screen's no-instruments-found message no longer singles out "start a Mock scope" — it
  points at the mock button for whichever instrument kind, since a mock power supply and mock
  function generator are just as available.
- A revoked credential no longer keeps streaming to a client with an active token, and no longer
  blocks a new user from claiming the session. A periodic liveness check in each stream catches
  a revocation in a different process (default every 5 seconds), and closes the client's WebSocket
  with code 4403 to signal that the credential was revoked rather than the session ending (4410).
- The admin panel's Close and Revoke confirmations are now genuinely modal: a backdrop over the
  page, focus trapped inside, dismissible by Escape or a backdrop click, and focus returned to the
  triggering button when closed. Previously they appeared as inline panels below the table, so on a
  long list they could render below the fold and appear not to work.
- Acting on one session (releasing or revoking) no longer disables the action buttons on every
  other row — each row's actions are now independent.
- The live-session list refreshes every 10 seconds, so the Idle column stays current instead of
  being a snapshot from page load. Refreshes pause while a Close confirmation is open, so the list
  cannot reshuffle under a question you are reading, and a failed refresh leaves the previous rows
  visible rather than blanking the table.
- The gateway serves `index.html` with `Cache-Control: no-store` on both the gateway and admin
  panel, so a rebuilt webapp appears on an ordinary reload instead of requiring a hard refresh and
  cache clear.

## [5.8.0] - 2026-07-27

### Added

- The web gateway can now host a power supply (SPD3303X series) alongside oscilloscopes. A power
  supply found by the network scan shows up under "Power supplies" with its own Connect button,
  and "Mock power supply" in the Connect-manually rail opens a PSU session with no hardware at
  all. The panel gives every output a voltage setpoint, a current limit, an on/off switch, and
  live voltage/current/power readings that update as the instrument does.
- The output switch reflects what the instrument actually reports, never what was just asked for,
  and a reading the supply will not answer shows as `--.--` or "state unknown" rather than as a
  confident zero or a confident "off". An SPD3303X's CH3 has no output-state query at all, so
  this is the normal case there, not an edge case.
- `POST /api/sessions` accepts an optional `kind` field (`"scope"` by default, so an existing
  caller that omits it is unaffected), and the new `/api/sessions/{id}/psu/...` routes read and
  control PSU outputs. A session refuses to start if the connected instrument identifies as a
  different kind than the one asked for. The 26 existing `/scope/` routes are unchanged, as is
  every public name on `InstrumentSession`.

## [5.7.1] - 2026-07-26

### Fixed

- A synthesized waveform no longer carries a spurious full-amplitude sample where a cycle begins.
  `synthesize` builds its time array as `t0 + i / sample_rate`, and for an arbitrary `t0` — a trigger
  crossing, a free-run drift offset, a device model's lead-in — that sum cannot land exactly on a
  whole number of periods, so the cycle count came out an ULP below an integer and the modulo mapped
  it to 0.9999999999999991 instead of 0. Continuous kinds never showed it, but `square` read its low
  level at the instant it should switch high and `ramp` reset a sample early: one sample at full
  amplitude, roughly 50 int8 codes of spike in a mock capture. The cycle count is now snapped to a
  whole cycle when it sits within a few ULP of one, which moves the cycle position by less than any
  consumer can resolve and leaves every other sample bit-identical. Note this covers the cycle wrap
  only; a sample landing exactly on a *duty* or edge threshold is still subject to the same float
  error, which shifts that edge by one sample rather than inverting a sample, and
  `tests/test_cycle_boundary.py` pins that residual so it stays visible.

## [5.7.0] - 2026-07-26

### Added

- `batch_capture` gained a circuit breaker: `max_consecutive_failures` (default 3) stops a run
  after that many back-to-back capture failures, counted across configurations and reset by any
  success. This guards the common unattended failure — a trigger level the signal never crosses —
  which otherwise times out on every single capture: at a 70 s timeout and 100 triggers per
  configuration, that is hours of waiting to collect nothing, previously surfaced only as one log
  line per failure. Everything gathered before the breaker trips is still returned, with the
  failed entries carrying their `error` field, and an error-level log names the reason and the
  shortfall. Note this changes the default behaviour of a run whose captures all fail: it now stops
  early instead of attempting every planned capture. Pass `max_consecutive_failures=None` to
  restore the old behaviour; a run with genuinely sparse triggers should raise `max_wait` instead.
- A mock AWG's output can now be captured by a mock oscilloscope: wire
  `AwgLoopback(awg_connection, awg_channel=1)` into the scope's `signals=`, and a SCPI write to the
  AWG changes the next capture. Previously the mock AWG was a write-only surface — you could set a
  waveform and read it back, but nothing in the system responded to its output, which made it
  untestable end to end without hardware. `MockConnection`'s `signals=` now accepts a callable
  returning a `SignalSpec` as well as a static one, evaluated at every acquisition; this is a
  general extension point, not AWG-specific, so any dynamic signal source works the same way.
  `scpi_control.dut.RCLowPass` is a new first-order RC low-pass usable as a device under test
  between the two instruments, or on any array on its own, using exact zero-order-hold
  discretisation; the mock applies it with a lead-in rendered before the capture window so a
  capture has no settling transient at its head. Two conversions are worth knowing, because
  getting them wrong produces plausible-looking output: AWG amplitude is peak-to-peak and is
  halved into `SignalSpec`'s peak amplitude, and phase is degrees and becomes radians — an output
  that is off reads flat. `ARB` is captured as a sine with a logged warning, since the mock stores
  no arbitrary sample data, and extreme duty values are clamped rather than raising. Non-breaking:
  a static `SignalSpec` in `signals=` behaves exactly as before.

### Changed

- `start_continuous_capture` with `output_dir` set now returns per-capture metadata instead of an
  empty list. Entries carry `timestamp`, `elapsed_time`, `capture_num` and the `files` written,
  omitting the bulky waveform arrays (those are on disk). Previously the function returned `[]`
  whether it had written ten thousand files or none, so a caller had no way to tell what happened.
  In-memory mode (no `output_dir`) is unchanged and still returns the `waveforms`.

### Fixed

- `start_continuous_capture` no longer hides save failures. Saving sat inside the capture loop's
  broad `except`, which logs and continues, so a rejected `file_format` or an unwritable
  `output_dir` failed identically on every iteration for the run's entire duration while the
  function returned an empty list — an overnight run producing an empty directory and no signal
  at all. This is what kept the `npz` default (fixed in 5.6.0) invisible for so long. Saves now
  have their own handler: if the *first* save fails and no file has been written, the run stops
  immediately with a `SiglentError` naming the format and chaining the underlying cause, because
  that is configuration rather than a transient fault and every later attempt would fail the same
  way. Once one file has landed the configuration is proven, so later failures are counted,
  logged, and summarised at the end without aborting a long unattended run. The raised error keeps
  its original type when it is already a library exception, so a caller catching
  `InvalidParameterError` still catches it. A run that writes nothing because no save was ever
  *attempted* — every capture yielding no waveforms, from disabled channels or a failing
  `acquire()` — now ends with a warning too; that is the same empty-directory symptom reached by a
  different route, and it was equally silent.
- `batch_capture` no longer discards the whole run when interrupted or when the instrument stops
  answering. It had no `KeyboardInterrupt` handler at all, so an operator stopping a run they could
  see was doomed lost every capture already taken; it now keeps and returns them, matching what
  `start_continuous_capture` already did. The guard covers the whole per-configuration body rather
  than only the capture, because the gap between configurations — two socket writes plus the settle
  delay — is exactly where an impatient operator tends to press Ctrl-C.
- `batch_capture` now records any `SiglentError` as a failed entry, not just `SiglentTimeoutError`.
  A dropped link mid-run previously propagated and discarded every capture already taken, which is
  the precise loss the failed-entry path exists to prevent. Connection failures count toward the
  circuit breaker as well — an instrument that has stopped answering is exactly what it is for. A
  failure while *applying* a configuration stops the run and returns what was collected.

## [5.6.0] - 2026-07-26

### Fixed

- `save_waveform` now accepts `npz` and `h5` as aliases for `NPY` and `HDF5`. `npz` is
  `start_continuous_capture`'s default, so an overnight run using default arguments previously
  raised on every save and wrote nothing; four shipped examples were broken the same way. The
  same spellings were already valid as file *extensions* via auto-detect — that inconsistency is
  what produced the bug.
- `batch_capture` now parses the SI unit strings its own docstring documents (`'1us'`, `'500mV'`),
  via the new `scpi_control.units.parse_si_value`. Previously the documented example raised
  `TypeError` and discarded every capture already taken. Numeric scales keep working unchanged.
- `capture_single` now polls `acquisition_status()` instead of sleeping a fixed 0.5 s, with a
  timeout derived from the current timebase and a new optional `max_wait`. On a slow timebase it
  previously returned the *previous* acquisition, which `batch_capture` then recorded under the
  new config's label — wrong data, correctly formatted, no warning. A timed-out capture now
  appears in `batch_capture`'s results as an entry with empty `waveforms` and an `error` field,
  rather than aborting the run or holding stale data.
- `capture_single` no longer clobbers a user-configured `NORM` trigger mode. It previously always
  armed a single-shot acquisition regardless of trigger mode; it now leaves `NORM` alone and waits
  for the next natural trigger, matching what `TriggerWaitCollector.wait_for_trigger` already did,
  and continues to arm a single shot in every other mode as before.
- `parse_si_value` scales by shifting the decimal exponent rather than multiplying by a float, so
  `'10us'` is exactly `1e-05`. The multiply-based approach produced `9.999999999999999e-06`, which
  reached the instrument as `TDIV 9.999999999999999e-06` instead of `TDIV 1e-05`.
- The oscilloscope screenshot at the top of the README no longer fails to load on the PyPI
  project page. It used a repository-relative path, which GitHub resolves against the repo but
  PyPI cannot — PyPI renders the README as a standalone document with no repo context, so the
  image silently broke there while looking fine on GitHub. It now uses an absolute raw URL. Note
  that PyPI project pages are immutable per release, so the fix appears from the next release
  onward; already-published pages keep the broken image.

## [5.5.0] - 2026-07-26

### Added

- Four new synthetic signal kinds join `sine`/`square`/`triangle`/`ramp`/`dc`/`noise`: `chirp`, a
  repeating frequency sweep from `frequency` to `end_frequency` over `sweep_time` (linear or, with
  `sweep_log`, logarithmic), with phase carried across the retrace so the sweep boundary is
  discontinuity-free — it's also the one kind the mock free-runs rather than trigger-aligns, since
  a sweep has no stable period; `exponential`, a square wave through an RC network with time
  constant `tau`, evaluated at its periodic steady state so it's settled from the first cycle
  rather than over the first few, and split by `duty`; `pulse`, a trapezoid whose width and edge
  rate are set independently of the period by `pulse_width` and `edge_time` (`edge_time` may be 0
  for an ideal edge) rather than by `duty`, which `pulse` ignores — `pulse_width` is the
  50%-to-50% (FWHM) width, matching both instrument convention and the threshold the repo's timing
  analyzer measures at, so the flat top runs for `pulse_width - edge_time`; and `multitone`, a
  fundamental plus a coherent harmonic series (`harmonics` gives the relative amplitudes of the
  2nd, 3rd, ... harmonic), where `amplitude` sets the fundamental rather than the peak of the sum
  — deliberately not normalized, since normalizing would make THD depend on the harmonic set. The
  new kinds give the repo's timing, THD and spectrum analyzers a closed-form answer to check
  against for the first time, rather than only a pure sine, a square, or noise. Non-breaking:
  every new `SignalSpec` field is optional and appended at the end of the dataclass, so existing
  specs and positional construction are unaffected.

### Fixed

- Signal synthesis documented ringing as having "no effect" on kinds without edges. That was
  wrong: ringing finds its edges with `np.diff(samples) != 0` — any nonzero sample-to-sample
  change — so on a continuous signal every sample qualifies and the impairment acts as a
  derivative-weighted filter rather than an edge response. At 1 MSa/s, 1 V amplitude and 50 kHz
  ringing, the measured deviation is 1.04e-1 V on `chirp`, 5.60e-2 V on `exponential`,
  1.33e-2 V on `multitone` and 9.85e-3 V on `sine`; only `dc` is a genuine no-op. The behaviour
  is unchanged and defensible as a band-limited edge response — only the documentation was
  wrong, and it now states the real effect with those measured figures.
- `SignalSpec` accepted non-finite kind parameters. `pulse_width=nan` passed validation entirely
  (both `nan <= edge_time` and `nan > 1/frequency` are False) and produced a finite but silently
  wrong waveform with no `nan` in the output to give it away; `tau=inf` produced an all-`nan`
  trace and a numpy RuntimeWarning. `end_frequency`, `sweep_time`, `tau`, `pulse_width` and
  `edge_time` are now checked with `np.isfinite` and raise `InvalidParameterError`.
- A `multitone` spec whose `harmonics` contained a non-numeric element raised a raw `TypeError`
  from numpy instead of the `InvalidParameterError` the module promises for every bad parameter.
- The mock's trigger search now sees the ideal signal. `_trigger_crossing` synthesizes a short
  reference trace to locate where the signal crosses the trigger level, but left the impairments
  enabled, so drift, glitches and ringing each moved the crossing (68.85 us to 66.41, 64.70 and
  10.25 us respectively) and ringing added roughly 21 ms per acquisition. It now zeroes them
  alongside the noise it already stripped, so trigger alignment no longer jitters with the
  impairment settings.

## [5.4.0] - 2026-07-26

### Added

- The mock instrument can now misbehave the way real hardware does. It keeps a real SCPI error
  queue behind `SYST:ERR?` (drained by `*CLS` and `*RST`) and rejects out-of-range parameters
  instead of storing them — a bad value is accepted by the transport, ignored, and reported as
  `-222,"Data out of range (<parameter>)"` on the next query, which is what an instrument
  actually does. Validation covers the Siglent scope, PSU and AWG personalities, plus the
  Tektronix and LeCroy scope dialects; DAQ mode gains the `SYST:ERR?` queue itself but has no
  numeric parameters to validate (its only two writes, `ROUT:SCAN` and `TRIG:SOUR`, are
  non-numeric). `reject_if_invalid` gained an optional `max_magnitude` override, since the shared
  scope-calibrated bound rejected legitimate AWG frequencies (and tightened it for AWG
  percentages/phase, which never legitimately need it), plus an optional `non_negative` bound for
  parameters whose real-driver validation is `>= 0` rather than `> 0` (trigger holdoff, AWG
  phase/ramp symmetry, PSU voltage/current). `FunctionGenerator.get_error()` and
  `PowerSupply.get_error()` go from timing out entirely to answering `SYST:ERR?` for the first
  time; `DataLogger.get_error()` already answered before this work, but only ever the hardcoded
  `+0,"No error"` — it can now report a real queued error too. Unimplemented commands still time
  out under `strict=True`, unchanged.
- `SignalSpec` gained optional signal impairments — baseline drift, glitches and edge ringing —
  so measurement and analysis code can be exercised against imperfect signals instead of
  mathematically clean ones. All default to off, so existing synthesised output is unchanged.
  Ringing is continuous across `stream()` chunks, the same way drift already is, rather than
  resetting at each chunk boundary; it's an edge impairment, meaningful only on signals that
  actually have edges (`"square"`, or a pulse-like `"ramp"`).

## [5.3.0] - 2026-07-25

### Fixed

- Provenance and report output no longer state things the software cannot know. Enhanced CSV
  headers label the save timestamp as `Saved` and only emit `Captured` when provenance carries a
  real acquisition time; the report manifest shows `unknown` instead of passing a file's
  modification time off as a capture time; AI-generated Key Findings and Recommendations are
  labelled as such in both Markdown and PDF output, so machine-written text is distinguishable
  from engineering judgement in a signed report; manifest file paths render verbatim instead of
  being italicised and stripped of underscores by the markdown converter; the shipped comparison and
  batch examples no longer stamp synthetic waveforms with a real instrument identity; and
  `scpi-extract` reports missing provenance without inventing a reason for it.

## [5.2.0] - 2026-07-25

### Fixed

- Measurements now work on modern-dialect Siglent oscilloscopes (SDS800X HD, SDS5000X and
  siblings). `measure()` previously sent the legacy `PAVA?` command, which does not exist on
  those instruments, so every measurement failed — including the whole GUI Measurements tab and
  the web gateway's measurement calls. It now uses the documented `:MEASure:SIMPle` subsystem.
  Note that a modern measurement is not side-effect-free: it enables the measurement function,
  pins the measurement mode to simple (an instrument left in advanced mode is not guaranteed to
  answer the simple-value query the same way), sets the simple-measurement source, and switches
  the requested item on, which is visible on the instrument display. These are left in place
  rather than cleared, because the instrument's clear command is all-or-nothing and would remove
  measurements you configured yourself — so enabled measurement items accumulate on the
  instrument display across repeated calls rather than being switched off.

## [5.1.0] - 2026-07-25

### Changed

- Licensing metadata migrated to PEP 639: the package now declares
  `License-Expression: MIT` and ships `License-File: LICENSE` instead of the deprecated
  `license = { text = "MIT" }` table. **Building from source now requires `setuptools>=77`**
  (raised from 61); installing a prebuilt wheel is unaffected.
- PyPI summary, keywords, and classifiers rewritten to lead with the SCPI/test-automation
  category, and the README now opens with a short pitch instead of a single dense paragraph.

### Fixed

- GUI: the Measurements tab now works for all 15 measurement types. Top, Base, Max, Min, Positive
  Width, and Negative Width previously showed `---` (indistinguishable from an instrument fault)
  because the panel called core methods that didn't exist; it now routes every type through the
  instrument's measurement dispatch.
- GUI: the duty-cycle marker divides the pulse width by the signal's actual period instead of the
  gate span, so a marker spanning several cycles reads the true duty cycle — or N/A when no period
  is detectable — rather than a value that shrank as the gate widened.
- GUI: the DAQ "Suggest Thresholds" action no longer errors on success; the analysis-result signal
  now carries the structured suggestion instead of rejecting it.
- `scpi_control.gui.widgets` now imports its widgets lazily, so importing a Qt-free submodule (such
  as the measurement-marker math) no longer pulls in PyQt6. Importing those modules previously
  failed outright wherever the optional `gui` extra was not installed.
  `from scpi_control.gui.widgets import ChannelControl` is unchanged.

## [5.0.0] - 2026-07-24

### ⚠️ Breaking Changes

- Web gateway: every `/api/*` request now requires a bearer token, and the live-stream
  WebSocket requires one too. On first run `scpi-web` mints a token and prints a
  `http://127.0.0.1:8765/?token=…` URL; mint more with `scpi-web token add <name>`.
  **Migration:** scripted HTTP clients must send `Authorization: Bearer <token>`; WebSocket
  clients must offer the `scpi-token.<token>` subprotocol (alongside a plain `scpi`). A
  query-parameter token is accepted only on the initial web-UI page load and is rejected on
  `/api/*`. `GET /api/health` stays unauthenticated. See the
  [gateway security guide](docs/gateway/security.md).
- Web gateway: the interactive API docs at `/docs` and `/redoc` are removed and the OpenAPI
  schema moved to `/api/openapi.json` (token required) — the old locations served the whole
  control surface unauthenticated.
- Reference waveforms: stored metadata moved from a pickled dict to a JSON string so reference
  files load without `allow_pickle`. Files saved by 4.x raise an error naming the file until
  converted. **Migration:** run `scpi-web references migrate` once.
- Power supply (SPD3303X/-E): `ovp_level`/`ocp_level` now raise `NotImplementedError` — the
  SPD3303X command set has no protection subsystem, so these calls never armed anything on real
  hardware (they emitted a `FutureWarning` in 4.1.0). The model's `has_ovp`/`has_ocp` capabilities
  are now `False`. **Migration:** stop calling these on an SPD3303X; gate on
  `has_ovp`/`has_ocp` if you support multiple PSU models.
- Testing: `MockConnection` now defaults to `strict=True`, so an unmatched PSU/AWG/DAQ query raises
  `TimeoutError` like real hardware instead of returning `""`. **Migration:** pass `strict=False`
  explicitly to restore the old lenient behavior.
- Testing: `MockConnection` no longer answers the legacy `C<n>:WF?` waveform read on a
  modern-dialect instance (SDS800X HD / SDS5000X); it now times out, matching real modern
  hardware, which documents no such command. Legacy-dialect scopes are unaffected.

### Added

- Web gateway: named bearer tokens — `scpi-web token add|list|revoke <name>`, stored hashed in
  `~/.siglent/tokens.json` (relocate with `--config-dir`).
- Web gateway: session ownership. The identity that creates an instrument session may write to
  it; anyone authenticated may read, stream, and export. Non-owner writes return `409`.
  `POST /api/sessions/{id}/claim` takes over a session whose owner has been idle past
  `--abandon-after` (default 300 s) and is not actively watching the stream;
  `POST /api/sessions/{id}/owner` hands it over by name (or releases it with `""`). The web UI
  shows a read-only badge and a claim button to non-owners.
- Web gateway: `--allow-port` to permit instrument ports beyond 5025, `--max-sessions`
  (default 8) to bound concurrent sessions, and an unauthenticated `GET /api/health` endpoint.
- Web gateway: `scpi-web references migrate` converts pre-5.0 reference files to the new format
  (atomic and idempotent; `--dir` to point at a non-default store).

### Fixed

- Security: loading a waveform or reference archive no longer unpickles it, so a crafted `.npz`
  can no longer execute code via `scpi-extract`, the report generator's loader, or the gateway.
  The one remaining place that reads the old pickled format is `scpi-web references migrate`,
  which the user runs explicitly on their own files.
- Security: reference lookup no longer honours absolute paths or `..` traversal, and listing
  references no longer deserializes every file in the storage directory.
- Security: session creation validates the target before connecting — hostnames are resolved
  and every resolved address checked, loopback/link-local/cloud-metadata addresses are refused,
  ports must be allowlisted, and a failed connect returns a generic message rather than
  reflecting the peer's bytes (no SSRF port-scanning or banner-grabbing).
- Web gateway: full-resolution CSV/JSON serialization of deep-memory captures runs off the
  event loop, so one large export no longer freezes the gateway for other users; the session
  cap holds correctly under concurrent requests.
- Reference storage: `rename_reference` no longer leaks the source file handle (a Windows-only
  `WinError 32` that made it fail); reference lookups now confine themselves to the storage
  directory.
- Web UI: file downloads (capture CSV, screenshot, waveform JSON, trend CSV) fetch with the
  bearer token instead of bare `<a href>` links, which could not carry an `Authorization`
  header and would have returned `401` against the authenticated gateway.

## [4.1.1] - 2026-07-24

### Fixed

- Packaging: the six screenshots in the README are now absolute URLs, so they render on the PyPI
  project page. They used repository-relative paths, which PyPI cannot resolve because it renders
  the README with no repository context — the images showed as broken there while displaying
  correctly on GitHub.

## [4.1.0] - 2026-07-23

### Added

- Testing: a vendor-example conformance corpus (`tests/wire_forms.py`) pins every command in the
  covered SCPI tables to a request/response pair transcribed from the vendor's programming guide,
  with document and page citations. A coverage test (`tests/test_wire_conformance.py`) fails the
  suite if any command in those tables (the legacy and modern scope dialects, the SPD power-supply
  overrides, and the SDG function-generator overrides — 159 commands) has no cited corpus entry, so
  an invented command can no longer be added silently to a covered table. (The IEEE-488.2 base, the
  generic fallbacks, and the Tektronix/LeCroy/DAQ tables are not yet enforced — see
  `docs/development/wire-form-inventory.md`, which records the full audit.)
- Oscilloscope: modern-dialect deep-memory waveform capture is chunked over `:WAVeform:MAXPoint`
  windows using `:WAVeform:STARt`, so records larger than a single transfer are reassembled correctly.
- Oscilloscope: modern-dialect (SDS800X HD / SDS5000X) waveform capture now goes over the documented
  `:WAVeform:SOURce`/`:WAVeform:PREamble?`/`:WAVeform:DATA?` subsystem instead of the legacy
  `C<n>:WF? DAT2`/`DESC` forms, which have zero occurrences anywhere in the modern programming guide
  (audit H9). Voltage and time reconstruction use the guide's own documented formulas (p.758/p.759).

### Fixed

- Oscilloscope (legacy Siglent): measurements use the documented `C<n>:PAVA? <param>` form and parse
  its two-field response, and sample-rate responses carrying an SI magnitude letter (`SARA 500.0kSa`)
  now parse. The previous `PAVA? <param>,C<n>` form and scientific-only sample-rate parsing failed on
  real hardware (audit H7/H30/H8/H34).
- Power supply (SPD3303X/-E): measurement queries use the documented `MEASure:VOLTage? CH<n>` form
  (channel as an argument), tracking mode uses the documented numeric `OUTPut:TRACK {0|1|2}`, and
  output state is read by decoding the `SYSTem:STATus?` word — the instrument documents no output-state
  query (audit H6/H19/H20).
- Function generator (SDG): parameter readback uses the documented bare `C<n>:BSWV?` / `C<n>:OUTP?`
  queries and parses the returned key-value list; the previous per-field selector grammar
  (`C<n>:BSWV? FRQ`) does not exist on the instrument (audit H5).
- USB/GPIB/serial: `VISAConnection` can now be instantiated — it implemented neither `read` nor
  `read_raw`, so it raised `TypeError` at construction and every documented VISA example failed
  (audit H10).
- Testing (mock fidelity): the mock now answers documented legacy probe (`C<n>:ATTN?`) and
  bandwidth-limit (`BWL?`) queries instead of timing out; the DAQ dispatch no longer matches `R?` as a
  substring (which hijacked `SYST:ERR?`/`TRIG:SOUR?`) and interprets scan-list/trigger writes; and
  `MockConnection.read_raw` honors the requested byte count.

### Deprecated

- Power supply: setting `ovp_level`/`ocp_level` on an SPD3303X/-E now emits a `FutureWarning`. The
  SPD3303X command set contains no protection subsystem, so these calls have never armed anything on
  real hardware. In v5.0.0 the model's `has_ovp`/`has_ocp` capabilities become `False` and the calls
  raise `NotImplementedError`.
- Testing: `MockConnection` gained `strict=True`, which makes unmatched PSU/AWG/DAQ queries raise
  `TimeoutError` like real instruments instead of returning `""`. Strict becomes the default in v5.0.0 —
  pass `strict=False` explicitly to keep the old behavior past that release.
- Testing: `MockConnection` still answers legacy `C<n>:WF?` writes on a modern-dialect (`SDS8xx HD`/
  `SDS5000X`) instance, even though the driver's modern capture path no longer sends it (audit H9,
  Task 18). This is a backward-compatibility shim for anything still issuing that form by hand; the
  modern guide documents no such command, and the mock handler is removed in v5.0.0.

## [4.0.0] - 2026-07-22

### ⚠️ Breaking Changes

- Power supply and function-generator readback (`measure_voltage`/`measure_current`/`measure_power`,
  setpoint/OVP/OCP getters, and AWG `frequency`/`amplitude`/`offset`/`phase`) now raise
  `CommandError` when the instrument returns an unparseable response, instead of silently returning
  `0.0`. Callers that relied on the silent zero must handle the exception.

### Added

- Dev tooling: `pytest-xdist` in the `dev` extra for parallel local test runs (`python -m pytest -n auto`); complements `--testmon` (use one or the other per invocation).
- Report generator: before/after comparison and multi-DUT batch reports — load multiple capture-file runs, overlay their waveforms, and get delta tables (comparison) or per-DUT summary with aggregates and yield (batch). Available from the Python API and the GUI's new Report → Comparison / Batch Report dialog.
- Report generator: optional raw-data appendix (source-file manifest with SHA-256 checksums, capture timestamps, and instrument identity from provenance) and a configurable sign-off block (template-defined roles with signature/date lines). Both also work on ordinary single-run reports.
- Report generator: `top_flatness` waveform statistic (top-plateau deviation as % of amplitude); the probe-calibration preset now evaluates overshoot/undershoot (pass/fail) and top flatness (warning).

### Fixed

- Report generator: the waveform loader no longer drops acquisition provenance when loading capture files.
- Analysis: corrected THD (each harmonic is read at its own bin, robust to an off-bin fundamental),
  noise/SNR (estimated from a signal-free residual instead of the whole-signal RMS), `vamp`
  (Vtop − Vbase amplitude, not the vertical midpoint), overshoot/undershoot (only reported for
  flat-topped signals), duty cycle (correct when the capture starts on the high level), DC
  classification (no longer fooled by a large offset over real ripple), FFT peak detection (finds
  peaks below 0 dB), and SciPy window handling for the power spectrum / spectrogram.
- Reports and the live webapp spectrum now use a single THD engine, so they report the same number
  for the same capture. Report-path THD now sums the first 5 harmonics (previously 10).
- DAQ AI threshold suggestions now bind each extracted number to its label instead of grabbing the
  first number in the sentence.
- Comparison/batch reports: pass/fail criteria now match analyzer statistics (case-insensitive plus
  display-name aliases) — previously the shipped criteria template produced empty verdicts. Criteria
  that cannot be evaluated are surfaced as warnings (never silently dropped), half-open RANGE criteria
  are enforced, verdicts are severity-aware (only `critical` criteria gate) with a distinct INCOMPLETE
  state, and yield reports an incomplete count instead of inflating the pass rate.

## [3.3.1] - 2026-07-21

### Changed

- README and docs now cover the full current feature set: multi-vendor scopes, DAQ, PSU/AWG models, the web gateway and `usb` extras, all four CLI tools, `load_waveform()`/`scpi-extract` usage, and API reference pages for `signal_synth`, `waveform_io`, `provenance`, and `scpi_extract`. Every example now carries a fully spelled-out docstring (what it shows, what it needs, what to expect).

### Fixed

- `DataCollector.save_data()`/`save_batch()` no longer raise `InvalidParameterError` with their default format — the format is now auto-detected from the filename extension (pass CSV, CSV_ENHANCED, NPY, MAT, or HDF5 explicitly to override).
- Report-analyzer calibration guidance and example-script output are now ASCII-safe, so they no longer crash on Windows consoles with legacy codepages.
- Documentation sweep: corrected the README's report-generator sample to the real API, fixed the default SCPI port (5025) and GUI frame-rate claims, repaired all broken links and anchors across README and the docs site, synced the docs changelog page through 3.3.0, and excluded internal planning files from the built documentation site.

## [3.3.0] - 2026-07-21

### Added

- `signal_synth.stream()`: an infinite or duration-bounded generator of phase-continuous voltage chunks for live-signal simulation — optional wall-clock pacing (`realtime=True`), correct seeded-noise semantics (seed advances per chunk, so seeded streams are reproducible without repeating noise blocks), and eager parameter validation.
- Dev tooling: `pytest-testmon` in the `dev` extra for impact-based local test selection (`python -m pytest --testmon`); CI and pre-merge checks still run the full suite.

## [3.2.0] - 2026-07-21

### Added

- Synthetic signals: a public generator API — `SignalSpec` plus `synthesize()`/`make_waveform()` in `scpi_control.signal_synth` — producing sine, square (with duty cycle), triangle, ramp, DC, and Gaussian-noise waveforms as numpy arrays or ready-to-analyze `WaveformData`, with seedable reproducibility.
- Mock scopes now synthesize realistic waveforms by default (all vendor personalities): traces are computed from the mock's live timebase, V/div, offset, and trigger state at every acquisition — over-range clips at 8-bit full scale, the trigger level/slope aligns the edge at the window center, and unseeded captures animate with fresh noise. Pass `signals={ch: SignalSpec(...)}` to choose the signal, or `waveform_payloads` bytes for the old fixed-payload behavior (unchanged). Web-gateway mock sessions stream synthesized signals out of the box.

### Changed

- MockConnection's default (no `waveform_payloads` given) no longer serves a fixed 4-byte payload — channels synthesize state-coupled signals instead.

## [3.1.0] - 2026-07-21

### Added

- Report generator: a built-in **probe-calibration template preset** (`ReportTemplate.create_probe_calibration_template()`, seedable from the Template Manager via "Create Probe Cal Template") — probe_calibration test type, a compensation procedure, and overshoot/undershoot/ringing/flatness pass/fail limits.
- Examples: four new runnable, no-hardware examples — `report_ai_qa.py` (local-LLM tool-calling Q&A over a report), `network_discovery.py` (scan the network for SCPI instruments), `report_branding.py` (apply company branding/colours to a report), and `report_computed_analysis.py` (deterministic, LLM-free report analysis).
- Examples: a `tests/test_examples_smoke.py` guard that executes the no-hardware examples, compile-checks the rest, and blocks known-stale tokens from reappearing.
- Docs: a real screen capture and a real 1&nbsp;kHz calibration-square-wave plot from a Siglent SDS824X HD (in `docs/images/`), plus the raw capture committed as a test fixture (`tests/fixtures/cal_square_sds824x.npz`) that exercises the analyzer against genuine hardware data.
- Acquisition provenance: waveforms captured with `acquire()`/`get_waveform()` now record the instrument identity, per-channel settings, trigger configuration, timebase, and UTC timestamp, embedded in every save format (new keys only — existing files and keys are unchanged; pass `provenance=False` to skip the snapshot on high-rate paths).
- `scpi_control.waveform_io.load_waveform()`: public parser that reads all five waveform file formats (old and new files) into numpy arrays plus normalized metadata/provenance, with an optional `to_dataframe()` pandas helper.
- `scpi-extract` CLI: inspect provenance (`--info`), dump raw data (`--csv`), or emit machine-readable metadata (`--json`) from any saved waveform file.
- Waveform savers now persist the previously dropped `timebase`, `voltage_scale`, and `voltage_offset` fields; plain CSV gains a `#`-commented provenance header (channel, sample rate, scales, instrument, timestamp) (suppress with `save_waveform(..., bare=True)`).

### Changed

- Report generator AI: every oscilloscope system prompt now carries one shared grounding rule (claim only what the report data or a tool actually returned; say so plainly when a value is missing rather than inventing it).
- Report generator AI: key-findings and recommendations are parsed more tolerantly — multi-digit numbering, markdown-bold list markers, and a leading preamble line no longer corrupt the extracted list.
- Report generator (internal): the oscilloscope and DAQ LLM prompt layers now share one grounding constant and the prompt-lookup / chat-prompt assembly via `llm/_prompt_helpers.py`, removing duplicated boilerplate.

### Fixed

- Report generator analysis: `WaveformAnalyzer`'s noise check no longer computes an O(n²) full autocorrelation — it now reads only the two autocorrelation lags it uses, so analysing large captures (e.g. 1,000,000-sample records) completes in milliseconds instead of hanging. Also removes a divide-by-zero `RuntimeWarning` on constant signals.
- Examples: repaired broken examples — `simple_capture.py` and `advanced_analysis.py` referenced a non-existent `waveform.time_interval` (now the sample period `1.0 / sample_rate`), and the interactive tutorial saved with an invalid `format="NPZ"` (now `"NPY"`). The report-generation and branding examples now degrade cleanly when reportlab is absent instead of crashing.
- Examples: updated the stale `Siglent-Oscilloscope` package name (and dead repo links) to `SCPI-Instrument-Control`, and corrected the README's hardware/no-hardware annotations.
- Screen capture on modern-dialect scopes (SDS800X HD): `ScreenCapture` now selects the correct SCDP command per dialect and reads the raw BMP sized by its own header, instead of over-reading a fixed 10&nbsp;MB — which timed out and dropped the connection. `scope.screen_capture.get_screenshot_pil()` now works on the modern scopes.
- Report generator analysis: `WaveformAnalyzer.detect_signal_type` no longer misclassifies clean periodic signals (e.g. a square wave captured over many periods) as noise. The noise check now measures spectral concentration — whether one frequency bin dominates — instead of testing autocorrelation at an arbitrary fixed lag.
- Report generator analysis: `WaveformAnalyzer.detect_signal_type` now classifies pulse/PWM signals (non-50%-duty square waves) as pulse instead of sawtooth. Two-level (flat-topped) signals are separated from ramps before the harmonic scorers run.
- Report generator DAQ AI: the data-logger analysis prompts now carry the same grounding rule as the oscilloscope prompts (claim only what the data shows; say so when a value is missing), and the session-summary prompt no longer invites a "Here is the summary" preamble.
- Report generator PDF: characters outside the built-in font's range (⚠, ✓/✗, σ, Ω, …) no longer render as blank boxes — they are normalized to readable text, with a catch-all so any unexpected glyph can never box out.

## [3.0.0] - 2026-07-17

### ⚠️ Breaking Changes

- **The report generator's `WaveformData` fields are renamed, and `channel`
  moved from the first constructor argument to the third.** `channel_name`,
  `time_data`, and `voltage_data` are now `channel`, `time`, and `voltage`,
  matching the base class's field order (`time`, `voltage`, `channel`, ...).
  Because the position changed along with the name, positional construction
  such as `WaveformData("CH1", t, v, ...)` does **not** fail with a
  recognizable rename error — it silently assigns `"CH1"` to `time` and
  blows up later with `AttributeError: 'str' object has no attribute
  'shape'`. Construct with keywords (`channel=`, `time=`, `voltage=`) to
  migrate safely. This is a documented public API — see
  [`docs/report-generator/api-reference.md`](docs/report-generator/api-reference.md).
- **`WaveformData.source` and `WaveformData.description` are removed**, on
  both the library and report waveform types. `WaveformData(..., source="x")`
  now raises `TypeError` instead of silently accepting the keyword.
- **`WaveformData.timebase` and `WaveformData.voltage_scale` are `None`
  unless an instrument actually reported them**, instead of being derived by
  assuming a 14-division horizontal grid and an 8-division vertical one —
  Siglent's geometry, previously applied to Tektronix and LeCroy captures too
  — with a flat trace given a bare 1.0 V/div. Real acquisitions are
  unaffected: all three vendor backends pass genuine scope values. Code that
  does arithmetic on `timebase`/`voltage_scale` from a *synthetic* waveform
  (a math channel, or hand-built test data) — e.g. `wf.timebase * 1e6` — now
  raises `TypeError` on `None` instead of silently using an invented number.
  Guard with a `None` check, or supply real values.

### Added

- Tektronix and LeCroy oscilloscope support (core control, waveform
  acquisition, measurements): two more wire dialects (`tektronix`, `lecroy`)
  alongside the existing Siglent legacy/modern pair, auto-detected from
  `*IDN?` via a manufacturer-first routing step. Covers the Tektronix
  TBS1000C Series and 2 Series MSO, and the LeCroy WaveSurfer 3000z and
  WaveRunner 8000 series. See the
  [SCPI Dialects guide](docs/user-guide/scpi-dialects.md) for the full
  per-vendor command tables and known gaps (e.g. LeCroy
  statistics/cursors/holdoff, Tek 16-bit waveform transfer).
- Tektronix MSO 4/5/6 Series support (MSO44, MSO46, MSO54, MSO56, MSO58,
  MSO58LP, MSO64), including 6- and 8-channel models.
- Badge-based measurements for the modern Tektronix MSO families, which also
  enables `measure()` on the MSO 2-Series.
- **Report generator — local-LLM analysis and richer PDFs**
  (`pip install "SCPI-Instrument-Control[report-generator]"`). Everything here
  is local-only — no cloud providers, no API keys.
  - Local-LLM (Ollama) tool calling: the model can call read-only report tools
    to ground its answers, behind a capability gate that no-ops when the local
    model cannot do tool calls.
  - Waveform analysis tools for the model — `analyze_plateaus`, `list_edges`,
    and `analyze_spectrum` — plus `WaveformAnalyzer.calculate_spectrum`.
  - Deterministic no-LLM analysis: a `ComputedAnalyzer` populates per-waveform
    statistics and regions on every report, and composes a summary, findings,
    and recommendations when no LLM wrote them. Reports now attribute their
    summary by source (manual / AI / computed) rather than a bare AI flag.
  - Vector PDF plots: waveform, FFT, and region plots render as scalable vector
    graphics instead of rasterized images.
  - Page framework: a running header/footer and page numbers on every page,
    with section headings kept from stranding at the bottom of a page.
  - Template branding: a template's logo, company name, header/footer text, and
    four brand colours apply to the generated PDF, and a built-in starter
    template can be seeded from the Template Manager.

### Changed

- On the Siglent modern dialect, `trigger.holdoff`, measurement statistics,
  cursors, and `channel.unit` now raise `FeatureNotSupportedError` immediately
  instead of writing an unsupported command and timing out
  (`SiglentTimeoutError`). Code that caught the timeout to detect these
  unsupported operations must now catch `FeatureNotSupportedError` instead.
- Probe-ratio wire format on the legacy and modern dialects now serializes
  floats compactly (`10.0` is sent as `10`), matching how real scopes echo the
  value back.
- `add_measurement` now validates and case-normalizes its measurement type
  (unknown types raise instead of being sent verbatim to the instrument).
- Channel numbers are validated against the connected model's channel count
  instead of a fixed 1-4 range. Scopes with fewer than four channels now raise
  `InvalidParameterError` for a channel they do not have, where they
  previously queried it.
- The report generator's `WaveformData` is now a subclass of
  `scpi_control.waveform.WaveformData` (see Breaking Changes above for the
  field rename and reorder this involved). Report waveforms now inherit the
  library's array-shape validation, and `channel` is now guaranteed to be a
  `str` by the type itself. The loader's explicit `str()` calls at each
  construction site are unchanged and now redundant, not removed — they stay
  as a defensive measure against `np.str_`/`bytes` values handed back at the
  MAT/HDF5 boundary.

## [2.0.0] - 2026-07-15

### ⚠️ Breaking Changes

- **Removed the `siglent` compatibility shim.** `import siglent` now raises
  `ModuleNotFoundError`; use `import scpi_control` (identical API). The shim
  had emitted a `DeprecationWarning` since 1.0.0, which announced its removal
  in v2.0.0. If you cannot migrate yet, pin `SCPI-Instrument-Control<2.0`.
- **Python 3.9+ required** (was 3.8+; Python 3.8 reached end of life in
  October 2024). CI now tests Python 3.9 through 3.14.

### Added

- **Browser-based lab gateway** (`pip install "SCPI-Instrument-Control[web]"`,
  then `scpi-web` or `python -m scpi_control.server`): a FastAPI server that
  manages named multi-instrument sessions and serves a React UI to any
  browser on the LAN. Mock-first — every feature works against the built-in
  mock scope (`mock: true`).
  - Live waveform streaming over WebSocket, with channel, timebase, trigger,
    and acquisition (run/stop/single/auto) controls
  - LAN instrument discovery and a dashboard-style home screen
  - Measurements with live values and cross-tab-synchronized selection
  - Software math channels (M1/M2) streamed as canvas traces
  - SCPI terminal, instrument screenshot PNG, full-resolution waveform
    export as CSV and JSON
  - FFT spectrum view computed server-side from full-resolution data
    (window selection, peak markers, THD readout)
  - Software Butterworth filters (lowpass/highpass/bandpass) streamed as
    F1/F2 traces
  - Reference waveforms: save named snapshots, ghost overlay on the canvas,
    live correlation and max-deviation statistics
  - Measurement trend recording: server-side ring buffer at ~1 Hz, live
    trend chart, CSV export; the measurement selection locks while recording
- Dual-dialect SCPI support: legacy (e.g. SDS1104X-E) and modern
  (e.g. SDS800X HD) Siglent command sets behind one API, auto-detected from
  `*IDN?` with a manual override

### Changed

- Connection layer hardened: thread-safe socket handling, exact-length
  binary reads, default SCPI port 5025
- `wait_for_trigger` honors a user-configured NORMAL trigger mode instead of
  forcing SINGLE
- Black formatting standardized on the 26.x stable style; dev extra now
  requires `black>=26.5,<27` (installed on Python >= 3.10, where Black 26 is available)
- Removed the unused `uplot` frontend dependency (the UI draws on a
  hand-rolled canvas)

### Fixed

- Mock-fidelity and hardware-behavior fixes from the 2026-07 code audit
  (trigger vocabulary mapping, waveform preamble parsing, measurement
  timeout handling, and related issues)

## [1.1.0] - 2026-01-12

### Added

- Data acquisition / data logger instrument support (`DataLogger`): Keysight
  34970A/DAQ970A-style SCPI units — DMM function configuration (V/I/R/
  temperature), scan lists, triggering, alarms, channel scaling, and timed
  logging helpers (PR #39)

## [1.0.1] - 2026-01-07

Packaging and metadata fixes for the 1.0.0 rename release; no functional changes.

## [1.0.0] - 2026-01-06

### ⚠️ MAJOR RELEASE - Package Renamed

**This is a major release with a package rename.** The project has been renamed from `Siglent-Oscilloscope` to `SCPI-Instrument-Control` to better reflect its expanded capabilities beyond just Siglent oscilloscopes.

### Breaking Changes

- **PyPI Package Name**: `siglent` → `SCPI-Instrument-Control`
- **Python Import Name**: `import siglent` → `import scpi_control` (recommended)
- **Old import still works** with deprecation warning (will be removed in v2.0.0)

### Added

**Backward Compatibility Layer**
- Created `siglent/` compatibility shim package
- Old `import siglent` syntax still works with `DeprecationWarning`
- Re-exports all `scpi_control` modules for seamless backward compatibility
- Warning message guides users to migrate imports
- Compatibility layer will be removed in v2.0.0

**Migration Guide**
- Comprehensive migration documentation in README.md
- Step-by-step upgrade instructions
- Comparison table showing what changed and what stayed the same
- Code examples for old vs new import syntax
- Explanation of why the rename was necessary

### Changed

**Package Structure**
- Renamed `siglent/` directory to `scpi_control/` (preserving git history)
- Updated all internal imports from `siglent.*` to `scpi_control.*`
  - 192 import occurrences updated in `scpi_control/` modules
  - All imports updated in `tests/` directory
  - All imports updated in `examples/` directory
- Package now reflects multi-instrument, multi-vendor capabilities

**PyPI Metadata** (`pyproject.toml`)
- Package name: `siglent` → `SCPI-Instrument-Control`
- Version bump: `0.5.1` → `1.0.0` (major release)
- Updated description to emphasize universal SCPI instrument control
- Updated keywords to reflect multi-instrument support
- Updated all URLs to point to new repository name
  - Homepage, Repository, Issues, Documentation, Changelog

**Documentation**
- Updated README.md with new project name and branding
- Added "Package Renamed" notice at top of README
- Updated all badge URLs to reference new repository name
- Updated installation commands to use `SCPI-Instrument-Control`
- Changed GUI application overview section title
- Updated git clone directory name in examples
- Added comprehensive Migration Guide section with:
  - Installation update instructions
  - Import statement migration examples
  - Backward compatibility explanation
  - CLI command compatibility notice
  - Comparison table of changes
  - Rationale for the rename

**Command-Line Tools** (No Changes)
- `siglent-gui` command **unchanged** for convenience
- `siglent-report-generator` command **unchanged**
- No changes needed to scripts or automation using these commands

### Why the Rename?

This library has evolved significantly beyond its original Siglent oscilloscope focus:

1. **Multi-Instrument Support**: Now supports oscilloscopes, power supplies, and function generators
2. **Multi-Vendor Support**: Works with any SCPI-compatible equipment, not just Siglent
3. **Universal Protocol**: Based on industry-standard SCPI commands (IEEE 488.2)

The new name `SCPI-Instrument-Control` accurately represents what the library does: **control any SCPI-compatible test equipment**.

### Migration Instructions

#### For New Users

```bash
pip install SCPI-Instrument-Control
pip install "SCPI-Instrument-Control[gui]"
pip install "SCPI-Instrument-Control[all]"
```

```python
from scpi_control import Oscilloscope, PowerSupply, FunctionGenerator
```

#### For Existing Users

**Option 1: Update imports** (recommended)
```bash
pip uninstall siglent
pip install SCPI-Instrument-Control
```

Change imports:
```python
# Old
from siglent import Oscilloscope
from siglent.gui.app import main

# New
from scpi_control import Oscilloscope
from scpi_control.gui.app import main
```

**Option 2: Use compatibility layer** (temporary)
```bash
pip install SCPI-Instrument-Control
```

Keep old imports (will show `DeprecationWarning`):
```python
from siglent import Oscilloscope  # Still works, but deprecated
```

**Note**: The compatibility layer will be removed in v2.0.0. Please migrate when convenient.

### Technical Details

**Git History Preservation**
- Used `git mv siglent/ scpi_control/` to preserve file history
- All commit history for individual files maintained
- No loss of attribution or change tracking

**Import Updates**
- Used automated find/replace for import statement updates
- 192 occurrences in `scpi_control/` directory
- All test files updated
- All example files updated
- No manual edits required for import changes

**Compatibility Implementation**
- `siglent/__init__.py` re-exports entire `scpi_control` module
- Uses `warnings.warn()` with `DeprecationWarning` category
- Warning includes migration instructions and timeline
- `stacklevel=2` ensures warning points to user code, not library

### Dependencies

No dependency changes. All existing dependencies remain the same.

### Deprecation Timeline

- **v1.0.0** (2026-01-06): Old `import siglent` works with deprecation warning
- **v2.0.0** (TBD): Compatibility layer removed, `import siglent` will fail

Users have until v2.0.0 to migrate their imports.

## [0.5.1] - 2026-01-05

### Fixed

**Documentation Build and Deployment**
- Fixed GUI API documentation with incorrect module references
  - Corrected all wildcard references (`*`) to proper underscores (`_`) in `docs/api/gui.md`
  - Fixed 20+ module reference errors (e.g., `siglent.gui.main*window` → `siglent.gui.main_window`)
  - Documentation now builds successfully without errors
- Set up automated GitHub Pages deployment
  - Created `.github/workflows/docs.yml` for automatic documentation deployment
  - Documentation auto-deploys to GitHub Pages on every push to main branch
  - Integrated with existing `make docs-generate` automation
- Updated PyPI documentation URL
  - Changed from README-only link to proper documentation site
  - PyPI now links to https://little-did-I-know.github.io/Siglent-Oscilloscope/
  - Users can access complete API documentation and guides from PyPI

**MkDocs Build System**
- Ensured autodoc generation works correctly with mkdocstrings
- Verified API reference pages generate from Python docstrings
- Confirmed cross-references between documentation pages work properly

### Changed

**Documentation Infrastructure**
- Documentation now automatically generated and deployed on every main branch update
- API documentation uses mkdocstrings for automatic extraction from code
- Examples documentation auto-generated from example scripts
- Improved documentation discoverability for users installing from PyPI

## [0.5.0] - 2026-01-04

### Added

**Automated Test Report Generation** 📊
- **Installation**: `pip install "Siglent-Oscilloscope[report-generator]"`
- **PDF and Markdown Report Generators**
  - Professional publication-ready reports with waveform plots and analysis
  - Comprehensive metadata tracking (test ID, operator, timestamp, scope model)
  - Multiple output formats (PDF via ReportLab, Markdown with embedded plots)
  - Automatic file organization and asset management

- **Signal Type Detection** (`siglent/report_generator/utils/waveform_analyzer.py`)
  - Automatic waveform classification using FFT harmonic analysis
  - Detects 9 signal types: sine, square, triangle, sawtooth, pulse, DC, noise, complex, unknown
  - Confidence scoring for classification accuracy
  - THD (Total Harmonic Distortion) calculation for waveform quality assessment
  - Pattern matching algorithms for periodic signal identification:
    - Square waves: odd harmonics at 1/n amplitude ratio
    - Triangle waves: odd harmonics at 1/n² amplitude ratio
    - Sawtooth waves: all harmonics at 1/n amplitude ratio
  - Signal type displayed in both PDF and Markdown reports with confidence percentage
  - Added `SignalType` constants class for standardized type identification

- **Enhanced Waveform Statistics** (`siglent/report_generator/models/report_data.py`)
  - Comprehensive signal analysis with 25+ measurement parameters
  - Amplitude measurements: Vmax, Vmin, Vpp, VRMS, Vmean, DC offset
  - Frequency and timing: frequency, period, rise time, fall time, pulse width, duty cycle
  - Quality metrics: SNR (Signal-to-Noise Ratio), THD, noise level, overshoot, undershoot, jitter
  - Automatic statistics calculation via `WaveformData.analyze()` method
  - Smart unit formatting with SI prefixes (mV, µs, kHz, etc.)
  - Statistics integration in PDF and Markdown report generators

- **Plateau Stability Analysis** (Optional Feature)
  - Measures noise on high and low plateaus for periodic signals
  - Uses run-length encoding to identify flat signal regions
  - Analyzes middle 60% of each plateau to exclude edge transitions
  - Reports three metrics:
    - Plateau High Noise: Standard deviation on high-level plateaus
    - Plateau Low Noise: Standard deviation on low-level plateaus
    - Plateau Stability: Average noise across all plateaus
  - User-configurable via Report Options dialog checkbox
  - Auto-applies to pulse, square, triangle, sawtooth, and sine waves
  - Helpful for power supply ripple, logic level stability, and signal quality testing

- **LLM Model Detection Feature** (`siglent/report_generator/widgets/llm_settings_dialog.py`)
  - "Detect Models" button in Ollama and LM Studio configuration tabs
  - Automatically queries server for available models and populates dropdown
  - Changed model input from text field to editable combo box
  - Preserves previously selected model after detection
  - User-friendly error messages with troubleshooting steps
  - Shows model count and lists detected models
  - Leverages existing `LLMClient.get_available_models()` API
  - Works with both Ollama Python SDK and OpenAI-compatible endpoints

- **Report Options Dialog** (`siglent/report_generator/widgets/report_options_dialog.py`)
  - New checkbox: "Plateau Stability Analysis (Advanced)"
  - Tooltip explains feature usage and applicability
  - Settings persist with report templates
  - Integrated with `ReportOptions` model

### Changed - Report Generator Features

- **PDF Generation Progress Tracking** (`siglent/report_generator/generators/pdf_generator.py`)
  - Enhanced with granular waveform-level progress updates
  - Progress now updates for each waveform being processed: 20%, 25%, 30%, ..., 80%
  - Prevents freezing appearance during matplotlib plot generation
  - Progress callback shows current operation: "Processing section X/Y", "Rendering waveform Z"
  - Smooth progression instead of jumping from 20% to 100%
  - Integrated with `QProgressDialog` in GUI for visual feedback

- **Unicode Character Normalization** (`siglent/report_generator/generators/pdf_generator.py`)
  - Comprehensive character mapping for AI-generated text compatibility
  - Handles 30+ Unicode characters that ReportLab can't render:
    - Smart quotes (U+201C, U+201D, U+2018, U+2019) → regular quotes
    - Em-dash (U+2014) and en-dash (U+2013) → hyphens
    - Bullets (U+2022) → asterisks
    - Ellipsis (U+2026) → three dots
    - Math symbols: ≤→<=, ≥→>=, ≠→!=, ×→x, ÷→/
    - Degree symbols: °→deg, ℃→C, ℉→F
    - Non-breaking spaces and special formatting characters → regular space
  - Applied to all AI-generated text fields: executive summary, AI insights, AI summary
  - Prevents empty boxes, question marks, or missing characters in PDFs
  - Maintains readability while ensuring PDF compatibility

- **Waveform Statistics Display** (PDF and Markdown Generators)
  - Statistics tables now include signal type with confidence
  - Plateau stability metrics shown when enabled and applicable
  - Enhanced formatting with proper units and precision
  - Color-coded headers and organized metric grouping in PDFs
  - Responsive table layout that adapts to content

### Fixed - Report Generator Features

- **AI-Generated Text Rendering in PDFs**
  - Fixed special Unicode characters not rendering (showing as boxes/question marks)
  - Root cause: LLMs generate smart quotes, bullets, and math symbols that ReportLab can't handle
  - Solution: Comprehensive character normalization before PDF generation
  - Now handles text from Claude, GPT, Llama, and other LLMs correctly

- **Progress Bar Freezing During Plot Generation**
  - Fixed progress bar appearing to freeze at 20% during PDF generation
  - Root cause: No progress updates during slow matplotlib plot rendering
  - Solution: Track waveforms across sections and report per-waveform progress
  - Users now see smooth progression throughout the entire generation process

### Technical Improvements - Report Generator

- **FFT-Based Signal Analysis**
  - NumPy FFT with harmonic ratio analysis for signal classification
  - Autocorrelation for period detection in non-periodic signals
  - Robust against noise with configurable confidence thresholds
  - Optimized for real-world oscilloscope waveforms

- **Extensible Waveform Analyzer**
  - Static methods for modular analysis capabilities
  - Separation of detection, measurement, and formatting logic
  - Easy to add new signal types or analysis algorithms
  - Comprehensive docstrings with algorithm explanations

- **Report Options Architecture**
  - `ReportOptions` dataclass for type-safe configuration
  - Passed through generator chain to all analysis functions
  - Enables feature flags for optional expensive computations
  - JSON-serializable for template saving

- **Model Detection Integration**
  - Reuses existing LLMClient infrastructure
  - Handles both Ollama native API and OpenAI-compatible endpoints
  - Graceful error handling with actionable user feedback
  - No duplicate code between Ollama and LM Studio detection

**Power Supply - Now Stable** ✅
- Power supply support graduated from BETA to stable
- API is now considered production-ready
- Removed experimental warnings and beta tags
- Full support for SPD3303X series power supplies
- Installation: Standard package or `pip install "Siglent-Oscilloscope[power-supply-beta]"` (alias maintained)

**Pre-Commit Checks and Code Coverage** 🔍
- New `make pre-commit-branch` target for lightweight branch commit validation
  - Code formatting checks (Black, Flake8)
  - Fast parallel test execution
  - ~1 minute validation for rapid development
- Enhanced `make pre-pr` with codecov integration
  - Full test suite with coverage reporting
  - Automatic coverage upload to Codecov
  - Comprehensive validation before pull requests
- Codecov configuration (`.codecov.yml`)
  - 70-100% coverage range targets
  - Project and patch thresholds
  - Proper ignore patterns for tests, examples, docs
- Coverage documentation (`docs/development/PRE_COMMIT_CHECKS.md`)
  - Complete guide for pre-commit workflows
  - Coverage concepts and best practices
  - Troubleshooting and CI/CD integration

### Changed

**Documentation Updates**
- Updated README with comprehensive Automated Report Generation section
  - Installation instructions for `[report-generator]` extra
  - Code examples and feature highlights
  - Added to Features, Installation, Optional Extras, and Examples sections
- Removed BETA designation from power supply in documentation
- Enhanced package description with automated report generation features

**Project Organization**
- Reorganized main directory structure for better clarity
- Moved test/development scripts to `scripts/` directory:
  - `test_llm_model_detection.py`
  - `test_pdf_progress.py` and `test_report_progress.pdf`
  - `test_signal_detection.py`
  - `test_unicode_rendering.py` and `test_unicode_rendering.pdf`
- Moved `ICON_SETUP.md` to `docs/development/` for better organization
- Removed duplicate `codecov.yml` (keeping `.codecov.yml`)
- Cleaned up empty `node_modules/` directory
- Root directory now contains 22 essential files/directories

### Fixed

**Development Dependencies**
- Added `pytest-cov>=4.0.0` to dev dependencies
  - Fixes "unrecognized arguments: --cov" error
  - Ensures coverage plugin available after `pip install -e ".[dev]"`
- Added `codecov>=2.1.0` to dev dependencies
  - Required by `make codecov-report` and `make pre-pr`
  - Enables coverage uploads in development

**Makefile Pytest Integration**
- Updated all pytest calls to use `python -m pytest`
  - Ensures pytest-cov plugin is properly loaded
  - Fixes coverage generation in nested make calls
  - Updated targets: `test`, `test-cov`, `test-fast`, `test-exceptions`

## [0.4.0-beta.1] - 2026-01-04

### Added (EXPERIMENTAL 🧪)

**Power Supply Control** - BETA Release
- ⚠️ **EXPERIMENTAL**: Power supply API is unstable and may change without warning
- **Installation**: `pip install "Siglent-Oscilloscope[power-supply-beta]"`
- **Target Stable Release**: v0.5.0 (pending community feedback)
- **Feedback**: Please report issues at [GitHub Issues](https://github.com/little-did-I-know/Siglent-Oscilloscope/issues)

**Core Power Supply Features**:
- **Main PowerSupply Class** (`siglent.power_supply.PowerSupply`)
  - SCPI-based communication over Ethernet (port 5024) or USB
  - **Multiple connection types supported**:
    - **Ethernet/LAN** via `SocketConnection` (default)
    - **USB** via `VISAConnection` (new - requires `[usb]` extras)
    - **GPIB** via `VISAConnection` (IEEE-488)
    - **Serial** via `VISAConnection` (RS-232)
  - Automatic model detection from `*IDN?` response
  - Capability-based feature availability
  - Context manager support for automatic connection management
  - Support for multiple power supply models via capability registry

- **Model Support**:
  - **Siglent SPD3303X / SPD3303X-E** (triple output, 30V/3A + 30V/3A + 5V/3A)
    - Full feature support including OVP, OCP, timer, waveform generation, tracking modes
  - **Siglent SPD1305X** (single output, 30V/5A)
  - **Siglent SPD1168X** (single output, 16V/8A)
  - **Generic SCPI-99 PSUs** (fallback with conservative defaults)

- **Output Control** (`siglent.power_supply_output.PowerSupplyOutput`)
  - Voltage setpoint control with validation against model limits
  - Current limit configuration
  - Output enable/disable
  - Real-time voltage, current, and power measurements
  - Operating mode detection (CV/CC)
  - Over-voltage protection (OVP) and over-current protection (OCP) settings
  - Timer functionality (Siglent SPD specific)
  - Waveform generation enable/disable (SPD3303X specific)

- **Advanced Features**:
  - **Tracking Modes** for multi-output PSUs:
    - Independent mode (default)
    - Series tracking (voltages add)
    - Parallel tracking (currents add)
  - Dynamic output creation based on model capabilities
  - Model-specific SCPI command variants
  - Comprehensive error handling and logging

- **Model Registry and Capability System** (`siglent.psu_models`)
  - `PSUCapability` dataclass with complete model specifications
  - `OutputSpec` defining per-output voltage/current/power limits
  - Automatic model detection with fuzzy matching
  - Generic SCPI fallback for unknown models
  - Extensible registry for adding new models

- **SCPI Command Management** (`siglent.psu_scpi_commands`)
  - Model-specific command variants (Siglent SPD vs generic SCPI)
  - Template-based command generation with parameter substitution
  - Support for multiple SCPI dialects

- **Data Logging** (`siglent.psu_data_logger`)
  - **PSUDataLogger**: Manual data capture with configurable channels
  - **TimedPSULogger**: Automated time-series data collection
    - Configurable sampling intervals
    - Background thread-based acquisition
    - Real-time data access during logging
    - Export to CSV, JSON, or custom formats
  - Voltage, current, and power logging for all outputs
  - Timestamp-based data organization

- **Connection Layer** (`siglent.connection`)
  - **VISAConnection** class for USB/GPIB/Serial support (new)
    - PyVISA-based connection supporting multiple transport protocols
    - USB-TMC protocol for USB connections
    - GPIB (IEEE-488) support
    - Serial (RS-232) support
    - Optional dependency: install with `[usb]` extras
    - Pure Python backend (pyvisa-py) requires no proprietary drivers
  - **Resource discovery utilities**:
    - `list_visa_resources()` - List all VISA devices
    - `find_siglent_devices()` - Automatically find Siglent instruments
  - Graceful fallback when PyVISA not installed

- **Examples**:
  - `examples/psu_basic_control.py` - Basic voltage/current control, measurements (Ethernet)
  - `examples/psu_usb_connection.py` - USB/GPIB/Serial connection examples (new)
  - `examples/psu_advanced_features.py` - Tracking modes, data logging, timer, waveform generation
  - `examples/psu_gui_test.py` - GUI integration test (experimental)

- **Testing**:
  - `tests/test_power_supply.py` - Unit tests with mock connection
  - `tests/test_visa_connection.py` - Tests for USB/VISA connections (new)
  - Hardware tests marked with `@pytest.mark.hardware`
  - Coverage for core functionality, model detection, SCPI commands, VISA connections

**Documentation**:
- Added `docs/development/EXPERIMENTAL_FEATURES.md` - Comprehensive guide for experimental features
  - Guidelines for marking features as experimental
  - Version numbering strategies (alpha/beta/rc)
  - Installation and discovery patterns
  - Documentation standards
  - Testing requirements
  - Graduation and deprecation processes
- Updated `docs/development/contributing.md` with experimental features section
- Module docstrings with experimental warnings and installation instructions

### Changed

- **Version Bumped**: `0.3.2` → `0.4.0-beta.1`
  - Pre-release version indicates experimental status
  - Follows semantic versioning with beta tag

- **Package Description Updated**:
  - PyPI description now mentions power supply support (beta)
  - Added SPD series models to package description
  - New keywords: "power supply", "SPD", "PSU", "voltage", "current"

- **Export Structure**:
  - `siglent.__init__.py` clearly separates stable vs experimental exports
  - PowerSupply, PSUDataLogger, TimedPSULogger marked as experimental (v0.4.0-beta.1)
  - Documentation in docstring warns about experimental status

### Technical Details

**Experimental Feature Implementation**:
- Module-level `FutureWarning` on import with clear experimental notice
- Optional dependency groups in pyproject.toml:
  - `[power-supply-beta]` - Power supply features (no extra dependencies)
  - `[usb]` - USB/GPIB/Serial support via PyVISA (optional)
- `[experimental]` group added for future experimental features
- Graceful degradation when optional dependencies not installed

**Architecture Highlights**:
- **Connection abstraction layer** (`BaseConnection`)
  - `SocketConnection` for TCP/IP Ethernet (default)
  - `VISAConnection` for USB/GPIB/Serial (optional via PyVISA)
  - Consistent SCPI interface across all connection types
- Shares exception hierarchy (`SiglentConnectionError`, `SiglentTimeoutError`, `CommandError`)
- Capability-based design allows easy addition of new models
- SCPI command abstraction supports multiple manufacturers and SCPI dialects
- Pluggable transport layer - easy to add new connection types

**Known Limitations** (Beta Status):
- Limited hardware testing (primarily SPD3303X-E)
- Some SCPI commands may vary between models
- Timer and waveform generation features only tested on SPD3303X
- Remote sensing support not yet implemented
- No GUI integration for power supply control (gui test script only)

**API Stability Notice**:
- Power supply API may change in future releases without deprecation warnings
- Breaking changes possible in any 0.x release
- Recommend pinning to specific version for production use: `Siglent-Oscilloscope==0.4.0-beta.1`
- Feedback welcome to help stabilize API before v0.5.0 stable release

### Upgrading from 0.3.x

**For Oscilloscope Users** (No Changes Required):
- All oscilloscope functionality remains stable
- No breaking changes to existing APIs
- Update to `0.4.0-beta.1` is backward compatible

**For Power Supply Users** (New Feature):
```bash
# Install with power supply support (Ethernet/LAN only)
pip install "Siglent-Oscilloscope[power-supply-beta]==0.4.0-beta.1"

# Install with USB support (includes PyVISA for USB/GPIB/Serial)
pip install "Siglent-Oscilloscope[usb]==0.4.0-beta.1"

# Install both
pip install "Siglent-Oscilloscope[power-supply-beta,usb]==0.4.0-beta.1"
```

**For Developers**:
- See `docs/development/EXPERIMENTAL_FEATURES.md` for guidance on experimental features
- Power supply modules will show experimental warnings on import
- Set `PYTHONWARNINGS=default::FutureWarning` to see all warnings during development

## [0.3.1] - 2026-01-02

### Added
- **Comprehensive MkDocs Documentation**
  - Added complete user guide documentation (5 files, ~3,000 lines):
    - `basic-usage.md` - Foundation for connecting and controlling oscilloscope
    - `waveform-capture.md` - Advanced capture techniques and data formats
    - `measurements.md` - Automated measurement capabilities
    - `trigger-control.md` - Comprehensive trigger configuration
    - `advanced-features.md` - FFT, math channels, automation, protocol decoding
  - Added GUI documentation (7 files, ~4,700 lines):
    - `overview.md` - GUI introduction and installation
    - `interface.md` - Complete UI reference with keyboard shortcuts
    - `live-view.md` - Real-time waveform visualization
    - `visual-measurements.md` - Interactive measurement markers
    - `fft-analysis.md` - Frequency domain analysis
    - `protocol-decoding.md` - I2C/SPI/UART decoding
    - `vector-graphics.md` - XY mode and waveform generation
  - Added connection guide (~960 lines):
    - `connection.md` - Network setup, troubleshooting, VNC access
  - Added development documentation (3 files, ~2,950 lines):
    - `building.md` - Build system, testing, documentation generation
    - `structure.md` - Codebase organization and design patterns
    - `testing.md` - Testing strategy and best practices
  - Added API reference:
    - `gui.md` - Auto-generated GUI API docs using mkdocstrings
  - **Total: 17 documentation files, ~11,900 lines**
- Material for MkDocs theme with admonitions (tip, info, warning)
- Comprehensive examples, troubleshooting sections, and cross-references
- mkdocstrings integration for auto-generating API docs from Python docstrings

### Fixed
- **Windows Executable Build Workflow**
  - Fixed 7-Zip archive creation failing with "The system cannot find the file specified" errors
  - Updated Windows build workflow to correctly reference README.md and LICENSE from parent directory
  - Changed paths from `README.md LICENSE` to `../README.md ../LICENSE` to match macOS/Linux builds
  - Resolved workflow exit code 1 error during archive creation

## [0.3.0] - Unreleased

### ⚠️ BREAKING CHANGES

- **Exception Class Renaming** (Issue #3 from Code Review)
  - `ConnectionError` renamed to `SiglentConnectionError` to avoid shadowing Python's built-in `ConnectionError`
  - `TimeoutError` renamed to `SiglentTimeoutError` to avoid shadowing Python's built-in `TimeoutError`
  - **Migration Guide:**
    - Update imports: `from siglent.exceptions import SiglentConnectionError, SiglentTimeoutError`
    - Update exception handling: `except (SiglentConnectionError, SiglentTimeoutError) as e:`
    - Backward compatibility aliases provided for transition period (will be removed in v1.0.0)
    - If you use `from siglent import ConnectionError`, update to `from siglent import SiglentConnectionError`
  - **Why:** Prevents naming conflicts with Python built-ins, improves code clarity, follows best practices
  - **Impact:** All code that imports or catches `ConnectionError` or `TimeoutError` from siglent.exceptions needs updating

### Added
- **Waveform Validation System** (`siglent/gui/utils/validators.py`)
  - `WaveformValidator` class for comprehensive data quality checks
  - Validates waveform data before plotting or processing
  - Catches common issues that cause blank plots:
    - None/missing waveforms
    - Empty voltage or time arrays
    - Mismatched array lengths between time and voltage
    - All-NaN or excessive NaN values (>50%)
    - Invalid voltage ranges (all zeros, infinite values)
    - Suspiciously large voltages (>1000V)
  - `validate()` method returns (is_valid, list_of_issues)
  - `validate_multiple()` separates valid from invalid waveforms
  - `get_summary()` generates diagnostic strings like "CH1: 50,000 samples, range -2.5V to +2.5V"
- **Detailed Error Dialog Widget** (`siglent/gui/widgets/error_dialog.py`)
  - `DetailedErrorDialog` class for user-friendly error reporting
  - Two-level error display:
    - User-friendly summary for non-technical users
    - Expandable technical details (stack trace, context) for debugging
  - Features:
    - Error icon and timestamp display
    - "Show Details" / "Hide Details" toggle button
    - Read-only text area for stack traces and context
    - "Copy to Clipboard" button for comprehensive error reports
    - Automatic dialog resizing when showing/hiding details
  - Structured error info dictionary format:
    - `type`: Error type name (e.g., 'TimeoutError')
    - `message`: User-friendly error message
    - `details`: Additional error details
    - `context`: Dictionary of context info (operation, settings, etc.)
    - `traceback`: Full stack trace string
    - `timestamp`: Error occurrence time
  - Convenience function `show_error_dialog()` for quick usage
- **Real-Time Status Updates** (LiveViewWorker)
  - New `status_update` signal (pyqtSignal(str)) for user feedback
  - Status messages during acquisition cycle:
    - "Checking enabled channels..."
    - "Acquiring CH1...", "Acquiring CH2...", etc.
    - "Validating waveforms..."
    - "Live view: CH1, CH2 (50,000, 100,000 samples)"
    - "No enabled channels", "Not connected"
  - Status bar updates reflect worker progress in real-time

### Changed
- **LiveViewWorker Error Handling Enhanced**
  - Changed `error_occurred` signal from `pyqtSignal(str)` → `pyqtSignal(dict)`
  - Errors now emit structured dictionaries with full context
  - Error info includes:
    - Error type, message, details
    - Operation context (update_interval, operation name)
    - Full traceback for debugging
    - Timestamp for error tracking
  - Integration with `WaveformValidator` for data quality checks
  - Only emits valid waveforms (invalid ones logged at WARNING level)
  - Enhanced logging: acquisition results logged at INFO/WARNING for visibility
- **WaveformCaptureWorker Validation Integration**
  - Validates all captured waveforms before emitting via `WaveformValidator.validate_multiple()`
  - Logs validation failures at WARNING level (visible to users)
  - Only emits valid waveforms to prevent blank plots
  - Enhanced error messages include validation failure details
  - Progress message updated: "Processing waveforms..." → "Validating waveforms..."
- **WaveformDisplayPG Pre-Plot Validation**
  - Validates all waveforms before plotting via `WaveformValidator.validate_multiple()`
  - Invalid waveforms logged at WARNING level with specific issues
  - Info label shows "Invalid data - check logs" when all waveforms fail validation
  - Enhanced diagnostic logging:
    - Valid waveforms logged at INFO level with summary
    - Runtime validation checks for None and empty arrays
    - Voltage range logging: "[−2.5V to +2.5V]" or "[all NaN]"
  - Only stores and plots valid waveforms
- **Main Window Error Handling Integration**
  - Connected to new `status_update` signal from LiveViewWorker
  - New `_on_live_view_status()` method updates status bar with worker messages
  - Enhanced `_on_live_view_error()` method:
    - Accepts structured error dictionary instead of plain string
    - Shows `DetailedErrorDialog` for rich error information
    - Brief error message in status bar (60 chars max, 5 second timeout)
    - Fallback to QMessageBox for legacy string errors
  - User-friendly error display with expandable technical details

### Fixed
- **Blank Plot Issue from Invalid Waveforms**
  - Root cause: Invalid waveforms (None, empty arrays, all NaN) were being plotted
  - Solution: Comprehensive validation before plotting in all code paths
  - Workers now validate data before emitting to GUI
  - Display widget validates again before rendering as safety check
- **Cryptic Error Messages**
  - Users previously saw raw exception strings in status bar
  - Now see structured error dialogs with context and debugging info
  - Technical details hidden by default but available on demand
- **Missing Waveform Quality Diagnostics**
  - Added comprehensive validation with specific issue reporting
  - Users now see exactly why waveforms failed (e.g., "CH1: All voltage values are NaN")
  - Validation results logged at WARNING level for visibility
- **Bare Exception Handling in Vector Graphics** (Issue #2 from Code Review)
  - Replaced bare `except:` clauses with specific exception types in `vector_graphics.py`
  - Now catches `CommandError`, `SiglentConnectionError`, `SiglentTimeoutError` explicitly
  - Prevents catching system exceptions like `KeyboardInterrupt` and `SystemExit`
  - Improves debugging and error handling clarity
- **Socket Read Race Condition** (Issue #5 from Code Review)
  - Added timeout protection in `socket.py` read loop
  - Prevents infinite loop if oscilloscope doesn't send newline-terminated responses
  - Raises `SiglentTimeoutError` with detailed message showing bytes received
  - Improves reliability and error diagnostics
- **Version Mismatch** (Issue #1 from Code Review)
  - Fixed version inconsistency between `__init__.py` (0.1.0) and `pyproject.toml` (0.2.6)
  - Both now correctly report version 0.2.6 (will be bumped to 0.3.0 for this release)

### Technical Improvements
- **Input Validation for SCPI Commands** (Issue #4 from Code Review)
  - Added ASCII validation before encoding commands in `socket.py`
  - Raises `CommandError` with clear message if non-ASCII characters detected
  - Prevents `UnicodeEncodeError` exceptions during command transmission
  - Example: `CommandError: SCPI command contains non-ASCII characters: "C1:VDIV 1.0V\u2013"`
- **Magic Number Constants** (Issue #6 from Code Review)
  - Added named constants for waveform conversion in `waveform.py`:
    - `WAVEFORM_CODE_PER_DIV_8BIT = 25.0` (codes per division for 8-bit ADC)
    - `WAVEFORM_CODE_PER_DIV_16BIT = 6400.0` (codes per division for 16-bit ADC)
    - `WAVEFORM_CODE_CENTER = 0` (center code for signed integer data)
  - Improved code documentation with conversion formula from SCPI manual
  - Makes waveform parsing logic easier to understand and maintain
- Centralized waveform validation logic in reusable `WaveformValidator` class
- Structured error reporting enables better debugging and user support
- Separation of user-facing messages from technical diagnostics
- Thread-safe error propagation from workers to main GUI thread
- Validation happens at multiple checkpoints (capture → emit → display)
- All docstrings updated to reference new exception names
- Backward compatibility aliases ensure gradual migration path

## [0.2.6] - 2025-12-31

### Added
- **Background Waveform Capture Worker** (`waveform_capture_worker.py`)
  - Non-blocking waveform acquisition in separate thread
  - Progress updates during multi-channel capture
  - Cancellable long-running downloads
  - Thread-safe signal/slot architecture
  - Real-time status updates: "Downloading CH1 data from scope..."
- **Progress Dialog for Capture Operations**
  - Visual progress indication during waveform downloads
  - Shows channel-by-channel progress
  - Cancel button to abort slow captures
  - Auto-closes on completion
  - Prevents concurrent capture operations
- **Intelligent Waveform Downsampling**
  - Min-max decimation algorithm for large datasets
  - Preserves signal peaks, valleys, and transients
  - Configurable threshold (default: 500,000 points)
  - Downsamples 5M point waveforms to 500K for display
  - Original data fully preserved for export/analysis
  - Status indicator shows "(display downsampled)" when active
- **Modern Graph Visual Styling** (PyQtGraph)
  - GitHub-inspired dark theme (#0d1117 background)
  - Thicker, smoother waveform lines (2.0px with antialiasing)
  - Vibrant channel colors for better visibility:
    - CH1: Bright Yellow (255, 220, 50)
    - CH2: Turquoise/Cyan (64, 224, 208)
    - CH3: Hot Pink (255, 105, 180)
    - CH4: Bright Green (50, 255, 100)
  - Subtle dotted grid (20% opacity)
  - Modern typography (Segoe UI, 11pt labels)
  - Muted axis colors for professional appearance
  - Sample count with thousands separators (e.g., "5,000,000 samples")

### Changed
- **Waveform Capture Architecture Refactored**
  - Moved from synchronous to asynchronous capture model
  - Capture operations now run in `WaveformCaptureWorker` thread
  - Main GUI thread remains responsive during downloads
  - Enhanced error handling with user-friendly messages
- **Canvas Rendering Optimization** (Matplotlib)
  - Replaced all blocking `canvas.draw()` calls with `canvas.draw_idle()`
  - Removed redundant `canvas.update()`, `canvas.repaint()` calls
  - Deferred rendering prevents GUI thread blocking
  - Applied to 17+ instances across waveform_display.py
- **Downsampling Threshold Increased**
  - Changed from 100,000 to 500,000 point threshold
  - Provides 5x more waveform detail on display
  - Maintains smooth performance even with millions of samples
- **Progress Dialog Signal Handling Improved**
  - Disconnects `canceled` signal before closing to prevent race conditions
  - Only triggers cancellation if worker thread is actually running
  - Eliminates spurious "User cancelled capture" messages

### Fixed
- **Critical: GUI Freezing During Waveform Capture**
  - Fixed multi-second GUI freeze when capturing large waveforms (5M samples)
  - Root cause: Synchronous SCPI queries blocked main thread for 5-10+ seconds
  - Solution: Background worker thread handles all network I/O
  - GUI remains fully responsive during capture operations
- **Progress Dialog Race Condition**
  - Fixed spurious cancellation events when dialog auto-closed
  - Dialog now properly disconnects signals before closing
  - Prevents "cancelled" state after successful capture
- **Large Waveform Display Performance**
  - Fixed severe lag when plotting 5+ million point waveforms
  - PyQtGraph could still block GUI thread with massive datasets
  - Min-max downsampling reduces display points by 10x while preserving signal fidelity
- **Incomplete Waveform Display Issue**
  - Fixed waveforms not showing full captured data
  - Increased downsampling threshold from 100K to 500K points
  - Users now see 5x more detail in displayed waveforms

### Performance
- **Waveform Capture**: No longer blocks GUI (runs in background thread)
- **Display Rendering**: 10x faster for large waveforms via intelligent downsampling
- **Canvas Updates**: Non-blocking deferred rendering throughout
- **User Responsiveness**: Can interact with GUI during long captures

### Technical Improvements
- Thread-safe capture worker with Qt signals for status updates
- Signal/slot disconnect pattern prevents race conditions
- Min-max decimation preserves signal integrity during downsampling
- NumPy-optimized downsampling algorithm for performance
- Clean separation of capture, processing, and display concerns

## [0.2.5] - 2025-12-30

### Added
- **Buy Me a Coffee Badge**
  - Added support/donation badge to README
  - Links to https://buymeacoffee.com/little.did.i.know
- **Comprehensive Test Suite**
  - Added `tests/test_channel.py` - 50+ test cases for channel control (280 lines)
    - Tests for enable/disable, voltage scale, offset, coupling
    - Probe ratio, bandwidth limit configuration
    - Multi-channel validation
  - Added `tests/test_trigger_comprehensive.py` - 40+ test cases for trigger (320 lines)
    - Mode control (AUTO, NORMAL, SINGLE, STOP)
    - Source, level, slope configuration
    - Edge trigger setup and actions
    - Holdoff and coupling control
  - Added `tests/test_measurement_comprehensive.py` - 45+ test cases for measurements (340 lines)
    - Frequency, period, Vpp, RMS, amplitude measurements
    - Min/max/mean voltage measurements
    - Timing measurements (rise/fall time, duty cycle)
    - Statistical measurements and cursor support
  - Added `tests/test_waveform_comprehensive.py` - 35+ test cases for waveform handling (280 lines)
    - WaveformData creation and properties
    - Binary waveform capture and parsing
    - Multi-format save/load (CSV, NPZ, MAT, HDF5)
    - Waveform analysis and comparison
  - Added `tests/test_socket_connection.py` - 33+ test cases for connection (270 lines)
    - Connection lifecycle (connect, disconnect, reconnect)
    - Command sending and querying
    - Binary data queries
    - Context manager and error handling
  - **Total: 490+ new test cases across 5 test modules**
- **Test Coverage and Quality Assurance**
  - Integrated pytest with coverage reporting in CI workflow
  - Added Codecov integration for test coverage tracking and visualization
  - Multi-version testing across Python 3.8-3.12
  - Coverage badge display on GitHub and PyPI
  - **Coverage Improvement**: Overall coverage increased from 39% to 42%
    - channel.py: Enhanced test coverage with comprehensive scenarios
    - trigger.py: Added extensive mode and configuration tests
    - measurement.py: Added tests for all measurement types
    - waveform.py: Added capture, save/load, and analysis tests
    - connection/socket.py: Added full connection lifecycle tests
- **Professional Project Badges**
  - CI build status badge (GitHub Actions)
  - Test coverage badge (Codecov)
  - PyPI downloads per month badge
  - GitHub issues tracker badge
  - GitHub stars badge
  - Last commit timestamp badge
- **Codecov Configuration**
  - Added `codecov.yml` with project-specific settings
  - Configured coverage thresholds and reporting
- **Pytest Configuration**
  - Added `[tool.pytest.ini_options]` to `pyproject.toml`
  - Configured test markers for hardware and GUI tests
  - Added strict pytest configuration for better test quality
- **Contributing Guide**
  - Comprehensive `CONTRIBUTING.md` with development guidelines
  - Code style, testing, and PR submission instructions
  - Development setup and best practices documentation
- **Community Standards**
  - Added `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1)
    - Private reporting contacts (email, GitHub, security advisory)
    - Clear enforcement responsibilities (maintainers defined)
    - Anti-retaliation policy
    - Step-by-step "What Happens Next" process
    - Appeals process for disputed decisions
  - Added `SECURITY.md` with vulnerability reporting process
  - Added security best practices and safe usage guidelines
- **Development Automation**
  - Added `.pre-commit-config.yaml` for automated code quality checks
  - Configured Black, Flake8, isort, Bandit security scanning
  - Added file cleanup and validation hooks
- **Makefile for Development**
  - Added comprehensive Makefile with common development tasks
  - Commands for testing, linting, formatting, building, publishing
  - Quick setup commands: `make dev-setup`, `make check`
  - Shortcuts: `make test-cov`, `make format`, `make gui`
  - Pre-PR commands: `make pre-pr`, `make pre-pr-fast`, `make pre-pr-fix`
- **Pre-PR Validation Scripts**
  - Added `scripts/pre_pr_check.py` - Comprehensive Python validation script
  - Added `scripts/pre_pr_check.sh` - Bash version for Unix-like systems
  - Automated checks: formatting, linting, security, tests, coverage, build
  - Options: `--fast` (skip slow checks), `--fix` (auto-fix issues)
  - Color-coded output with detailed error reporting
- **GitHub Issue Templates**
  - Structured bug report template (`.github/ISSUE_TEMPLATE/bug_report.yml`)
  - Feature request template (`.github/ISSUE_TEMPLATE/feature_request.yml`)
  - Issue template configuration with links to discussions
- **Pull Request Template**
  - Comprehensive PR template (`.github/PULL_REQUEST_TEMPLATE.md`)
  - Checklists for code quality, testing, and documentation
  - Sections for type of change, testing details, and migration guides
- **Dependabot Configuration**
  - Automated dependency updates (`.github/dependabot.yml`)
  - Weekly updates for Python packages and GitHub Actions
  - Grouped updates by dependency type (dev, security, GUI, core)
- **Interactive Tutorial**
  - Jupyter notebook tutorial (`examples/interactive_tutorial.ipynb`)
  - Step-by-step guide for oscilloscope control
  - Examples of waveform capture, FFT analysis, measurements
  - Multi-channel capture and data export demonstrations

### Changed
- **SEO and PyPI Metadata Improvements**
  - Enhanced package description with comprehensive feature highlights for better discoverability
  - Expanded keywords from 7 to 20 terms covering automation, data acquisition, GUI, protocol decoding, and visualization
  - Improved search ranking for oscilloscope automation, SCPI control, and lab equipment software
- **CI/CD Enhancements**
  - Enhanced CI workflow with dedicated test suite job
  - Added pytest-cov and pytest-xdist dependencies
  - Improved test execution with verbose output and coverage reporting
- **Test Organization**
  - Moved manual test scripts to `scripts/` directory
  - Reorganized interactive GUI tests as manual scripts
  - Ensured automated tests properly handle optional dependencies
- **README Improvements**
  - Added Community and Support section with links to issues, discussions, security
  - Added Resources section highlighting tutorial, examples, and guides
  - Added Quick Start for Contributors with Makefile commands
  - Improved Contributing section with detailed instructions

### Fixed
- **Test Suite Issues**
  - Fixed CI test failures due to missing PyQt6 dependencies
  - Moved manual test scripts (`test_live_view.py`, `test_pyqtgraph.py`, `test_dependency_check.py`, `test_waveform_display.py`) to `scripts/` directory
  - Prevented pytest from collecting non-test GUI demo scripts
  - Ensured GUI tests skip gracefully when PyQt6 is not installed
  - Fixed hanging test in `test_socket_connection.py::TestSocketQueryBinary::test_query_binary`
    - Test was using `mock_socket.recv.return_value` which caused infinite loop in `read_raw()`
    - Changed to `side_effect` to return data once then raise timeout to signal end of data
- **Python 3.8 Compatibility**
  - Fixed `pyproject.toml` license field to use PEP 621 compliant format
  - Changed `license = "MIT"` to `license = {text = "MIT"}` for Python 3.8 compatibility
  - Resolved build errors in older setuptools versions

## [0.2.4] - 2025-12-29

### Added
- **Vector Graphics / XY Mode Features** (requires `[fun]` extras)
  - New `vector_graphics.py` module for generating waveforms for XY mode display
  - `VectorDisplay` class for managing XY mode and waveform generation
  - `Shape` factory with generators for:
    - Basic shapes: circle, rectangle, polygon, star, line
    - Lissajous figures for classic oscilloscope patterns
    - Text rendering (experimental)
  - `VectorPath` class with transformation methods (rotate, scale, translate, flip)
  - Waveform export to CSV, NumPy, and binary formats for AWG upload
  - **GUI Integration**: New "Vector Graphics 🎨" tab in GUI application
    - Shape selection with dynamic parameter controls (Circle, Rectangle, Star, Triangle, Lissajous, Line)
    - XY mode enable/disable directly from GUI
    - Waveform generation with sample rate and duration controls
    - Export to CSV, NumPy, or Binary format for AWG upload
    - Works even without scope connection (offline waveform generation)
    - Graceful degradation: shows installation instructions if `[fun]` extras not installed
  - Example script: `examples/vector_graphics_xy_mode.py` with animations
  - Optional dependency group `[fun]` in pyproject.toml:
    - shapely>=2.0.0 (geometric operations)
    - Pillow>=10.0.0 (text rendering)
    - svgpathtools>=1.6.0 (SVG path support)

### Changed
- Updated README.md with comprehensive Vector Graphics / XY Mode section
  - Added GUI tab documentation with step-by-step usage instructions
  - Added example use cases (calibration, education, pattern testing)
  - Updated installation instructions to include `[fun]` extras option
  - Added `[fun]` to Optional Extras requirements section
- Updated `siglent/gui/main_window.py` to integrate Vector Graphics tab
- Updated `siglent/gui/widgets/__init__.py` with import note for optional panel

## [0.2.3] - 2025-12-29

### Changed
- project.toml version number due to pypi version number conflict

## [0.2.2] - 2025-12-29

### Changed
- **GitHub Workflow Updates**
  - Simplified PyPI publishing workflow
  - Removed TestPyPI publishing step for streamlined releases
  - Workflow now publishes directly to PyPI on releases or manual trigger

## [0.2.1] - 2025-12-29

### Changed
- **Project Structure Reorganization** to follow Python packaging best practices
  - Moved all test files to `tests/` directory
  - Moved development utilities to `scripts/` directory
  - Consolidated documentation into `docs/` directory
  - Created `docs/development/` for build and deployment documentation
  - Updated MANIFEST.in to properly exclude development files from distribution
  - Updated .gitignore to properly exclude build artifacts
  - Added `docs/development/PROJECT_STRUCTURE.md` documenting the project layout

### Fixed
- Improved .gitignore to properly exclude dist/, build/, and egg-info directories

## [0.2.0] - 2025-12-29

### Added
- **High-Performance Live View** with PyQtGraph
  - 100x faster real-time plotting (1000+ fps capability vs 5-10 fps)
  - Replaced matplotlib with PyQtGraph for live waveform display
  - Non-blocking threaded data acquisition
  - Smooth updates at 5-20 fps with responsive GUI
  - Supports all 4 channels simultaneously
- **Interactive Visual Measurement System**
  - Click-and-drag measurement markers directly on waveforms
  - 15+ measurement types with specialized visual markers:
    - Frequency/Period with auto-detection
    - Voltage measurements (Vpp, Amplitude, Max, Min, RMS, Mean)
    - Timing measurements (Rise Time, Fall Time, Pulse Width, Duty Cycle)
  - Real-time measurement updates as you adjust marker gates
  - Visual gates and markers with color-coded styling
  - Auto-placement with intelligent positioning
- **Measurement Configuration Management**
  - Save measurement setups to JSON files
  - Load previously saved configurations
  - Configuration browser and management
  - Shareable measurement templates
- **Measurement Export Functionality**
  - Export results to CSV format
  - Export to JSON with full configuration
  - Batch measurement support
  - Timestamp and metadata inclusion
- **Background Worker Thread** (`LiveViewWorker`)
  - Prevents GUI freezing during SCPI queries
  - Thread-safe signal/slot communication
  - Configurable update intervals (default: 200ms)
  - Automatic error handling and reporting
- **Visual Measurement Panel** (`visual_measurement_panel.py`)
  - Add/remove markers via UI
  - Enable/disable individual markers
  - Live measurement value display
  - Auto-update mode with 1-second refresh
  - Marker list with real-time results
- **New Measurement Marker Classes**
  - Base `MeasurementMarker` abstract class
  - `FrequencyMarker` with period auto-detection
  - `VoltageMarker` with threshold visualization
  - `TimingMarker` with edge detection
- **PyQtGraph-based Waveform Display** (`waveform_display_pg.py`)
  - Drop-in replacement for matplotlib display
  - Preserved all existing features (cursors, zoom, pan)
  - Optimized update performance
  - Configurable visual styling
- **Measurement Data Models** (`measurement_config.py`)
  - `MeasurementMarkerConfig` dataclass
  - `MeasurementConfigSet` for collections
  - JSON serialization/deserialization
  - Configuration validation

### Changed
- Migrated live view from matplotlib to PyQtGraph for dramatic performance improvement
- Replaced timer-based acquisition with threaded worker pattern
- Enhanced waveform display with marker support methods
- Updated main window to integrate visual measurement panel
- Improved channel enabled detection to handle scope response format

### Fixed
- **Channel Detection Bug**: Fixed `channel.enabled` property failing to detect "C1:TRA ON" response format (channel.py:48)
- **GUI Freezing**: Moved blocking SCPI queries to background thread to maintain GUI responsiveness
- **Live View Startup**: Removed non-existent `refresh_state()` call that caused crashes
- **Waveform Update Performance**: Eliminated unnecessary canvas redraws during live view

### Dependencies
- Added `pyqtgraph>=0.13.0` to GUI dependencies
- Updated installation instructions for `[gui]` extra

### Technical Improvements
- Thread-safe Qt signal/slot architecture for live updates
- Abstract base class pattern for extensible measurement markers
- Dataclass-based configuration management
- Separation of rendering and calculation logic
- Optimized matplotlib blitting for fast partial updates (fallback mode)
- Coordinate system handling for zoom/pan compatibility

### Performance
- Live view: 100x faster (5-10 fps → 1000+ fps capability)
- SCPI queries: Moved to background thread (GUI unblocked)
- Canvas updates: <1ms per frame vs 100-500ms previously
- Measurement calculations: Real-time NumPy-based processing

## [0.1.0] - 2025-12-25

### Added
- Initial release of Siglent oscilloscope control package
- Complete programmatic API for controlling Siglent SD824x HD oscilloscopes
- TCP/IP socket connection via SCPI protocol (port 5024)
- Full channel control (all 4 channels)
  - Voltage scale and offset configuration
  - Coupling mode (DC/AC/GND)
  - Probe ratio settings
  - Bandwidth limiting
- Comprehensive trigger control
  - Trigger modes (Auto, Normal, Single, Stop)
  - Edge trigger configuration
  - Source selection and level control
  - Slope and coupling settings
- Waveform acquisition and processing
  - Binary waveform download
  - Automatic voltage conversion
  - NumPy array output
  - CSV and NPY export formats
- Automated measurements
  - Frequency, period, Vpp, RMS, amplitude
  - Rise/fall time, duty cycle
  - Min/max/mean calculations
  - Cursor support
- PyQt6-based GUI application
  - Connection management dialog
  - Acquisition controls (Run/Stop/Single)
  - Live waveform view with configurable update rate
  - Single waveform capture
  - Multi-channel matplotlib display with oscilloscope-style theming
  - Interactive zoom and pan
  - Waveform export to PNG/PDF/SVG
- Console script entry point (`siglent-gui`)
- Comprehensive example scripts
  - Basic usage and configuration
  - Waveform capture and export
  - Automated measurements
  - Live plotting
- Full documentation
  - API documentation in README
  - PyPI deployment guide
  - Build instructions
  - Example scripts with explanations

### Technical Details
- Python 3.8+ support
- Dependencies: PyQt6, NumPy, Matplotlib
- MIT License
- Type hints throughout codebase
- Context manager support for oscilloscope connections
- Comprehensive error handling with custom exceptions

[0.1.0]: https://github.com/siglent-control/siglent/releases/tag/v0.1.0
