# SCPI Dialects

This library speaks four oscilloscope wire dialects behind one Python API:
Siglent legacy, Siglent modern, Tektronix, and LeCroy.

## Why dialects exist

Older Siglent scopes from the SDS1000X-E era speak a **legacy** command set —
flat, LeCroy-derived commands like `C1:VDIV 500mV`, `TDIV`, and `PAVA?`.
Newer HD-generation Siglent scopes (SDS800X HD and later) speak **modern**
colon-form SCPI — `:CHANnel1:SCALe 0.5`, `:TIMebase:SCALe`, `:MEASure...`.
**Tektronix** scopes (TBS1000C, 2 Series MSO) speak a headerless SCPI dialect
of their own — `CH1:SCAle`, `HORizontal:SCAle`, `TRIGger:A:...`. **LeCroy**
scopes (WaveSurfer, WaveRunner) speak the MAUI remote-control command set —
`C1:VDIV`, `TDIV`, `TRIG_MODE`.

Worth calling out explicitly: LeCroy's dialect is the direct ancestor of
Siglent's legacy dialect. Siglent's early scopes borrowed LeCroy's flat
command grammar wholesale, which is why the legacy and LeCroy columns in the
table below look so similar — and why the differences that remain (see
[Known dialect gaps](#known-dialect-gaps)) are worth knowing about instead of
assuming the two are interchangeable.

Whichever scope you connect to, you call the same
`scope.channel1.voltage_scale`, `scope.timebase`, `scope.trigger.mode`, and
so on — the library translates to the right wire commands underneath.

## Auto-detection

The dialect is detected automatically from the instrument's `*IDN?` response
when you call `scope.connect()`, in two stages:

1. **Vendor routing on the manufacturer field.** A manufacturer field
   containing `TEKTRONIX` routes detection to the Tektronix registry.
   `LECROY` (which also matches `TELEDYNE LECROY`) routes to the LeCroy
   registry. Every other manufacturer string — including all Siglent scopes —
   takes the historic Siglent detection path unchanged.
2. **Model matching within that vendor.** Within the routed vendor, the model
   field is matched against the built-in registry (exact match, then a
   whitespace/case-insensitive fuzzy match, then a partial/substring match).
   A recognized model gets its pinned dialect and family variant
   (`scpi_variant`). An unrecognized model of a *known* vendor (Tektronix or
   LeCroy) falls back to a conservative generic profile for that vendor —
   4 channels assumed (2 for TBS1-pattern Tektronix models), a logged
   warning — rather than guessing wrong. An unrecognized Siglent model falls
   back to the original heuristic: model names containing ` HD` (with the
   space) or ending in `HD`, containing `PLUS`, or containing
   `SDS5`/`SDS6`/`SDS7` are treated as modern, everything else as legacy.

Check what was detected after connecting:

```python
from scpi_control import Oscilloscope

with Oscilloscope('192.168.1.100') as scope:
    print(scope.dialect)  # "legacy", "modern", "tektronix", or "lecroy"
```

## Overriding detection

If detection guesses wrong — an unlisted model that doesn't match the
heuristic, for instance — force the dialect explicitly:

```python
scope = Oscilloscope("192.168.1.100", dialect="modern")
```

`dialect=` accepts `"legacy"`, `"modern"`, `"tektronix"`, or `"lecroy"`. An
explicit `dialect=` always wins over the model registry and the fallback
heuristic.

## Side-by-side: wire commands across dialects

The library's command tables (`scpi_control/scpi_commands.py`) hold the
exact strings sent to each dialect. A sample of the underlying wire commands
(`{ch}` and other braces are template placeholders the library fills in):

| Operation | Legacy | Modern | Tektronix | LeCroy |
|---|---|---|---|---|
| Voltage scale | `C{ch}:VDIV {vdiv}` | `:CHANnel{ch}:SCALe {vdiv}` | `CH{ch}:SCAle {vdiv}` | `C{ch}:VDIV {vdiv}` |
| Timebase | `TDIV {tdiv}` | `:TIMebase:SCALe {tdiv}` | `HORizontal:SCAle {tdiv}` | `TDIV {tdiv}` |
| Trigger mode | `TRIG_MODE {mode}` | `:TRIGger:MODE {mode}` | `TRIGger:A:MODe {mode}` | `TRIG_MODE {mode}` |
| Run | `TRIG_MODE AUTO` | `:TRIGger:RUN` | `ACQuire:STATE RUN` | `TRIG_MODE AUTO` |
| Stop | `STOP` | `:TRIGger:STOP` | `ACQuire:STATE STOP` | `STOP` |
| Waveform fetch | `C{ch}:WF? DAT2` | `C{ch}:WF? DAT2` (unchanged for now) | `CURVe?` | `C{ch}:WF? ALL` |
| Sample rate | `SARA?` | `:ACQuire:SRATe?` | `HORizontal:SAMPLERate?` | `VBS? 'return=app.Acquisition.Horizontal.SamplingRate'` |

You never need to write these commands yourself for anything the API
covers — see the [Trigger Control](trigger-control.md) guide for the
properties that wrap them. For anything the API doesn't expose yet, the
gateway's Terminal tab (or `scope.write()` / `scope.query()`) lets you send
raw commands in whichever dialect the connected scope speaks.

## Known dialect gaps

Not every dialect implements every feature the public API exposes. Where a
dialect lacks a command, calling the corresponding property or method raises
`FeatureNotSupportedError` (or, for the two gaps noted below that involve
timeouts rather than gating, the appropriate timeout/parse error) —
`scpi_control.exceptions`.

| Feature | Supported on | Notes |
|---|---|---|
| Measurement statistics (`PAST`/`PASTAT`) and cursors (`CRST`/`CRVA?`) | legacy only | Absent from the modern, Tektronix, and LeCroy command tables. |
| `add_measurement` (`PACU`) | legacy only | LeCroy's `PACU` is slot-first (`PACU <slot>,<measurement>,<qualifier>`) — a different grammar from Siglent's `PACU {mtype},C{ch}`, so it isn't wired up rather than being silently wrong. |
| `WINDOW` trigger slope | legacy, modern (Siglent) | Tektronix edge trigger only has `RISe`/`FALL`; LeCroy `TRSL` only has `NEG`/`POS`. Neither has a window-slope equivalent. |
| Trigger holdoff | legacy, tektronix | On legacy, the wire command (`TRIG_DELAY`) is really *trigger delay*, not holdoff — an existing honesty note kept as-is pending a trigger-rework follow-up. Modern has no holdoff command at all. LeCroy holdoff lives in `TRIG_SELECT HT/HV`, a different shape not yet implemented (follow-up). |
| `GND` channel coupling | legacy, modern, lecroy | Not supported on Tektronix: neither the TBS1000C (`AC`\|`DC`) nor the 2 Series MSO (`AC`\|`DC`\|`DCREJect`) command set has a ground-coupling mode. The MSO2's `DCREJect` coupling readback is normalized to the public `AC` token rather than surfaced as a Tek-specific value. |
| Channel vertical unit (`C{ch}:UNIT`) | legacy only | No equivalent command in the modern, Tektronix, or LeCroy tables. |
| `measure()` automated measurements | legacy, lecroy, tektronix (TBS1000C family only) | **Modern:** `measure()` calls still time out and raise `SiglentTimeoutError` — a longstanding, unchanged gap. **Tektronix 2 Series MSO:** `measure()` raises `FeatureNotSupportedError` with a clear message; the MSO2 command set has no `MEASUrement:IMMed` subsystem (badge-based `MEASUrement:MEAS<x>` measurements are a follow-up). |
| Waveform transfer bit depth | 8-bit only, all dialects | Tektronix's `DATa:WIDth` is pinned to `1` (8-bit) for now; 16-bit transfer is a follow-up. |
| LeCroy waveform transfer format | lecroy | Uses `C{ch}:WF? ALL` (descriptor + data in one block), scaled from the `WAVEDESC` descriptor's vertical gain/offset and horizontal interval/offset fields, with `CFMT DEF9,{BYTE\|WORD},BIN` and `CORD LO` (LSB-first) pinning the wire encoding — a different transfer path from the Siglent-style `WF? DAT2` used by legacy and modern. |
| LeCroy bandwidth limit token | lecroy | The public `ON` token maps to the wire value `20MHZ`; LeCroy's `BWL` vocabulary (`OFF`, `20MHZ`, `200MHZ`, ...) has no `ON` token of its own to map onto. |

Automated measurements (`PAVA?`) on **Siglent modern** scopes remain a
documented, unchanged gap: `scope.measurement.measure(...)` calls time out
and raise `SiglentTimeoutError`. The web gateway catches this internally and
shows measurements as unavailable in its UI.

## Mock sessions

Mock sessions (`mock: true` in the web gateway, or `MockConnection` in code)
default to a **legacy**-dialect Siglent scope. Pass a different `idn` to
exercise another dialect's code path against a mock:

```python
from scpi_control import Oscilloscope
from scpi_control.connection.mock import MockConnection

# Siglent modern
idn = "Siglent Technologies,SDS824X HD,MOCK0001,1.0.0.0"
scope = Oscilloscope("mock", connection=MockConnection("mock", idn=idn))
scope.connect()
print(scope.dialect)  # "modern"

# Tektronix (2 Series MSO)
idn = "TEKTRONIX,MSO24,MOCK0100,CF:91.1CT FV:1.28"
scope = Oscilloscope("mock", connection=MockConnection("mock", idn=idn))
scope.connect()
print(scope.dialect)  # "tektronix"

# LeCroy (WaveSurfer 3000z)
idn = "LECROY,WAVESURFER3024Z,MOCK0200,8.5.0"
scope = Oscilloscope("mock", connection=MockConnection("mock", idn=idn))
scope.connect()
print(scope.dialect)  # "lecroy"
```

Each mock scope only answers its own dialect's commands. Send it a command
from a different dialect (e.g. `TDIV?` against a Tektronix mock, or
`:TIMebase:SCALe?` against either vendor mock) and the query still times out
with `SiglentTimeoutError`, the same as it would against real hardware
speaking a different command set. Only queries behave this way — an
unrecognized write is recorded but silently ignored, matching how real
scopes handle commands they don't understand.

## Manuals

The Tektronix and LeCroy command tables were verified command-by-command
against the vendor programmer manuals below. The PDFs themselves aren't
committed to this repo — consult the vendor for the current version:

- *Tektronix TBS1000C Series Programmer Manual* (Tektronix part number
  077-1691-01) — [tek.com](https://www.tek.com/)
- *Tektronix 2 Series MSO Programmer Manual* (Tektronix part number
  077-1776-07) — [tek.com](https://www.tek.com/)
- *Teledyne LeCroy MAUI Oscilloscopes Remote Control and Automation Manual* —
  [teledynelecroy.com](https://www.teledynelecroy.com/)
