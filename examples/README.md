# SCPI Instrument Control — Examples

These scripts show the library in action end to end: oscilloscope capture and
analysis, the web gateway's REST API, function generator / AWG control,
power supply control, data acquisition, and report generation. Most connect
to real hardware over LAN by default (update the IP/host constant near the
top of each file); a few run entirely against mock connections and need no
instrument at all — those are called out below.

Install the core library, then add the extras a given example needs:

```bash
pip install "SCPI-Instrument-Control"
```

## Oscilloscope

| File | What it shows | Requirements |
| --- | --- | --- |
| `basic_usage.py` | Connecting to an oscilloscope, configuring channels and trigger, and performing basic operations. | Oscilloscope on the network |
| `waveform_capture.py` | Capturing waveform data from the oscilloscope and saving it to a file. | Oscilloscope on the network, matplotlib |
| `measurements.py` | Automated measurements (frequency, Vpp, RMS, period, etc.) on oscilloscope channels. | Oscilloscope on the network |
| `live_plot.py` | Real-time waveform acquisition and plotting using matplotlib animation. | Oscilloscope on the network, matplotlib |
| `simple_capture.py` | Single waveform capture with analysis via the automation API (Vpp, RMS, frequency) and saving to NumPy format. | Oscilloscope on the network |
| `batch_capture.py` | Capturing multiple waveforms with different timebase and voltage-scale settings, for characterizing signals at different scales. | Oscilloscope on the network |
| `continuous_capture.py` | Collecting waveforms continuously over a period of time, for monitoring, statistics, or time-varying phenomena. | Oscilloscope on the network |
| `trigger_based_capture.py` | Waiting for specific trigger conditions and capturing waveforms when they occur, for sporadic events. | Oscilloscope on the network |
| `advanced_analysis.py` | Advanced waveform analysis and visualization: FFT analysis, statistical analysis, and matplotlib plots. | Oscilloscope on the network, matplotlib |
| `probe_calibration_analysis.py` | Waveform region extraction for probe compensation analysis: plateau detection, slope analysis, calibration guidance, and zoomed PDF report plots. | Oscilloscope on the network, `SCPI-Instrument-Control[report-generator]` |
| `dialect_override_example.py` | SCPI dialect auto-detection from `*IDN?` and the `dialect=` override for forcing a command set; runs entirely on mock connections. | Core install only (no hardware) |

## Web Gateway

| File | What it shows | Requirements |
| --- | --- | --- |
| `gateway_rest_client.py` | Driving the web gateway's REST API from Python: creating a mock session, configuring a channel, fetching waveform JSON, downloading a screenshot, and sending a raw SCPI command — the same API the browser UI uses. | `SCPI-Instrument-Control[web]` + a running `scpi-web` gateway |
| `trend_logging_walkthrough.py` | Recording measurement trends in-process via the gateway's session layer (no server or browser): polling measurements, recording them, and exporting to CSV. | Core install only (no hardware, no server) |

## Function Generator / AWG

| File | What it shows | Requirements |
| --- | --- | --- |
| `function_generator_basic.py` | Basic control of Siglent SDG-series function generators over Ethernet/LAN. | Function generator on the network |
| `vector_graphics_xy_mode.py` | Using the oscilloscope as a vector display: generating X/Y waveform data for shapes, saving waveform files for an AWG, and animating via rotation/transforms. | `SCPI-Instrument-Control[fun]`, external AWG/DAC feeding the scope's channels |

## Power Supply

| File | What it shows | Requirements |
| --- | --- | --- |
| `psu_basic_control.py` | Controlling a SCPI power supply (Siglent SPD series or generic SCPI-99) over Ethernet/LAN. | Power supply on the network |
| `psu_advanced_features.py` | Advanced PSU features: CSV data logging, tracking modes (series/parallel), timer functionality, waveform generation, and OVP/OCP protection. | Power supply on the network |
| `psu_usb_connection.py` | Connecting to a power supply via USB/GPIB/Serial/TCP-IP using `VISAConnection`. | `SCPI-Instrument-Control[usb]`, PSU reachable via USB-TMC/GPIB/Serial/VXI-11 |
| `psu_gui_test.py` | Testing the PSU control GUI against a mock connection, with no physical hardware required. | `SCPI-Instrument-Control[gui]` |

## Data Acquisition

| File | What it shows | Requirements |
| --- | --- | --- |
| `data_logger_basic.py` | Basic usage of the `DataLogger` class for DAQ/switch units (e.g. Keysight 34970A/DAQ970A style). | DAQ instrument on the network |

## Report Generator

| File | What it shows | Requirements |
| --- | --- | --- |
| `report_generation_example.py` | Generating professional PDF/Markdown test reports: loading waveform data, adding measurements with pass/fail criteria, optional AI analysis, and rendering the report. | `SCPI-Instrument-Control[report-generator]` |

## Interactive Tutorial

| File | What it shows | Requirements |
| --- | --- | --- |
| `interactive_tutorial.ipynb` | End-to-end Jupyter walkthrough: connect, configure channels/trigger, capture and plot a waveform, run automated measurements, FFT analysis, multi-channel capture, and export — narrated step by step. | Jupyter, oscilloscope on the network, matplotlib, scipy |

## Configuration

Most scripts read an IP/host constant (commonly `SCOPE_IP`) near the top of
the file — update it to match your instrument. To find an oscilloscope's
LAN address: **Utility → I/O → LAN** on the instrument's front panel.

The scripts marked "no hardware" above (`dialect_override_example.py`,
`trend_logging_walkthrough.py`, `psu_gui_test.py`) use mock connections and
run as-is.

## Running an example

```bash
python examples/basic_usage.py
```

For `gateway_rest_client.py`, start the gateway first, in another terminal:

```bash
pip install "SCPI-Instrument-Control[web]"
scpi-web
```

Then run the client script.
