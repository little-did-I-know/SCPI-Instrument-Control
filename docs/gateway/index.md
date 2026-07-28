# Web Gateway

The web gateway is a lab-gateway server built on FastAPI: run it on a PC that
sits near your instruments, and any browser on the LAN gets a full
instrument UI — no client install, no drivers, just a URL. It started
scope-only; the gateway can now also host a power supply or a function
generator, each with its own control panel, and the server supports named
multi-sessions, so several instruments (or several views of the same
instrument) can be open at once.

> **Security first:** every request needs a bearer token. Read the
> **[Gateway security guide](security.md)** for invitations, tokens, session
> ownership, the SSRF gate, and deployment guidance before exposing the
> gateway beyond `127.0.0.1`.

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

By default the gateway listens on `http://127.0.0.1:8765`, and prints that URL
every time it starts. On the very first run — when no tokens exist yet — it
also mints one and prints it in the URL (`http://127.0.0.1:8765/?token=…`);
open that to reach the browser UI.

To give someone else access, run `scpi-web invite <name>` on the gateway host.
It prints a link and a six-digit code, both good for ten minutes and for one
sign-in; send either. Nobody but you needs to handle a raw token.

## Security posture

Every `/api/*` route requires a valid bearer token, except `GET /api/health`
and `POST /api/join` (which redeems an invitation, and so cannot require the
credential it hands out). The server also binds to
`127.0.0.1` by default, so it is not reachable from the network until you opt
in. Exposing it to the LAN is an explicit choice:

```bash
scpi-web --host 0.0.0.0
```

See the **[Gateway security guide](security.md)** for the full model: tokens,
session ownership, the SSRF gate that validates outbound connection targets,
the session cap, and deployment guidance (TLS, reverse proxies).

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
- **Power supply and function generator sessions**, each with their own
  control panel and live readout strip, alongside the oscilloscope

## Where to next

- [Gateway security](security.md) — invitations, tokens, session ownership,
  the SSRF gate, and deployment guidance
- [Browser UI Tour](browser-ui.md) — a walkthrough of the home screen, canvas
  modes, and rail tabs
- [REST & WebSocket API](api.md) — the complete wire reference, with a curl
  quickstart
