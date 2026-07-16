"""SCPI command abstraction layer for the supported oscilloscope dialects.

Wire dialects with a command table:
- "legacy": the LeCroy-derived flat dialect (TRIG_SELECT, TDIV, C1:VDIV) spoken
  by Siglent SDS1000X-E era scopes.
- "modern": colon-form SCPI (:TRIGger:EDGE:SOURce, :TIMebase:SCALe) documented
  in the SDS Series Programming Guide EN11G for HD/Plus/SDS5000X+ scopes.
- "tektronix": Tek-style headerless SCPI (CH1:SCAle, HORizontal:SCAle) shared
  by the TBS1000C and 2 Series MSO families, with family differences captured
  in VARIANT_OVERRIDES ("tek_tbs" / "tek_mso").

This module holds the per-dialect command tables and the enum conversions
between the library's public vocabulary and each dialect's wire tokens.
"""

import re
from typing import Dict

# Wire dialects with a command table. Grows as vendor tables land.
SUPPORTED_DIALECTS = ("legacy", "modern", "tektronix", "lecroy")

# IEEE-488.2 mandated common commands, identical on every instrument.
IEEE488_BASE = {
    "identify": "*IDN?",
    "reset": "*RST",
    "clear_status": "*CLS",
    "operation_complete": "*OPC?",
}

# Commands written once right after connect-time dialect resolution.
# legacy: response headers off (Siglent legacy echoes headers by default)
# modern: nothing needed
# tektronix: HEADer OFF so queries return bare values (no "CH1:SCALE " prefix)
#            -- TBS1000C PM 077-1691-01 p.96 / 2 Series MSO PM 077-1776-07 p.2-340
CONNECT_SETUP = {
    "legacy": ["CHDR OFF"],
    "modern": [],
    "tektronix": ["HEADer OFF"],
    # CHDR is LeCroy's own short form of COMM_HEADER; OFF omits response
    # headers AND suppresses unit suffixes (MAUI p.7-46). Siglent inherited CHDR.
    "lecroy": ["CHDR OFF"],
}


