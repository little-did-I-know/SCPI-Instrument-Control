# Wire-form inventory

This is the durable answer to "how much of this driver's SCPI is invented?" Every
command in a covered command table is checked, one row at a time, against the
vendor programming guide that documents that dialect, and the result is recorded
here plus as a citation in `tests/wire_forms.py` (the corpus enforced by
`tests/test_wire_conformance.py`). See `docs/development/vendor-manuals.md` for
which manuals are cited, where to get them, and why they aren't committed to the
repo.

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

**Tally: 34 VERIFIED, 6 MISMATCH_DEFERRED, 0 UNCITED (40 total).**

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
