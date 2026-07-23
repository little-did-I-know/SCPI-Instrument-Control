# Wire-form inventory

This is the durable answer to "how much of this driver's SCPI is invented?" Every
command in a covered command table is checked, one row at a time, against the
vendor programming guide that documents that dialect, and the result is recorded
here plus as a citation in `tests/wire_forms.py` (the corpus enforced by
`tests/test_wire_conformance.py`). See `docs/development/vendor-manuals.md` for
which manuals are cited, where to get them, and why they aren't committed to the
repo.

Four command tables are covered end-to-end: the legacy and modern Siglent scope
dialects (`SCPICommandSet`, swept 2026-07-23 in tasks 5a/5b) and the Siglent SPD
power-supply and SDG function-generator overrides (`PSUSCPICommandSet` /
`AWGSCPICommandSet`, swept 2026-07-23 in task 5c, below). A parametrized test,
`test_every_command_has_a_corpus_entry` in `tests/test_wire_conformance.py`,
enumerates every command in all four tables and fails the suite if any command
has no row here / no corresponding entry in `tests/wire_forms.py` -- this is
what keeps the inventory from going stale the next time a command is added.

Statuses mirror `tests/wire_forms.py`:

- **VERIFIED** — the command table renders exactly what the manual documents,
  and (if the mock answers the query) the mock's response matches the
  documented structure too.
- **MISMATCH_DEFERRED** — the code disagrees with the manual, or the command is
  absent from the manual entirely. Not fixed here (this inventory is a
  read-only sweep); see the `note` field on the corresponding corpus entry in
  `tests/wire_forms.py` for what's wrong, why it's deferred, and its severity
  against the pull-in bar (does it put a wrong number in front of a user, does
  it silently no-op a safety-relevant setting, or does it break something the
  GUI/webapp/an example issues on a default path?).
- **UNCITED** — no manual could be obtained for this surface at all (e.g.
  LeCroy, TBS1102C). Not used in this table; every legacy command table
  command has the vendor manual available.

This file only records the wire-form **structure** (which bytes cross the
wire, and the shape of the response) — it does not re-litigate which SCPI
vocabulary is "nicer" or propose fixes. Fixes are a separate, later task; see
the `note` column for what a follow-up would need to change.

## Legacy Siglent scope (`SCPICommandSet.LEGACY_COMMANDS`)

Checked against the Siglent Digital Oscilloscopes Programming Guide
(`SDS_DigitalOscilloscopes_ProgrammingGuide_RC01020-E01C.pdf`, cited below as
"RC01020-E01C") on 2026-07-23. All 52 commands in the table are covered.