class SCPICommandSet:
    """Per-model SCPI command table (dialect base + family overrides)."""

    LEGACY_COMMANDS = {
        # Trigger control
        "set_trigger_mode": "TRIG_MODE {mode}",  # mode: AUTO, NORM, SINGLE, STOP
        "get_trigger_mode": "TRIG_MODE?",
        "arm_trigger": "ARM",
        "force_trigger": "FRTR",
        "stop": "STOP",
        "run": "TRIG_MODE AUTO",
        "get_acq_status": "SAST?",
        # Auto setup
        "auto_setup": "ASET",
        # Channel control
        "set_channel_display": "C{ch}:TRA {state}",
        "get_channel_display": "C{ch}:TRA?",
        "set_voltage_div": "C{ch}:VDIV {vdiv}",
        "get_voltage_div": "C{ch}:VDIV?",
        "set_voltage_offset": "C{ch}:OFST {offset}",
        "get_voltage_offset": "C{ch}:OFST?",
        "set_coupling": "C{ch}:CPL {coupling}",  # coupling wire tokens: A1M, D1M, GND
        "get_coupling": "C{ch}:CPL?",
        "set_probe_ratio": "C{ch}:ATTN {ratio}",
        "get_probe_ratio": "C{ch}:ATTN?",
        "set_bandwidth_limit": "C{ch}:BWL {limit}",  # limit: ON, OFF
        "get_bandwidth_limit": "C{ch}:BWL?",
        # Timebase control
        "set_time_div": "TDIV {tdiv}",
        "get_time_div": "TDIV?",
        "set_time_offset": "TRDL {offset}",
        "get_time_offset": "TRDL?",
        "get_sample_rate": "SARA?",
        # Trigger settings
        "set_trigger_select": "TRIG_SELECT {type},SR,{src}",
        "get_trigger_select": "TRIG_SELECT?",
        "set_trigger_level": "{src}:TRLV {level}",
        "get_trigger_level": "{src}:TRLV?",
        "set_trigger_slope": "{src}:TRSL {slope}",
        "get_trigger_slope": "{src}:TRSL?",
        "set_trigger_coupling": "{src}:TRCP {coupling}",
        "get_trigger_coupling": "{src}:TRCP?",
        # Waveform acquisition (transfer path unchanged until the waveform
        # sub-project; the DAT2 path works on both scope generations)
        "get_waveform": "C{ch}:WF? DAT2",
        "get_waveform_preamble": "C{ch}:WF? DESC",
        # Measurements
        # NOTE: get_parameter_value's wire form is "PAVA? {param},C{ch}" (mtype
        # first, then a C-prefixed channel) -- this is what measurement.py
        # actually sent pre-refactor and what the legacy mock's PAVA? regex
        # parses; do not "correct" it to "C{ch}:PAVA? {param}".
        "get_parameter_value": "PAVA? {param},C{ch}",
        "add_measurement": "PACU {mtype},C{ch}",
        "set_statistics": "PAST {state}",
        "clear_measurements": "PACL",
        "reset_statistics": "PASTAT RESET",
        # Cursor control
        "set_cursor_type": "CRST {type}",
        "get_cursor_type": "CRST?",
        # NOTE: bare query -- no cursor id is ever passed by measurement.py.
        "get_cursor_value": "CRVA?",
        # Trigger holdoff (AUDIT M4: TRIG_DELAY is really trigger delay, not
        # holdoff; legacy-only, routing deferred to a trigger-rework follow-up)
        "set_trigger_holdoff": "TRIG_DELAY {t}",
        "get_trigger_holdoff": "TRIG_DELAY?",
        # Channel vertical unit (legacy-only)
        "set_channel_unit": "C{ch}:UNIT {unit}",
        "get_channel_unit": "C{ch}:UNIT?",
        # Math operations (basic)
        "set_math_display": "MATH{n}:TRA {state}",
        "get_math_display": "MATH{n}:TRA?",
        # Screen capture
        "screen_dump": "SCDP",
        "set_hardcopy_format": "HCSU DEV,FORMAT,{format}",
        "hardcopy_print": "HCSU PRINT",
    }

    # Modern colon-form dialect, verbatim from the SDS Series Programming
    # Guide EN11G (page references in the design spec's command table).
    MODERN_COMMANDS = {
        # Trigger control (p.482-484; no standalone ARM/force — FTRIG forces)
        "set_trigger_mode": ":TRIGger:MODE {mode}",  # wire modes: AUTO, NORMal, SINGle, FTRIG
        "get_trigger_mode": ":TRIGger:MODE?",
        "force_trigger": ":TRIGger:MODE FTRIG",
        "stop": ":TRIGger:STOP",
        "run": ":TRIGger:RUN",
        "get_acq_status": ":TRIGger:STATus?",
        # Auto setup (p.33, command-only)
        "auto_setup": ":AUToset",
        # Channel control (p.50-60)
        "set_channel_display": ":CHANnel{ch}:SWITch {state}",
        "get_channel_display": ":CHANnel{ch}:SWITch?",
        "set_voltage_div": ":CHANnel{ch}:SCALe {vdiv}",
        "get_voltage_div": ":CHANnel{ch}:SCALe?",
        "set_voltage_offset": ":CHANnel{ch}:OFFSet {offset}",
        "get_voltage_offset": ":CHANnel{ch}:OFFSet?",
        "set_coupling": ":CHANnel{ch}:COUPling {coupling}",  # coupling wire tokens: DC, AC, GND
        "get_coupling": ":CHANnel{ch}:COUPling?",
        "set_probe_ratio": ":CHANnel{ch}:PROBe VALue,{ratio}",
        "get_probe_ratio": ":CHANnel{ch}:PROBe?",
        "set_bandwidth_limit": ":CHANnel{ch}:BWLimit {limit}",  # limit: FULL, 20M, 200M
        "get_bandwidth_limit": ":CHANnel{ch}:BWLimit?",
        # Timebase control (p.473-476)
        "set_time_div": ":TIMebase:SCALe {tdiv}",
        "get_time_div": ":TIMebase:SCALe?",
        "set_time_offset": ":TIMebase:DELay {offset}",
        "get_time_offset": ":TIMebase:DELay?",
        "get_sample_rate": ":ACQuire:SRATe?",  # p.46
        # Trigger settings (p.484-495)
        "set_trigger_type": ":TRIGger:TYPE {type}",
        "get_trigger_type": ":TRIGger:TYPE?",
        "set_trigger_source": ":TRIGger:EDGE:SOURce {src}",
        "get_trigger_source": ":TRIGger:EDGE:SOURce?",
        "set_trigger_level": ":TRIGger:EDGE:LEVel {level}",
        "get_trigger_level": ":TRIGger:EDGE:LEVel?",
        "set_trigger_slope": ":TRIGger:EDGE:SLOPe {slope}",  # wire slopes: RISing, FALLing, ALTernate
        "get_trigger_slope": ":TRIGger:EDGE:SLOPe?",
        "set_trigger_coupling": ":TRIGger:EDGE:COUPling {coupling}",
        "get_trigger_coupling": ":TRIGger:EDGE:COUPling?",
        # Waveform acquisition — unchanged until the waveform sub-project
        "get_waveform": "C{ch}:WF? DAT2",
        "get_waveform_preamble": "C{ch}:WF? DESC",
        # Measurements — get_parameter_value stays available (measure() keeps
        # working on modern, a documented gap); statistics/cursors/holdoff/unit
        # are legacy-only and intentionally absent so they gate cleanly.
        "get_parameter_value": "C{ch}:PAVA? {param}",
        # Screen capture (legacy strings accepted on modern scopes today; revisit with screen-capture overhaul)
        "screen_dump": "SCDP",
        "set_hardcopy_format": "HCSU DEV,FORMAT,{format}",
        "hardcopy_print": "HCSU PRINT",
    }

    # Tektronix dialect, verified command-by-command against the TBS1000C
    # Programmer Manual 077-1691-01 (current edition, supersedes 077-1430-xx;
    # cited below as "TBS p.N") and the 2 Series MSO (MSO22/MSO24) Programmer
    # Manual 077-1776-07 (cited as "MSO2 p.2-N"); both printed page numbers.
    # Family differences live in VARIANT_OVERRIDES["tek_tbs"/"tek_mso"]:
    # channel display, probe attenuation, PT_Off, and immediate measurements
    # diverge between the families.
    TEKTRONIX_COMMANDS = {
        # Acquisition control
        "set_trigger_mode": "TRIGger:A:MODe {mode}",  # AUTO|NORMal -- TBS p.155 / MSO2 p.2-684
        "get_trigger_mode": "TRIGger:A:MODe?",  # TBS p.155 / MSO2 p.2-684
        "force_trigger": "TRIGger FORCe",  # TBS p.149 / MSO2 p.2-626
        "run": "ACQuire:STATE RUN",  # TBS p.42 / MSO2 p.2-78
        "stop": "ACQuire:STATE STOP",  # TBS p.42 / MSO2 p.2-78
        "set_stop_after": "ACQuire:STOPAfter {mode}",  # RUNSTop|SEQuence -- TBS p.43 / MSO2 p.2-80
        "get_acq_status": "TRIGger:STATE?",  # ARMED|AUTO|READY|SAVE|TRIGGER -- TBS p.162 / MSO2 p.2-686
        "auto_setup": "AUTOSet EXECute",  # TBS p.47 / MSO2 p.2-113
        # Channel control
        "set_channel_display": "SELect:CH{ch} {state}",  # ON|OFF|<NR1> -- TBS p.144 (MSO2: tek_mso override)
        "get_channel_display": "SELect:CH{ch}?",  # returns 1|0 -- TBS p.144
        "set_voltage_div": "CH{ch}:SCAle {vdiv}",  # TBS p.58 / MSO2 p.2-184
        "get_voltage_div": "CH{ch}:SCAle?",  # TBS p.58 / MSO2 p.2-184
        "set_voltage_offset": "CH{ch}:OFFSet {offset}",  # TBS p.55 / MSO2 p.2-191
        "get_voltage_offset": "CH{ch}:OFFSet?",  # TBS p.55 / MSO2 p.2-191
        # Coupling: TBS {AC|DC} only, MSO2 {AC|DC|DCREJect}; neither family
        # has GND coupling -- TBS p.53 / MSO2 p.2-184
        "set_coupling": "CH{ch}:COUPling {coupling}",
        "get_coupling": "CH{ch}:COUPling?",  # TBS p.53 / MSO2 p.2-184
        # Bandwidth: TBS {TWEnty|FULl|<NR3>} p.53; MSO2 {<NR3>|FULl} p.2-183
        # (no TWEnty token on MSO2 -- send FULl or a hertz value for portability)
        "set_bandwidth_limit": "CH{ch}:BANdwidth {limit}",
        "get_bandwidth_limit": "CH{ch}:BANdwidth?",  # TBS p.53 / MSO2 p.2-183
        # Timebase
        "set_time_div": "HORizontal:SCAle {tdiv}",  # TBS p.104 / MSO2 p.2-349
        "get_time_div": "HORizontal:SCAle?",  # TBS p.104 / MSO2 p.2-349
        "set_time_offset": "HORizontal:DELay:TIMe {offset}",  # TBS p.103 / MSO2 p.2-343
        "get_time_offset": "HORizontal:DELay:TIMe?",  # TBS p.103 / MSO2 p.2-343
        "get_sample_rate": "HORizontal:SAMPLERate?",  # TBS p.104 (query only) / MSO2 p.2-348
        # Edge trigger
        "set_trigger_type": "TRIGger:A:TYPe {type}",  # TBS {EDGe|PULSe} p.161 / MSO2 {EDGE|WIDth|...} p.2-682
        "get_trigger_type": "TRIGger:A:TYPe?",  # TBS p.161 / MSO2 p.2-682
        "set_trigger_source": "TRIGger:A:EDGE:SOUrce {src}",  # TBS p.152 / MSO2 p.2-662
        "get_trigger_source": "TRIGger:A:EDGE:SOUrce?",  # TBS p.152 / MSO2 p.2-662
        "set_trigger_level": "TRIGger:A:LEVel:CH{ch} {level}",  # TBS p.154 / MSO2 p.2-663
        "get_trigger_level": "TRIGger:A:LEVel:CH{ch}?",  # TBS p.154 / MSO2 p.2-663
        "set_trigger_slope": "TRIGger:A:EDGE:SLOpe {slope}",  # TBS {RISe|FALL} p.151 / MSO2 adds EITher p.2-662
        "get_trigger_slope": "TRIGger:A:EDGE:SLOpe?",  # TBS p.151 / MSO2 p.2-662
        "set_trigger_coupling": "TRIGger:A:EDGE:COUPling {coupling}",  # DC|HFRej|LFRej|NOISErej -- TBS p.151 / MSO2 p.2-661
        "get_trigger_coupling": "TRIGger:A:EDGE:COUPling?",  # TBS p.151 / MSO2 p.2-661
        # Holdoff (TBS prints the keyword as HOLDOff, MSO2 as HOLDoff; the
        # full spelling below is identical on both -- SCPI is case-insensitive)
        "set_trigger_holdoff": "TRIGger:A:HOLDoff:TIMe {t}",  # TBS p.153 / MSO2 p.2-684
        "get_trigger_holdoff": "TRIGger:A:HOLDoff:TIMe?",  # TBS p.153 / MSO2 p.2-684
        # Waveform transfer (CURVe protocol)
        "set_data_source": "DATa:SOUrce CH{ch}",  # TBS p.71 / MSO2 p.2-208
        # DATa:ENCdg has no D-section entry in the TBS manual but is used by
        # its own transfer procedure (p.38) and echoed by DATa? (p.70);
        # RIBinary = signed int, MSB first on both families -- MSO2 p.2-205
        "set_data_encoding": "DATa:ENCdg RIBinary",
        "set_data_width": "DATa:WIDth 1",  # 8-bit for this project (16-bit is a follow-up) -- TBS p.72 / MSO2 p.2-211
        "set_data_start": "DATa:STARt {start}",  # TBS p.71 / MSO2 p.2-209
        "set_data_stop": "DATa:STOP {stop}",  # TBS p.72 / MSO2 p.2-210
        "get_wfm_nr_pt": "WFMOutpre:NR_Pt?",  # TBS p.174 / MSO2 p.2-204
        "get_wfm_xincr": "WFMOutpre:XINcr?",  # TBS p.175 / MSO2 p.2-706
        "get_wfm_xzero": "WFMOutpre:XZEro?",  # TBS p.176 / MSO2 p.2-702
        # NOTE: no WFMOutpre:PT_Off? on TBS1000C (leaf absent from its
        # WFMOutpre subsystem, pp.172-177) -- MSO2-only, see tek_mso override
        "get_wfm_ymult": "WFMOutpre:YMUlt?",  # TBS p.176 / MSO2 p.2-707
        "get_wfm_yzero": "WFMOutpre:YZEro?",  # TBS p.177 / MSO2 p.2-709
        "get_wfm_yoff": "WFMOutpre:YOFf?",  # TBS p.176 / MSO2 p.2-708
        "get_waveform": "CURVe?",  # TBS p.68 / MSO2 p.2-77
        # Immediate measurements (MEASUrement:IMMed) are TBS-only: the MSO2
        # manual has no IMMed:TYPe/SOUrce1/VALue commands (badge-based
        # MEASUrement:MEAS<x> instead) -- see tek_tbs override.
    }

    # LeCroy MAUI dialect, per the MAUI Oscilloscopes Remote Control and
    # Automation Manual (cited "MAUI p.<part>-<section>" by printed page number;
    # command reference is Part 7, VBS?/automation wrapper is Part 2). Every
    # entry was verified against that manual (see task-13 report). Siglent's
    # legacy dialect is derived from this one; entries below are the LeCroy
    # originals.
    LECROY_COMMANDS = {
        # Trigger control -- all page cites are printed "Part-Section" numbers
        # from Part 7 (IEEE 488.2 Command Reference) unless noted.
        "set_trigger_mode": "TRIG_MODE {mode}",  # TRIG_MODE (TRMD) {AUTO,NORM,SINGLE,STOP} -- MAUI p.7-34
        "get_trigger_mode": "TRIG_MODE?",  # resp "TRIG_MODE <mode>" -- MAUI p.7-34
        "arm_trigger": "ARM",  # ARM_ACQUISITION (ARM) -- MAUI p.7-15
        "force_trigger": "FRTR",  # FORCE_TRIGGER (FRTR) -- MAUI p.7-21
        "stop": "STOP",  # STOP: sets Stopped trigger mode -- MAUI p.7-28
        "run": "TRIG_MODE AUTO",  # continuous acquisition via TRIG_MODE -- MAUI p.7-34
        "get_acq_status": "INR?",  # INR? reads+clears INTERNAL_STATE_CHANGE reg (p.7-132); bit0="new signal acquired" (p.7-133). Siglent invented SAST.
        # Auto setup: bare ASET performs a normal auto-setup (channel prefix optional) -- MAUI p.7-16
        "auto_setup": "ASET",  # AUTO_SETUP (ASET) -- MAUI p.7-16
        # Channel control
        "set_channel_display": "C{ch}:TRA {state}",  # TRACE (TRA) {ON,OFF} -- MAUI p.7-88
        "get_channel_display": "C{ch}:TRA?",  # MAUI p.7-88
        "set_voltage_div": "C{ch}:VDIV {vdiv}",  # VOLT_DIV (VDIV) -- MAUI p.7-41
        "get_voltage_div": "C{ch}:VDIV?",  # MAUI p.7-41
        "set_voltage_offset": "C{ch}:OFST {offset}",  # OFFSET (OFST) -- MAUI p.7-24
        "get_voltage_offset": "C{ch}:OFST?",  # MAUI p.7-24
        "set_coupling": "C{ch}:CPL {coupling}",  # COUPLING (CPL) {A1M,D1M,D50,GND} -- MAUI p.7-20
        "get_coupling": "C{ch}:CPL?",  # query may also return OVL (overload) -- MAUI p.7-20
        "set_probe_ratio": "C{ch}:ATTN {ratio}",  # ATTENUATION (ATTN) {1..10000} -- MAUI p.7-17
        "get_probe_ratio": "C{ch}:ATTN?",  # MAUI p.7-17
        # Bandwidth limit differs from legacy: BWL is global, ch/mode pairs.
        # NOTE: LeCroy <mode> is {OFF,20MHZ,200MHZ,...} -- there is NO "ON"
        # token; channel.py maps public ON->20MHZ (and any non-OFF wire
        # token back to public ON on the getter) -- see task-16 report.
        "set_bandwidth_limit": "BWL C{ch},{limit}",  # BANDWIDTH_LIMIT (BWL) -- MAUI p.7-18
        "get_bandwidth_limit": "BWL?",  # returns "C1,OFF,C2,20MHZ,..." pairs -- MAUI p.7-18
        # Timebase control
        "set_time_div": "TDIV {tdiv}",  # TIME_DIV (TDIV) -- MAUI p.7-29
        "get_time_div": "TDIV?",  # MAUI p.7-29
        "set_time_offset": "TRDL {offset}",  # TRIG_DELAY (TRDL) = horizontal delay -- MAUI p.7-31
        "get_time_offset": "TRDL?",  # MAUI p.7-31
        # Sample rate: no legacy-style query on LeCroy -- read via the MAUI
        # automation (VBS?) object model. The VBS? 'return=app...' wrapper is
        # documented at MAUI p.2-12..2-18; the exact cvar SamplingRate is NOT
        # enumerated in this manual's Part 4 reference (UNVERIFIED, see report).
        "get_sample_rate": "VBS? 'return=app.Acquisition.Horizontal.SamplingRate'",  # VBS? wrapper -- MAUI p.2-13
        # Trigger settings
        "set_trigger_select": "TRIG_SELECT {type},SR,{src}",  # TRIG_SELECT (TRSE); SR=Trigger Source param, EDGE type -- MAUI p.7-36
        "get_trigger_select": "TRIG_SELECT?",  # MAUI p.7-36
        "set_trigger_level": "{src}:TRLV {level}",  # TRIG_LEVEL (TRLV) -- MAUI p.7-33
        "get_trigger_level": "{src}:TRLV?",  # MAUI p.7-33
        "set_trigger_slope": "{src}:TRSL {slope}",  # TRIG_SLOPE (TRSL) {NEG,POS} -- MAUI p.7-40
        "get_trigger_slope": "{src}:TRSL?",  # MAUI p.7-40
        "set_trigger_coupling": "{src}:TRCP {coupling}",  # TRIG_COUPLING (TRCP) {AC,DC,HFREJ,LFREJ} -- MAUI p.7-30
        "get_trigger_coupling": "{src}:TRCP?",  # MAUI p.7-30
        # Waveform acquisition: WF? ALL returns descriptor+data in one block;
        # CFMT/CORD pin the binary block encoding for the transfer sub-project.
        "get_waveform": "C{ch}:WF? ALL",  # WAVEFORM (WF) ALL block -- MAUI p.7-150
        "get_waveform_preamble": "C{ch}:WF? DESC",  # WAVEFORM (WF) DESC block -- MAUI p.7-150
        "set_comm_format": "CFMT DEF9,{fmt},BIN",  # COMM_FORMAT (CFMT) DEF9,{BYTE,WORD},BIN -- MAUI p.7-44
        "set_comm_order": "CORD LO",  # COMM_ORDER (CORD) {HI,LO}, LO=LSB first -- MAUI p.7-49
        # Measurements
        # PAVA-form decision: use the LeCroy-native trace-prefix form
        # "C{ch}:PAVA? {param}" (MAUI p.7-70), NOT the Siglent "PAVA? p,C{ch}"
        # form. LeCroy's PAVA? response is "<param>,<value>,<state>" (3 fields);
        # measurement.py's parser reads parts[2] (=value on Siglent, =state on
        # LeCroy), so measure() has a lecroy branch reading parts[1] instead
        # (see task-16 report). Vocabulary = PARAMETER_VALUE.
        "get_parameter_value": "C{ch}:PAVA? {param}",  # PARAMETER_VALUE? (PAVA?) -- MAUI p.7-70
        "clear_measurements": "PACL",  # PARAMETER_CLR (PACL / PARAMETER_CLEAR), no args -- MAUI p.7-58
        # add_measurement OMITTED: LeCroy PACU is "PACU <slot>,<measurement>,
        #   <qualifier>" (slot number first, MAUI p.7-59), NOT the Siglent
        #   "PACU {mtype},C{ch}" form -> FeatureNotSupportedError until a
        #   slot-aware implementation lands.
        # set_statistics/reset_statistics OMITTED: PAST/PASTAT are Siglent
        #   spellings, not LeCroy commands -> FeatureNotSupportedError.
        # set_cursor_type/get_cursor_value OMITTED: LeCroy CRST is CURSOR_SET
        #   (positioning) and CRVA? is trace-prefixed with {HABS,HREL,VABS,VREL}
        #   modes (MAUI p.7-55) -- neither matches the Siglent cursor path.
        # set_trigger_holdoff/get_trigger_holdoff OMITTED: TRDL is trigger delay,
        #   not holdoff; LeCroy holdoff lives in TRIG_SELECT HT/HV (MAUI p.7-36).
        # set_channel_unit/get_channel_unit OMITTED: no LeCroy C<n>:UNIT command.
        # Math operations: LeCroy math traces are F1..Fn (TRACE, MAUI p.7-88),
        # NOT Siglent's MATH<n> (math module out of scope; corrected for honesty)
        "set_math_display": "F{n}:TRA {state}",  # TRACE (TRA) on F<n> -- MAUI p.7-88
        "get_math_display": "F{n}:TRA?",  # MAUI p.7-88
        # Screen capture -- keep (LeCroy-origin; screen module out of scope).
        # NOTE: HCSU arg grammar below is the Siglent-adapted form; LeCroy HCSU
        # uses "DEV,<device>,FORMAT,<format>,..." pairs and has no PRINT keyword
        # (print = SCDP to a PRINTER destination) -- rework with the screen module.
        "screen_dump": "SCDP",  # SCREEN_DUMP (SCDP) -- MAUI p.7-104
        "set_hardcopy_format": "HCSU DEV,FORMAT,{format}",  # HARDCOPY_SETUP (HCSU) -- MAUI p.7-102
        "hardcopy_print": "HCSU PRINT",  # HARDCOPY_SETUP (HCSU) -- MAUI p.7-102
    }

    # Dialect base tables, keyed by dialect name.
    DIALECT_TABLES = {
        "legacy": LEGACY_COMMANDS,
        "modern": MODERN_COMMANDS,
        "tektronix": TEKTRONIX_COMMANDS,
        "lecroy": LECROY_COMMANDS,
    }

    # Family overrides applied on top of the dialect base table.
    VARIANT_OVERRIDES: Dict[str, Dict[str, str]] = {
        "standard": {},
        "hd_series": {},
        "x_series": {},  # HCSU? screen-dump override removed: it was a hardcopy SETUP query, not a dump
        "plus_series": {},
        "tek_tbs": {
            # Probe attenuation as gain factor: "a common 10x probe has a
            # gain of 0.1" -- TBS p.56 (no PRObe:GAIN on MSO2)
            "set_probe_ratio": "CH{ch}:PRObe:GAIN {gain}",
            "get_probe_ratio": "CH{ch}:PRObe:GAIN?",
            # Immediate measurements -- TBS pp.117-121 (absent from the MSO2
            # command set, so MSO models gate with FeatureNotSupportedError)
            "set_meas_immed_type": "MEASUrement:IMMed:TYPe {type}",  # TBS p.119
            "set_meas_immed_source": "MEASUrement:IMMed:SOUrce1 CH{ch}",  # TBS p.117
            "get_meas_immed_value": "MEASUrement:IMMed:VALue?",  # TBS p.121
        },
        "tek_mso": {
            # MSO2 has no SELect subsystem; display is per-channel global
            # state {<NR1>|OFF|ON} -- MSO2 p.2-225
            "set_channel_display": "DISplay:GLObal:CH{ch}:STATE {state}",
            "get_channel_display": "DISplay:GLObal:CH{ch}:STATE?",
            # External attenuation "as a multiplier" (gain form, e.g.
            # 167.00E-3) -- MSO2 p.2-192; closest equivalent of TBS PRObe:GAIN
            "set_probe_ratio": "CH{ch}:PROBEFunc:EXTAtten {gain}",
            "get_probe_ratio": "CH{ch}:PROBEFunc:EXTAtten?",
            # Preamble trigger-point offset, MSO2-only -- MSO2 p.2-701
            "get_wfm_pt_off": "WFMOutpre:PT_Off?",
        },
        # LeCroy MAUI family: the base table is already MAUI-correct, so no
        # per-family overrides are needed today (placeholder for future splits
        # between WaveRunner/HDO/WaveSurfer generations).
        "lecroy_maui": {},
    }

    def __init__(self, dialect: str = "legacy", scpi_variant: str = "standard"):
        """Build the command set for a dialect + model family.

        Args:
            dialect: wire dialect (one of SUPPORTED_DIALECTS) — selects the base table
            scpi_variant: family identifier ("standard", "hd_series", "x_series", "plus_series") for overrides
        """
        if dialect not in SUPPORTED_DIALECTS:
            raise ValueError(f"Unknown SCPI dialect: {dialect}. Must be one of {SUPPORTED_DIALECTS}.")
        self.dialect = dialect
        self.scpi_variant = scpi_variant
        self._command_set = self._build_command_set(dialect, scpi_variant)

    def _build_command_set(self, dialect: str, variant: str) -> Dict[str, str]:
        command_set = dict(IEEE488_BASE)
        command_set.update(self.DIALECT_TABLES[dialect])
        command_set.update(self.VARIANT_OVERRIDES.get(variant, {}))
        return command_set

    def get_command(self, command_name: str, **kwargs) -> str:
        """Get SCPI command string with parameter substitution.

        Args:
            command_name: Name of the command (e.g., "set_voltage_div")
            **kwargs: Parameters to substitute in the command template
                     Common parameters:
                     - ch: Channel number (1-4)
                     - mode: Mode value
                     - state: State value (ON/OFF)
                     - vdiv: Voltage division
                     - etc.

        Returns:
            Formatted SCPI command string

        Raises:
            KeyError: If command_name is not in the command set

        Example:
            >>> cmd_set = SCPICommandSet("hd_series")
            >>> cmd_set.get_command("set_voltage_div", ch=1, vdiv="1V")
            'C1:VDIV 1V'
        """
        if command_name not in self._command_set:
            raise KeyError(f"Unknown command: {command_name}")

        command_template = self._command_set[command_name]

        # Substitute parameters if any
        if kwargs:
            try:
                return command_template.format(**kwargs)
            except KeyError as e:
                raise ValueError(f"Missing required parameter for command '{command_name}': {e}")

        return command_template

    def has_command(self, command_name: str) -> bool:
        """Check if a command is available in this command set.

        Args:
            command_name: Name of the command to check

        Returns:
            True if command exists, False otherwise
        """
        return command_name in self._command_set

    def list_commands(self) -> list:
        """Get list of all available command names.

        Returns:
            List of command names
        """
        return sorted(self._command_set.keys())

    def add_custom_command(self, command_name: str, command_template: str) -> None:
        """Add or override a command in the command set.

        This is useful for adding model-specific commands or user extensions.

        Args:
            command_name: Name for the command
            command_template: SCPI command template string
        """
        self._command_set[command_name] = command_template

    def __repr__(self) -> str:
        """String representation."""
        return f"SCPICommandSet(dialect='{self.dialect}', variant='{self.scpi_variant}', commands={len(self._command_set)})"


