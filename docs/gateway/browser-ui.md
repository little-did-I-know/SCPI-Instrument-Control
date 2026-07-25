# Browser UI Tour

This page walks through the gateway's browser interface tab by tab. There
are no screenshots yet — read this alongside a running gateway
(`scpi-web`) and follow along.

## Home screen

The home screen is split into two zones: sessions already held by the server
(each with an **Open** button to jump back in) and devices discovered on the
LAN (each with a **Connect** button to start a session). Both zones group
entries by kind and support search. A recent-connections list remembers
addresses you've used before, and a manual-connect field lets you type an IP
directly if discovery doesn't find it. A mock scope is always available here
too, so there's never a hardware requirement to get started.

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
- **Terminal** — send raw SCPI commands. A trailing `?` sends it as a query
  and shows the response; anything else is a bare write.

## Toolbar

Across the top: Run / Stop / Single / Auto acquisition controls, the canvas
view-mode toggle, CSV / JSON / Screenshot export buttons, and Disconnect.

## Multi-tab behavior

The server is the single source of truth for a session. Open the same
session in two browser tabs (or two different browsers) and they stay in
sync: acquisition state, the measurement selection, the active reference
overlay, and trend-recording status all update live across every connected
tab.