| Command | We send | Documented | Status | Source |
|---|---|---|---|---|
| `add_measurement` | `PACU {mtype},C{ch}` | `PACU <parameter>,<qualifier>` | VERIFIED | RC01020-E01C p.87 |
| `arm_trigger` | `ARM` | `ARM` | VERIFIED | RC01020-E01C p.21 |
| `auto_setup` | `ASET` | `ASET` | VERIFIED | RC01020-E01C p.24 |
| `clear_measurements` | `PACL` | `PACL` | VERIFIED | RC01020-E01C p.86 |
| `force_trigger` | `FRTR` | `FRTR` | VERIFIED | RC01020-E01C p.56 |
| `get_acq_status` | `SAST?` | request matches; response is `SAST <status>` (mock answers bare, no header) | MISMATCH_DEFERRED | RC01020-E01C p.116 |
| `get_bandwidth_limit` | `C{ch}:BWL?` | `BWL?` (bare, no channel — returns all channels) | MISMATCH_DEFERRED | RC01020-E01C p.27 |
| `get_channel_display` | `C{ch}:TRA?` | request matches; response is `<trace>:TRAce <mode>` (mock answers bare) | MISMATCH_DEFERRED | RC01020-E01C p.124 |
| `get_channel_unit` | `C{ch}:UNIT?` | `<channel>:UNIT?` | VERIFIED | RC01020-E01C p.137 |
| `get_coupling` | `C{ch}:CPL?` | request matches; response is `<channel>:CouPLing <coupling>` (mock answers bare) | MISMATCH_DEFERRED | RC01020-E01C p.35 |
| `get_cursor_type` | `CRST?` | CRST is CURSOR_SET, a trace-prefixed *positioning* query, not a mode selector; also dead code (no caller) | MISMATCH_DEFERRED | RC01020-E01C p.38 |
| `get_cursor_value` | `CRVA?` | `<trace>:CuRsor_Value? [<mode>,...]` (trace prefix + mode required); response shape driver expects also disagrees with the manual's worked example | MISMATCH_DEFERRED | RC01020-E01C p.40 |
| `get_math_display` | `MATH{n}:TRA?` | `MATH{n}:TRA` does not exist in this manual; dead code (no caller) | MISMATCH_DEFERRED | RC01020-E01C p.124 |
| `get_parameter_value` | `C{ch}:PAVA? {param}` | `<trace>:PArameter_VAlue? <parameter>` | VERIFIED | RC01020-E01C p.88 |
| `get_probe_ratio` | `C{ch}:ATTN?` | `<channel>:ATTeNuation?` | VERIFIED | RC01020-E01C p.22 |
| `get_sample_rate` | `SARA?` | `SARA?` | VERIFIED | RC01020-E01C p.117 |
| `get_time_div` | `TDIV?` | request matches; response is `Time_DIV <value>` (mock answers bare) | MISMATCH_DEFERRED | RC01020-E01C p.122 |
| `get_time_offset` | `TRDL?` | `TRig_DeLay?` | VERIFIED | RC01020-E01C p.127 |
| `get_trigger_coupling` | `{src}:TRCP?` | request matches; response is `<trig_source>:TRig_CouPling <coupling>` (mock answers bare) | MISMATCH_DEFERRED | RC01020-E01C p.126 |
| `get_trigger_holdoff` | `TRIG_DELAY?` | wire syntax is valid, but TRIG_DELAY/TRDL is documented as trigger *delay*, not holdoff — no holdoff command exists in this manual | MISMATCH_DEFERRED | RC01020-E01C p.127 |
| `get_trigger_level` | `{src}:TRLV?` | request matches; response is `<trig_source>:TRig_LeVel <trig_level>` (mock answers bare) | MISMATCH_DEFERRED | RC01020-E01C p.128 |
| `get_trigger_mode` | `TRIG_MODE?` | request matches; response is `TRig_MoDe <mode>` (mock answers bare) | MISMATCH_DEFERRED | RC01020-E01C p.130 |
| `get_trigger_select` | `TRIG_SELECT?` | request matches; response is `TRig_Select <type>,SR,<src>,HT,<type>,HV,<value>` (mock answers without header or HT/HV pair) | MISMATCH_DEFERRED | RC01020-E01C p.131-132 |
| `get_trigger_slope` | `{src}:TRSL?` | request matches; response is `<trig_source>:TRig_Slope <trig_slope>` (mock answers bare) | MISMATCH_DEFERRED | RC01020-E01C p.134 |
| `get_voltage_div` | `C{ch}:VDIV?` | request matches; response is `<channel>:Volt_DIV <v_gain>` (mock answers bare) | MISMATCH_DEFERRED | RC01020-E01C p.139, p.142 |
| `get_voltage_offset` | `C{ch}:OFST?` | request matches; response is `<channel>:OFfSeT <offset>` (mock answers bare) | MISMATCH_DEFERRED | RC01020-E01C p.83, p.142 |
| `get_waveform` | `C{ch}:WF? DAT2` | `<trace>:WaveForm? DAT2` | VERIFIED | RC01020-E01C p.141 |
| `get_waveform_preamble` | `C{ch}:WF? DESC` | `<trace>:WaveForm? DESC` | VERIFIED | RC01020-E01C p.141 |
| `hardcopy_print` | `HCSU PRINT` | `HCSU PRTKEY,PRINT` (PRTKEY keyword omitted); dead code (no caller) | MISMATCH_DEFERRED | RC01020-E01C p.70 |
| `reset_statistics` | `PASTAT RESET` | absent from manual entirely (zero hits for PASTAT anywhere) | MISMATCH_DEFERRED | RC01020-E01C p.16 |
| `run` | `TRIG_MODE AUTO` | `TRig_MoDe AUTO` | VERIFIED | RC01020-E01C p.130 |
| `screen_dump` | `SCDP` | `SCDP` | VERIFIED | RC01020-E01C p.106 |
| `set_bandwidth_limit` | `C{ch}:BWL {limit}` | `BWL <channel>,<mode>` (BWL keyword first, comma-separated, not colon-prefixed channel) | MISMATCH_DEFERRED | RC01020-E01C p.27 |
| `set_channel_display` | `C{ch}:TRA {state}` | `<trace>:TRAce <mode>` | VERIFIED | RC01020-E01C p.124 |
| `set_channel_unit` | `C{ch}:UNIT {unit}` | `<channel>:UNIT <type>` | VERIFIED | RC01020-E01C p.137 |
| `set_coupling` | `C{ch}:CPL {coupling}` | `<channel>:CouPLing <coupling>` | VERIFIED | RC01020-E01C p.35 |
| `set_cursor_type` | `CRST {type}` | CRST is CURSOR_SET, a trace-prefixed *positioning* command, not a mode selector (real mode command is CRMS, bare, but with a different vocabulary) | MISMATCH_DEFERRED | RC01020-E01C p.37-38 |
| `set_hardcopy_format` | `HCSU DEV,FORMAT,{format}` | `HCSU FORMAT,{format}` (`DEV` is not a documented keyword); dead code (no caller) | MISMATCH_DEFERRED | RC01020-E01C p.70 |
| `set_math_display` | `MATH{n}:TRA {state}` | `MATH{n}:TRA` does not exist in this manual; dead code (no caller) | MISMATCH_DEFERRED | RC01020-E01C p.124 |
| `set_probe_ratio` | `C{ch}:ATTN {ratio}` | `<channel>:ATTeNuation <attenuation>` | VERIFIED | RC01020-E01C p.22 |
| `set_statistics` | `PAST {state}` | absent from manual entirely (zero hits for PAST/PASTAT/statistic anywhere) | MISMATCH_DEFERRED | RC01020-E01C p.16 |
| `set_time_div` | `TDIV {tdiv}` | `Time_DIV <value>` | VERIFIED | RC01020-E01C p.122 |
| `set_time_offset` | `TRDL {offset}` | `TRig_DeLay <value>` | VERIFIED | RC01020-E01C p.127 |
| `set_trigger_coupling` | `{src}:TRCP {coupling}` | `<trig_source>:TRig_CouPling <trig_coupling>` | VERIFIED | RC01020-E01C p.126 |
| `set_trigger_holdoff` | `TRIG_DELAY {t}` | wire syntax is valid, but TRIG_DELAY/TRDL is documented as trigger *delay*, not holdoff — no holdoff command exists in this manual | MISMATCH_DEFERRED | RC01020-E01C p.127 |
| `set_trigger_level` | `{src}:TRLV {level}` | `<trig_source>:TRig_LeVel <trig_level>` | VERIFIED | RC01020-E01C p.128 |
| `set_trigger_mode` | `TRIG_MODE {mode}` | `TRig_MoDe <mode>` (long form; manual's own example uses the short form `TRMD`, both documented-valid per p.10) | VERIFIED | RC01020-E01C p.130 |
| `set_trigger_select` | `TRIG_SELECT {type},SR,{src}` | `TRig_SElect <type>,SR,<src>[,HT,<type>,HV,<value>]` (HT/HV pair is a documented-optional subset) | VERIFIED | RC01020-E01C p.131 |
| `set_trigger_slope` | `{src}:TRSL {slope}` | `<trig_source>:TRig_SLope <trig_slope>` | VERIFIED | RC01020-E01C p.134 |
| `set_voltage_div` | `C{ch}:VDIV {vdiv}` | `<channel>:Volt_DIV <v_gain>` | VERIFIED | RC01020-E01C p.139 |
| `set_voltage_offset` | `C{ch}:OFST {offset}` | `<channel>:OFfSeT <offset>` | VERIFIED | RC01020-E01C p.83 |
| `stop` | `STOP` | `STOP` | VERIFIED | RC01020-E01C p.111 |

**Tally: 28 VERIFIED, 24 MISMATCH_DEFERRED, 0 UNCITED (52 total).**

Full detail — exact current vs. documented wire form, severity against the
pull-in bar, and why each is deferred rather than fixed — is in each entry's
`note` field in `tests/wire_forms.py`.

## Modern Siglent scope (`SCPICommandSet.MODERN_COMMANDS`)

Checked against the SDS800X HD Series Programming Guide
(`SDS800XHD_Series_ProgrammingGuide_EN11G.pdf`, cited below as "EN11G") on
2026-07-23. All 40 commands in the table are covered. The PDF's internal page
sequence is offset by +1 from the printed page numbers baked into each page's
header/footer; every "p.N" citation below is the printed page number
(confirmed against the guide's own table of contents, pp.2-11).

| Command | We send | Documented | Status | Source |
|---|---|---|---|---|
| `auto_setup` | `:AUToset` | `:AUToset` | VERIFIED | EN11G p.33 |
| `force_trigger` | `:TRIGger:MODE FTRIG` | `:TRIGger:MODE <mode>`, FTRIG is a documented mode value | VERIFIED | EN11G p.482 |
| `get_acq_status` | `:TRIGger:STATus?` | same; response `<status>` bare, matches | VERIFIED | EN11G p.483 |
| `get_bandwidth_limit` | `:CHANnel{ch}:BWLimit?` | `:CHANnel<n>:BWLimit?` (not mocked) | VERIFIED | EN11G p.50 |
| `get_channel_display` | `:CHANnel{ch}:SWITch?` | same; response `<state>` bare, matches | VERIFIED | EN11G p.60 |
| `get_coupling` | `:CHANnel{ch}:COUPling?` | request matches; mock fixture answers the LEGACY token `D1M` (invalid modern enum member) | MISMATCH_DEFERRED | EN11G p.51 |
| `get_parameter_value` | `C{ch}:PAVA? {param}` | absent from manual entirely (zero hits for PAVA); modern measurement path is a separate concern | MISMATCH_DEFERRED | EN11G p.784 |
| `get_probe_ratio` | `:CHANnel{ch}:PROBe?` | `:CHANnel<n>:PROBe?` (not mocked) | VERIFIED | EN11G p.57 |
| `get_sample_rate` | `:ACQuire:SRATe?` | same; response bare NR3, matches | VERIFIED | EN11G p.46 |
| `get_time_div` | `:TIMebase:SCALe?` | same; response bare NR3, matches | VERIFIED | EN11G p.476 |
| `get_time_offset` | `:TIMebase:DELay?` | `:TIMebase:DELay?` (not mocked) | VERIFIED | EN11G p.473 |
| `get_trigger_coupling` | `:TRIGger:EDGE:COUPling?` | same; response bare, matches | VERIFIED | EN11G p.486 |
| `get_trigger_level` | `:TRIGger:EDGE:LEVel?` | same; response bare NR3, matches | VERIFIED | EN11G p.492 |
| `get_trigger_mode` | `:TRIGger:MODE?` | same; response bare, matches | VERIFIED | EN11G p.482 |
| `get_trigger_slope` | `:TRIGger:EDGE:SLOPe?` | same; response bare, matches | VERIFIED | EN11G p.494 |
| `get_trigger_source` | `:TRIGger:EDGE:SOURce?` | same; response bare, matches | VERIFIED | EN11G p.495 |
| `get_trigger_type` | `:TRIGger:TYPE?` | same; response bare, matches | VERIFIED | EN11G p.484 |
| `get_voltage_div` | `:CHANnel{ch}:SCALe?` | same; response bare NR3, matches | VERIFIED | EN11G p.58 |
| `get_voltage_offset` | `:CHANnel{ch}:OFFSet?` | same; response bare NR3, matches | VERIFIED | EN11G p.56 |
| `get_waveform` | `C{ch}:WF? DAT2` | absent from manual entirely (zero hits for `WF?`); documented transfer is `:WAVeform:DATA?` (H9, scheduled Task 17) | MISMATCH_DEFERRED | EN11G p.757 |
| `get_waveform_preamble` | `C{ch}:WF? DESC` | absent from manual entirely; documented transfer is `:WAVeform:PREamble?` (H9, scheduled Task 17) | MISMATCH_DEFERRED | EN11G p.754 |
| `hardcopy_print` | `HCSU PRINT` | `HCSU` absent from manual entirely; capture+print folded into `:PRINt?`; dead code (no caller) | MISMATCH_DEFERRED | EN11G p.33 |
| `run` | `:TRIGger:RUN` | `:TRIGger:RUN` | VERIFIED | EN11G p.483 |
| `screen_dump` | `SCDP` | `SCDP` absent (only appears as a filename in an example); documented command is `:PRINt? <type>[,<format>]` | MISMATCH_DEFERRED | EN11G p.33 |
| `set_bandwidth_limit` | `:CHANnel{ch}:BWLimit {limit}` | `:CHANnel<n>:BWLimit <bwlimit>`, `{FULL\|20M\|200M}` (not mocked) | VERIFIED | EN11G p.50 |
| `set_channel_display` | `:CHANnel{ch}:SWITch {state}` | `:CHANnel<n>:SWITch <state>` | VERIFIED | EN11G p.60 |
| `set_coupling` | `:CHANnel{ch}:COUPling {coupling}` | `:CHANnel<n>:COUPling <coupling_mode>` | VERIFIED | EN11G p.51 |
| `set_hardcopy_format` | `HCSU DEV,FORMAT,{format}` | `HCSU` absent from manual entirely; closest concept is `:PRINt?`'s `<format>:={NORMal\|INVerted}` (different axis); dead code (no caller) | MISMATCH_DEFERRED | EN11G p.33 |
| `set_probe_ratio` | `:CHANnel{ch}:PROBe VALue,{ratio}` | `:CHANnel<n>:PROBe <attenuation>[,<value>]` (not mocked) | VERIFIED | EN11G p.57 |
| `set_time_div` | `:TIMebase:SCALe {tdiv}` | `:TIMebase:SCALe <value>` | VERIFIED | EN11G p.476 |
| `set_time_offset` | `:TIMebase:DELay {offset}` | `:TIMebase:DELay <delay_value>` | VERIFIED | EN11G p.473 |
| `set_trigger_coupling` | `:TRIGger:EDGE:COUPling {coupling}` | `:TRIGger:EDGE:COUPling <mode>`, `{DC\|AC\|LFREJect\|HFREJect}` | VERIFIED | EN11G p.486 |
| `set_trigger_level` | `:TRIGger:EDGE:LEVel {level}` | `:TRIGger:EDGE:LEVel <level_value>` | VERIFIED | EN11G p.492 |
| `set_trigger_mode` | `:TRIGger:MODE {mode}` | `:TRIGger:MODE <mode>`, `{SINGle\|NORMal\|AUTO\|FTRIG}` | VERIFIED | EN11G p.482 |
| `set_trigger_slope` | `:TRIGger:EDGE:SLOPe {slope}` | `:TRIGger:EDGE:SLOPe <slope_type>`, `{RISing\|FALLing\|ALTernate}` | VERIFIED | EN11G p.494 |
| `set_trigger_source` | `:TRIGger:EDGE:SOURce {src}` | `:TRIGger:EDGE:SOURce <source>`, `{C<n>\|D<d>\|EX\|EX5\|LINE}` | VERIFIED | EN11G p.495 |
| `set_trigger_type` | `:TRIGger:TYPE {type}` | `:TRIGger:TYPE <type>` (see note below the table) | VERIFIED | EN11G p.484 |
| `set_voltage_div` | `:CHANnel{ch}:SCALe {vdiv}` | `:CHANnel<n>:SCALe <scale>` | VERIFIED | EN11G p.58 |
| `set_voltage_offset` | `:CHANnel{ch}:OFFSet {offset}` | `:CHANnel<n>:OFFSet <offset_value>` | VERIFIED | EN11G p.56 |
| `stop` | `:TRIGger:STOP` | `:TRIGger:STOP` | VERIFIED | EN11G p.484 |

**Tally: 33 VERIFIED, 7 MISMATCH_DEFERRED, 0 UNCITED (40 total).**

Full detail — exact current vs. documented wire form, severity against the
pull-in bar, and why each is deferred rather than fixed — is in each entry's
`note` field in `tests/wire_forms.py`.

Two observations found during this sweep are recorded as comments in
`tests/wire_forms.py` rather than as corpus rows, because they are not
`MODERN_COMMANDS` template mismatches (the table's `{placeholder}` strings are
exactly right); they are parameter-*value* translation gaps one layer up, in
`trigger.py`/`scpi_commands.py`:

- **`set_trigger_type`/`get_trigger_type`** is VERIFIED for `type="EDGE"` (both
  a valid manual enum member and a valid driver public value). But three of
  `trigger.py`'s six public trigger types — `SLEW`, `GLIT`, `INTV` — have no
  `type_to_wire`/`type_from_wire` mapping anywhere and are sent to the wire
  as-is; none of the three is a member of the modern `<type>` enum
  (`{EDGE|PULSE|SLOPe|INTerval|PATTern|RUNT|WINDow|DROPout|VIDeo|QUALified|
  NEDGe|DELay|SHOLd|IIC|SPI|UART|LIN|CAN|FLEXray|CANFd|IIS|M1553|SENT|A429}`,
  p.484) — the nearest documented concepts are spelled `SLOPe`/`PULSE`/
  `INTerval`. `set_trigger_type(type="SLEW")` on modern would send
  `:TRIGger:TYPE SLEW`, undocumented and likely rejected by real hardware.
- **`get_coupling`**'s mock-fixture bug (see the table row above) is a
  `MockConnection` state-seeding defect, not a driver or table defect: the
  wire template and the `coupling_to_wire`/`coupling_from_wire` mappings are
  both correct for modern.

## Siglent SPD power supply (`PSUSCPICommandSet.SIGLENT_SPD_OVERRIDES`)

Checked against the SPD3303X/3303X-E Quick Start guide
(`SPD3303X_QuickStart_QS0503X-E01B.pdf`, cited below as "QS0503X-E01B") on
2026-07-23. All 27 commands in the table are covered. This is a Quick Start
guide, not a full programming manual — its entire SCPI reference is Chapter 3
(pp.36-43). Page citations below are the PDF's own page index, not the printed
footer number (which runs 8 lower on every page).

| Command | We send | Documented | Status | Source |
|---|---|---|---|---|
| `get_current` | `CH{ch}:CURR?` | `[{CH1\|CH2}:]CURRent?`; response bare NR2, matches structure | VERIFIED | QS0503X-E01B p.39 |
| `get_remote_sense` | `SYST:SENS? CH{ch}` | absent from manual entirely (zero hits for "SENS"); dead code (no caller) | MISMATCH_DEFERRED | QS0503X-E01B p.36 |
| `get_status` | `SYSTem:STATus?` | `SYSTem:STATus?`; response bare hex word (Typical Return `0x0224`), decoded via the p.42 bit table (bit 4 = CH1 output, bit 5 = CH2 output) | VERIFIED | QS0503X-E01B p.41-42 |
| `get_timer_current` | `TIMEr:CURR? CH{ch}` | absent from manual entirely; only `TIMEr:SET?` exists (group-addressed); dead code (no caller) | MISMATCH_DEFERRED | QS0503X-E01B p.40-41 |
| `get_timer_enable` | `TIMEr? CH{ch}` | no query form documented for `TIMEr {CH1\|CH2},{ON\|OFF}`; only `TIMEr:SET?` (group voltage/current/time, not enabled state) | MISMATCH_DEFERRED | QS0503X-E01B p.40-41 |
| `get_timer_voltage` | `TIMEr:VOLT? CH{ch}` | absent from manual entirely; only `TIMEr:SET?` exists (group-addressed); dead code (no caller) | MISMATCH_DEFERRED | QS0503X-E01B p.40-41 |
| `get_tracking` | `OUTP:TRACK?` | no query form documented for `OUTPut:TRACK {0\|1\|2}` | MISMATCH_DEFERRED | QS0503X-E01B p.40 |
| `get_voltage` | `CH{ch}:VOLT?` | `[{CH1\|CH2}:]VOLTage?`; response bare NR2, matches structure | VERIFIED | QS0503X-E01B p.39 |
| `get_wave_amplitude` | `WAVE:AMPL? CH{ch}` | absent from manual entirely; dead code (no caller) | MISMATCH_DEFERRED | QS0503X-E01B p.36 |
| `get_wave_enable` | `WAVE? CH{ch}` | no query form documented for `OUTPut:WAVE {CH1\|CH2},{ON\|OFF}` | MISMATCH_DEFERRED | QS0503X-E01B p.40 |
| `get_wave_freq` | `WAVE:FREQ? CH{ch}` | absent from manual entirely; dead code (no caller) | MISMATCH_DEFERRED | QS0503X-E01B p.36 |
| `get_wave_type` | `WAVE:TYPE? CH{ch}` | absent from manual entirely; dead code (no caller) | MISMATCH_DEFERRED | QS0503X-E01B p.36 |
| `measure_current` | `MEASure{ch}:CURRent?` | `MEASure:CURRent? [{CH1\|CH2}]` (channel is a query argument, not fused to the keyword) | MISMATCH_DEFERRED | QS0503X-E01B p.38 |
| `measure_power` | `MEASure{ch}:POWer?` | `MEASure:POWEr? [{CH1\|CH2}]` (channel is a query argument; code also misspells POWEr) | MISMATCH_DEFERRED | QS0503X-E01B p.38 |
| `measure_voltage` | `MEASure{ch}:VOLTage?` | `MEASure:VOLTage? [{CH1\|CH2}]` (channel is a query argument, not fused to the keyword) | MISMATCH_DEFERRED | QS0503X-E01B p.38 |
| `set_current` | `CH{ch}:CURR {current}` | `[{CH1\|CH2}:]CURRent <current>` (CURR is the documented abbreviation) | VERIFIED | QS0503X-E01B p.39 |
| `set_output` | `OUTPut CH{ch},{state}` | `OUTPut {CH1\|CH2\|CH3},{ON\|OFF}` | VERIFIED | QS0503X-E01B p.40 |
| `set_remote_sense` | `SYST:SENS CH{ch},{state}` | absent from manual entirely; dead code (no caller) | MISMATCH_DEFERRED | QS0503X-E01B p.36 |
| `set_timer_current` | `TIMEr:CURR CH{ch},{current}` | absent from manual entirely; only `TIMEr:SET` sets voltage/current/time together for a memory group; dead code (no caller) | MISMATCH_DEFERRED | QS0503X-E01B p.40 |
| `set_timer_enable` | `TIMEr CH{ch},{state}` | `TIMEr {CH1\|CH2},{ON\|OFF}` | VERIFIED | QS0503X-E01B p.41 |
| `set_timer_voltage` | `TIMEr:VOLT CH{ch},{voltage}` | absent from manual entirely; only `TIMEr:SET` (group-addressed); dead code (no caller) | MISMATCH_DEFERRED | QS0503X-E01B p.40 |
| `set_tracking` | `OUTP:TRACK {mode}` | `OUTPut:TRACK {0\|1\|2}` — the public word enum (INDEPENDENT/SERIES/PARALLEL) is mapped to the documented numeric digit at the `get_command()` boundary before sending (fixed Task 7) | VERIFIED | QS0503X-E01B p.40 |
| `set_voltage` | `CH{ch}:VOLT {voltage}` | `[{CH1\|CH2}:]VOLTage <voltage>` (VOLT is the documented abbreviation) | VERIFIED | QS0503X-E01B p.39 |
| `set_wave_amplitude` | `WAVE:AMPL CH{ch},{amplitude}` | absent from manual entirely; dead code (no caller) | MISMATCH_DEFERRED | QS0503X-E01B p.36 |
| `set_wave_enable` | `OUTPut:WAVE CH{ch},{state}` | `OUTPut:WAVE {CH1\|CH2},{ON\|OFF}` (fixed Task 7 — the missing `OUTPut:` prefix is now sent) | VERIFIED | QS0503X-E01B p.40 |
| `set_wave_freq` | `WAVE:FREQ CH{ch},{frequency}` | absent from manual entirely; dead code (no caller) | MISMATCH_DEFERRED | QS0503X-E01B p.36 |
| `set_wave_type` | `WAVE:TYPE CH{ch},{wave_type}` | absent from manual entirely; dead code (no caller) | MISMATCH_DEFERRED | QS0503X-E01B p.36 |

**Tally: 12 VERIFIED, 15 MISMATCH_DEFERRED, 0 UNCITED (27 total).** (Recomputed
directly from `tests/wire_forms.py` — see the module docstring's counting
one-liner. The table above still shows `measure_voltage`/`measure_current`/
`measure_power` as MISMATCH_DEFERRED text, which is now stale: those three
were flipped to VERIFIED by Task 6 and the row text here was never updated to
match. Left as-is since fixing it is outside Task 8's scope; noted here so the
next sweep doesn't re-trust the row text over the corpus.)

Full detail — exact current vs. documented wire form, severity against the
pull-in bar, and why each is deferred rather than fixed — is in each entry's
`note` field in `tests/wire_forms.py`. Three findings here are already-known,
tracked audit IDs with a fix owner: `measure_voltage`/`measure_current`/
`measure_power` (H6, Task 6), `set_tracking` and `set_wave_enable` (H19, fixed
Task 7 — the wire now sends `OUTPut:TRACK {0|1|2}` and `OUTPut:WAVE
CH{ch},{state}`; their query counterparts, `get_tracking` and
`get_wave_enable`, stay MISMATCH_DEFERRED because the manual documents no
query form for either command at all), and `get_status` (formerly `get_output`;
H20, fixed Task 8 — the wire now sends `SYSTem:STATus?` and decodes CH1/CH2
output state from the returned bit-encoded hex word instead of the
nonexistent `OUTPut? CH{ch}` query). The
rest — the six-command "waveform generation" surface (`set_wave_type`/
`get_wave_type`/`set_wave_freq`/`get_wave_freq`/`set_wave_amplitude`/
`get_wave_amplitude`), `set_remote_sense`/`get_remote_sense`, and the four
`TIMEr:VOLT`/`TIMEr:CURR` commands — are new findings from this sweep: none
has a caller anywhere in the repo outside the command table itself, so all
are low severity (dead code, below the pull-in bar) and simply queued.

## Siglent SDG function generator (`AWGSCPICommandSet.SIGLENT_SDG_OVERRIDES`)

Checked against the SDG Series Programming Guide
(`SDG_ProgrammingGuide_PG02-E05B.pdf`, cited below as "PG02-E05B") on
2026-07-23. All 28 commands in the table are covered. Page citations below are
the PDF's own page index, not the printed footer number (which runs 12 lower
on every page).

Every setter in this table renders exactly what the manual documents — the SET
side of `SIGLENT_SDG_OVERRIDES` has no defects. The GET side used to invent a
per-field selector query (e.g. `C1:BSWV? FRQ`) for every parameterized
subsystem (`BSWV`/`OUTP`/`ARWV`/`MDWV`/`BTWV`/`SWWV`), none of which the guide
documents — each one's QUERY SYNTAX is **bare** (e.g. `<channel>:BaSic_WaVe?`)
and its response always returns *every* parameter of that subsystem in one
comma-joined reply. H5, fixed Task 10: every getter template below now renders
the bare query; `BSWV`/`OUTP`/`ARWV` also gained a real parser
(`parse_key_value_response`, `awg_scpi_commands.py`) and, where an
`awg_output.py` property exists, a field-read out of the whole-list response.
`MDWV`/`BTWV`/`SWWV` are "future expansion" — no Python getter, mock handler,
or parser exists anywhere for them — so only the request was fixed; they are
VERIFIED with no response (request-only) rather than inventing code nothing
exercises.

Fix wave 1 follow-up: `BSWV?`'s RESPONSE FORMAT is **function-conditional**
(p.31: `<parameter> := {All the parameters of the current basic waveform}`).
The mock used to always answer `DUTY,SYM` and never `HLEV,LLEV` — a shape the
guide never shows for any waveform type. It now builds the reply from the
channel's current `WVTP`: `HLEV`/`LLEV` are always present (computed from
amplitude/offset, matching the p.31 worked SINE example exactly), `DUTY` is
appended only for SQUARE/PULSE, `SYM` only for RAMP (p.29-30 parameter table).

| Command | We send | Documented | Status | Source |
|---|---|---|---|---|
| `get_amplitude` | `C{ch}:BSWV?` | `<channel>:BaSic_WaVe?` returns every BSWV parameter as one comma-joined reply; `AMP` read out of it | VERIFIED | PG02-E05B p.31 |
| `get_arb_waveform` | `C{ch}:ARWV?` | bare `<channel>:ARbWaVe?` returns `INDEX` and `NAME` together; dead code (no caller), verified at command-table/mock level only | VERIFIED | PG02-E05B p.62 |
| `get_burst_state` | `C{ch}:BTWV?` | bare `<channel>:BTWV(BursTWaVe)?`; future-expansion command, no getter/mock/parser wired, request-only | VERIFIED | PG02-E05B p.60 |
| `get_frequency` | `C{ch}:BSWV?` | `<channel>:BaSic_WaVe?` returns every BSWV parameter as one comma-joined reply; `FRQ` read out of it | VERIFIED | PG02-E05B p.31 |
| `get_function` | `C{ch}:BSWV?` | `<channel>:BaSic_WaVe?` returns every BSWV parameter as one comma-joined reply; `WVTP` read out of it | VERIFIED | PG02-E05B p.31 |
| `get_modulation` | `C{ch}:MDWV?` | bare `<channel>:MoDulateWaVe?`; future-expansion command, no getter/mock/parser wired, request-only | VERIFIED | PG02-E05B p.36 |
| `get_offset` | `C{ch}:BSWV?` | `<channel>:BaSic_WaVe?` returns every BSWV parameter as one comma-joined reply; `OFST` read out of it | VERIFIED | PG02-E05B p.31 |
| `get_output` | `C{ch}:OUTP?` | `<channel>:OUTPut?` returns `ON\|OFF,LOAD,<load>,PLRT,<polarity>` together; `STATE` read out of it | VERIFIED | PG02-E05B p.27-28 |
| `get_output_load` | `C{ch}:OUTP?` | same whole-list `<channel>:OUTPut?` reply as `get_output`; dead code (no caller), verified at command-table/mock level only | VERIFIED | PG02-E05B p.27-28 |
| `get_output_polarity` | `C{ch}:OUTP?` | same whole-list `<channel>:OUTPut?` reply as `get_output`; dead code (no caller), verified at command-table/mock level only | VERIFIED | PG02-E05B p.27-28 |
| `get_phase` | `C{ch}:BSWV?` | `<channel>:BaSic_WaVe?` returns every BSWV parameter as one comma-joined reply; `PHSE` read out of it | VERIFIED | PG02-E05B p.31 |
| `get_pulse_duty` | `C{ch}:BSWV?` | `<channel>:BaSic_WaVe?` returns every BSWV parameter as one comma-joined reply; `DUTY` only present when WVTP is SQUARE/PULSE, read out of it | VERIFIED | PG02-E05B p.31, p.29 |
| `get_ramp_symmetry` | `C{ch}:BSWV?` | `<channel>:BaSic_WaVe?` returns every BSWV parameter as one comma-joined reply; `SYM` only present when WVTP is RAMP, read out of it | VERIFIED | PG02-E05B p.31, p.30 |
| `get_sweep_state` | `C{ch}:SWWV?` | bare `<channel>:SWeepWaVe?`; future-expansion command, no getter/mock/parser wired, request-only | VERIFIED | PG02-E05B p.38 |
| `set_amplitude` | `C{ch}:BSWV AMP,{amplitude}` | `<channel>:BaSic_WaVe AMP,<amplitude>` | VERIFIED | PG02-E05B p.31 |
| `set_arb_waveform` | `C{ch}:ARWV NAME,{name}` | `<channel>:ArbWaVe NAME,<name>` (Format2); not mocked, dead code (no caller) | VERIFIED | PG02-E05B p.62, p.188 |
| `set_burst_state` | `C{ch}:BTWV STATE,{state}` | `<channel>:BursTWaVe STATE,<state>`; not mocked, dead code (no caller) | VERIFIED | PG02-E05B p.59-60 |
| `set_frequency` | `C{ch}:BSWV FRQ,{frequency}` | `<channel>:BaSic_WaVe FRQ,<frequency>` | VERIFIED | PG02-E05B p.31 |
| `set_function` | `C{ch}:BSWV WVTP,{function}` | `<channel>:BaSic_WaVe WVTP,<type>` | VERIFIED | PG02-E05B p.31 |
| `set_modulation` | `C{ch}:MDWV STATE,{state}` | `<channel>:MoDulateWaVe STATE,<state>`; not mocked, dead code (no caller) | VERIFIED | PG02-E05B p.33, p.36 |
| `set_offset` | `C{ch}:BSWV OFST,{offset}` | `<channel>:BaSic_WaVe OFST,<offset>` | VERIFIED | PG02-E05B p.29-30, p.31 |
| `set_output` | `C{ch}:OUTP {state}` | `<channel>:OUTPut ON\|OFF` (state independently settable per the worked EXAMPLEs) | VERIFIED | PG02-E05B p.28 |
| `set_output_load` | `C{ch}:OUTP LOAD,{load}` | `<channel>:OUTPut LOAD,<load>`; not mocked | VERIFIED | PG02-E05B p.28 |
| `set_output_polarity` | `C{ch}:OUTP PLRT,{polarity}` | `<channel>:OUTPut PLRT,<polarity>`; not mocked, dead code (no caller) | VERIFIED | PG02-E05B p.28 |
| `set_phase` | `C{ch}:BSWV PHSE,{phase}` | `<channel>:BaSic_WaVe PHSE,<phase>` | VERIFIED | PG02-E05B p.29-30, p.31 |
| `set_pulse_duty` | `C{ch}:BSWV DUTY,{duty}` | `<channel>:BaSic_WaVe DUTY,<duty>` | VERIFIED | PG02-E05B p.29-30 |
| `set_ramp_symmetry` | `C{ch}:BSWV SYM,{symmetry}` | `<channel>:BaSic_WaVe SYM,<symmetry>` | VERIFIED | PG02-E05B p.29-30 |
| `set_sweep_state` | `C{ch}:SWWV STATE,{state}` | `<channel>:SweepWaVe STATE,<state>`; not mocked, dead code (no caller) | VERIFIED | PG02-E05B p.37, p.39 |

**Tally: 28 VERIFIED, 0 MISMATCH_DEFERRED, 0 UNCITED (28 total).**

Full detail — the parser, which fields each property reads, and why the three
future-expansion getters stay request-only — is in each entry's `note` field
in `tests/wire_forms.py`. All fourteen getters shared one audit ID (H5, fixed
Task 10): `get_function`/`get_frequency`/`get_amplitude`/`get_offset`/
`get_phase`/`get_pulse_duty`/`get_ramp_symmetry`/`get_output` now read their
own field out of a single real `C{ch}:BSWV?`/`C{ch}:OUTP?` query via
`parse_key_value_response` (`awg_scpi_commands.py`); `get_output_load`/
`get_output_polarity`/`get_arb_waveform` got the same template+mock treatment
but have no `awg_output.py` property to update (dead code, no caller), so
they are verified at the command-table/mock level only; `get_modulation`/
`get_burst_state`/`get_sweep_state` are "future expansion" — no getter, mock
handler, or parser exists anywhere for them — so only the request template
was fixed and they are VERIFIED with no response (request-only) rather than
inventing code nothing exercises.
