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
