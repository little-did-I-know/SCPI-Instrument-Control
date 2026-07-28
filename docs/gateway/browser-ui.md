# Browser UI Tour

This page walks through the gateway's browser interface tab by tab. There
are no screenshots yet — read this alongside a running gateway
(`scpi-web`) and follow along.

## Signing in

Before the home screen there is a **Sign in** panel with a single **Join code**
field: type the six digits your lab admin read out and press **Connect**. An
invitation link (`…/?invite=…`) skips this screen entirely — it redeems itself
as the page loads. Automation authors, who hold an `scpi_…` token rather than a
code, will find an **I have an access token** disclosure below the field. See
[Gateway security](security.md#inviting-someone) for where codes come from.

## Home screen

The home screen is split into two zones: sessions already held by the server
(each with an **Open** button to jump back in) and devices discovered on the
LAN (each with a **Connect** button to start a session). Both zones group
entries by kind — oscilloscope, power supply, or AWG — and support search. A
recent-connections list remembers addresses you've used before, and a
manual-connect field lets you type an IP directly if discovery doesn't find
it. A mock oscilloscope, mock power supply and mock function generator are
all available here too — one button per connectable instrument kind — so
there's never a hardware requirement to get started with any of them.

The next section, Header, describes chrome that looks the same no matter
which instrument kind is connected. The three sections after it — Canvas
modes, Rail tabs, and Toolbar — describe an oscilloscope session
specifically. A power supply or function generator session replaces all of
it with its own panel; see [Power supply session](#power-supply-session) and
[Function generator session](#function-generator-session) below.

## Header

The header spans the top of the window and looks the same no matter which
instrument kind is connected: the connection status indicator, a
**read-only** badge with a **Claim** button when the session belongs to
someone else (the same control the home screen offers — see
[Home screen](#home-screen) above), the **Terminal** button (see
[SCPI terminal](#scpi-terminal) below), and **Disconnect**, which ends the
session and returns to the home screen. Because it's in the header rather
than an instrument-specific toolbar, Disconnect is available for every
session kind — a power supply or function generator session no longer has
to be abandoned by reloading the page.

Directly under the header, an error banner appears when the session itself
fails — a dropped stream, or an error frame from the instrument — carrying
the detail that a red status dot alone can't show. Dismissing the banner
clears the message but does **not** change what the status indicator
reports: the connection state is the instrument's to report, not a side
effect of closing a notification.

## Canvas modes

Once connected, the main canvas toggles between three modes:

```
[ Time | Spectrum | Trend ]
```

- **Time** — live traces. Channels are drawn as solid lines, math traces
  (M1/M2) and filters (F1/F2) as dashed lines, and an active reference
  waveform as a gray ghost trace overlaid on the live signal.
- **Spectrum** — a server-computed FFT of a chosen channel, with peak
  markers and a THD readout. If spectrum analysis is off, the canvas shows
  an **Enable** button instead of a plot.
- **Trend** — recorded measurement series over time, one line per series
  with independent auto-scaling and a legend showing the latest, min, and
  max value for each. Before any recording has been made, this mode shows an
  empty state prompting you to "start one in the Log tab."

## Rail tabs

The side rail holds one tab per feature area:

- **Channels** — per-channel enable, V/div, offset, coupling, and probe
  ratio.
- **Trigger** — mode, source, level, slope, and coupling.
- **Math** — configure the M1/M2 expressions, e.g. `C1 - C2` or `INTG(C1)`.
- **Analysis** — spectrum configuration (source channel, window function,
  dB scale) and the two filter slots F1/F2 (kind, cutoff(s), order).
- **Reference** — save a named snapshot of a channel's current waveform,
  toggle Show/Hide to overlay it on the live trace, and read live
  correlation and max-deviation stats against the current signal.
- **Log** — start/stop trend recording, watch a live row counter, and
  download the result as CSV. **The measurement selection locks while a
  recording is active**, so you can't change what's being recorded mid-run.
- **Measure** — per-channel measurement checkboxes with live values, on every
  supported dialect (see [SCPI Dialects](../user-guide/scpi-dialects.md) for
  how each one is wired up).

## Toolbar

Across the top: Run / Stop / Single / Auto acquisition controls, the canvas
view-mode toggle, and CSV / JSON / Screenshot export buttons. Disconnect
lives in the header, not here — see [Header](#header) above, since it applies
to every session kind, not just an oscilloscope's.

## Power supply session

A power supply session's panel gives every output a voltage setpoint, a
current-limit setpoint, and an on/off switch, one group box per output. A
readout strip above the panel shows what the supply actually reports —
measured voltage, current, and power for each output, and whether it's live —
which is not the same as the setpoints just entered: the readout reflects the
instrument's own measurement, not an echo of what was sent. A setpoint the
supply won't answer shows as `--.--`, and an output whose on/off state it
won't report (an SPD3303X's CH3 has no output-state query at all) shows as
unknown rather than a confident off.

## Function generator session

A function generator session's panel gives every channel a waveform picker
(sine, square, ramp, pulse, noise, arbitrary, or DC), and setpoints for
frequency, amplitude, offset, and phase, plus an on/off switch — one group box
per channel. Duty cycle appears only when that channel's waveform is a pulse,
and symmetry only when it's a ramp; neither field appears for any other
waveform. One "All outputs off" button below the channels kills every output
in a single request, rather than one click per channel.

Above the panel, a readout strip shows one card per channel with what the
generator reports back, including channels that are currently off — for a
source, "is this output driving my circuit?" is exactly what the strip
answers. These are read-back values, not echoes of the setpoints: an AWG
clamps amplitude against its load setting and snaps frequency to its
resolution, so the reading can differ from what was asked for. A value the
generator won't answer shows as `--.--`, and a channel whose on/off state it
won't report shows as unknown rather than a confident off.

## SCPI terminal

The console for sending raw SCPI commands is no longer a rail tab — it lives
in a **Terminal** button in the header, next to the connection status. Click
it to open a full-width drawer below the rest of the session (Escape closes
it too); a trailing `?` sends your command as a query and shows the response,
anything else is a bare write. Because it lives in the header rather than the
scope's rail, it is available for **every** connected instrument kind, not
just a scope — a power supply session gets the same drawer for anything its
panel doesn't expose.

## Multi-tab behavior

The server is the single source of truth for a session. Open the same
session in two browser tabs (or two different browsers) and they stay in
sync: acquisition state, the measurement selection, the active reference
overlay, and trend-recording status all update live across every connected
tab.
