"""Documented SCPI request/response pairs, transcribed from vendor programming guides.

Every entry is a verbatim transcription of an EXAMPLE block in a vendor manual.
The manuals are NOT committed (see docs/development/vendor-manuals.md for sources
and .git/info/exclude for why), so `source` must always name document and page.
What is pinned verbatim is the documented request/response *structure*; where a
manual's example value differs from the fixture value already in use elsewhere,
the structure is what is transcribed and the divergence is called out in the
entry's comment -- the value itself is not required to match the manual's.

RULE: never edit an entry to make a test pass. If an entry and the code disagree,
either the code is wrong or the transcription is wrong -- re-open the PDF.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

#: Transcribed from a manual example; all three conformance assertions run.
VERIFIED = "VERIFIED"
#: Known to disagree with the manual; fix queued. Assertions xfail.
MISMATCH_DEFERRED = "MISMATCH_DEFERRED"
#: No manual obtainable (LeCroy, TBS1102C). Recorded as unverified; asserts nothing.
UNCITED = "UNCITED"


@dataclass(frozen=True)
class WireForm:
    """One documented request/response pair.

    Attributes:
        table: Which command table owns `op` -- "scope", "psu", "awg" or "daq".
        op: Key in that command table (e.g. "get_sample_rate").
        request: The documented request string, verbatim from the manual.
        source: "<document filename> p.<page>".
        status: VERIFIED, MISMATCH_DEFERRED or UNCITED.
        dialect: Scope dialect ("legacy"/"modern"/"tektronix"/"lecroy"). Scope table only.
        variant: Command-set variant ("standard", "siglent_spd", "siglent_sdg", ...).
        params: kwargs passed to get_command() to render `request`.
        response: The documented response, verbatim. None when the manual shows none.
        parsed: What the driver's parser must extract from `response`.
        mock_kwargs: kwargs for MockConnection so it answers in the right personality.
        note: Free text -- for MISMATCH_DEFERRED, the audit ID and why it is deferred.
    """

    table: str
    op: str
    request: str
    source: str
    status: str = VERIFIED
    dialect: str = "legacy"
    variant: str = "standard"
    params: Dict[str, Any] = field(default_factory=dict)
    response: Optional[str] = None
    parsed: Optional[Any] = None
    mock_kwargs: Dict[str, Any] = field(default_factory=dict)
    note: str = ""


LEGACY_GUIDE = "SDS_DigitalOscilloscopes_ProgrammingGuide_RC01020-E01C.pdf"
SPD_GUIDE = "SPD3303X_QuickStart_QS0503X-E01B.pdf"
SDG_GUIDE = "SDG_ProgrammingGuide_PG02-E05B.pdf"
MODERN_GUIDE = "SDS800XHD_Series_ProgrammingGuide_EN11G.pdf"
DAQ_GUIDE = "34970A-34972A_CommandReference.pdf"

LEGACY_IDN = "Siglent Technologies,SDS1104X-E,MOCK0001,1.0.0.0"
MODERN_IDN = "Siglent Technologies,SDS814X HD,MOCK0001,1.0.0.0"


WIRE_FORMS: List[WireForm] = [
    # --- Legacy Siglent scope -------------------------------------------------
    WireForm(
        table="scope",
        dialect="legacy",
        op="get_time_div",
        params={},
        request="TDIV?",
        response=None,
        parsed=None,
        source=f"{LEGACY_GUIDE} p.122",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "p.122 (TIME_DIV,TDIV) has no worked query/response EXAMPLE to "
            "transcribe -- its EXAMPLE only shows the SET form ('TDIV 500US'). "
            "Its RESPONSE FORMAT line reads 'Time_DIV <value>' (prefixed), which "
            "the adjacent SAST command (p.116, RESPONSE FORMAT 'SAST <status>', "
            "EXAMPLE response literally 'SAST trig'd') confirms this manual means "
            "literally on the wire. MockConnection.query('TDIV?') "
            "(connection/mock/siglent.py, ~line 205) answers unprefixed, e.g. "
            "'1.00E-03S' instead of 'TDIV 1.00E-03S'. New instance of audit theme "
            "2 (mock-invented response shape, 2026-07-22 audit) -- no prior "
            "finding ID covers TDIV specifically. Deferred because task 1 is "
            "additive scaffolding only and may not edit MockConnection."
        ),
    ),
    # RC01020-E01C p.88:
    #   QUERY SYNTAX    <trace>:PArameter_VAlue? [<parameter>, ...]
    #   RESPONSE FORMAT <trace>: PArameter_VAlue <parameter>, <value>
    #   EXAMPLE         C2: PAVA? RISE   ->   C2: PAVA RISE, 3.6E-9S
    # We normalise the manual's cosmetic spaces after ':' -- real instruments
    # emit "C2:PAVA RISE,3.6E-9S". The field STRUCTURE is what is being pinned.
    WireForm(
        table="scope",
        dialect="legacy",
        op="get_parameter_value",
        params={"ch": 2, "param": "RISE"},
        request="C2:PAVA? RISE",
        response="C2:PAVA RISE,3.500E-05S",
        parsed=3.5e-05,
        source=f"{LEGACY_GUIDE} p.88",
        mock_kwargs={"idn": LEGACY_IDN},
    ),
    # RC01020-E01C p.117:
    #   RESPONSE FORMAT SARA< value >
    #   EXAMPLE         SARA?   ->   SARA  500.0kSa
    # Note the SI magnitude letter and the unit "Sa" (NOT "Sa/s"). AUDIT.md H8
    # predicted "1.00GSa/s"; the guide's own example disagrees.
    WireForm(
        table="scope",
        dialect="legacy",
        op="get_sample_rate",
        params={},
        request="SARA?",
        response="SARA 1.00kSa",
        parsed=1000.0,
        source=f"{LEGACY_GUIDE} p.117",
        mock_kwargs={"idn": LEGACY_IDN},
    ),
    # --- Legacy Siglent scope: sweep 2026-07-23 (task 5a) -----------------
    # Every command in SCPICommandSet.LEGACY_COMMANDS not already covered
    # above. RC01020-E01C p.10: "the name (header) is given in both long and
    # short form"; the manual's own worked EXAMPLEs mostly use the short
    # form (e.g. "TRMD NORM"), while this driver's trigger-family commands
    # consistently use the long form ("TRIG_MODE NORM") -- both are
    # documented-valid spellings of the identical header, so a long-form
    # rendering is not treated as a mismatch below.

    # -- Acquisition control --
    # p.21: COMMAND SYNTAX "ARM acquisition", EXAMPLE "ARM".
    WireForm(table="scope", dialect="legacy", op="arm_trigger", params={}, request="ARM", source=f"{LEGACY_GUIDE} p.21", mock_kwargs={"idn": LEGACY_IDN}),
    # p.56: COMMAND SYNTAX "FoRce_TRigger", EXAMPLE uses "FRTR".
    WireForm(table="scope", dialect="legacy", op="force_trigger", params={}, request="FRTR", source=f"{LEGACY_GUIDE} p.56", mock_kwargs={"idn": LEGACY_IDN}),
    # p.111: COMMAND SYNTAX/EXAMPLE "STOP" (bare). The page's own "Response
    # message: *STB 0" line is garbled OCR (STOP has no response in the
    # description or the TOC, which lists it as "Command" only) and is not
    # transcribed.
    WireForm(table="scope", dialect="legacy", op="stop", params={}, request="STOP", source=f"{LEGACY_GUIDE} p.111", mock_kwargs={"idn": LEGACY_IDN}),
    # p.130: <mode>:={AUTO,NORM,SINGLE,STOP}; "run" is TRIG_MODE with AUTO,
    # a fixed template with no placeholders to substitute.
    WireForm(table="scope", dialect="legacy", op="run", params={}, request="TRIG_MODE AUTO", source=f"{LEGACY_GUIDE} p.130", mock_kwargs={"idn": LEGACY_IDN}),
    # p.24: COMMAND SYNTAX "AUTO_SETUP" (no args), EXAMPLE "ASET".
    WireForm(table="scope", dialect="legacy", op="auto_setup", params={}, request="ASET", source=f"{LEGACY_GUIDE} p.24", mock_kwargs={"idn": LEGACY_IDN}),
    # p.130 EXAMPLE: "TRMD NORM" -- long form per p.10 (see module note above).
    WireForm(table="scope", dialect="legacy", op="set_trigger_mode", params={"mode": "NORM"}, request="TRIG_MODE NORM", source=f"{LEGACY_GUIDE} p.130", mock_kwargs={"idn": LEGACY_IDN}),
    WireForm(
        table="scope",
        dialect="legacy",
        op="get_trigger_mode",
        params={},
        request="TRIG_MODE?",
        response="TRMD AUTO",
        source=f"{LEGACY_GUIDE} p.130",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[low severity] Request matches (query syntax 'TRig_MoDe?'). p.130 has no "
            "worked query EXAMPLE, only RESPONSE FORMAT 'TRig_MoDe <mode>' (prefixed); "
            "confirmed literal by the sibling worked query examples on p.116 (SAST?) "
            "and p.142 (C1:VDIV?/C1:OFST?), which show this manual's convention of "
            "echoing the header on query responses. Mock's TRIG_MODE? handler "
            "(connection/mock/siglent.py) answers with the bare wire token (e.g. "
            "'STOP') instead of 'TRMD STOP'. Same pattern as the already-catalogued "
            "TDIV?/VDIV?/OFST?/TRLV? findings. mode_from_wire() reads only the last "
            "whitespace token, so this does not reach the user as a wrong value -- "
            "below the pull-in bar. Queued."
        ),
    ),

    # -- Channel control --
    # p.124 EXAMPLE: "C1: TRA ON" (cosmetic space after ':' normalised away).
    WireForm(table="scope", dialect="legacy", op="set_channel_display", params={"ch": 1, "state": "ON"}, request="C1:TRA ON", source=f"{LEGACY_GUIDE} p.124", mock_kwargs={"idn": LEGACY_IDN}),
    WireForm(
        table="scope",
        dialect="legacy",
        op="get_channel_display",
        params={"ch": 1},
        request="C1:TRA?",
        response="C1:TRA ON",
        source=f"{LEGACY_GUIDE} p.124",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[low severity] Request matches ('<trace>:TRAce?'). RESPONSE FORMAT is "
            "'<trace>:TRAce <mode>' (prefixed, e.g. 'C1:TRA ON'); no worked query "
            "EXAMPLE on this page, confirmed by the same p.116/p.142 cross-reference "
            "as get_trigger_mode above. Mock's C(n):TRA? handler answers bare "
            "'ON'/'OFF'. channel.py's enabled getter reads only the last token, so no "
            "wrong value reaches the user. Below the pull-in bar. Queued."
        ),
    ),
    # p.139 EXAMPLE: "C1: VDIV 50MV".
    WireForm(table="scope", dialect="legacy", op="set_voltage_div", params={"ch": 1, "vdiv": "50MV"}, request="C1:VDIV 50MV", source=f"{LEGACY_GUIDE} p.139", mock_kwargs={"idn": LEGACY_IDN}),
    WireForm(
        table="scope",
        dialect="legacy",
        op="get_voltage_div",
        params={"ch": 1},
        request="C1:VDIV?",
        response="C1:VDIV 5.00E-01V",
        parsed=0.5,
        source=f"{LEGACY_GUIDE} p.139, p.142",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[low severity] Request matches. p.142's waveform-recovery walkthrough "
            "gives a genuine worked query EXAMPLE: 'Send command \"C1:VDIV?\", "
            "return \"C1:VDIV 5.00E-01V\"' (prefixed). Mock's C(n):VDIV? handler "
            "(connection/mock/siglent.py ~line177) answers bare '5.00E-01V'. "
            "channel.py's voltage_scale getter tolerates a missing header (splits on "
            "whitespace, takes the last token), so no wrong value reaches the user. "
            "Below the pull-in bar. One of the four known findings named in the "
            "task-5 brief. Queued."
        ),
    ),
    # p.83 EXAMPLE: "C2: OFST -3V".
    WireForm(table="scope", dialect="legacy", op="set_voltage_offset", params={"ch": 2, "offset": "-3V"}, request="C2:OFST -3V", source=f"{LEGACY_GUIDE} p.83", mock_kwargs={"idn": LEGACY_IDN}),
    WireForm(
        table="scope",
        dialect="legacy",
        op="get_voltage_offset",
        params={"ch": 1},
        request="C1:OFST?",
        response="C1:OFST -5.00E-01V",
        parsed=-0.5,
        source=f"{LEGACY_GUIDE} p.83, p.142",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[low severity] Request matches. p.142 worked EXAMPLE: 'Send command "
            "\"C1:OFST?\", return \"C1:OFST -5.00E-01V\"' (prefixed). Mock's "
            "C(n):OFST? handler answers bare '-5.00E-01V'. channel.py's "
            "voltage_offset getter tolerates the missing header the same way as "
            "voltage_scale. Below the pull-in bar. One of the four known findings "
            "named in the task-5 brief. Queued."
        ),
    ),
    # p.35 EXAMPLE: "C2: CPL D50".
    WireForm(table="scope", dialect="legacy", op="set_coupling", params={"ch": 2, "coupling": "D50"}, request="C2:CPL D50", source=f"{LEGACY_GUIDE} p.35", mock_kwargs={"idn": LEGACY_IDN}),
    WireForm(
        table="scope",
        dialect="legacy",
        op="get_coupling",
        params={"ch": 2},
        request="C2:CPL?",
        response="C2:CPL D50",
        source=f"{LEGACY_GUIDE} p.35",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[low severity] Request matches ('<channel>:CouPLing?'). RESPONSE FORMAT "
            "is '<channel>:CouPLing <coupling>' (prefixed); no worked query EXAMPLE "
            "on this page, confirmed by the p.116/p.142 cross-reference. Mock's "
            "C(n):CPL? handler answers bare 'D1M'/etc. coupling_from_wire() reads "
            "only the last token. Below the pull-in bar. Queued."
        ),
    ),
    # p.22 EXAMPLE: "C1:ATTN 100" (no cosmetic space in this one).
    WireForm(table="scope", dialect="legacy", op="set_probe_ratio", params={"ch": 1, "ratio": 100}, request="C1:ATTN 100", source=f"{LEGACY_GUIDE} p.22", mock_kwargs={"idn": LEGACY_IDN}),
    # get_probe_ratio is not mocked (no ATTN? handler in connection/mock/siglent.py) --
    # request-only citation. QUERY SYNTAX "<channel>:ATTeNuation?".
    WireForm(table="scope", dialect="legacy", op="get_probe_ratio", params={"ch": 1}, request="C1:ATTN?", source=f"{LEGACY_GUIDE} p.22", mock_kwargs={"idn": LEGACY_IDN}),
    WireForm(
        table="scope",
        dialect="legacy",
        op="set_bandwidth_limit",
        params={"ch": 1, "limit": "ON"},
        request="BWL C1,ON",
        source=f"{LEGACY_GUIDE} p.27",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[medium severity] p.27 COMMAND SYNTAX is 'BandWidth_Limit <channel>, "
            "<mode> [, <channel>, <mode>...]', EXAMPLE 'BWL C1, ON' -- the BWL "
            "keyword comes first, channel and mode are comma-separated arguments to "
            "it. Code (scpi_control/scpi_commands.py LEGACY_COMMANDS) sends "
            "'C{ch}:BWL {limit}' (colon-prefixed channel, like VDIV/OFST/CPL), a "
            "different structure this manual does not document. Not mocked "
            "(no BWL handler in connection/mock/siglent.py), so no test currently "
            "exercises this. No wrong number reaches a user today only because "
            "nothing reads the result; on real hardware the malformed write would "
            "likely be silently ignored (writes don't raise). Not on a default path "
            "(channel.py's bandwidth_limit is opt-in). Queued for a code fix, not "
            "just a mock fix."
        ),
    ),
    WireForm(
        table="scope",
        dialect="legacy",
        op="get_bandwidth_limit",
        params={"ch": 1},
        request="BWL?",
        source=f"{LEGACY_GUIDE} p.27",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[medium severity] p.27 QUERY SYNTAX is bare 'BandWidth_Limit?' (no "
            "channel argument) with RESPONSE FORMAT returning ALL channels as "
            "'<channel>,<mode>' pairs. Code sends 'C{ch}:BWL?' (per-channel), a form "
            "this manual does not document. Not mocked. Same root cause as "
            "set_bandwidth_limit above; queued together."
        ),
    ),

    # -- Timebase control --
    # p.122 EXAMPLE: "TDIV 500US" (get_time_div is the already-catalogued MISMATCH_DEFERRED above; this is the SET side, which the manual does example directly).
    WireForm(table="scope", dialect="legacy", op="set_time_div", params={"tdiv": "500US"}, request="TDIV 500US", source=f"{LEGACY_GUIDE} p.122", mock_kwargs={"idn": LEGACY_IDN}),
    # p.127 EXAMPLE: "TRDL -2MS".
    WireForm(table="scope", dialect="legacy", op="set_time_offset", params={"offset": "-2MS"}, request="TRDL -2MS", source=f"{LEGACY_GUIDE} p.127", mock_kwargs={"idn": LEGACY_IDN}),
    # get_time_offset is not mocked (no TRDL? handler). QUERY SYNTAX "TRig_DeLay?".
    WireForm(table="scope", dialect="legacy", op="get_time_offset", params={}, request="TRDL?", source=f"{LEGACY_GUIDE} p.127", mock_kwargs={"idn": LEGACY_IDN}),

    # -- Trigger settings --
    # p.126 EXAMPLE: "C2: TRCP AC".
    WireForm(table="scope", dialect="legacy", op="set_trigger_coupling", params={"src": "C2", "coupling": "AC"}, request="C2:TRCP AC", source=f"{LEGACY_GUIDE} p.126", mock_kwargs={"idn": LEGACY_IDN}),
    WireForm(
        table="scope",
        dialect="legacy",
        op="get_trigger_coupling",
        params={"src": "C2"},
        request="C2:TRCP?",
        response="C2:TRCP AC",
        source=f"{LEGACY_GUIDE} p.126",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[low severity] Request matches ('<trig_source>:TRig_CouPling?'). "
            "RESPONSE FORMAT is prefixed; no worked query EXAMPLE on this page, "
            "confirmed by the p.116/p.142 cross-reference. Mock's C(n):TRCP? "
            "handler answers bare. trigger.py's coupling getter for flat-trigger "
            "dialects reads only the last token. Below the pull-in bar. Queued."
        ),
    ),
    # p.128: EXAMPLE 'C3:TRig_LeVel 52.00mv' collapses to 'C3:TRLV 52.00mv'.
    WireForm(table="scope", dialect="legacy", op="set_trigger_level", params={"src": "C3", "level": "52.00mv"}, request="C3:TRLV 52.00mv", source=f"{LEGACY_GUIDE} p.128", mock_kwargs={"idn": LEGACY_IDN}),
    WireForm(
        table="scope",
        dialect="legacy",
        op="get_trigger_level",
        params={"src": "C3"},
        request="C3:TRLV?",
        response="C3:TRLV 5.200E-02V",
        source=f"{LEGACY_GUIDE} p.128",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[low severity] Request matches ('<trig_source>:TRig_LeVel?'). p.128 has "
            "no worked query EXAMPLE (only the SET example); RESPONSE FORMAT "
            "'<trig_source>:TRig_LeVel <trig_level>' is prefixed, confirmed literal "
            "by the p.142 VDIV?/OFST? worked query examples. Mock's C(n):TRLV? "
            "handler (connection/mock/siglent.py ~line194) answers bare. "
            "trigger.py's level getter tolerates the missing header. Below the "
            "pull-in bar. One of the four known findings named in the task-5 "
            "brief. Queued."
        ),
    ),
    # p.134 EXAMPLE: "C2: TRSL NEG".
    WireForm(table="scope", dialect="legacy", op="set_trigger_slope", params={"src": "C2", "slope": "NEG"}, request="C2:TRSL NEG", source=f"{LEGACY_GUIDE} p.134", mock_kwargs={"idn": LEGACY_IDN}),
    WireForm(
        table="scope",
        dialect="legacy",
        op="get_trigger_slope",
        params={"src": "C2"},
        request="C2:TRSL?",
        response="C2:TRSL NEG",
        source=f"{LEGACY_GUIDE} p.134",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[low severity] Request matches ('<trig_source>:TRig_Slope?'). RESPONSE "
            "FORMAT is prefixed; no worked query EXAMPLE on this page, confirmed by "
            "the p.116/p.142 cross-reference. Mock's C(n):TRSL? handler answers "
            "bare. slope_from_wire() reads only the last token. Below the pull-in "
            "bar. Queued."
        ),
    ),
    # p.131 EXAMPLE: "TRSE EDGE, SR, C1, HT, TI, HV, 1.43US". The description
    # explicitly allows a subset ("Pairs may be given in any order and
    # restricted to those variables to be changed"), so the code's HT/HV-less
    # "TRIG_SELECT EDGE,SR,C1" is a documented-valid partial form, not a defect.
    WireForm(table="scope", dialect="legacy", op="set_trigger_select", params={"type": "EDGE", "src": "C1"}, request="TRIG_SELECT EDGE,SR,C1", source=f"{LEGACY_GUIDE} p.131", mock_kwargs={"idn": LEGACY_IDN}),
    WireForm(
        table="scope",
        dialect="legacy",
        op="get_trigger_select",
        params={},
        request="TRIG_SELECT?",
        response="TRSE EDGE,SR,C1,HT,TI,HV,1.43US",
        source=f"{LEGACY_GUIDE} p.131, p.132",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[low severity] Request matches ('TRig_SElect?'). RESPONSE FORMAT is "
            "'TRig_Select <trig_type>,SR,<source>,HT,<hold_type>,HV,<hold_value>' "
            "(prefixed, and always includes the HT/HV pair per the format line). "
            "Mock's TRIG_SELECT? handler (connection/mock/siglent.py) answers "
            "'{type},SR,{source}' -- no header echo AND no HT/HV pair, since the "
            "mock tracks no hold-type/hold-value state. trigger.py's source and "
            "trigger_type getters only read parts[0] and parts[2] of a comma split, "
            "so a missing header (attached to parts[0] via a space, not a comma) "
            "and a missing trailing pair do not shift those indices -- no wrong "
            "value reaches the user. Below the pull-in bar. Queued."
        ),
    ),

    # -- Measurements --
    # p.87 EXAMPLE: "PACU PKPK, C1" (cosmetic space after comma removed).
    WireForm(table="scope", dialect="legacy", op="add_measurement", params={"mtype": "PKPK", "ch": 1}, request="PACU PKPK,C1", source=f"{LEGACY_GUIDE} p.87", mock_kwargs={"idn": LEGACY_IDN}),
    # p.86: COMMAND SYNTAX "PArameter_CLr" (bare, no EXAMPLE block on this page,
    # but the header names the short form "PACL" unambiguously).
    WireForm(table="scope", dialect="legacy", op="clear_measurements", params={}, request="PACL", source=f"{LEGACY_GUIDE} p.86", mock_kwargs={"idn": LEGACY_IDN}),
    WireForm(
        table="scope",
        dialect="legacy",
        op="set_statistics",
        params={"state": "ON"},
        request="PAST ON",
        source=f"{LEGACY_GUIDE} p.16",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[low severity] PAST/PARAMETER_STATISTICS does not exist anywhere in "
            "this manual -- exhaustive full-text search (every page) for 'PAST', "
            "'PASTAT', and 'statistic' (any case) returns zero hits. p.16's Table of "
            "Commands lists PARAMETER_CUSTOM (PACU) immediately followed by "
            "PARAMETER_VALUE? (PAVA?) with nothing between them, where "
            "PARAMETER_STATISTICS would alphabetically sort if it existed. Request "
            "left as the current form per the absent-command rule. Not reachable on "
            "a default path (measurement.py's enable_statistics/add_measurement "
            "stat=True are opt-in). Queued."
        ),
    ),
    WireForm(
        table="scope",
        dialect="legacy",
        op="reset_statistics",
        params={},
        request="PASTAT RESET",
        source=f"{LEGACY_GUIDE} p.16",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[low severity] Same absence as set_statistics above -- 'PASTAT' has "
            "zero hits in the manual. Request left as the current form. Opt-in "
            "only (measurement.py's reset_statistics is user-invoked). Queued."
        ),
    ),
    # p.38-39: CURSOR_SET (CRST) COMMAND SYNTAX is
    # "<trace>:CuRsor_SeT<cursor>,<position>[,<cursor>,<position>,...]" -- a
    # trace-prefixed cursor *positioning* command (cursor names VREF, VDIF,
    # TREF, TDIF, HREF, HDIF; EXAMPLE "C1: CRST VREF, 3DIV, VDIF, -1DIV"). The
    # code's set_cursor_type sends a bare "CRST {type}" with type one of
    # OFF/HREL/VREL/HREF/VREF -- neither a valid CRST positioning call (missing
    # trace prefix and a position value) nor the manual's mode-selection
    # command, which is CURSOR_MEASURE (CRMS, p.37): "CuRsor_MeaSure <mode>",
    # <mode>:={OFF,HREL,VREL,AUTO} (Format 2), EXAMPLE "CRMS OFF" -- bare, no
    # trace prefix, matching the shape the code already sends.
    WireForm(
        table="scope",
        dialect="legacy",
        op="set_cursor_type",
        params={"type": "OFF"},
        request="C1:CRST VREF,3DIV,VDIF,-1DIV",
        source=f"{LEGACY_GUIDE} p.38",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[medium severity] Code sends 'CRST {type}' (e.g. 'CRST OFF') for "
            "measurement.py's set_cursor_type. CRST is CURSOR_SET, a trace-prefixed "
            "cursor *positioning* command (p.38, EXAMPLE 'C1:CRST VREF,3DIV,"
            "VDIF,-1DIV' transcribed above) -- not a mode selector, and the code's "
            "call has neither the required trace prefix nor a position value. The "
            "manual's actual mode-selection command is CURSOR_MEASURE (CRMS, p.37): "
            "'CRMS <mode>', <mode>={OFF,HREL,VREL,AUTO}, bare like the code's call "
            "shape but a different header, and missing HREF/VREF from the code's "
            "vocabulary (those are CRST's position names, not CRMS modes). Likely "
            "rejected or a no-op on real hardware; reachable via "
            "Measurement.set_cursor_type() (user-invoked, not a default path). "
            "Queued for a code fix, not just a mock fix."
        ),
    ),
    WireForm(
        table="scope",
        dialect="legacy",
        op="get_cursor_type",
        params={},
        request="C1:CRST?",
        source=f"{LEGACY_GUIDE} p.38",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[low severity] Same CRST/CRMS confusion as set_cursor_type above. Code "
            "sends bare 'CRST?'; CURSOR_SET? QUERY SYNTAX is trace-prefixed "
            "'<trace>:CuRsor_SeT? [<cursor>,...]'. Additionally dead code: no "
            "caller anywhere in the repo invokes get_cursor_type (measurement.py "
            "has a set_cursor_type method but no getter). Queued."
        ),
    ),
    # p.40 EXAMPLE: Command "C2:CRVA? VREL" -> Response "C2:CuRsor_Value VREL
    # 1.00V" (collapsed to the short form on the wire, "C2:CRVA VREL 1.00V";
    # note the manual's own RESPONSE FORMAT line uses a comma
    # ("VREL,<delta_vert>") where the worked EXAMPLE uses a space -- transcribed
    # as the EXAMPLE literally shows).
    WireForm(
        table="scope",
        dialect="legacy",
        op="get_cursor_value",
        params={},
        request="C2:CRVA? VREL",
        response="C2:CRVA VREL 1.00V",
        source=f"{LEGACY_GUIDE} p.40",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[HIGH severity -- pull-in candidate] Code sends bare 'CRVA?' "
            "(scpi_commands.py has a NOTE that 'no cursor id is ever passed by "
            "measurement.py'). CURSOR_VALUE? QUERY SYNTAX is trace-prefixed "
            "'<trace>:CuRsor_Value? [<mode>,...<mode>]', e.g. 'C2:CRVA? VREL' -- "
            "without a trace and mode, this is not a documented query at all. "
            "Worse, measurement.py's get_cursor_value() parses the response as "
            "'response.split(\",\")' expecting a comma-joined 'CRVA' NUL-prefixed "
            "payload (docstring example 'CRVA VREL,1.00V,2.00V,1.00V'), but the "
            "manual's real worked response has no comma at all ('C2:CuRsor_Value "
            "VREL 1.00V') -- against a real instrument this parser would silently "
            "return an empty 'values' list and a garbage 'type' string instead of "
            "raising, i.e. a wrong/missing number reaching the user (pull-in bar "
            "#1). Not fixed here per the task-5a read-only constraint; flagged for "
            "a follow-up task."
        ),
    ),

    # -- Trigger holdoff --
    # p.127: TRIG_DELAY/TRDL's own COMMAND/QUERY SYNTAX is correctly rendered
    # by the code ('TRIG_DELAY {t}' / 'TRIG_DELAY?' are the same command as
    # set_time_offset/get_time_offset above, just spelled with the long form)
    # -- this is not a wire-syntax defect. The defect is that TRIG_DELAY is
    # documented as "the time at which the trigger is to occur" (pre/post
    # trigger delay), not oscilloscope trigger *holdoff* (minimum re-trigger
    # blanking time) -- a distinct concept this manual does not document under
    # any header. Already flagged in code as AUDIT M4
    # (scpi_control/trigger.py: "NOTE: TRIG_DELAY is legacy-only and actually
    # controls trigger delay, not holdoff").
    WireForm(
        table="scope",
        dialect="legacy",
        op="set_trigger_holdoff",
        params={"t": 1e-6},
        request="TRIG_DELAY 1e-06",
        source=f"{LEGACY_GUIDE} p.127",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[medium-high severity -- pull-in candidate] The rendered command IS "
            "syntactically valid (TRIG_DELAY is the documented long form of TRDL, "
            "p.127) -- there is no wrong wire form here. But this manual documents "
            "no 'holdoff' command; TRIG_DELAY/TRDL is 'the time at which the "
            "trigger is to occur' (pre/post-trigger delay), the exact same wire "
            "parameter as set_time_offset above. Trigger.holdoff therefore silently "
            "reads/writes trigger DELAY under the 'holdoff' name -- the intended "
            "holdoff setting is never applied (a silent no-op of the feature the "
            "caller asked for), while an unrelated parameter (acquisition delay) is "
            "mutated as a side effect. Already flagged in code as AUDIT M4. "
            "Possible pull-in bar #2 match (silent no-op of a setting); flagged for "
            "a follow-up task rather than fixed here."
        ),
    ),
    WireForm(
        table="scope",
        dialect="legacy",
        op="get_trigger_holdoff",
        params={},
        request="TRIG_DELAY?",
        source=f"{LEGACY_GUIDE} p.127",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[medium-high severity -- pull-in candidate] Same TRIG_DELAY/holdoff "
            "confusion as set_trigger_holdoff above -- get_trigger_holdoff and "
            "get_time_offset query the identical wire command under two different "
            "public names. AUDIT M4. Queued alongside the setter."
        ),
    ),

    # -- Channel vertical unit --
    # p.137 EXAMPLE: "C1: UNIT V".
    WireForm(table="scope", dialect="legacy", op="set_channel_unit", params={"ch": 1, "unit": "V"}, request="C1:UNIT V", source=f"{LEGACY_GUIDE} p.137", mock_kwargs={"idn": LEGACY_IDN}),
    # get_channel_unit is not mocked. QUERY SYNTAX "<channel>:UNIT?".
    WireForm(table="scope", dialect="legacy", op="get_channel_unit", params={"ch": 1}, request="C1:UNIT?", source=f"{LEGACY_GUIDE} p.137", mock_kwargs={"idn": LEGACY_IDN}),

    # -- Math operations --
    # MATH{n}:TRA does not exist anywhere in this manual -- full-text search
    # for "MATH1", "MATH2", "MATH:" and bare "MATH " (all case-sensitive
    # variants) returns zero hits outside of MATH_VERT_POS/MATH_VERT_DIV
    # (MTVP/MTVD, p.79-80, which adjust a math trace's position/scale, not its
    # display state). TRACE (TRA, p.124) is the command that enables/disables
    # trace display, and its <trace> enum explicitly includes the math/function
    # trace identifiers: "{C1, C2, C3, C4, TA, TB, TC, TD}" -- the closest
    # documented equivalent of "math display" would be "TA:TRA {state}", not
    # "MATH1:TRA {state}".
    WireForm(
        table="scope",
        dialect="legacy",
        op="set_math_display",
        params={"n": 1, "state": "ON"},
        request="MATH1:TRA ON",
        source=f"{LEGACY_GUIDE} p.124",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[low severity] 'MATH{n}:TRA' is absent from the manual entirely (see "
            "module comment above). Request left as the current form. TRACE's own "
            "<trace> enum (p.124) includes TA/TB/TC/TD for math/function traces, "
            "suggesting the real equivalent is 'TA:TRA {state}'. Dead code: no "
            "caller anywhere in the repo invokes set_math_display. Queued."
        ),
    ),
    WireForm(
        table="scope",
        dialect="legacy",
        op="get_math_display",
        params={"n": 1},
        request="MATH1:TRA?",
        source=f"{LEGACY_GUIDE} p.124",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[low severity] Same absence as set_math_display above. Dead code: no "
            "caller anywhere in the repo invokes get_math_display. Queued."
        ),
    ),

    # -- Waveform acquisition --
    # p.141 EXAMPLE: "C1: WF? DAT2".
    WireForm(table="scope", dialect="legacy", op="get_waveform", params={"ch": 1}, request="C1:WF? DAT2", source=f"{LEGACY_GUIDE} p.141", mock_kwargs={"idn": LEGACY_IDN}),
    # p.141 QUERY SYNTAX lists <section>:={DESC,DAT2,ALL} as siblings; only
    # DAT2 has a worked EXAMPLE on this page, but DESC is the same syntax with
    # a different documented enum value.
    WireForm(table="scope", dialect="legacy", op="get_waveform_preamble", params={"ch": 1}, request="C1:WF? DESC", source=f"{LEGACY_GUIDE} p.141", mock_kwargs={"idn": LEGACY_IDN}),

    # -- Acquisition status --
    WireForm(
        table="scope",
        dialect="legacy",
        op="get_acq_status",
        params={},
        request="SAST?",
        response="SAST trig'd",
        parsed="TRIGD",
        source=f"{LEGACY_GUIDE} p.116",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[low severity] Request matches exactly. p.116's own worked EXAMPLE: "
            "'SAST?' -> 'SAST trig'd' (prefixed, transcribed above). Mock's SAST? "
            "handler (connection/mock/siglent.py) returns the bare internal status "
            "word (e.g. 'Ready', 'Stop', 'Auto') with neither the 'SAST' header nor "
            "the manual's exact vocabulary casing. normalize_status() reads only "
            "the last whitespace token and maps a fixed vocabulary that includes "
            "both, so no wrong status reaches the user. Below the pull-in bar. "
            "Queued."
        ),
    ),

    # -- Screen capture --
    # p.106 COMMAND SYNTAX/EXAMPLE: bare "SCDP". Note: screen_capture.py's
    # _capture_with_scdp() does not call SCPICommandSet.get_command("screen_dump")
    # at all -- it hardcodes "SCDP?" (with a query mark) for the legacy/mock
    # path, bypassing this table entirely. That is a separate, pre-existing
    # observation (dead command-table entry) and does not change the fact
    # that LEGACY_COMMANDS["screen_dump"] itself renders exactly what p.106
    # documents.
    WireForm(table="scope", dialect="legacy", op="screen_dump", params={}, request="SCDP", source=f"{LEGACY_GUIDE} p.106", mock_kwargs={"idn": LEGACY_IDN}),
    # p.70 COMMAND SYNTAX: "HCSU PSIZE,<page_size>,ISIZE,<image_size>,FORMAT,
    # <format>,BCKG,<bckg>,PRTKEY,<printkey>" -- EXAMPLE "HCSU ISIZE, 6*8CM,
    # FORMAT, PORTRAIT" shows a subset of the documented keyword pairs is
    # valid. "DEV" is not one of the five recognised keywords
    # (PSIZE/ISIZE/FORMAT/BCKG/PRTKEY).
    WireForm(
        table="scope",
        dialect="legacy",
        op="set_hardcopy_format",
        params={"format": "LANDSCAPE"},
        request="HCSU FORMAT,LANDSCAPE",
        source=f"{LEGACY_GUIDE} p.70",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[low severity] Code sends 'HCSU DEV,FORMAT,{format}'. 'DEV' is not a "
            "documented HCSU keyword -- the five recognised pairs are PSIZE, ISIZE, "
            "FORMAT, BCKG, PRTKEY (p.70), and the worked EXAMPLE shows a bare "
            "subset ('HCSU ISIZE, 6*8CM, FORMAT, PORTRAIT') is valid, so a plain "
            "'HCSU FORMAT,{format}' is the documented form. Dead code: no caller "
            "anywhere in the repo invokes set_hardcopy_format. Queued."
        ),
    ),
    # <printkey>:={SAVE,PRINT} is a value paired with the "PRTKEY" keyword.
    WireForm(
        table="scope",
        dialect="legacy",
        op="hardcopy_print",
        params={},
        request="HCSU PRTKEY,PRINT",
        source=f"{LEGACY_GUIDE} p.70",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": LEGACY_IDN},
        note=(
            "[low severity] Code sends bare 'HCSU PRINT', omitting the 'PRTKEY,' "
            "keyword the manual requires before the SAVE|PRINT value. Dead code: no "
            "caller anywhere in the repo invokes hardcopy_print. Queued."
        ),
    ),
]
