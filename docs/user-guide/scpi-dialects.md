# SCPI Dialects

This library speaks four oscilloscope wire dialects behind one Python API:
Siglent legacy, Siglent modern, Tektronix, and LeCroy.

## Why dialects exist

Older Siglent scopes from the SDS1000X-E era speak a **legacy** command set —
flat, LeCroy-derived commands like `C1:VDIV 500mV`, `TDIV`, and `PAVA?`.
Newer HD-generation Siglent scopes (SDS800X HD and later) speak **modern**
colon-form SCPI — `:CHANnel1:SCALe 0.5`, `:TIMebase:SCALe`, `:MEASure...`.
**Tektronix** scopes (TBS1000C, 2/4/5/6 Series MSO) speak a headerless SCPI
dialect of their own — `CH1:SCAle`, `HORizontal:SCAle`, `TRIGger:A:...`. **LeCroy**
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

The built-in Tektronix registry, and the command-set variant (`scpi_variant`)
each model gets:

| Model | Series | Channels | `scpi_variant` |
|---|---|---|---|
| TBS1102C | TBS1000C | 2 | `tek_tbs` |
| MSO24 | 2 Series MSO | 4 | `tek_mso` |
| MSO44 | 4 Series MSO | 4 | `tek_mso` |
| MSO46 | 4 Series MSO | 6 | `tek_mso` |
| MSO54 | 5 Series MSO | 4 | `tek_mso` |
| MSO56 | 5 Series MSO | 6 | `tek_mso` |
| MSO58 | 5 Series MSO | 8 | `tek_mso` |
| MSO58LP | 5 Series MSO (Low Profile) | 8 | `tek_mso` |
| MSO64 | 6 Series MSO | 4 | `tek_mso` |

