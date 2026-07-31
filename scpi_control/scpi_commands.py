"""SCPI command abstraction layer for the supported oscilloscope dialects.

Wire dialects with a command table:
- "legacy": the LeCroy-derived flat dialect (TRIG_SELECT, TDIV, C1:VDIV) spoken
  by Siglent SDS1000X-E era scopes.
- "modern": colon-form SCPI (:TRIGger:EDGE:SOURce, :TIMebase:SCALe) documented
  in the SDS Series Programming Guide EN11G for HD/Plus/SDS5000X+ scopes.
- "tektronix": Tek-style headerless SCPI (CH1:SCAle, HORizontal:SCAle) shared
  by the TBS1000C, 2 Series MSO, and 4/5/6 Series MSO families, with family
  differences captured in VARIANT_OVERRIDES ("tek_tbs" / "tek_mso"). The
  MSO 2-Series and the 4/5/6 Series both resolve to "tek_mso".

This module holds the per-dialect command tables and the enum conversions
between the library's public vocabulary and each dialect's wire tokens.
"""

import logging
import re
from typing import Dict

logger = logging.getLogger(__name__)

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
#            / 4/5/6 Series MSO PM 077-1305-11 p.2-490
CONNECT_SETUP = {
    "legacy": ["CHDR OFF"],
    "modern": [],
    "tektronix": ["HEADer OFF"],
    # CHDR is LeCroy's own short form of COMM_HEADER; OFF omits response
    # headers AND suppresses unit suffixes (MAUI p.7-46). Siglent inherited CHDR.
    "lecroy": ["CHDR OFF"],
}