# ---- Public-vocabulary <-> wire-token conversions -------------------------
# The library's public API always speaks: modes AUTO|NORM|SINGLE|STOP,
# slopes POS|NEG|WINDOW, coupling DC|AC|GND, sources C1..C4|EX|EX5|LINE.
# These tables convert at the dialect boundary and are the only place wire
# enums are spelled out. A missing (dialect, token) pair means the dialect
# cannot express that public token -> FeatureNotSupportedError.

from scpi_control import exceptions

# Dialects whose trigger commands are per-source-prefixed (C1:TRLV ...) rather
# than global (:TRIGger:EDGE:LEVel ...). These also have a STOP trigger-mode
# wire token; the global-style dialects detect STOP via acquisition status.
FLAT_TRIGGER_DIALECTS = frozenset({"legacy", "lecroy"})

# Dialects whose numeric queries return a bare NR3 value with no unit suffix.
# LeCroy joins because CHDR OFF also suppresses the trailing unit token on
# LeCroy responses -- e.g. C1:VDIV? returns "200E-3", not "200E-3 V" (MAUI
# p.7-46) -- unlike Siglent legacy, which keeps the unit.
BARE_NR3_DIALECTS = frozenset({"modern", "tektronix", "lecroy"})


def is_flat_trigger(dialect: str) -> bool:
    return dialect in FLAT_TRIGGER_DIALECTS


