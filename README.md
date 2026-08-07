# SCPI Instrument Control

[![CI](https://github.com/little-did-I-know/SCPI-Instrument-Control/actions/workflows/ci.yml/badge.svg)](https://github.com/little-did-I-know/SCPI-Instrument-Control/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/SCPI-Instrument-Control.svg)](https://pypi.org/project/SCPI-Instrument-Control/)
[![Python Version](https://img.shields.io/pypi/pyversions/SCPI-Instrument-Control)](https://pypi.org/project/SCPI-Instrument-Control/)
[![codecov](https://codecov.io/gh/little-did-I-know/SCPI-Instrument-Control/branch/main/graph/badge.svg)](https://codecov.io/gh/little-did-I-know/SCPI-Instrument-Control)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://little-did-I-know.github.io/SCPI-Instrument-Control/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Drive your whole bench from Python.** Oscilloscopes, function generators, power
supplies, and DAQ units — one API, over LAN, USB, GPIB, or serial.

Point it at an IP address and it identifies the instrument, picks the right SCPI
dialect, and gets out of your way. Or point it at nothing at all: the built-in
mock synthesizes real waveforms so you can write and test the entire acquisition
pipeline with an empty bench.

<p align="center">
  <!-- Absolute raw URLs, not repo-relative paths: PyPI renders this README as a
       standalone document with no repo context, so a relative src has nothing to
       resolve against and the image silently fails to load there. -->
  <img src="https://raw.githubusercontent.com/little-did-I-know/SCPI-Instrument-Control/main/docs/images/mock-demo.gif" alt="A terminal session capturing a 1 kHz square wave from the built-in mock scope with no instrument attached" width="760">
</p>

## Try it with no instrument on your desk

```bash
pip install SCPI-Instrument-Control
```

```python
from scpi_control.connection import MockConnection
from scpi_control.oscilloscope import Oscilloscope
from scpi_control.signal_synth import SignalSpec

# A virtual SDS1104X-E probing a 3.3 V, 1 kHz logic clock.
scope = Oscilloscope("mock", connection=MockConnection(
    "mock",
    channel_states={1: True},
    signals={1: SignalSpec(kind="square", frequency=1000.0, amplitude=1.65, offset=1.65)},
    sample_rate=20e6,
    timebase=500e-6,
))
scope.connect()

wf = scope.get_waveform(channel=1)
print(f"{len(wf.time)} samples")
print(f"Vpp  {wf.voltage.max() - wf.voltage.min():.3f} V")
print(f"Freq {scope.measurement.measure_frequency(1):.2f} Hz")
```

```text
14000 samples
Vpp  3.280 V
Freq 1000.00 Hz
```

Those are the same 3.28 V rails as the real SDS824X&nbsp;HD calibration square
wave further down this page — captured with nothing plugged in.
The mock is not a stub replaying a canned buffer: every sample is computed from
the scope's current timebase, volts/division, offset, and trigger state, so the
capture window follows the timebase, the code grid quantizes the way an 8-bit
digitizer does, and free-running acquisitions drift in phase like a real one.
Your CI can exercise the full stack with nothing plugged in.

## What you get

|  | |
|---|---|
| **One API, many vendors** | Siglent, Tektronix, and LeCroy scopes auto-detected from `*IDN?`, plus AWGs, PSUs, and DAQ units. Unknown models fall back to a conservative per-vendor profile instead of being rejected. |
| **Capture with provenance** | Every saved waveform records the instrument, settings, and timestamp that produced it. Read any of it back with `load_waveform()` or the `scpi-extract` CLI. |
| **Analysis built in** | FFT, SNR, THD, jitter, rise/fall, and 25+ statistics — no separate toolchain. |
| **A real desktop GUI** | PyQt6 + PyQtGraph live view with draggable measurement markers. |
| **A browser lab gateway** | Share an instrument with the bench next door over HTTP/WebSocket. |
| **Publication-ready reports** | Automated PDF/Markdown test reports, optionally analyzed by a local LLM. |

### Honest about limits

This project would rather raise than invent a number. Setting a trigger type a
scope's dialect cannot express raises `FeatureNotSupportedError` instead of
silently leaving the instrument as it was; a PSU without a documented protection
subsystem refuses `ovp_level` rather than sending a command the firmware
discards. Tektronix and LeCroy command tables were verified line-by-line against
the vendor programming manuals and exercised against a dialect-aware mock, but
have **not** yet been run against physical Tektronix or LeCroy hardware — the
Siglent path has.

## Install

```bash
pip install SCPI-Instrument-Control          # core: capture + analysis
pip install "SCPI-Instrument-Control[all]"   # everything below
```

| Extra | Adds |
|---|---|
| `[gui]` | PyQt6 desktop application, live view, visual measurements |
| `[web]` | `scpi-web` browser lab gateway (FastAPI) |
| `[report-generator]` | PDF/Markdown test reports, local-LLM analysis |
| `[usb]` | USB-TMC, GPIB, and serial instruments via PyVISA |
| `[hdf5]` | `.h5` waveform export |
| `[fun]` | Vector graphics / XY-mode drawing |

Requires Python 3.9+. The core install needs only NumPy, SciPy, and Matplotlib.

## Then point it at real hardware

<p align="center">
  <img src="https://raw.githubusercontent.com/little-did-I-know/SCPI-Instrument-Control/main/docs/images/sds824x-hd-cal-square.png" alt="Live screen capture pulled over LAN from a Siglent SDS824X HD oscilloscope" width="700">
  <br>
  <em>Not a mockup — a live screen grab pulled over LAN from a Siglent
  SDS824X&nbsp;HD with <code>scope.screen_capture.get_screenshot_pil()</code>.</em>
</p>

```python
from scpi_control import Oscilloscope

scope = Oscilloscope("192.168.1.100")   # dialect auto-detected from *IDN?
scope.connect()

scope.channel1.enable()
scope.channel1.voltage_scale = 1.0      # V/div
scope.channel1.coupling = "DC"

scope.trigger.set_edge_trigger(source="C1", slope="POS")
scope.trigger.level = 1.0

wf = scope.get_waveform(channel=1)
scope.waveform.save_waveform(wf, "capture.npz")   # provenance travels with it

scope.disconnect()
```

Ask the instrument what it can actually do before you ask it to do something:

```python
caps = scope.capabilities
print(caps.trigger_types, caps.channel_couplings)
```

Batch sweeps, continuous logging, and trigger-driven capture live in
`scpi_control.automation` — see the
[automation guide](https://little-did-I-know.github.io/SCPI-Instrument-Control/user-guide/advanced-features/).

## The desktop GUI

```bash
pip install "SCPI-Instrument-Control[gui]"
siglent-gui
```

<p align="center">
  <img src="https://raw.githubusercontent.com/little-did-I-know/SCPI-Instrument-Control/main/docs/images/gui-live-view.png" alt="The PyQt6 desktop application showing two live channels — a 1 kHz square wave and a noisy sine" width="860">
  <br>
  <em>Two channels live. This one is the mock again — the desktop app runs
  hardware-free too.</em>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/little-did-I-know/SCPI-Instrument-Control/main/docs/images/gui-fft.png" alt="FFT tab showing the odd-harmonic comb of a square wave with the first three peaks marked" width="860">
  <br>
  <em>FFT of that square wave — the odd-harmonic comb, peaks picked out at
  1, 3, and 5&nbsp;kHz.</em>
</p>

A live view that holds 5–20 fps on four channels, measurement markers you drag
directly onto the trace, cursors, FFT, math channels, reference-waveform
overlays, and a raw SCPI terminal for when you need to talk to the instrument
yourself. Dedicated tabs connect to a **power supply** or a **DAQ / data logger**
alongside the scope.

Software protocol decoding covers **I2C, SPI, and UART**.

→ [Full GUI guide](https://little-did-I-know.github.io/SCPI-Instrument-Control/gui/overview/)

## The browser lab gateway

```bash
pip install "SCPI-Instrument-Control[web]"
scpi-web                    # prints its URL on every start
scpi-web invite alice       # a 10-minute link + code for a colleague
```

Run one gateway on the bench machine and reach your instruments from any browser
on the LAN — live traces, screenshots, measurements, server-side FFT and
filters, and ~1 Hz measurement logging with CSV export. `GET /api/discover`
sweeps the subnet for instruments when DHCP moves them.

Every request needs a token, each session has an owner (owner writes, everyone
else watches), and outbound connection targets are validated. The admin panel
binds loopback only. It does **not** terminate TLS — keep it on a trusted
network or behind a reverse proxy.

→ [Gateway guide](https://little-did-I-know.github.io/SCPI-Instrument-Control/gateway/) ·
[Security model](https://little-did-I-know.github.io/SCPI-Instrument-Control/gateway/security/)

## Automated test reports

```bash
pip install "SCPI-Instrument-Control[report-generator]"
```

Turn captures into PDF or Markdown reports with plots, signal classification,
25+ statistics, pass/fail criteria, and a SHA-256 manifest of the raw data.
Comparison and batch modes handle before/after runs and multi-DUT yield tables.
Analysis text can be generated by a local LLM through Ollama — on your machine,
no cloud provider, no API key.

See [`example_reports/`](example_reports/) for generated samples, including one
with LLM analysis.

→ [Report generator guide](https://little-did-I-know.github.io/SCPI-Instrument-Control/report-generator/)

## Supported instruments

| Class | Models |
|---|---|
| **Siglent scopes** (hardware-tested) | SDS800X HD (SDS804X/824X HD) · SDS1000X-E (1102X-E/1104X-E/1202X-E/1204X-E) · SDS2000X Plus (2104X+/2204X+/2354X+) · SDS5000X (5034X/5054X/5104X) |
| **Tektronix scopes** (manual-verified) | TBS1000C (TBS1102C) · 2 Series MSO (MSO24) · 4 Series (MSO44/46) · 5 Series (MSO54/56/58/58LP) · 6 Series (MSO64) |
| **LeCroy scopes** (manual-verified) | WaveSurfer 3000z (3024z) · WaveRunner 8000 (8104) |
| **Function generators** | Siglent SDG1000X (1032X/1025/1020) · SDG2000X (2122X/2082X/2042X) |
| **Power supplies** | Siglent SPD3303X / SPD3303X-E · SPD1305X / SPD1168X |
| **DAQ / data loggers** | Keysight 34970A / 34972A · DAQ970A / DAQ973A · generic SCPI-99 |

Other SCPI instruments generally work: model-specific behavior comes from the
`ModelCapability` registry, and unrecognized models fall back to a conservative
profile for their vendor with a logged warning.

→ [SCPI dialects and per-vendor gaps](https://little-did-I-know.github.io/SCPI-Instrument-Control/user-guide/scpi-dialects/)

## Command-line tools

| Command | Does |
|---|---|
| `siglent-gui` | Launch the desktop application |
| `scpi-web` | Serve the browser lab gateway |
| `scpi-extract` | Inspect or export a saved waveform file |
| `siglent-report-generator` | Launch the standalone report generator |

## Documentation

- **[Full documentation](https://little-did-I-know.github.io/SCPI-Instrument-Control/)** — guides, tutorials, API reference
- **[Quick start](https://little-did-I-know.github.io/SCPI-Instrument-Control/getting-started/quickstart/)** · **[Connecting an instrument](https://little-did-I-know.github.io/SCPI-Instrument-Control/getting-started/connection/)**
- **[Interactive tutorial](examples/interactive_tutorial.ipynb)** — Jupyter notebook, step by step
- **[31 runnable examples](examples/)** — 14 of them run with no instrument attached
- **[Changelog](CHANGELOG.md)** · **[Security policy](SECURITY.md)**

> **Upgrading?** `import siglent` became `import scpi_control` in v1.0.0 and the
> compatibility shim was removed in v2.0.0; the API is otherwise identical. Pin
> `SCPI-Instrument-Control<2.0` if you cannot migrate yet. The v4.x → 5.0 gateway
> now requires a token — see the
> [security guide](https://little-did-I-know.github.io/SCPI-Instrument-Control/gateway/security/).

## Contributing

Issues and pull requests are welcome — see the
[Contributing Guide](CONTRIBUTING.md).

```bash
git clone https://github.com/little-did-I-know/SCPI-Instrument-Control.git
cd SCPI-Instrument-Control
make dev-setup
make check
```

## License

MIT — see [LICENSE](LICENSE).