All modern MSO models — 2, 4, 5, and 6 Series alike — share the single
`tek_mso` command variant; only the TBS1000C gets its own `tek_tbs` variant.
Channel numbers passed to the API are validated against the connected
model's `num_channels` above (an `MSO44` rejects channel 5 with
`InvalidParameterError`, for instance), not a fixed 1-4 range.

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
| `measure()` automated measurements | legacy, lecroy, tektronix (all families) | **Modern (Siglent):** `measure()` calls still time out and raise `SiglentTimeoutError` — a longstanding, unchanged gap. **Tektronix:** the TBS1000C uses the `MEASUrement:IMMed` subsystem; the 2/4/5/6 Series MSO families have no `IMMed` subsystem and use stateful "badges" instead (`MEASUrement:MEAS<n>`) — see [Measurement badges](#measurement-badges) below. This closes the previous MSO 2-Series gap: `measure()` now works there too. |
| Badge measurement types `CMEAN`, `CRMS` | not available on badge families (2/4/5/6 Series MSO) | Both raise `FeatureNotSupportedError`. `CMEAN`: neither manual's `MEASUrement:MEAS<x>:TYPe` argument list (MSO2 PM 077-1776-07 p.2-468; 4/5/6 PM 077-1305-11 p.2-702) lists a cycle-mean badge token. `CRMS`: the badge vocabulary's `ACRMS` is AC-coupled RMS, a different measurement than cycle RMS — mapping it would misrepresent what's measured. **`TOP` and `BASE` are supported** on badge families (both manuals list `TOP`/`BASE` tokens; see the model table above) — they are not a gap. |
| `LINE` trigger source | not available on the `tektronix` dialect (gated for all families) | TBS1000C (PM 077-1691-01 p.152) and the 4/5/6 Series (PM 077-1305-11 p.2-1406) both support a `LINE` edge-trigger source; only the 2 Series MSO (PM 077-1776-07 p.2-663) lacks it. That divergence runs *inside* the shared `tek_mso` variant (2 Series vs. 4/5/6), which the current `channel_token(dialect, source)` signature — it branches on dialect only — cannot express, so `LINE` is gated dialect-wide rather than risk sending a token the 2 Series would reject. A deliberate, conservative gap; adding `LINE` for the families that do have it is a follow-up (needs a `tek_mso` split or a per-model capability flag). `EX` passes through as `AUX` (the SCPI short form of `AUXiliary`, present on every Tek family); `EX5` has no token on any Tek family and is also gated. |
| Waveform transfer bit depth | 8-bit only, all dialects | Tektronix's `DATa:WIDth` is pinned to `1` (8-bit) for now; 16-bit transfer is a follow-up. |
| LeCroy waveform transfer format | lecroy | Uses `C{ch}:WF? ALL` (descriptor + data in one block), scaled from the `WAVEDESC` descriptor's vertical gain/offset and horizontal interval/offset fields, with `CFMT DEF9,{BYTE\|WORD},BIN` and `CORD LO` (LSB-first) pinning the wire encoding — a different transfer path from the Siglent-style `WF? DAT2` used by legacy and modern. |
| LeCroy bandwidth limit token | lecroy | The public `ON` token maps to the wire value `20MHZ`; LeCroy's `BWL` vocabulary (`OFF`, `20MHZ`, `200MHZ`, ...) has no `ON` token of its own to map onto. |

Automated measurements (`PAVA?`) on **Siglent modern** scopes remain a
documented, unchanged gap: `scope.measurement.measure(...)` calls time out
and raise `SiglentTimeoutError`. The web gateway catches this internally and
shows measurements as unavailable in its UI.

## Measurement badges

The 2/4/5/6 Series MSO families have no `MEASUrement:IMMed` subsystem. A
measurement is a stateful "badge" — added to the instrument, configured with
a type and source, then read — verified against both manuals: MSO2 PM
077-1776-07 (`ADDNew` p.2-395, `TYPe` p.2-468, `SOUrce` p.2-464, `RESUlts`
p.2-462, `DELete` p.2-405, `LIST` p.2-411) and 4/5/6 PM 077-1305-11 (`ADDNew`
p.2-561, `TYPe` p.2-702, `SOUrce` p.2-694, `RESUlts` p.2-690, `DELete`
p.2-581, `LIST` p.2-592). `scope.measurement.measure(mtype, channel)` hides
this lifecycle behind the same call used on every other dialect:

- **Lazy allocation.** No badges are created on connect. The first call for a
  given measurement type + channel pair allocates one; every later call for
  that same pair reuses it — a single query per read instead of a full
  add/configure/read cycle, which matters for something like the web gateway
  polling measurements at ~1 Hz.
- **One badge per type + channel.** `MEASUrement:ADDNew "MEAS{n}"` creates
  the badge, `MEASUrement:MEAS{n}:TYPe {type}` and
  `MEASUrement:MEAS{n}:SOUrce {src}` configure it, and
  `MEASUrement:MEAS{n}:RESUlts:CURRentacq:MEAN?` reads the current value (the
  plain, non-`SUBGROUP` result query — the `SUBGROUP` form needs the
  5-DPM/5-IMDA/6-DPM options, which this library doesn't gate on).
- **User badges are never touched.** Before allocating its first badge, the
  library reads `MEASUrement:LIST?` once to learn which slots already exist
  on the instrument, and only ever allocates around them — badges you added
  yourself, from the front panel or another client, are never reused or
  deleted. (An empty list answers `NONE`; that's documented explicitly in
  the MSO2 manual, p.2-411 — the 4/5/6 manual doesn't call out the empty
  case, though nothing suggests it behaves differently.)
- **Cleanup is scoped to what this session created.** `disconnect()` deletes
  (`MEASUrement:DELete "MEAS{n}"`) only the badges this library allocated;
  anything pre-existing (user badges, or another session's) is left alone.
- **First-read acquisition caveat.** Badge results accumulate across
  acquisitions. The first read of a freshly created badge may need a
  running acquisition (`scope.run()`) before it returns a real value instead
  of a stale or non-numeric one. **The mock scope returns badge values
  immediately on the first read and does not simulate this** — code that
  passes against the mock isn't proof the same call will succeed against
  real hardware with acquisition stopped.

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
- *4/5/6 Series MSO, 6 Series LPD Programmer Manual* (Tektronix part number
  077-1305-11) — [tek.com](https://www.tek.com/), covering the MSO44, MSO46,
  MSO54, MSO56, MSO58, MSO58LP, and MSO64
- *Teledyne LeCroy MAUI Oscilloscopes Remote Control and Automation Manual* —
  [teledynelecroy.com](https://www.teledynelecroy.com/)