_MODE_TO_WIRE = {
    "legacy": {"AUTO": "AUTO", "NORM": "NORM", "SINGLE": "SINGLE", "STOP": "STOP"},
    "modern": {"AUTO": "AUTO", "NORM": "NORMal", "SINGLE": "SINGle"},
    # AUTO|NORMal (TBS p.155 / MSO2 p.2-684); SINGLE/STOP are command sequences
    "tektronix": {"AUTO": "AUTO", "NORM": "NORMal"},
    # LeCroy TRIG_MODE {AUTO,NORM,SINGLE,STOP} -- ancestor of legacy tokens (MAUI p.7-34)
    "lecroy": {"AUTO": "AUTO", "NORM": "NORM", "SINGLE": "SINGLE", "STOP": "STOP"},
}
_MODE_FROM_WIRE = {
    "legacy": {"AUTO": "AUTO", "NORM": "NORM", "SINGLE": "SINGLE", "STOP": "STOP"},
    "modern": {"AUTO": "AUTO", "NORMAL": "NORM", "SINGLE": "SINGLE", "FTRIG": "AUTO"},
    "tektronix": {"AUTO": "AUTO", "NORMAL": "NORM", "NORM": "NORM"},
    "lecroy": {"AUTO": "AUTO", "NORM": "NORM", "SINGLE": "SINGLE", "STOP": "STOP"},
}
_SLOPE_TO_WIRE = {
    "legacy": {"POS": "POS", "NEG": "NEG", "WINDOW": "WINDOW"},
    "modern": {"POS": "RISing", "NEG": "FALLing", "WINDOW": "ALTernate"},
    # RISe|FALL (TBS p.151 / MSO2 p.2-662); WINDOW has no Tek edge equivalent
    # (MSO2's third token is EITher, which is absent on TBS)
    "tektronix": {"POS": "RISe", "NEG": "FALL"},
    # LeCroy TRIG_SLOPE is {NEG, POS} only (MAUI p.7-40) -- no WINDOW edge slope,
    # so WINDOW gates as FeatureNotSupportedError (mirrors the Tek GND removal).
    "lecroy": {"POS": "POS", "NEG": "NEG"},
}
_SLOPE_FROM_WIRE = {
    "legacy": {"POS": "POS", "NEG": "NEG", "WINDOW": "WINDOW"},
    "modern": {"RISING": "POS", "FALLING": "NEG", "ALTERNATE": "WINDOW"},
    "tektronix": {"RISE": "POS", "FALL": "NEG"},
    "lecroy": {"POS": "POS", "NEG": "NEG"},
}
_COUPLING_TO_WIRE = {
    "legacy": {"DC": "D1M", "AC": "A1M", "GND": "GND"},
    "modern": {"DC": "DC", "AC": "AC", "GND": "GND"},
    # No GND coupling on either Tek family: TBS is {AC|DC} (p.53), MSO2 is
    # {AC|DC|DCREJect} (p.2-184) -- GND gates as FeatureNotSupportedError
    "tektronix": {"DC": "DC", "AC": "AC"},
    # LeCroy COUPLING {A1M,D1M,D50,GND} (MAUI p.7-20) -- ancestor of legacy tokens
    "lecroy": {"DC": "D1M", "AC": "A1M", "GND": "GND"},
}
_COUPLING_FROM_WIRE = {
    "legacy": {"D1M": "DC", "A1M": "AC", "D50": "DC", "A50": "AC", "GND": "GND"},
    "modern": {"DC": "DC", "AC": "AC", "GND": "GND"},
    # DCREJect (MSO2 PM 077-1776-07 p.2-184) passes AC only -- normalize to
    # the public AC token rather than surfacing the Tek-specific spelling.
    "tektronix": {"DC": "DC", "AC": "AC", "DCREJ": "AC", "DCREJECT": "AC"},
    # LeCroy CPL? returns {A1M,D1M,D50,GND} (D50=DC 50 ohm; also OVL on overload,
    # which is intentionally unmapped -> ValueError). A50 is not a LeCroy token
    # but is kept as a harmless superset. -- MAUI p.7-20
    "lecroy": {"D1M": "DC", "A1M": "AC", "D50": "DC", "A50": "AC", "GND": "GND"},
}

