# Web Gateway

The web gateway is a lab-gateway server built on FastAPI: run it on a PC that
sits near your instruments, and any browser on the LAN gets a full
oscilloscope UI — no client install, no drivers, just a URL. V1 is
scope-only, and the server supports named multi-sessions, so several
instruments (or several views of the same instrument) can be open at once.

## Install and run

```bash
pip install "SCPI-Instrument-Control[web]"
```

Requires Python 3.9 or newer. Start the server with either of:

```bash
scpi-web
# or
python -m scpi_control.server
```

By default the gateway listens on `http://127.0.0.1:8765`.

## Security posture

The server binds to `127.0.0.1` by default, so it is not reachable from the
network until you opt in. Exposing it to the LAN is an explicit choice:

```bash
scpi-web --host 0.0.0.0
```

There is **no authentication** in this release. Anyone who can reach the
gateway's port can control the connected instruments. Only bind to `0.0.0.0`
on networks you trust.

## Mock-first

You don't need hardware to try the gateway. The home screen always offers a
mock oscilloscope session (`mock: true`), and every feature — waveform
streaming, math, spectrum, filters, references, trend logging, the SCPI
terminal — works against it exactly as it would against a real scope. This
makes the gateway a good way to explore the library's capabilities before
ever plugging in an instrument.

## What it does

- **Live waveform streaming** over a WebSocket, so the display updates as the
  instrument acquires
- **Channel, timebase, trigger, and run controls** (Run/Stop/Single/Auto)
  from the browser
- **LAN discovery** and a dashboard home screen that lists reachable
  instruments alongside sessions you already have open
- **Measurements** (legacy dialect) with live cross-tab selection sync
- **Math channels** M1/M2 with user-defined expressions
- **FFT spectrum view**, computed server-side
- **Software filters** F1/F2 (lowpass/highpass/bandpass)
- **Reference waveforms** with a live overlay and comparison stats
  (correlation, max deviation)
- **Measurement trend recording**, with CSV export
- **A SCPI terminal** for raw commands
- **Screenshot, CSV, and JSON export** of the current waveform

## Where to next

- [Browser UI Tour](browser-ui.md) — a walkthrough of the home screen, canvas
  modes, and rail tabs
- [REST & WebSocket API](api.md) — the complete wire reference, with a curl
  quickstart