# Which model families (scpi_variant) belong to which dialect. Variants only
# apply to their own dialect; a forced-dialect override (e.g. a Tek-detected
# scope run with dialect="modern") on a mismatched instrument falls back to the
# plain base table instead of contaminating it with the wrong family overrides.
DIALECT_VARIANTS = {
    "legacy": frozenset({"standard", "hd_series", "x_series", "plus_series"}),
    "modern": frozenset({"standard", "hd_series", "x_series", "plus_series"}),
    "tektronix": frozenset({"standard", "tek_tbs", "tek_mso"}),
    "lecroy": frozenset({"standard", "lecroy_maui"}),
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
        # BWL is global -- BWL keyword first, comma-separated channel/mode
        # pairs, not a colon-prefixed per-channel command like VDIV/OFST/CPL
        # above (RC01020-E01C p.27; task 14, audit L3 -- the previous
        # "C{ch}:BWL {limit}"/"C{ch}:BWL?" forms were invented, never
        # documented anywhere in this manual).
        "set_bandwidth_limit": "BWL C{ch},{limit}",  # limit: ON, OFF
        "get_bandwidth_limit": "BWL?",  # returns "BWL C1,OFF,C2,ON,..." pairs for ALL channels
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
        # Waveform acquisition -- legacy-only, unchanged by Task 18. DAT2/DESC
        # are documented for this dialect (RC01020-E01C p.141); the modern
        # dialect's equivalent moved to the :WAVeform: subsystem below.
        "get_waveform": "C{ch}:WF? DAT2",
        "get_waveform_preamble": "C{ch}:WF? DESC",
        # Measurements
        # RC01020-E01C p.88: QUERY SYNTAX <trace>:PArameter_VAlue? <parameter>,
        # <trace> = {C1..C4}. The trace prefix is mandatory. A previous NOTE here
        # pinned the headerless "PAVA? {param},C{ch}" form on the grounds that it
        # was "what the legacy mock's PAVA? regex parses" -- the mock was wrong,
        # and the comment made the defect load-bearing (audit H7/H30).
        "get_parameter_value": "C{ch}:PAVA? {param}",
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
        # Waveform acquisition (Task 18, audit H9 fix): the modern guide has
        # ZERO occurrences of "WF?" anywhere -- "C{ch}:WF? DAT2"/"DESC" were
        # invented. The documented transfer is the :WAVeform: subsystem
        # (SOURce p.749, STARt p.750, INTerval p.751, POINt p.752, MAXPoint
        # p.753, WIDTh p.754, PREamble p.755, DATA p.757/758). ModernTransfer
        # (waveform_transfer.py) is the only caller of get_waveform_preamble/
        # get_waveform_data/set_waveform_source/set_waveform_width below; the
        # generic "get_waveform" key is kept (repointed, not removed) purely
        # for symmetry with the other three dialect tables and any direct
        # get_command("get_waveform") caller.
        "get_waveform": ":WAVeform:DATA?",  # p.757
        "get_waveform_preamble": ":WAVeform:PREamble?",  # p.755
        "get_waveform_data": ":WAVeform:DATA?",  # p.757 (ModernTransfer's own name for the DATA? leaf)
        # Waveform transfer-parameter scalars (Task 17, audit H9): the
        # documented :WAVeform: subsystem's SOURce/STARt/INTerval/POINt
        # commands, verified against the SDS800XHD guide.
        "set_waveform_source": ":WAVeform:SOURce C{ch}",  # p.749
        "get_waveform_source": ":WAVeform:SOURce?",  # p.749
        "set_waveform_start": ":WAVeform:STARt {value}",  # p.750
        "get_waveform_start": ":WAVeform:STARt?",  # p.750
        "set_waveform_interval": ":WAVeform:INTerval {value}",  # p.751
        "get_waveform_interval": ":WAVeform:INTerval?",  # p.751
        "set_waveform_point": ":WAVeform:POINt {value}",  # p.752
        "get_waveform_point": ":WAVeform:POINt?",  # p.752
        # Transfer width (Task 18, audit H9): selects BYTE/WORD samples,
        # which the WAVEDESC's COMM_TYPE field (offset 32-33) then echoes.
        "set_waveform_width": ":WAVeform:WIDTh {value}",  # p.754
        "get_waveform_width": ":WAVeform:WIDTh?",  # p.754
        # Deep-memory chunking (Task 19, audit H9 follow-up): p.753 documents
        # :WAVeform:MAXPoint as "Query" ONLY -- unlike WIDTh/POINt/etc. above,
        # its own DESCRIPTION/COMMAND-SYNTAX/QUERY-SYNTAX layout has no
        # COMMAND SYNTAX section at all, so there is no set_waveform_maxpoint;
        # a scope tells the controller its own per-transfer cap, the
        # controller does not set it. ModernTransfer.acquire reads this once
        # to learn how many :WAVeform:STARt-driven DATA? windows a full
        # record needs.
        "get_waveform_maxpoint": ":WAVeform:MAXPoint?",  # p.753
        # The record length, i.e. how many points the acquisition holds. NOT
        # :WAVeform:MAXPoint? (p.753), which is the maximum per transfer -- using
        # that to size a stride would under-decimate a deep record.
        "get_acq_points": ":ACQuire:POINts?",  # p.36, p.43
        # Measurements — the :MEASure:SIMPle subsystem (p.335 index). The legacy
        # PAVA? command is deliberately ABSENT: it appears zero times in this
        # guide (exhaustive full-text search), so offering it here made measure()
        # send a command modern instruments do not implement. Statistics, cursors,
        # holdoff and unit remain legacy-only and intentionally absent so they
        # gate cleanly as FeatureNotSupportedError; they need the :MEASure:ADVanced
        # slot subsystem, which is a separate project.
        "set_measure_state": ":MEASure {state}",  # {ON|OFF}, p.337
        "set_measure_mode": ":MEASure:MODE {mode}",  # {SIMPle|ADVanced}, p.365
        "set_simple_source": ":MEASure:SIMPle:SOURce C{ch}",  # p.368
        "set_simple_item": ":MEASure:SIMPle:ITEM {param},{state}",  # p.367
        "get_simple_value": ":MEASure:SIMPle:VALue? {param}",  # bare NR3 reply, p.369
        # INR? bit 0 is a read-and-clear "new signal acquired" latch -- the only
        # honest "has a new frame landed?" signal on this dialect. The manual's own
        # example polls exactly this before fetching (SDS800XHD guide p.829).
        # :TRIGger:STATus? cannot substitute: it reports a state that latches, so
        # it says TRIGD long after the frame it referred to was consumed.
        # READ-AND-CLEAR: exactly one consumer, Oscilloscope.new_acquisition_ready().
        "get_new_data": "INR?",
        # Screen capture (legacy strings accepted on modern scopes today; revisit with screen-capture overhaul)
        "screen_dump": "SCDP",
        "set_hardcopy_format": "HCSU DEV,FORMAT,{format}",
        "hardcopy_print": "HCSU PRINT",
    }

    # Tektronix dialect, verified command-by-command against the TBS1000C
    # Programmer Manual 077-1691-01 (current edition, supersedes 077-1430-xx;
    # cited below as "TBS p.N"), the 2 Series MSO (MSO22/MSO24) Programmer
    # Manual 077-1776-07 (cited as "MSO2 p.2-N"), and the 4/5/6 Series MSO,
    # 6 Series LPD Programmer Manual 077-1305-11 (cited as "MSO456 p.2-N",
    # covering MSO44/46/54/56/58/58LP/64); all printed page numbers.
    # Family differences live in VARIANT_OVERRIDES["tek_tbs"/"tek_mso"]:
    # channel display, probe attenuation, PT_Off, and immediate measurements
    # diverge between the families. NOTE: "tek_mso" serves BOTH the 2 Series
    # and the 4/5/6 Series; where those two diverge (see the LINE trigger
    # source in channel_token) the variant granularity cannot express it.
    TEKTRONIX_COMMANDS = {
        # Acquisition control
        "set_trigger_mode": "TRIGger:A:MODe {mode}",  # AUTO|NORMal -- TBS p.155 / MSO2 p.2-684 / MSO456 p.2-1432
        "get_trigger_mode": "TRIGger:A:MODe?",  # TBS p.155 / MSO2 p.2-684 / MSO456 p.2-1432
        "force_trigger": "TRIGger FORCe",  # TBS p.149 / MSO2 p.2-626 / MSO456 p.2-1291
        "run": "ACQuire:STATE RUN",  # {<NR1>|OFF|ON|RUN|STOP} -- TBS p.42 / MSO2 p.2-78 / MSO456 p.2-136
        "stop": "ACQuire:STATE STOP",  # TBS p.42 / MSO2 p.2-78 / MSO456 p.2-136
        "set_stop_after": "ACQuire:STOPAfter {mode}",  # RUNSTop|SEQuence -- TBS p.43 / MSO2 p.2-80 / MSO456 p.2-137
        "get_acq_status": "TRIGger:STATE?",  # ARMED|AUTO|READY|SAVE|TRIGGER -- TBS p.162 / MSO2 p.2-686 / MSO456 p.2-1439
        "auto_setup": "AUTOSet EXECute",  # TBS p.47 / MSO2 p.2-113 / MSO456 p.2-160
        # Channel control
        # SELect:CH<x> is the TBS spelling. It has no command-reference entry in
        # either MSO manual (both use the tek_mso DISplay:GLObal override), though
        # the 4/5/6 settings dump does echo ":SELECT:CH1 1" (MSO456 p.2-515).
        "set_channel_display": "SELect:CH{ch} {state}",  # ON|OFF|<NR1> -- TBS p.144 (MSO2/MSO456: tek_mso override)
        "get_channel_display": "SELect:CH{ch}?",  # returns 1|0 -- TBS p.144
        "set_voltage_div": "CH{ch}:SCAle {vdiv}",  # TBS p.58 / MSO2 p.2-184 / MSO456 p.2-318
        "get_voltage_div": "CH{ch}:SCAle?",  # TBS p.58 / MSO2 p.2-184 / MSO456 p.2-318
        "set_voltage_offset": "CH{ch}:OFFSet {offset}",  # TBS p.55 / MSO2 p.2-191 / MSO456 p.2-305
        "get_voltage_offset": "CH{ch}:OFFSet?",  # TBS p.55 / MSO2 p.2-191 / MSO456 p.2-305
        # Coupling: TBS {AC|DC} only, MSO2 {AC|DC|DCREJect}, MSO456 {AC|DC|DCREJ}
        # (same token, short spelling); no family has GND coupling
        # -- TBS p.53 / MSO2 p.2-184 / MSO456 p.2-299
        "set_coupling": "CH{ch}:COUPling {coupling}",
        "get_coupling": "CH{ch}:COUPling?",  # TBS p.53 / MSO2 p.2-184 / MSO456 p.2-299
        # Bandwidth: TBS {TWEnty|FULl|<NR3>} p.53; MSO2 {<NR3>|FULl} p.2-183;
        # MSO456 {<NR3>|FULl} p.2-297 (no TWEnty token on either MSO family --
        # send FULl or a hertz value for portability)
        "set_bandwidth_limit": "CH{ch}:BANdwidth {limit}",
        "get_bandwidth_limit": "CH{ch}:BANdwidth?",  # TBS p.53 / MSO2 p.2-183 / MSO456 p.2-297
        # Timebase
        "set_time_div": "HORizontal:SCAle {tdiv}",  # TBS p.104 / MSO2 p.2-349 / MSO456 p.2-508
        "get_time_div": "HORizontal:SCAle?",  # TBS p.104 / MSO2 p.2-349 / MSO456 p.2-508
        "set_time_offset": "HORizontal:DELay:TIMe {offset}",  # TBS p.103 / MSO2 p.2-343 / MSO456 p.2-493
        "get_time_offset": "HORizontal:DELay:TIMe?",  # TBS p.103 / MSO2 p.2-343 / MSO456 p.2-493
        # get_sample_rate: query only on TBS; MSO2 and MSO456 also accept a
        # setter form (<NR3>), which this table deliberately does not expose.
        "get_sample_rate": "HORizontal:SAMPLERate?",  # TBS p.104 / MSO2 p.2-348 / MSO456 p.2-506
        # Edge trigger
        # MSO456 prints the trigger keywords as TRIGger:{A|B}:...; the A-form
        # below is the same command (B is the delayed-trigger sibling).
        "set_trigger_type": "TRIGger:A:TYPe {type}",  # TBS {EDGe|PULSe} p.161 / MSO2 {EDGE|WIDth|...} p.2-682 / MSO456 p.2-1426
        "get_trigger_type": "TRIGger:A:TYPe?",  # TBS p.161 / MSO2 p.2-682 / MSO456 p.2-1426
        "set_trigger_source": "TRIGger:A:EDGE:SOUrce {src}",  # TBS p.152 / MSO2 p.2-663 / MSO456 p.2-1405
        "get_trigger_source": "TRIGger:A:EDGE:SOUrce?",  # TBS p.152 / MSO2 p.2-663 / MSO456 p.2-1405
        "set_trigger_level": "TRIGger:A:LEVel:CH{ch} {level}",  # TBS p.154 / MSO2 p.2-663 / MSO456 p.2-1406
        "get_trigger_level": "TRIGger:A:LEVel:CH{ch}?",  # TBS p.154 / MSO2 p.2-663 / MSO456 p.2-1406
        "set_trigger_slope": "TRIGger:A:EDGE:SLOpe {slope}",  # TBS {RISe|FALL} p.151 / MSO2 + MSO456 add EITher -- MSO2 p.2-662 / MSO456 p.2-1405
        "get_trigger_slope": "TRIGger:A:EDGE:SLOpe?",  # TBS p.151 / MSO2 p.2-662 / MSO456 p.2-1405
        "set_trigger_coupling": "TRIGger:A:EDGE:COUPling {coupling}",  # DC|HFRej|LFRej|NOISErej -- TBS p.151 / MSO2 p.2-661 / MSO456 p.2-1404
        "get_trigger_coupling": "TRIGger:A:EDGE:COUPling?",  # TBS p.151 / MSO2 p.2-661 / MSO456 p.2-1404
        # Holdoff (TBS prints the keyword as HOLDOff, MSO2/MSO456 as HOLDoff; the
        # full spelling below is identical on all three -- SCPI is case-insensitive).
        # MSO456 also gates this on TRIGger:A:HOLDoff:BY TIMe (p.2-1431), which
        # is the default; this table does not set it.
        "set_trigger_holdoff": "TRIGger:A:HOLDoff:TIMe {t}",  # TBS p.153 / MSO2 p.2-684 / MSO456 p.2-1431
        "get_trigger_holdoff": "TRIGger:A:HOLDoff:TIMe?",  # TBS p.153 / MSO2 p.2-684 / MSO456 p.2-1431
        # Waveform transfer (CURVe protocol)
        "set_data_source": "DATa:SOUrce CH{ch}",  # TBS p.71 / MSO2 p.2-208 / MSO456 p.2-339
        # DATa:ENCdg has no D-section entry in the TBS manual but is used by
        # its own transfer procedure (p.38) and echoed by DATa? (p.70);
        # RIBinary = signed int, MSB first on all three families
        # -- MSO2 p.2-205 / MSO456 p.2-337
        "set_data_encoding": "DATa:ENCdg RIBinary",
        # MSO456 allows NR1 1 or 2 for analog channels (p.2-342), same as MSO2.
        "set_data_width": "DATa:WIDth 1",  # 8-bit for this project (16-bit is a follow-up) -- TBS p.72 / MSO2 p.2-211 / MSO456 p.2-342
        "set_data_start": "DATa:STARt {start}",  # TBS p.71 / MSO2 p.2-209 / MSO456 p.2-341
        "set_data_stop": "DATa:STOP {stop}",  # TBS p.72 / MSO2 p.2-210 / MSO456 p.2-341
        "get_wfm_nr_pt": "WFMOutpre:NR_Pt?",  # TBS p.174 / MSO2 p.2-204 / MSO456 p.2-1461
        "get_wfm_xincr": "WFMOutpre:XINcr?",  # TBS p.175 / MSO2 p.2-706 / MSO456 p.2-1465
        "get_wfm_xzero": "WFMOutpre:XZEro?",  # TBS p.176 / MSO2 p.2-702 / MSO456 p.2-1466
        # NOTE: no WFMOutpre:PT_Off? on TBS1000C (leaf absent from its
        # WFMOutpre subsystem, pp.172-177) -- present on both MSO families,
        # see tek_mso override
        "get_wfm_ymult": "WFMOutpre:YMUlt?",  # TBS p.176 / MSO2 p.2-707 / MSO456 p.2-1467
        # NOTE (MSO456): YOFf? always returns 0.0 and YZEro? returns the combined
        # vertical position+offset (p.2-1467/p.2-1468), a documented departure
        # from earlier Tek families. waveform_transfer.py's standard
        # (code - yoff) * ymult + yzero still evaluates correctly because yoff=0.
        "get_wfm_yzero": "WFMOutpre:YZEro?",  # TBS p.177 / MSO2 p.2-709 / MSO456 p.2-1468
        "get_wfm_yoff": "WFMOutpre:YOFf?",  # TBS p.176 / MSO2 p.2-708 / MSO456 p.2-1467
        "get_waveform": "CURVe?",  # TBS p.68 / MSO2 p.2-77 / MSO456 p.2-332
        # Immediate measurements (MEASUrement:IMMed) are wired for TBS only
        # (see tek_tbs override); both MSO families gate with
        # FeatureNotSupportedError and steer callers at the badge-based
        # MEASUrement:MEAS<x> subsystem.
        # NOTE: neither MSO manual gives MEASUrement:IMMed a command-reference
        # entry, but both evidence it working elsewhere -- MSO2 in its
        # programming-examples appendix (p.3-12/3-13) and factory-defaults table
        # (p.C-11), MSO456 in its own examples appendix (p.3-13:
        # "MEASUREMENT:IMMED:TYPE AMPLITUDE / :SOURCE CH1 / :VALUE?"), its
        # factory-defaults table (p.C-12/C-13), and its *LRN? settings dump
        # (p.2-551). So this gate is deliberately conservative on both MSO
        # families, not manual-contradicted.
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
    DIALECT_TABLES: Dict[str, Dict[str, str]] = {
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
            # gain of 0.1" -- TBS p.56. No settable PRObe:GAIN on either MSO
            # family (MSO456 has a query-only CH<x>:PRObe:GAIN?, p.2-308).
            "set_probe_ratio": "CH{ch}:PRObe:GAIN {gain}",
            "get_probe_ratio": "CH{ch}:PRObe:GAIN?",
            # Immediate measurements -- TBS pp.117-121 (no command-reference
            # entry in either MSO manual, so MSO models gate with
            # FeatureNotSupportedError; see the NOTE on the base table)
            "set_meas_immed_type": "MEASUrement:IMMed:TYPe {type}",  # TBS p.119
            "set_meas_immed_source": "MEASUrement:IMMed:SOUrce1 CH{ch}",  # TBS p.117
            "get_meas_immed_value": "MEASUrement:IMMed:VALue?",  # TBS p.121
        },
        # Serves the 2 Series MSO (MSO22/MSO24) and the 4/5/6 Series MSO
        # (MSO44/46/54/56/58/58LP/64) -- both verified against their manuals.
        "tek_mso": {
            # Neither MSO family documents a SELect subsystem; display is
            # per-channel global state {<NR1>|OFF|ON}
            # -- MSO2 p.2-225 / MSO456 p.2-352
            "set_channel_display": "DISplay:GLObal:CH{ch}:STATE {state}",
            "get_channel_display": "DISplay:GLObal:CH{ch}:STATE?",
            # External attenuation "as a multiplier" (gain form, e.g.
            # 167.00E-3) -- MSO2 p.2-192 / MSO456 p.2-316; closest equivalent of
            # TBS PRObe:GAIN. (MSO456 does have CH<x>:PRObe:GAIN? but query-only,
            # p.2-308, so EXTAtten is the only read/write attenuation path here.)
            "set_probe_ratio": "CH{ch}:PROBEFunc:EXTAtten {gain}",
            "get_probe_ratio": "CH{ch}:PROBEFunc:EXTAtten?",
            # Preamble trigger-point offset, absent on TBS
            # -- MSO2 p.2-701 / MSO456 p.2-1462
            "get_wfm_pt_off": "WFMOutpre:PT_Off?",
            # Badge measurements. The modern MSO families have no
            # MEASUrement:IMMed subsystem -- measurements are stateful "badges"
            # that are added, configured, then read. Verified on both families:
            # MSO2 PM 077-1776-07 (ADDNew p.2-395, TYPe p.2-468, SOUrce p.2-464,
            # RESUlts p.2-462, DELete p.2-405, LIST p.2-411) and 4/5/6 PM 077-1305-11
            # (ADDNew p.2-561, TYPe p.2-702, SOUrce p.2-694, RESUlts p.2-690,
            # DELete p.2-581, LIST p.2-592).
            "add_measurement_badge": 'MEASUrement:ADDNew "MEAS{n}"',
            "set_badge_type": "MEASUrement:MEAS{n}:TYPe {type}",
            "set_badge_source": "MEASUrement:MEAS{n}:SOUrce {src}",
            # Plain result query -- the SUBGROUP form needs the 5-DPM/5-IMDA/
            # 6-DPM options, this one does not (4/5/6 p.2-690).
            "get_badge_value": "MEASUrement:MEAS{n}:RESUlts:CURRentacq:MEAN?",
            "delete_badge": 'MEASUrement:DELete "MEAS{n}"',
            "list_badges": "MEASUrement:LIST?",
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
        # Only apply family overrides that belong to this dialect. A forced
        # dialect override can pair a variant with the wrong base table (e.g.
        # dialect="modern" over an MSO24-detected scope, variant "tek_mso");
        # applying those overrides would write Tek commands onto the modern
        # table. Fall back to the plain base table instead.
        if variant not in DIALECT_VARIANTS[dialect]:
            logger.warning(
                "SCPI variant %r does not belong to the %r dialect; ignoring " "family overrides and using the plain base table.",
                variant,
                dialect,
            )
            variant = "standard"
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
    # AUTO|NORMal (TBS p.155 / MSO2 p.2-684 / MSO456 p.2-1432); SINGLE/STOP are
    # command sequences
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
    # RISe|FALL (TBS p.151 / MSO2 p.2-662 / MSO456 p.2-1405); WINDOW has no Tek
    # edge equivalent (the MSO third token is EITher on both MSO families,
    # which is absent on TBS -- and EITher is "either edge", not a window)
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

_TRIGGER_TYPES = {"EDGE", "SLEW", "GLIT", "INTV", "RUNT", "PATTERN"}
_TRIGGER_TYPE_TO_WIRE = {
    # Legacy TRSE types ARE the public vocabulary (legacy guide TRSE section).
    "legacy": {t: t for t in _TRIGGER_TYPES},
    # SDS800X HD guide EN11G p.485: :TRIGger:TYPE {EDGE|PULSE|SLOPe|INTerval|
    # PATTern|RUNT|WINDow|DROPout|VIDeo|...}. Public SLEW = slope trigger,
    # public GLIT = pulse/glitch trigger (MAUI-descended naming).
    "modern": {"EDGE": "EDGE", "SLEW": "SLOPe", "GLIT": "PULSE", "INTV": "INTerval", "RUNT": "RUNT", "PATTERN": "PATTern"},
    # Only EDGE is spelled identically across Tek families: TBS is {EDGe|PULSe}
    # (p.161) while MSO2 (p.2-682) and MSO456 (p.2-1426) use WIDth for the
    # pulse class. The pulse-class token diverges per family, so everything but
    # EDGE gates as FeatureNotSupportedError until per-family maps exist.
    "tektronix": {"EDGE": "EDGE"},
    # LeCroy TRIG_SELECT types (MAUI p.7-36) -- ancestor of the legacy tokens.
    "lecroy": {t: t for t in _TRIGGER_TYPES},
}
_TRIGGER_TYPE_FROM_WIRE = {
    "legacy": {t: t for t in _TRIGGER_TYPES},
    "modern": {"EDGE": "EDGE", "SLOPE": "SLEW", "PULSE": "GLIT", "INTERVAL": "INTV", "RUNT": "RUNT", "PATTERN": "PATTERN"},
    "tektronix": {"EDGE": "EDGE"},
    "lecroy": {t: t for t in _TRIGGER_TYPES},
}


def trigger_type_to_wire(dialect: str, trig_type: str) -> str:
    return _to_wire(_TRIGGER_TYPE_TO_WIRE, _TRIGGER_TYPES, dialect, trig_type, "trigger type")


def trigger_type_from_wire(dialect: str, raw: str) -> str:
    # Unlike slope/coupling, a scope can legitimately sit in a type this API
    # cannot set (VIDeo, DROPout, IIC, ... via front panel). Reads must not
    # explode a state snapshot, so unmapped wire tokens pass through
    # uppercased instead of raising the way _from_wire does.
    token = _last_token(raw)
    return _TRIGGER_TYPE_FROM_WIRE.get(dialect, {}).get(token, token)


_COUPLING_TO_WIRE = {
    "legacy": {"DC": "D1M", "AC": "A1M", "GND": "GND"},
    "modern": {"DC": "DC", "AC": "AC", "GND": "GND"},
    # No GND coupling on any Tek family: TBS is {AC|DC} (p.53), MSO2 is
    # {AC|DC|DCREJect} (p.2-184), MSO456 is {AC|DC|DCREJ} (p.2-299)
    # -- GND gates as FeatureNotSupportedError
    "tektronix": {"DC": "DC", "AC": "AC"},
    # LeCroy COUPLING {A1M,D1M,D50,GND} (MAUI p.7-20) -- ancestor of legacy tokens
    "lecroy": {"DC": "D1M", "AC": "A1M", "GND": "GND"},
}
_COUPLING_FROM_WIRE = {
    "legacy": {"D1M": "DC", "A1M": "AC", "D50": "DC", "A50": "AC", "GND": "GND"},
    "modern": {"DC": "DC", "AC": "AC", "GND": "GND"},
    # DCREJect (MSO2 PM 077-1776-07 p.2-184) / DCREJ (MSO456 PM 077-1305-11
    # p.2-299) passes AC only -- normalize to the public AC token rather than
    # surfacing the Tek-specific spelling. Both spellings are mapped because the
    # two MSO manuals print the token differently.
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
# stopped) -- TBS p.162 / MSO2 p.2-686 / MSO456 p.2-1439. All three families
# return exactly {ARMED|AUTO|READY|SAVE|TRIGGER}.
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
    # Modern :MEASure:SIMPle:ITEM / :VALue? vocabulary, verbatim from the
    # SDS800X HD guide p.367 (ITEM) and p.369 (VALue?). NOT an identity map:
    # per the parameter table at p.345, modern WID is the positive BURST width
    # (first rising edge to last falling edge) while the positive PULSE width
    # -- which is what our public WID means, cf. "WID": "PWIdth" in the
    # tektronix map below -- is PWID. Mapping WID -> WID would silently return
    # burst width. NWID is the negative PULSE width on both sides (NBWID is the
    # burst form and we never send it).
    "modern": {
        "PKPK": "PKPK",
        "MAX": "MAX",
        "MIN": "MIN",
        "AMPL": "AMPL",
        "TOP": "TOP",
        "BASE": "BASE",
        "CMEAN": "CMEAN",
        "MEAN": "MEAN",
        "RMS": "RMS",
        "CRMS": "CRMS",
        "FREQ": "FREQ",
        "PER": "PER",
        "RISE": "RISE",
        "FALL": "FALL",
        "WID": "PWID",
        "NWID": "NWID",
        "DUTY": "DUTY",
    },
    # LeCroy PARAMETER_VALUE (PAVA) parameter names -- identity, the ancestor
    # of the Siglent legacy vocabulary (MAUI p.7-70).
    "lecroy": {m: m for m in _MEASUREMENT_TYPES},
    # Tek MEASUrement:IMMed:TYPe vocabulary, verbatim from TBS p.119 (the
    # IMMed subsystem is wired for TBS only; the MSO families' MEAS<x> badge
    # vocabulary differs -- neither MSO manual documents IMMed:TYPe -- and is a
    # follow-up when badge measurements land). Reachable only via the tek_tbs
    # override commands, so the MSO families never hit these tokens.
    "tektronix": {
        "PKPK": "PK2Pk",
        "MAX": "MAXimum",
        "MIN": "MINImum",
        "AMPL": "AMPlitude",
        "TOP": "HIGH",
        "BASE": "LOW",
        "CMEAN": "CMEan",
        "MEAN": "MEAN",
        "RMS": "RMS",
        "CRMS": "CRMs",
        "FREQ": "FREQuency",
        "PER": "PERIod",
        "RISE": "RISe",
        "FALL": "FALL",
        "WID": "PWIdth",
        "NWID": "NWIdth",
        "DUTY": "PDUty",
    },
}


def measurement_to_wire(dialect: str, mtype: str) -> str:
    """Convert a public measurement type to the dialect's wire token."""
    return _to_wire(_MEASUREMENT_TO_WIRE, _MEASUREMENT_TYPES, dialect, mtype, "measurement type")


# Badge measurement vocabulary (MEASUrement:MEAS<x>:TYPe). Distinct from the
# IMMed vocabulary above -- e.g. RISe/FALL there vs RISETIME/FALLTIME here.
# Verified by parsing each manual's MEASUrement:MEAS<x>:TYPe argument list
# (the brace-delimited, |-separated token set) directly:
#   MSO2 PM 077-1776-07 p.2-468 and 4/5/6 PM 077-1305-11 p.2-702.
# TOP and BASE are listed by BOTH manuals and are mapped below. 4/5/6 adds
# HIGH and LOW as a superset; our public vocabulary has no HIGH/LOW equivalent,
# so those extra tokens are simply never reached.
# Deliberately unmapped, so they gate as FeatureNotSupportedError:
#   CMEAN -- neither manual lists a cycle-mean badge token
#   CRMS  -- ACRMS is AC-coupled RMS, a different measurement
_BADGE_TYPE_TO_WIRE = {
    "tektronix": {
        "PKPK": "PK2Pk",
        "MAX": "MAXIMUM",
        "MIN": "MINIMUM",
        "AMPL": "AMPLITUDE",
        "TOP": "TOP",
        "BASE": "BASE",
        "MEAN": "MEAN",
        "RMS": "RMS",
        "FREQ": "FREQUENCY",
        "PER": "PERIOD",
        "RISE": "RISETIME",
        "FALL": "FALLTIME",
        "WID": "PWIDTH",
        "NWID": "NWIDTH",
        "DUTY": "PDUTY",
    },
}


def badge_type_to_wire(dialect: str, mtype: str) -> str:
    """Convert a public measurement type to a badge TYPe token."""
    return _to_wire(_BADGE_TYPE_TO_WIRE, _MEASUREMENT_TYPES, dialect, mtype, "badge measurement type")


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
            if dialect == "tektronix":
                # Every Tek family exposes a single external ("Aux In") trigger
                # and accepts the SCPI short form AUX for it. Edge-source
                # vocabularies, verbatim:
                #   TBS1000C  PM 077-1691-01 p.152    {CH1|CH2|LINE|AUX}
                #   2 Series  PM 077-1776-07 p.2-663  {CH<x>|DCH<x>_D<x>|INTernal|AUXiliary}
                #   4/5/6 Ser PM 077-1305-11 p.2-1406 {CH<x>|CH<x>_D<y>|LINE|AUXiliary}
                # (AUX is the SCPI short form of AUXiliary. The 4/5/6 manual
                # notes the Aux In connector itself is model-dependent -- "for
                # instruments that have an Auxiliary Input (such as the MSO58LP)"
                # p.2-1405 -- a hardware fact this table cannot express.)
                if token == "EX":
                    return "AUX"
                # EX5 (external /5) has no token on any Tek family.
                #
                # LINE is NOT TBS-only: TBS (p.152) and the 4/5/6 Series
                # (p.2-1406) both have it, the 2 Series (p.2-663) does not.
                # That divergence runs *inside* the tek_mso variant -- MSO2 and
                # MSO 4/5/6 share it -- so neither the dialect nor the variant
                # identifies whether LINE is legal. Gating dialect-wide keeps a
                # typed client-side error instead of shipping a token an MSO2
                # would reject, and matches how GND coupling and the WINDOW
                # slope are handled above. Serving LINE to the families that do
                # have it needs a tek_mso split or a per-model capability flag;
                # see the task-3 report before changing this.
                raise exceptions.FeatureNotSupportedError(f"trigger source {token} is not supported on the tektronix dialect")
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
    """Normalize an acquisition-status response to ARM|READY|AUTO|TRIGD|STOP|ROLL.

    Reads the last whitespace-separated token of the response (tolerating a
    residual header echo such as a leading "SAST") and maps it from whichever
    dialect produced it:

    - Siglent legacy (SAST?) / modern (:TRIGger:STATus?): ARM, READY, AUTO,
      TRIG'D, STOP, ROLL.
    - Tektronix (TRIGger:STATE?): ARMED, AUTO, READY, SAVE, TRIGGER, where SAVE
      means acquisition stopped and TRIGGER is the triggered state
      (TBS p.162 / MSO2 p.2-686 / MSO456 p.2-1439).

    Raises:
        ValueError: If the token is not a recognized status in any dialect.
    """
    token = _last_token(raw)
    if token not in _STATUS_MAP:
        raise ValueError(f"Unrecognized acquisition status response: {raw!r}")
    return _STATUS_MAP[token]


def probe_to_wire(dialect: str, ratio: float) -> str:
    """Convert a probe attenuation ratio to the wire value (Tek speaks gain = 1/ratio).

    TBS PRObe:GAIN: "a common 10x probe has a gain of 0.1" (TBS p.56);
    PROBEFunc:EXTAtten takes the same multiplier form on both MSO families
    (MSO2 p.2-192 / MSO456 p.2-316, "specified as a multiplier in the range
    from 1.00E-10 to 1.00E+10").
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