_PUBLIC_MODES = {"AUTO", "NORM", "SINGLE", "STOP"}
_PUBLIC_SLOPES = {"POS", "NEG", "WINDOW"}
_PUBLIC_COUPLINGS = {"DC", "AC", "GND"}

# Acquisition-status vocabulary shared by every dialect's status query.
# TRIGGER/SAVE are the Tek TRIGger:STATE? vocabulary (SAVE == acquisition
# stopped) -- TBS p.162 / MSO2 p.2-686.
_STATUS_MAP = {"ARM": "ARM", "ARMED": "ARM", "READY": "READY", "AUTO": "AUTO", "TRIG'D": "TRIGD", "TRIGGER": "TRIGD", "STOP": "STOP", "SAVE": "STOP", "ROLL": "ROLL"}


def _last_token(raw: str) -> str:
    return raw.strip().split()[-1].upper() if raw.strip() else ""


def _to_wire(table, public_values, dialect: str, token: str, what: str) -> str:
    token = token.upper()
    if token not in public_values:
        raise ValueError(f"Invalid {what}: {token}. Must be one of {sorted(public_values)}.")
    try:
        return table[dialect][token]
    except KeyError:
        raise exceptions.FeatureNotSupportedError(f"{what} {token} is not supported on the {dialect} dialect")


