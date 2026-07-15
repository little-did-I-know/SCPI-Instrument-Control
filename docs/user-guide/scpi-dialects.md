# SCPI Dialects

Siglent's oscilloscope line spans two generations of wire protocol, and this
library speaks both through the exact same Python API.

## Why dialects exist

Older scopes from the SDS1000X-E era speak a **legacy** command set — flat,
LeCroy-derived commands like `C1:VDIV 500mV`, `TDIV`, and `PAVA?`. Newer
HD-generation scopes (SDS800X HD and later) speak **modern** colon-form
SCPI — `:CHANnel1:SCALe 0.5`, `:TIMebase:SCALe`, `:MEASure...`. Whichever
generation you connect to, you call the same `scope.channel1.voltage_scale`,
`scope.timebase`, `scope.trigger.mode`, and so on — the library translates
to the right wire commands underneath.

## Auto-detection

The dialect is detected automatically from the instrument's `*IDN?` response
when you call `scope.connect()`. Detection first checks the built-in model
registry (which pins the dialect for every officially supported model); for
an unrecognized model it falls back to a heuristic — model names ending in
`HD`, containing `PLUS`, or starting with `SDS5`/`SDS6`/`SDS7` are treated as
modern, everything else as legacy.

Check what was detected after connecting:

```python
from scpi_control import Oscilloscope

with Oscilloscope('192.168.1.100') as scope:
    print(scope.dialect)  # "legacy" or "modern"
```

## Overriding detection

If detection guesses wrong — an unlisted model that doesn't match the
heuristic, for instance — force the dialect explicitly:

```python
scope = Oscilloscope("192.168.1.100", dialect="modern")   # or dialect="legacy"
```

An explicit `dialect=` always wins over the model registry and the
fallback heuristic.

## Side-by-side: legacy vs. modern wire commands

The library's command tables (`scpi_control/scpi_commands.py`) hold the
exact strings sent to each dialect. A sample of the underlying wire
commands (`{ch}` and other braces are template placeholders the library
fills in):

| Operation | Legacy wire command | Modern wire command |
|---|---|---|
| Voltage scale | `C{ch}:VDIV {vdiv}` | `:CHANnel{ch}:SCALe {vdiv}` |
| Timebase | `TDIV {tdiv}` | `:TIMebase:SCALe {tdiv}` |
| Trigger mode | `TRIG_MODE {mode}` | `:TRIGger:MODE {mode}` |
| Run | `TRIG_MODE AUTO` | `:TRIGger:RUN` |
| Stop | `STOP` | `:TRIGger:STOP` |
| Waveform fetch | `C{ch}:WF? DAT2` | `C{ch}:WF? DAT2` (unchanged for now) |
| Sample rate | `SARA?` | `:ACQuire:SRATe?` |

You never need to write these commands yourself for anything the API
covers — see the [Trigger Control](trigger-control.md) guide for the
properties that wrap them. For anything the API doesn't expose yet, the
gateway's Terminal tab (or `scope.write()` / `scope.query()`) lets you send
raw commands in whichever dialect the connected scope speaks.

## Known dialect gaps

Automated measurements (`PAVA?`) are **legacy-only** today. On a
modern-dialect scope, `scope.measurement.measure(...)` returns `None`
instead of raising, and the web gateway's Measure tab shows measurements as
unavailable rather than trying to display stale or missing values.

## Mock sessions

Mock sessions (`mock: true` in the web gateway, or `MockConnection` in
code) default to a **legacy**-dialect scope. To exercise the modern code
path against a mock, pass a modern model name:

```python
from scpi_control import Oscilloscope
from scpi_control.connection.mock import MockConnection

idn = "Siglent Technologies,SDS824X HD,MOCK0001,1.0.0.0"
scope = Oscilloscope("mock", connection=MockConnection("mock", idn=idn))
scope.connect()
print(scope.dialect)  # "modern"
```