def _from_wire(table, dialect: str, raw: str, what: str) -> str:
    token = _last_token(raw)
    try:
        return table[dialect][token]
    except KeyError:
        raise ValueError(f"Unrecognized {dialect} {what} response: {raw!r}")


# Public measurement vocabulary (PAVA parameter names). Identity for Siglent
# dialects; vendor dialects map or reject per their manuals.
_MEASUREMENT_TYPES = {"PKPK", "MAX", "MIN", "AMPL", "TOP", "BASE", "CMEAN", "MEAN", "RMS", "CRMS", "FREQ", "PER", "RISE", "FALL", "WID", "NWID", "DUTY"}
_MEASUREMENT_TO_WIRE = {
    "legacy": {m: m for m in _MEASUREMENT_TYPES},
    "modern": {m: m for m in _MEASUREMENT_TYPES},
    # LeCroy PARAMETER_VALUE (PAVA) parameter names -- identity, the ancestor
    # of the Siglent legacy vocabulary (MAUI p.7-70).
    "lecroy": {m: m for m in _MEASUREMENT_TYPES},
    # Tek MEASUrement:IMMed:TYPe vocabulary, verbatim from TBS p.119 (the
    # IMMed subsystem is TBS-only; MSO2's MEAS<x> badge vocabulary differs
    # and is a follow-up when badge measurements land).
    "tektronix": {
        "PKPK": "PK2Pk", "MAX": "MAXimum", "MIN": "MINImum", "AMPL": "AMPlitude",
        "TOP": "HIGH", "BASE": "LOW", "CMEAN": "CMEan", "MEAN": "MEAN",
        "RMS": "RMS", "CRMS": "CRMs", "FREQ": "FREQuency", "PER": "PERIod",
        "RISE": "RISe", "FALL": "FALL", "WID": "PWIdth", "NWID": "NWIdth", "DUTY": "PDUty",
    },
}


def measurement_to_wire(dialect: str, mtype: str) -> str:
    """Convert a public measurement type to the dialect's wire token."""
    return _to_wire(_MEASUREMENT_TO_WIRE, _MEASUREMENT_TYPES, dialect, mtype, "measurement type")


def mode_to_wire(dialect: str, mode: str) -> str:
    """Convert a public trigger mode to the wire token.

    STOP is only a wire mode on flat-trigger dialects; global-style dialects
    implement it via their stop command, and callers handle it before converting.
    """
    return _to_wire(_MODE_TO_WIRE, _PUBLIC_MODES, dialect, mode, "trigger mode")


def mode_from_wire(dialect: str, raw: str) -> str:
    """Normalize a trigger-mode query response to AUTO|NORM|SINGLE|STOP."""
    return _from_wire(_MODE_FROM_WIRE, dialect, raw, "trigger mode")


def slope_to_wire(dialect: str, slope: str) -> str:
    return _to_wire(_SLOPE_TO_WIRE, _PUBLIC_SLOPES, dialect, slope, "trigger slope")


def slope_from_wire(dialect: str, raw: str) -> str:
    return _from_wire(_SLOPE_FROM_WIRE, dialect, raw, "trigger slope")


def coupling_to_wire(dialect: str, coupling: str) -> str:
    return _to_wire(_COUPLING_TO_WIRE, _PUBLIC_COUPLINGS, dialect, coupling, "coupling mode")


def coupling_from_wire(dialect: str, raw: str) -> str:
    return _from_wire(_COUPLING_FROM_WIRE, dialect, raw, "coupling mode")


def channel_token(dialect: str, source) -> str:
    """Convert a public channel source (int, 'C2', 'EX', 'LINE') to the wire token."""
    if isinstance(source, int):
        number = source
    else:
        token = str(source).strip().upper()
        match = re.fullmatch(r"C(?:H)?(\d+)", token)
        if not match:
            return token  # EX, EX5, LINE and friends pass through
        number = int(match.group(1))
    return f"CH{number}" if dialect == "tektronix" else f"C{number}"


def source_from_wire(dialect: str, raw: str) -> str:
    """Normalize a trigger-source query response to the public vocabulary."""
    token = raw.strip().upper()
    match = re.fullmatch(r"C(?:H)?(\d+)", token)
    if match:
        return f"C{int(match.group(1))}"
    return token


def normalize_status(raw: str) -> str:
    """Normalize an acquisition-status response to ARM|READY|AUTO|TRIGD|STOP|ROLL."""
    token = _last_token(raw)
    if token not in _STATUS_MAP:
        raise ValueError(f"Unrecognized acquisition status response: {raw!r}")
    return _STATUS_MAP[token]


def probe_to_wire(dialect: str, ratio: float) -> str:
    """Convert a probe attenuation ratio to the wire value (Tek speaks gain = 1/ratio).

    TBS PRObe:GAIN: "a common 10x probe has a gain of 0.1" (TBS p.56);
    MSO2 PROBEFunc:EXTAtten takes the same multiplier form (MSO2 p.2-192).
    """
    if dialect == "tektronix":
        return f"{1.0 / ratio:g}"
    return f"{ratio:g}"


def probe_from_wire(dialect: str, raw: str) -> float:
    """Convert a probe query response back to an attenuation ratio."""
    token = _last_token(raw).replace("X", "")
    value = float(token)
    if dialect == "tektronix":
        return 1.0 / value if value else 0.0
    return value
