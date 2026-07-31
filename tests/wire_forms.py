"""Documented SCPI request/response pairs, transcribed from vendor programming guides.

Every entry is a verbatim transcription of an EXAMPLE block in a vendor manual.
Most manuals are NOT committed (the two modern SDS guides are tracked in docs/;
the rest are kept local -- see docs/development/vendor-manuals.md for sources
and .git/info/exclude for why), so `source` must always name document and page.
A `source` page number is the PDF file page position ("go to page N"), which for
these front-matter-bearing guides runs a few pages ahead of the printed footer --
see the citation-convention table in docs/development/vendor-manuals.md.
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
#: Known to disagree with the manual; fix queued. Filtered out of the
#: parametrized request/response assertions (not collected as xfail).
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
            'gives a genuine worked query EXAMPLE: \'Send command "C1:VDIV?", '
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
            '"C1:OFST?", return "C1:OFST -5.00E-01V"\' (prefixed). Mock\'s '
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
    # p.22 RESPONSE FORMAT: "<channel>: ATTeNuation <attenuation>" (header-echoed,
    # collapsed to the short form "C1:ATTN <value>"). Task 14 (audit L3): the mock
    # gained an ATTN?/ATTN-write handler (connection/mock/siglent.py) backed by new
    # `probe_ratios` state (connection/mock/base.py), defaulting every channel to
    # 1.0 -- so a fresh mock's "C1:ATTN?" answers "C1:ATTN 1", matched below.
    WireForm(
        table="scope",
        dialect="legacy",
        op="get_probe_ratio",
        params={"ch": 1},
        request="C1:ATTN?",
        response="C1:ATTN 1",
        parsed=1.0,
        source=f"{LEGACY_GUIDE} p.22",
        mock_kwargs={"idn": LEGACY_IDN},
    ),
    # p.27 EXAMPLE: "BWL C1, ON" (cosmetic space after comma normalised away).
    # Task 14 (audit L3) fix: the driver used to send the invented, colon-prefixed
    # "C{ch}:BWL {limit}" -- this manual documents no such form anywhere. The BWL
    # keyword comes first; channel and mode are its comma-separated arguments,
    # identical in shape to the LeCroy MAUI form (MAUI p.7-18) this dialect is
    # descended from. scpi_commands.py's legacy set_bandwidth_limit template now
    # renders exactly this.
    WireForm(
        table="scope",
        dialect="legacy",
        op="set_bandwidth_limit",
        params={"ch": 1, "limit": "ON"},
        request="BWL C1,ON",
        source=f"{LEGACY_GUIDE} p.27",
        mock_kwargs={"idn": LEGACY_IDN},
    ),
    # p.27 QUERY SYNTAX is bare "BandWidth_Limit?" (no channel argument);
    # RESPONSE FORMAT returns ALL channels as "<channel>,<mode>" pairs, header-
    # echoed as "BandWidth_Limit <channel>,<mode>[,...]" (collapsed short form
    # "BWL C1,OFF,C2,OFF,..."). Task 14 fix: scpi_commands.py's legacy
    # get_bandwidth_limit template now sends bare "BWL?" (was the invented
    # per-channel "C{ch}:BWL?"); the mock gained a BWL?/BWL-write handler backed
    # by new `bandwidth_limits` state, defaulting every channel to OFF -- a fresh
    # mock's "BWL?" answers "BWL C1,OFF,C2,OFF" (2 default channels), matched
    # below. channel.py's bandwidth_limit getter now reuses the same pairs-
    # parsing branch as the LeCroy dialect, extended to also strip legacy's
    # "BWL " header echo before splitting (LeCroy's own CHDR OFF setup already
    # suppresses that header on the wire, so it needs no stripping).
    WireForm(
        table="scope",
        dialect="legacy",
        op="get_bandwidth_limit",
        params={"ch": 1},
        request="BWL?",
        response="BWL C1,OFF,C2,OFF",
        parsed="OFF",
        source=f"{LEGACY_GUIDE} p.27",
        mock_kwargs={"idn": LEGACY_IDN},
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
    WireForm(
        table="scope", dialect="legacy", op="set_trigger_level", params={"src": "C3", "level": "52.00mv"}, request="C3:TRLV 52.00mv", source=f"{LEGACY_GUIDE} p.128", mock_kwargs={"idn": LEGACY_IDN}
    ),
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
    WireForm(
        table="scope",
        dialect="legacy",
        op="set_trigger_select",
        params={"type": "EDGE", "src": "C1"},
        request="TRIG_SELECT EDGE,SR,C1",
        source=f"{LEGACY_GUIDE} p.131",
        mock_kwargs={"idn": LEGACY_IDN},
    ),
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
        note=("[low severity] Same absence as set_math_display above. Dead code: no " "caller anywhere in the repo invokes get_math_display. Queued."),
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
    # --- Modern Siglent scope: sweep 2026-07-23 (task 5b; extended tasks 17-19)
    # Every command in SCPICommandSet.MODERN_COMMANDS (52 total), checked
    # against MODERN_GUIDE (SDS800XHD_Series_ProgrammingGuide_EN11G.pdf, 855
    # pages). Every "p.N" citation below is a PDF file page position ("go to
    # page N"), matching the convention in the module docstring and
    # docs/development/vendor-manuals.md -- for this guide the printed footer
    # runs one behind the file position (file page 749 = printed footer 748).
    # Unlike the legacy dialect (which is abbreviations-only), the modern
    # table renders the long-form header spelled out in COMMAND/QUERY SYNTAX
    # (e.g. ":CHANnel1:SWITch?"), so driver output matches the manual's own
    # syntax line directly rather than its abbreviated worked EXAMPLE
    # ("CHAN1:SWIT?") -- both are the same documented header per SCPI's
    # upper/lowercase short-form convention (see p.10, same rule as legacy).
    # -- Root / acquisition control --
    # p.33 COMMAND SYNTAX/EXAMPLE: bare ":AUToset" (abbreviated "AUT").
    WireForm(table="scope", dialect="modern", op="auto_setup", params={}, request=":AUToset", source=f"{MODERN_GUIDE} p.33", mock_kwargs={"idn": MODERN_IDN}),
    # p.482 <mode>:={SINGle|NORMal|AUTO|FTRIG} -- FTRIG is a documented mode
    # value ("Force to acquire a frame regardless of..."), so force_trigger
    # sending it through :TRIGger:MODE (rather than a standalone FORCE
    # command, which this manual does not have) is the documented mechanism.
    WireForm(table="scope", dialect="modern", op="force_trigger", params={}, request=":TRIGger:MODE FTRIG", source=f"{MODERN_GUIDE} p.482", mock_kwargs={"idn": MODERN_IDN}),
    # p.483: RESPONSE FORMAT <status>:={Arm|Ready|Auto|Trig'd|Stop|Roll}, bare
    # (unprefixed) -- EXAMPLE "TRIG:STAT?" -> "Stop". normalize_status()
    # upper-cases before matching _STATUS_MAP, whose keys already cover this
    # exact vocabulary (scpi_commands.py) -- unlike the legacy SAST? finding,
    # this one is not prefixed and needs no header-stripping tolerance.
    WireForm(
        table="scope",
        dialect="modern",
        op="get_acq_status",
        params={},
        request=":TRIGger:STATus?",
        response="Stop",
        parsed="STOP",
        source=f"{MODERN_GUIDE} p.483",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    # "INR" appears on exactly one page of this 855-page guide -- p.829 -- and
    # not as a COMMAND/QUERY SYNTAX/RESPONSE FORMAT entry: it is a C# EXAMPLE
    # ("Acquisition Status" helper) that polls in a loop --
    # `mbSession.RawIO.Write("INR?"); ... Int16 state = Convert.ToInt16(result);
    # if ((state & 0x01) == 1) { Console.WriteLine("Acquisition finished"); ... }`
    # -- exactly the bit new_acquisition_ready() (oscilloscope.py) reads.
    # Documented by example, not by a syntax block: no concrete request/response
    # PAIR is worked through (the snippet shows the bit test, never a literal
    # "INR?" -> "N" value), so `response` is left unset rather than invented.
    # LeCroy's MAUI Remote Control manual documents the same INR bit-0 register,
    # at p.7-132/7-133 (see the `get_acq_status`/lecroy comment in
    # oscilloscope.py's acquisition_status()) -- a different vendor guide for a
    # different dialect/table not covered by this corpus (LeCroy is UNCITED
    # throughout, see the module docstring), so it is referenced here rather
    # than duplicated as a second WireForm entry.
    WireForm(table="scope", dialect="modern", op="get_new_data", params={}, request="INR?", source=f"{MODERN_GUIDE} p.829", mock_kwargs={"idn": MODERN_IDN}),
    WireForm(table="scope", dialect="modern", op="run", params={}, request=":TRIGger:RUN", source=f"{MODERN_GUIDE} p.483", mock_kwargs={"idn": MODERN_IDN}),
    WireForm(table="scope", dialect="modern", op="stop", params={}, request=":TRIGger:STOP", source=f"{MODERN_GUIDE} p.484", mock_kwargs={"idn": MODERN_IDN}),
    # -- Channel control --
    # p.60 EXAMPLE: "CHAN1:SWIT ON" -> "CHANnel1:SWITch ON"; query response
    # bare "ON". Mock's modern SWITch? handler returns bare ON/OFF -- matches.
    WireForm(table="scope", dialect="modern", op="set_channel_display", params={"ch": 1, "state": "ON"}, request=":CHANnel1:SWITch ON", source=f"{MODERN_GUIDE} p.60", mock_kwargs={"idn": MODERN_IDN}),
    WireForm(
        table="scope",
        dialect="modern",
        op="get_channel_display",
        params={"ch": 1},
        request=":CHANnel1:SWITch?",
        response="ON",
        source=f"{MODERN_GUIDE} p.60",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    # p.58 EXAMPLE: "CHAN1:SCAL 5.00E-02" -> "CHANnel1:SCALe 5.00E-02"; query
    # response bare NR3 (manual shows the probe-adjusted alternate too, e.g.
    # "5.00E-01 (when the probe attenuation ratio is 10:1)").
    WireForm(
        table="scope", dialect="modern", op="set_voltage_div", params={"ch": 1, "vdiv": "5.00E-02"}, request=":CHANnel1:SCALe 5.00E-02", source=f"{MODERN_GUIDE} p.58", mock_kwargs={"idn": MODERN_IDN}
    ),
    WireForm(
        table="scope",
        dialect="modern",
        op="get_voltage_div",
        params={"ch": 1},
        request=":CHANnel1:SCALe?",
        response="1.00E+00",
        parsed=1.0,
        source=f"{MODERN_GUIDE} p.58",
        mock_kwargs={"idn": MODERN_IDN},
        note=(
            "Mock's default scale (1.00E+00) differs from the manual's worked "
            "example value (5.00E-02) -- same divergence-is-fine rule as the "
            "legacy SARA?/get_sample_rate entry above; only the bare-NR3 "
            "structure is pinned."
        ),
    ),
    # p.56 EXAMPLE: "CHAN2:OFFS -3.8E+00" -> "CHANnel2:OFFSet -3.8E+00".
    WireForm(
        table="scope",
        dialect="modern",
        op="set_voltage_offset",
        params={"ch": 2, "offset": "-3.8E+00"},
        request=":CHANnel2:OFFSet -3.8E+00",
        source=f"{MODERN_GUIDE} p.56",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    WireForm(
        table="scope",
        dialect="modern",
        op="get_voltage_offset",
        params={"ch": 2},
        request=":CHANnel2:OFFSet?",
        response="0.00E+00",
        parsed=0.0,
        source=f"{MODERN_GUIDE} p.56",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    # p.51 EXAMPLE: "CHAN1:COUP AC" -> "CHANnel1:COUPling AC";
    # <coupling_mode>:={DC|AC|GND}.
    WireForm(table="scope", dialect="modern", op="set_coupling", params={"ch": 1, "coupling": "AC"}, request=":CHANnel1:COUPling AC", source=f"{MODERN_GUIDE} p.51", mock_kwargs={"idn": MODERN_IDN}),
    WireForm(
        table="scope",
        dialect="modern",
        op="get_coupling",
        params={"ch": 1},
        request=":CHANnel1:COUPling?",
        response="D1M",
        source=f"{MODERN_GUIDE} p.51",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": MODERN_IDN},
        note=(
            "[medium severity] Request matches exactly ('<channel>:COUPling?'). "
            "The wire template and coupling_to_wire/coupling_from_wire mappings "
            "(scpi_commands.py) are both correct for modern -- {'DC':'DC', "
            "'AC':'AC', 'GND':'GND'}, matching p.51's <coupling_mode>:={DC|AC|GND} "
            "exactly. The bug is in the mock fixture only: MockConnection seeds "
            "'_channel_coupling' with the LEGACY wire token 'D1M' unconditionally "
            "for every dialect (connection/mock/base.py, ~line 82: \"{ch: 'D1M' "
            'for ch in channels}", no scope_dialect branch, unlike trigger_mode/ '
            "trigger_slope a few lines below which do branch on dialect). 'D1M' "
            "is not a member of the modern enum, so Channel.coupling on a freshly "
            "constructed modern MockConnection (before any set_coupling call) "
            "raises 'ValueError: Unrecognized modern coupling mode response: "
            "'D1M'' via coupling_from_wire() -- a real, reachable crash against "
            "this test fixture, though it cannot happen against real hardware "
            "(this is a mock-state defect, not a driver or table defect). Queued "
            "for a mock fix (seed _channel_coupling per-dialect), not a code-table "
            "change."
        ),
    ),
    # p.57 EXAMPLE: "CHAN1:PROB VAL,1.00E+02" -> "CHANnel1:PROBe VALue,1.00E+02";
    # <attenuation>:={DEFault|VALue}. Backend review 2026-07-31 (Task 4) added
    # a modern PROBe set/query handler to connection/mock/siglent.py (the
    # "Not mocked" gap this comment used to describe), driven by the same
    # hardware measurement that fixed ModernTransfer.acquire's probe scaling.
    WireForm(
        table="scope",
        dialect="modern",
        op="set_probe_ratio",
        params={"ch": 1, "ratio": "1.00E+02"},
        request=":CHANnel1:PROBe VALue,1.00E+02",
        source=f"{MODERN_GUIDE} p.57",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    # RESPONSE FORMAT is bare NR3 (p.57 EXAMPLE response "1.00E+02", after the
    # VALue,1.00E+02 set above) -- same bare-NR3 shape as SCALe?/OFFSet?
    # above. Queried here on a FRESH mock (no prior set), so the value is the
    # documented default (DEFault = "1X", p.57) rather than the manual's
    # post-set example value -- same divergence-is-fine rule as the
    # get_voltage_div entry above: only the bare-NR3 structure is pinned.
    WireForm(
        table="scope",
        dialect="modern",
        op="get_probe_ratio",
        params={"ch": 1},
        request=":CHANnel1:PROBe?",
        response="1.00E+00",
        parsed=1.0,
        source=f"{MODERN_GUIDE} p.57",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    # p.50 EXAMPLE: "CHAN1:BWL 20M" -> "CHANnel1:BWLimit 20M";
    # <bwlimit>:={FULL|20M|200M} -- matches channel.py's modern wire vocabulary
    # (FULL/20M) exactly. Not mocked (no BWLimit handler in the modern branch).
    WireForm(
        table="scope", dialect="modern", op="set_bandwidth_limit", params={"ch": 1, "limit": "20M"}, request=":CHANnel1:BWLimit 20M", source=f"{MODERN_GUIDE} p.50", mock_kwargs={"idn": MODERN_IDN}
    ),
    WireForm(table="scope", dialect="modern", op="get_bandwidth_limit", params={"ch": 1}, request=":CHANnel1:BWLimit?", source=f"{MODERN_GUIDE} p.50", mock_kwargs={"idn": MODERN_IDN}),
    # -- Timebase control --
    # p.476 EXAMPLE: "TIM:SCAL 1.00E-07" -> "TIMebase:SCALe 1.00E-07".
    WireForm(table="scope", dialect="modern", op="set_time_div", params={"tdiv": "1.00E-07"}, request=":TIMebase:SCALe 1.00E-07", source=f"{MODERN_GUIDE} p.476", mock_kwargs={"idn": MODERN_IDN}),
    WireForm(
        table="scope",
        dialect="modern",
        op="get_time_div",
        params={},
        request=":TIMebase:SCALe?",
        response="1.00E-03",
        parsed=0.001,
        source=f"{MODERN_GUIDE} p.476",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    # p.473 EXAMPLE: "TIM:DEL 1.00E-05" -> "TIMebase:DELay 1.00E-05".
    WireForm(table="scope", dialect="modern", op="set_time_offset", params={"offset": "1.00E-05"}, request=":TIMebase:DELay 1.00E-05", source=f"{MODERN_GUIDE} p.473", mock_kwargs={"idn": MODERN_IDN}),
    # get_time_offset is not mocked (no TIMebase:DELay? handler in the modern
    # branch of connection/mock/siglent.py -- only TIMebase:SCALe? is
    # implemented there) -- request-only citation.
    WireForm(table="scope", dialect="modern", op="get_time_offset", params={}, request=":TIMebase:DELay?", source=f"{MODERN_GUIDE} p.473", mock_kwargs={"idn": MODERN_IDN}),
    # p.46 EXAMPLE: "ACQ:SRAT?" -> "5.00E+09" -> ":ACQuire:SRATe?", bare NR3.
    WireForm(
        table="scope",
        dialect="modern",
        op="get_sample_rate",
        params={},
        request=":ACQuire:SRATe?",
        response="1.00E+03",
        parsed=1000.0,
        source=f"{MODERN_GUIDE} p.46",
        mock_kwargs={"idn": MODERN_IDN},
        note="Mock default (1000.0) differs from the manual's example value (5.00E9); structure (bare NR3) is what's pinned.",
    ),
    # p.36 lists :ACQuire:POINts in the ACQUire subsystem's command index only
    # (query-only, no COMMAND SYNTAX -- just a "?" marker, no worked example).
    # The full entry -- QUERY SYNTAX ":ACQuire:POINts?", RESPONSE FORMAT
    # "<point> := Value in NR3 format... like 1.23E+2", EXAMPLE "ACQ:POIN?" ->
    # "1.25E+08" -- is on p.43, cited below. (p.752's :WAVeform:POINt entry
    # cross-references :ACQuire:POINts under its own RELATED COMMANDS footer --
    # a pointer to this same command, not a second specification of it.)
    # get_acq_points is not mocked (no :ACQuire:POINts? handler in the modern
    # branch of connection/mock/siglent.py) -- request-only citation, same
    # rationale as the get_time_offset entry above.
    WireForm(table="scope", dialect="modern", op="get_acq_points", params={}, request=":ACQuire:POINts?", source=f"{MODERN_GUIDE} p.43", mock_kwargs={"idn": MODERN_IDN}),
    # -- Trigger settings --
    # p.482 <mode>:={SINGle|NORMal|AUTO|FTRIG}; EXAMPLE "TRIG:MODE SING" ->
    # ":TRIGger:MODE SINGle", response bare "SINGle". mode_to_wire('modern',
    # 'SINGLE') already renders this exact wire spelling (scpi_commands.py).
    WireForm(table="scope", dialect="modern", op="set_trigger_mode", params={"mode": "SINGle"}, request=":TRIGger:MODE SINGle", source=f"{MODERN_GUIDE} p.482", mock_kwargs={"idn": MODERN_IDN}),
    WireForm(
        table="scope",
        dialect="modern",
        op="get_trigger_mode",
        params={},
        request=":TRIGger:MODE?",
        response="AUTO",
        parsed="AUTO",
        source=f"{MODERN_GUIDE} p.482",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    # p.484 <type>:={EDGE|PULSE|SLOPe|INTerval|PATTern|RUNT|WINDow|DROPout|
    # VIDeo|QUALified|NEDGe|DELay|SHOLd|IIC|SPI|UART|LIN|CAN|FLEXray|CANFd|
    # IIS|M1553|SENT|A429} -- EXAMPLE "TRIG:TYPE EDGE" -> "EDGE" bare. EDGE is
    # both a valid manual enum member and a valid trigger.py public value, so
    # it pins the identity case. Backend review 2026-07-31, finding High-2: the
    # other three of trigger.py's six public values have no modern equivalent
    # at all -- "SLEW"/"GLIT"/"INTV" are not members of the manual's <type>
    # enum (the nearest concepts are spelled "SLOPe"/"PULSE"/"INTerval"). This
    # is no longer a gap: _TRIGGER_TYPE_TO_WIRE / _TRIGGER_TYPE_FROM_WIRE
    # (scpi_commands.py) and the trigger_type_to_wire()/trigger_type_from_wire()
    # wrappers now translate at the dialect boundary, exercised by the two
    # entries below (p.485).
    WireForm(table="scope", dialect="modern", op="set_trigger_type", params={"type": "EDGE"}, request=":TRIGger:TYPE EDGE", source=f"{MODERN_GUIDE} p.484", mock_kwargs={"idn": MODERN_IDN}),
    WireForm(
        table="scope",
        dialect="modern",
        op="get_trigger_type",
        params={},
        request=":TRIGger:TYPE?",
        response="EDGE",
        source=f"{MODERN_GUIDE} p.484",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    WireForm(table="scope", dialect="modern", op="set_trigger_type", params={"type": "SLOPe"}, request=":TRIGger:TYPE SLOPe", source=f"{MODERN_GUIDE} p.485", mock_kwargs={"idn": MODERN_IDN}),
    WireForm(table="scope", dialect="modern", op="get_trigger_type", params={}, request=":TRIGger:TYPE?", response="EDGE", source=f"{MODERN_GUIDE} p.485", mock_kwargs={"idn": MODERN_IDN}),
    # p.495 <source>:={C<n>|D<d>|EX|EX5|LINE}; EXAMPLE "TRIG:EDGE:SOUR C1" ->
    # ":TRIGger:EDGE:SOURce C1", response bare "C1".
    WireForm(table="scope", dialect="modern", op="set_trigger_source", params={"src": "C1"}, request=":TRIGger:EDGE:SOURce C1", source=f"{MODERN_GUIDE} p.495", mock_kwargs={"idn": MODERN_IDN}),
    WireForm(
        table="scope",
        dialect="modern",
        op="get_trigger_source",
        params={},
        request=":TRIGger:EDGE:SOURce?",
        response="C1",
        parsed="C1",
        source=f"{MODERN_GUIDE} p.495",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    # p.492 <level_value> in NR3; EXAMPLE "TRIG:EDGE:LEV 5.00E-01" ->
    # ":TRIGger:EDGE:LEVel 5.00E-01", response bare "5.00E-01".
    WireForm(
        table="scope", dialect="modern", op="set_trigger_level", params={"level": "5.00E-01"}, request=":TRIGger:EDGE:LEVel 5.00E-01", source=f"{MODERN_GUIDE} p.492", mock_kwargs={"idn": MODERN_IDN}
    ),
    WireForm(
        table="scope",
        dialect="modern",
        op="get_trigger_level",
        params={},
        request=":TRIGger:EDGE:LEVel?",
        response="0.00E+00",
        parsed=0.0,
        source=f"{MODERN_GUIDE} p.492",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    # p.494 <slope_type>:={RISing|FALLing|ALTernate}; EXAMPLE "TRIG:EDGE:SLOP
    # RIS" -> ":TRIGger:EDGE:SLOPe RISing", response bare "RISing".
    WireForm(
        table="scope", dialect="modern", op="set_trigger_slope", params={"slope": "RISing"}, request=":TRIGger:EDGE:SLOPe RISing", source=f"{MODERN_GUIDE} p.494", mock_kwargs={"idn": MODERN_IDN}
    ),
    WireForm(
        table="scope",
        dialect="modern",
        op="get_trigger_slope",
        params={},
        request=":TRIGger:EDGE:SLOPe?",
        response="RISing",
        parsed="POS",
        source=f"{MODERN_GUIDE} p.494",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    # p.486 <mode>:={DC|AC|LFREJect|HFREJect}; EXAMPLE "TRIG:EDGE:COUP DC" ->
    # ":TRIGger:EDGE:COUPling DC", response bare "DC". trigger.py's coupling
    # setter has its own {"HFREJ":"HFREJect","LFREJ":"LFREJect"} wire mapping
    # (distinct from channel coupling_to_wire), matching this enum exactly --
    # unlike get_coupling above, there is no mock-fixture bug here (mock's
    # default trigger_coupling is seeded "DC", a valid modern token).
    WireForm(
        table="scope", dialect="modern", op="set_trigger_coupling", params={"coupling": "DC"}, request=":TRIGger:EDGE:COUPling DC", source=f"{MODERN_GUIDE} p.486", mock_kwargs={"idn": MODERN_IDN}
    ),
    WireForm(
        table="scope",
        dialect="modern",
        op="get_trigger_coupling",
        params={},
        request=":TRIGger:EDGE:COUPling?",
        response="DC",
        source=f"{MODERN_GUIDE} p.486",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    # -- Measurements --
    # PAVA appears ZERO times anywhere in this 855-page guide (exhaustive
    # full-text search, every page) -- the legacy PARAMETER_VALUE command has no
    # modern equivalent, so it is absent from MODERN_COMMANDS. Modern parameter
    # measurements use the :MEASure:SIMPle subsystem, indexed at p.335.
    #
    # NOTE: an earlier revision of this file cited "p.784ff" for the modern
    # measurement path. That was wrong -- p.774-855 is the built-in DIGITAL
    # MULTIMETER (MEASure:CONTinuity / :RESistance / CONFigure:*), which measures
    # external DMM inputs, not waveform parameters.
    WireForm(
        table="scope",
        dialect="modern",
        op="set_measure_state",
        params={"state": "ON"},
        request=":MEASure ON",
        source=f"{MODERN_GUIDE} p.337",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    # p.365: <type>:={SIMPle|ADVanced}. measure() pins SIMPle right after
    # :MEASure ON -- p.369's VALue? reads "the value that appears on the simple
    # measurement", which an instrument left in ADVanced mode may not serve.
    WireForm(
        table="scope",
        dialect="modern",
        op="set_measure_mode",
        params={"mode": "SIMPle"},
        request=":MEASure:MODE SIMPle",
        source=f"{MODERN_GUIDE} p.365",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    WireForm(
        table="scope",
        dialect="modern",
        op="set_simple_source",
        params={"ch": 1},
        request=":MEASure:SIMPle:SOURce C1",
        source=f"{MODERN_GUIDE} p.368",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    WireForm(
        table="scope",
        dialect="modern",
        op="set_simple_item",
        params={"param": "PKPK", "state": "ON"},
        request=":MEASure:SIMPle:ITEM PKPK,ON",
        source=f"{MODERN_GUIDE} p.367",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    # p.369:
    #   QUERY SYNTAX    :MEASure:SIMPle:VALue? <type>
    #   RESPONSE FORMAT <value> in NR3 format
    #   EXAMPLE         MEAS:SIMP:VAL? MAX   ->   2.000E+00
    # A bare value: no parameter echo and no unit suffix, unlike the legacy
    # PAVA? reply. The driver parses it with float() rather than the legacy
    # comma split.
    WireForm(
        table="scope",
        dialect="modern",
        op="get_simple_value",
        params={"param": "PKPK"},
        request=":MEASure:SIMPle:VALue? PKPK",
        response="2.000E+00",
        parsed=2.0,
        source=f"{MODERN_GUIDE} p.369",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    # -- Waveform acquisition --
    # WF? appears ZERO times anywhere in this guide -- the legacy C{ch}:WF?
    # transfer command has no modern equivalent under any header. Task 18
    # rewires the modern capture path (waveform_transfer.ModernTransfer) onto
    # the documented :WAVeform:SOURce/PREamble/DATA subsystem; these two ops
    # are the trigger commands for the descriptor and the sample data.
    WireForm(
        table="scope",
        dialect="modern",
        op="get_waveform",
        params={"ch": 1},
        request=":WAVeform:DATA?",
        source=f"{MODERN_GUIDE} p.757",
        mock_kwargs={"idn": MODERN_IDN},
        note=(
            "Task 18 (audit H9 fix): repointed from the invented "
            "'C{ch}:WF? DAT2' (zero hits anywhere in this 855-page guide) to "
            "the documented :WAVeform:DATA? query. Response is binary (an "
            "IEEE block, not a query()-able string), so this entry pins the "
            "REQUEST only (no `response`) -- see get_waveform_data below and "
            "tests/test_modern_waveform_transfer.py for the binary-transfer "
            "round trip. 'ch' is accepted for signature compatibility with "
            "the other three dialects' get_waveform but unused: the source "
            "channel is a separate :WAVeform:SOURce command (see below)."
        ),
    ),
    WireForm(
        table="scope",
        dialect="modern",
        op="get_waveform_preamble",
        params={},
        request=":WAVeform:PREamble?",
        source=f"{MODERN_GUIDE} p.755",
        mock_kwargs={"idn": MODERN_IDN},
        note=(
            "Task 18 (audit H9 fix): repointed from the invented "
            "'C{ch}:WF? DESC' (not in this manual) to the documented "
            ":WAVeform:PREamble? query. Binary response (a 346-byte WAVEDESC "
            "block per Table 1, p.755-756) -- pinned request-only, same as "
            "get_waveform above; see tests/test_modern_waveform_transfer.py."
        ),
    ),
    WireForm(
        table="scope",
        dialect="modern",
        op="get_waveform_data",
        params={},
        request=":WAVeform:DATA?",
        source=f"{MODERN_GUIDE} p.757",
        mock_kwargs={"idn": MODERN_IDN},
        note=(
            "Task 18: the :WAVeform:DATA? leaf under its own documented name "
            "(waveform_transfer.ModernTransfer calls this op, not the generic "
            "get_waveform alias above). Binary response, pinned request-only."
        ),
    ),
    WireForm(
        table="scope",
        dialect="modern",
        op="set_waveform_width",
        params={"value": "WORD"},
        request=":WAVeform:WIDTh WORD",
        source=f"{MODERN_GUIDE} p.754",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    WireForm(
        table="scope",
        dialect="modern",
        op="get_waveform_width",
        params={},
        request=":WAVeform:WIDTh?",
        response="BYTE",
        parsed="BYTE",
        source=f"{MODERN_GUIDE} p.754",
        mock_kwargs={"idn": MODERN_IDN},
        note="Mock's default width is 'BYTE' (COMM_TYPE=0), matching the guide's own 'Default value is 0' note on COMM_TYPE (p.755).",
    ),
    WireForm(
        table="scope",
        dialect="modern",
        op="get_waveform_maxpoint",
        params={},
        request=":WAVeform:MAXPoint?",
        response="10000000",
        parsed=10000000,
        source=f"{MODERN_GUIDE} p.753",
        mock_kwargs={"idn": MODERN_IDN},
        note=(
            "Task 19: query-only leaf (the guide's own entry for MAXPoint has no "
            "COMMAND SYNTAX section, unlike WIDTh/POINt/etc. above -- there is no "
            "set form). Mock's default max_points (10000000) is the guide's own "
            "EXAMPLE response verbatim ('the following return the maximum points "
            "of one piece in SDS2000X Plus series' -> '10000000'), not an "
            "arbitrary mock value."
        ),
    ),
    # -- Waveform transfer-parameter scalars (Task 17, audit H9) --
    # :WAVeform:SOURce/STARt/INTerval/POINt (guide pp.749-752): the documented
    # modern scalar transfer-parameter commands that configure the
    # :WAVeform:DATA?/:WAVeform:PREamble? transfer (see the VERIFIED entries
    # above -- Task 18 rewired the capture path onto them). Response
    # values below are the mock's fresh-connection defaults (no prior write),
    # matching how test_mock_answers_documented_response exercises every
    # RESPONSE_FORMS entry: it queries a brand-new MockConnection built from
    # `mock_kwargs` alone, never issuing the paired setter first. Each
    # manual EXAMPLE uses a non-default value (C2/1000/200/20000) to
    # demonstrate the round trip; the "divergence is fine, structure is what's
    # pinned" rule already used throughout this sweep (see get_voltage_div,
    # get_sample_rate above) applies identically here. Round-trip fidelity
    # (write the manual's example value, then query it back) was confirmed
    # by hand against MockConnection(idn=MODERN_IDN) for all four ops.
    WireForm(
        table="scope",
        dialect="modern",
        op="set_waveform_source",
        params={"ch": 2},
        request=":WAVeform:SOURce C2",
        source=f"{MODERN_GUIDE} p.749",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    WireForm(
        table="scope",
        dialect="modern",
        op="get_waveform_source",
        params={},
        request=":WAVeform:SOURce?",
        response="C1",
        parsed="C1",
        source=f"{MODERN_GUIDE} p.749",
        mock_kwargs={"idn": MODERN_IDN},
        note="Mock's default source is 'C1' (manual's own EXAMPLE sets 'C2' first); confirmed the round trip separately -- writing ':WAVeform:SOURce C2' then querying ':WAVeform:SOURce?' returns 'C2' verbatim.",
    ),
    WireForm(
        table="scope",
        dialect="modern",
        op="set_waveform_start",
        params={"value": 1000},
        request=":WAVeform:STARt 1000",
        source=f"{MODERN_GUIDE} p.750",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    WireForm(
        table="scope",
        dialect="modern",
        op="get_waveform_start",
        params={},
        request=":WAVeform:STARt?",
        response="0",
        parsed=0,
        source=f"{MODERN_GUIDE} p.750",
        mock_kwargs={"idn": MODERN_IDN},
        note="Mock's default start point is 0 (manual's own EXAMPLE sets 1000 first); round trip confirmed separately -- write ':WAVeform:STARt 1000' then query ':WAVeform:STARt?' returns '1000'.",
    ),
    WireForm(
        table="scope",
        dialect="modern",
        op="set_waveform_interval",
        params={"value": 200},
        request=":WAVeform:INTerval 200",
        source=f"{MODERN_GUIDE} p.751",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    WireForm(
        table="scope",
        dialect="modern",
        op="get_waveform_interval",
        params={},
        request=":WAVeform:INTerval?",
        response="1",
        parsed=1,
        source=f"{MODERN_GUIDE} p.751",
        mock_kwargs={"idn": MODERN_IDN},
        note="Mock's default interval is 1 (manual's own EXAMPLE sets 200 first); round trip confirmed separately -- write ':WAVeform:INTerval 200' then query ':WAVeform:INTerval?' returns '200'.",
    ),
    WireForm(
        table="scope",
        dialect="modern",
        op="set_waveform_point",
        params={"value": 20000},
        request=":WAVeform:POINt 20000",
        source=f"{MODERN_GUIDE} p.752",
        mock_kwargs={"idn": MODERN_IDN},
    ),
    WireForm(
        table="scope",
        dialect="modern",
        op="get_waveform_point",
        params={},
        request=":WAVeform:POINt?",
        response="0",
        parsed=0,
        source=f"{MODERN_GUIDE} p.752",
        mock_kwargs={"idn": MODERN_IDN},
        note="Mock's default point count is 0 (manual's own EXAMPLE sets 20000 first); round trip confirmed separately -- write ':WAVeform:POINt 20000' then query ':WAVeform:POINt?' returns '20000'.",
    ),
    # -- Screen capture --
    # SCDP appears exactly once in this 855-page guide -- as a literal
    # Windows filename ("F:\\SCDP.bmp") inside the "Screen Dump (PRINt)
    # Example" appendix code sample (p.853), never as a command. The Root(:)
    # command actually documented for screen capture is ":PRINt? <type>
    # [,<format>]" (p.33; <type>:={BMP|PNG}, <format>:={NORMal|INVerted}),
    # confirmed by that same appendix example, which sends "PRIN? BMP" (not
    # "SCDP"). screen_capture.py bypasses this command table entirely for
    # BOTH dialects (hardcodes literal "SCDP"/"SCDP?" strings rather than
    # calling get_command("screen_dump", ...) -- same pre-existing observation
    # as the legacy sweep's screen_dump entry), so this MISMATCH_DEFERRED
    # covers both the (dead) table entry and the live runtime path, which
    # sends the same undocumented "SCDP" literal for real modern hardware.
    WireForm(
        table="scope",
        dialect="modern",
        op="screen_dump",
        params={},
        request="SCDP",
        source=f"{MODERN_GUIDE} p.33",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": MODERN_IDN},
        note=(
            "[medium-high severity] 'SCDP' does not exist as a command "
            "anywhere in the modern guide (see module comment above); the "
            "documented command is ':PRINt? <type>[,<format>]' (p.33). The "
            "MODERN_COMMANDS table entry itself is dead (screen_capture.py "
            "never calls get_command('screen_dump', ...)), but the runtime "
            "path it mirrors -- screen_capture.py's _capture_with_scdp(), "
            "which hardcodes 'SCDP' (no '?') for dialect=='modern' -- sends the "
            "identical undocumented literal to real hardware. Already flagged "
            "in code as a known gap (scpi_commands.py comment: 'legacy strings "
            "accepted on modern scopes today; revisit with screen-capture "
            "overhaul'). User-invoked (GUI screenshot button / "
            "ScreenCapture.capture_screenshot()), not an automatic default "
            "path, so not pulled in here; queued for the screen-capture "
            "overhaul this comment already anticipates."
        ),
    ),
    # HCSU appears ZERO times anywhere in this guide -- the legacy
    # HARDCOPY_SETUP command has no modern equivalent under any header. The
    # closest documented concept is :PRINt?'s own <format>:={NORMal|INVerted}
    # (color inversion), a different axis than set_hardcopy_format's
    # LANDSCAPE/PORTRAIT paper orientation -- there is no modern orientation
    # setting at all.
    WireForm(
        table="scope",
        dialect="modern",
        op="set_hardcopy_format",
        params={"format": "LANDSCAPE"},
        request="HCSU DEV,FORMAT,LANDSCAPE",
        source=f"{MODERN_GUIDE} p.33",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": MODERN_IDN},
        note=(
            "[low severity] 'HCSU' is absent from the modern guide entirely "
            "(see module comment above). Request left as the current form. "
            "Dead code: no caller anywhere in the repo invokes "
            "set_hardcopy_format. Queued."
        ),
    ),
    WireForm(
        table="scope",
        dialect="modern",
        op="hardcopy_print",
        params={},
        request="HCSU PRINT",
        source=f"{MODERN_GUIDE} p.33",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"idn": MODERN_IDN},
        note=(
            "[low severity] Same absence as set_hardcopy_format above. The "
            "modern guide's actual print action is folded into ':PRINt?' "
            "itself (a query that both configures and captures in one call) -- "
            "there is no separate 'print'/'save' trigger command as a distinct "
            "step. Dead code: no caller anywhere in the repo invokes "
            "hardcopy_print. Queued."
        ),
    ),
    # --- Siglent SPD power supply: sweep 2026-07-23 (task 5c) -----------------
    # Every command in PSUSCPICommandSet.SIGLENT_SPD_OVERRIDES (27 total),
    # checked against SPD_GUIDE (SPD3303X_QuickStart_QS0503X-E01B.pdf, 45
    # pages -- a Quick Start guide, not a full programming manual; its entire
    # SCPI reference is Chapter 3, pp.36-43). Page citations below are the
    # PDF's own page index (i.e. the page you land on scrolling to "page N"),
    # NOT the printed footer number baked into each page (which runs 8 lower
    # on every page, e.g. footer "28" on PDF p.36) -- this matches how the
    # task-5c brief itself cites SPD pages, unlike the printed-page
    # convention used for the modern-scope EN11G guide above.
    # p.39 EXAMPLE: "CH1: VOLTage 25" -> "CH1:VOLTage 25"; VOLT is the
    # documented abbreviated spelling of VOLTage (p.35, syntax conventions --
    # upper-case letters are the short form).
    WireForm(table="psu", variant="siglent_spd", op="set_voltage", params={"ch": 1, "voltage": 25}, request="CH1:VOLT 25", source=f"{SPD_GUIDE} p.39", mock_kwargs={"psu_mode": True}),
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="get_voltage",
        params={"ch": 1},
        request="CH1:VOLT?",
        response="0.000",
        parsed=0.0,
        source=f"{SPD_GUIDE} p.39",
        mock_kwargs={"psu_mode": True},
        note=(
            "Manual's own worked EXAMPLE: 'CH1: VOLTage?' -> Typical Return "
            "'25.000' (bare, no header). Mock's default channel-1 voltage is "
            "0.0 (not the manual's 25V fixture value) -- same divergence-is-"
            "fine rule as the legacy get_sample_rate entry above; only the "
            "bare-NR2 structure is pinned."
        ),
    ),
    # p.39 EXAMPLE: "CH1:CURRent 0.5"; CURR is the documented abbreviation.
    WireForm(table="psu", variant="siglent_spd", op="set_current", params={"ch": 1, "current": 0.5}, request="CH1:CURR 0.5", source=f"{SPD_GUIDE} p.39", mock_kwargs={"psu_mode": True}),
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="get_current",
        params={"ch": 1},
        request="CH1:CURR?",
        response="0.000",
        parsed=0.0,
        source=f"{SPD_GUIDE} p.39",
        mock_kwargs={"psu_mode": True},
        note="Manual's example returns bare '0.500'; mock's default channel-1 current is 0.0. Structure (bare NR2) is what's pinned, same rule as get_voltage above.",
    ),
    # p.38: MEASure:VOLTage?/CURRent?/POWEr? all take the channel as an
    # ARGUMENT after the query mark ("MEASure:VOLTage? CH1"), not fused to
    # the MEASure keyword. Fixed under Task 6 (audit H6): psu_scpi_commands.py
    # SIGLENT_SPD_OVERRIDES now renders the documented form, and the mock's
    # measurement regexes (connection/mock/base.py) now match the channel as
    # a trailing "CH{n}" argument instead of fused to "MEASure{ch}". Mock's
    # default (no output configured) answer is "0.000" for all three --
    # the manual's Typical Return values (30.000/3.000/90.000) are for a
    # specific setpoint, not the mock's default state.
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="measure_voltage",
        params={"ch": 1},
        request="MEASure:VOLTage? CH1",
        response="0.000",
        parsed=0.0,
        source=f"{SPD_GUIDE} p.38",
        mock_kwargs={"psu_mode": True},
    ),
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="measure_current",
        params={"ch": 1},
        request="MEASure:CURRent? CH1",
        response="0.000",
        parsed=0.0,
        source=f"{SPD_GUIDE} p.38",
        mock_kwargs={"psu_mode": True},
    ),
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="measure_power",
        params={"ch": 1},
        request="MEASure:POWEr? CH1",
        response="0.000",
        parsed=0.0,
        source=f"{SPD_GUIDE} p.38",
        mock_kwargs={"psu_mode": True},
    ),
    # p.40 EXAMPLE: "OUTPut CH1,ON" -- matches exactly.
    WireForm(table="psu", variant="siglent_spd", op="set_output", params={"ch": 1, "state": "ON"}, request="OUTPut CH1,ON", source=f"{SPD_GUIDE} p.40", mock_kwargs={"psu_mode": True}),
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="get_status",
        params={},
        request="SYSTem:STATus?",
        response="0x0224",
        parsed={"ch1_output": False, "ch2_output": True},
        source=f"{SPD_GUIDE} p.41-42",
        status=VERIFIED,
        mock_kwargs={"psu_mode": True, "psu_outputs": {2: {"voltage": 0.0, "current": 0.0, "enabled": True}}},
        note=(
            "Fixed Task 8 (H20): the SPD3303X command list (p.36, Chapter "
            "3.2) has no output-state QUERY at all -- the invented "
            "'OUTPut? CH{ch}' this table used to send does not exist on this "
            "instrument; the OUTPut Subsystem section (p.40) documents only "
            "the setter 'OUTPut {CH1|CH2|CH3},{ON|OFF}'. Output state is "
            "instead read from this bit-encoded 'SYSTem:STATus?' response "
            "('0x0224' is the manual's own Typical Return, p.41), decoded via "
            "the p.42 state-correspondence table: bit 4 = CH1 output, bit 5 "
            "= CH2 output (decode_spd_status() in psu_scpi_commands.py). "
            "power_supply_output.py's 'enabled' property now queries this "
            "instead of the old fictitious per-channel query."
        ),
    ),
    # p.41 EXAMPLE: "TIMEr CH1,ON" -- matches exactly.
    WireForm(table="psu", variant="siglent_spd", op="set_timer_enable", params={"ch": 1, "state": "ON"}, request="TIMEr CH1,ON", source=f"{SPD_GUIDE} p.41", mock_kwargs={"psu_mode": True}),
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="get_timer_enable",
        params={"ch": 1},
        request="TIMEr? CH1",
        source=f"{SPD_GUIDE} p.40-41",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"psu_mode": True},
        note=(
            "[medium-high severity] 'TIMEr {CH1|CH2},{ON|OFF}' (p.41) has no "
            "documented query form at all -- the only query in the TIMEr "
            "subsystem is 'TIMEr:SET? {CH1|CH2},{1|2|3|4|5}' (p.40-41), which "
            "returns a memory group's stored voltage/current/time, not "
            "whether the timer is currently running. 'TIMEr? CH1' is absent "
            "from the manual entirely. Mock's TIMEr? handler "
            "(connection/mock/base.py) was written to answer this same "
            "invented form, not the manual's -- audit theme 2. Reachable: "
            "examples/psu_advanced_features.py reads and writes "
            "'output.timer_enabled' on its default walkthrough path. Queued."
        ),
    ),
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="set_timer_voltage",
        params={"ch": 1, "voltage": 1.0},
        request="TIMEr:VOLT CH1,1.0",
        source=f"{SPD_GUIDE} p.40",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"psu_mode": True},
        note=(
            "[low severity] 'TIMEr:VOLT' does not exist in this manual -- "
            "the only documented way to set a timer group's voltage is "
            "'TIMEr:SET {CH1|CH2},{1|2|3|4|5},<voltage>,<current>,<time>' "
            "(p.40), which sets all three parameters together for one of "
            "five stored memory groups, addressed by group number, not just "
            "a channel. Dead code: no caller anywhere in the repo invokes "
            "set_timer_voltage. Queued."
        ),
    ),
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="get_timer_voltage",
        params={"ch": 1},
        request="TIMEr:VOLT? CH1",
        source=f"{SPD_GUIDE} p.40-41",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"psu_mode": True},
        note=(
            "[low severity] Same absence as set_timer_voltage above; the "
            "documented query is 'TIMEr:SET? {CH1|CH2},{1|2|3|4|5}' (group-"
            "addressed, returns 'voltage,current,time' together, p.41). Dead "
            "code: no caller anywhere in the repo invokes get_timer_voltage. "
            "Queued."
        ),
    ),
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="set_timer_current",
        params={"ch": 1, "current": 1.0},
        request="TIMEr:CURR CH1,1.0",
        source=f"{SPD_GUIDE} p.40",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"psu_mode": True},
        note=(
            "[low severity] Same absence as set_timer_voltage above -- "
            "'TIMEr:CURR' does not exist; current is one field of the "
            "group-addressed 'TIMEr:SET' command. Dead code: no caller "
            "anywhere in the repo invokes set_timer_current. Queued."
        ),
    ),
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="get_timer_current",
        params={"ch": 1},
        request="TIMEr:CURR? CH1",
        source=f"{SPD_GUIDE} p.40-41",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"psu_mode": True},
        note=("[low severity] Same absence as get_timer_voltage above. Dead " "code: no caller anywhere in the repo invokes get_timer_current. " "Queued."),
    ),
    # p.40 EXAMPLE: "OUTPut:WAVE CH1,ON" -- fixed Task 7 (audit H19): the code
    # previously sent 'WAVE CH1,ON', omitting the required 'OUTPut:' prefix.
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="set_wave_enable",
        params={"ch": 1, "state": "ON"},
        request="OUTPut:WAVE CH1,ON",
        source=f"{SPD_GUIDE} p.40",
        mock_kwargs={"psu_mode": True},
    ),
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="get_wave_enable",
        params={"ch": 1},
        request="WAVE? CH1",
        source=f"{SPD_GUIDE} p.40",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"psu_mode": True},
        note=(
            "[medium-high severity] 'OUTPut:WAVE {CH1|CH2},{ON|OFF}' (p.40) "
            "has no documented query form at all (only the setter is "
            "shown). 'WAVE? CH1' is absent from the manual entirely; mock's "
            "WAVE? handler answers the same invented form the code sends. "
            "Reachable: examples/psu_advanced_features.py reads "
            "'output.waveform_enabled' on its default walkthrough path. "
            "Queued."
        ),
    ),
    # WAVE:TYPE / WAVE:FREQ / WAVE:AMPL do not exist anywhere in this manual
    # (zero hits, full-text search) -- the "Waveform display" feature this
    # manual documents (control-panel section 2.9) is a real-time V/I
    # *monitor* (a plotted readback of voltage/current already being drawn),
    # not a signal the PSU generates with a settable type, frequency, or
    # amplitude. This entire six-command "waveform generation" surface in
    # SIGLENT_SPD_OVERRIDES appears to be invented outright; none of the six
    # has a caller anywhere in the repo besides the table itself.
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="set_wave_type",
        params={"ch": 1, "wave_type": "SINE"},
        request="WAVE:TYPE CH1,SINE",
        source=f"{SPD_GUIDE} p.36",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"psu_mode": True},
        note="[low severity] Absent from manual entirely (see module comment above). Dead code: no caller. Queued.",
    ),
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="get_wave_type",
        params={"ch": 1},
        request="WAVE:TYPE? CH1",
        source=f"{SPD_GUIDE} p.36",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"psu_mode": True},
        note="[low severity] Absent from manual entirely. Dead code: no caller. Queued.",
    ),
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="set_wave_freq",
        params={"ch": 1, "frequency": 1000},
        request="WAVE:FREQ CH1,1000",
        source=f"{SPD_GUIDE} p.36",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"psu_mode": True},
        note="[low severity] Absent from manual entirely. Dead code: no caller. Queued.",
    ),
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="get_wave_freq",
        params={"ch": 1},
        request="WAVE:FREQ? CH1",
        source=f"{SPD_GUIDE} p.36",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"psu_mode": True},
        note="[low severity] Absent from manual entirely. Dead code: no caller. Queued.",
    ),
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="set_wave_amplitude",
        params={"ch": 1, "amplitude": 1},
        request="WAVE:AMPL CH1,1",
        source=f"{SPD_GUIDE} p.36",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"psu_mode": True},
        note="[low severity] Absent from manual entirely. Dead code: no caller. Queued.",
    ),
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="get_wave_amplitude",
        params={"ch": 1},
        request="WAVE:AMPL? CH1",
        source=f"{SPD_GUIDE} p.36",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"psu_mode": True},
        note="[low severity] Absent from manual entirely. Dead code: no caller. Queued.",
    ),
    # p.40 EXAMPLE: "OUTPut: TRACK 0" -- <mode>:={0|1|2} is a NUMERIC enum
    # (0=independent, 1=series, 2=parallel per the description). Fixed Task 7
    # (audit H19): psu_scpi_commands.py's get_command() now maps the public
    # word enum (params here is still the word, matching how power_supply.py
    # calls it) to the documented number before formatting.
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="set_tracking",
        params={"mode": "SERIES"},
        request="OUTP:TRACK 1",
        source=f"{SPD_GUIDE} p.40",
        mock_kwargs={"psu_mode": True},
    ),
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="get_tracking",
        params={},
        request="OUTP:TRACK?",
        source=f"{SPD_GUIDE} p.40",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"psu_mode": True},
        note=(
            "[medium-high severity] 'OUTPut:TRACK {0|1|2}' (p.40) has no "
            "documented query form at all -- only the setter is shown. If a "
            "query does exist on real hardware, per the setter's numeric "
            "enum it would presumably also answer numerically, not with the "
            "INDEPENDENT/SERIES/PARALLEL words the mock (and power_supply.py "
            "callers) use. Same root vocabulary issue as set_tracking above. "
            "H19, fix Task 7."
        ),
    ),
    # SENS/SENSE/'remote sens' has zero hits anywhere in this manual --
    # full-text search confirms the SPD3303X has no documented remote-sense
    # (4-wire) command under any header.
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="set_remote_sense",
        params={"ch": 1, "state": "ON"},
        request="SYST:SENS CH1,ON",
        source=f"{SPD_GUIDE} p.36",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"psu_mode": True},
        note="[low severity] Absent from manual entirely (see module comment above; zero hits for 'SENS'). Dead code: no caller. Queued.",
    ),
    WireForm(
        table="psu",
        variant="siglent_spd",
        op="get_remote_sense",
        params={"ch": 1},
        request="SYST:SENS? CH1",
        source=f"{SPD_GUIDE} p.36",
        status=MISMATCH_DEFERRED,
        mock_kwargs={"psu_mode": True},
        note="[low severity] Same absence as set_remote_sense above. Dead code: no caller. Queued.",
    ),
    # --- Siglent SDG function generator: sweep 2026-07-23 (task 5c) -----------
    # Every command in AWGSCPICommandSet.SIGLENT_SDG_OVERRIDES (28 total),
    # checked against SDG_GUIDE (SDG_ProgrammingGuide_PG02-E05B.pdf, 201
    # pages). Page citations are the PDF's own page index, same convention
    # as the SPD section above (this guide's own printed footer runs 12
    # lower, e.g. footer "16" on PDF p.28 -- not used here).
    #
    # Every setter below renders EXACTLY the documented "<channel>:BaSic_WaVe
    # <parameter>,<value>" (or sibling OUTP/ARWV/MDWV/BTWV/SWWV) form -- the
    # driver's SET side of this table is correct. The recurring defect was
    # entirely on the GET side: every "get_*" entry for the parameterized
    # subsystems (BSWV/OUTP/ARWV/MDWV/BTWV/SWWV) sent an invented
    # "<channel>:<CMD>? <PARAM>" selector-style query (e.g. 'C1:BSWV? FRQ').
    # H5, fixed Task 10: every SIGLENT_SDG_OVERRIDES get_* template now
    # renders the bare query below. BSWV/OUTP/ARWV also got a real parser
    # (`parse_key_value_response`, awg_scpi_commands.py) and, where an
    # awg_output.py property exists, a getter that reads its own field out of
    # the whole-list response -- those entries are VERIFIED with a response.
    # MDWV/BTWV/SWWV are "future expansion": no Python getter, mock handler,
    # or parser exists anywhere for them, so only the request was fixed; they
    # stay VERIFIED with response=None (request-only) rather than inventing
    # code nothing exercises.
    #
    # None of these command families documents a selector query anywhere in
    # this guide -- every QUERY SYNTAX is bare ("<channel>:BaSic_WaVe?",
    # "<channel>:ARbWaVe?", etc.) and its RESPONSE FORMAT always returns
    # EVERY parameter of the subsystem in one comma-joined reply. H5, fix
    # Task 10.
    # p.31 EXAMPLE: "Change the waveform type of C1 to Ramp: C1:BSWV WVTP,RAMP".
    WireForm(table="awg", variant="siglent_sdg", op="set_function", params={"ch": 1, "function": "RAMP"}, request="C1:BSWV WVTP,RAMP", source=f"{SDG_GUIDE} p.31", mock_kwargs={"awg_mode": True}),
    WireForm(
        table="awg",
        variant="siglent_sdg",
        op="get_function",
        params={"ch": 1},
        request="C1:BSWV?",
        response="C1:BSWV WVTP,SINE,FRQ,1000HZ,PERI,0.001S,AMP,1V,OFST,0V,HLEV,0.5V,LLEV,-0.5V,PHSE,0",
        parsed="SINE",
        source=f"{SDG_GUIDE} p.31",
        mock_kwargs={"awg_mode": True},
        note=(
            "H5 fixed (Task 10). QUERY SYNTAX '<channel>:BSWV?' is bare "
            "(p.31) -- the 'C1:BSWV? WVTP' selector this entry used to "
            "record was invented. RESPONSE FORMAT is function-conditional "
            "('<parameter> := {All the parameters of the current basic "
            "waveform}') -- the p.31 worked SINE example is "
            "WVTP,FRQ,PERI,AMP,OFST,HLEV,LLEV,PHSE with no DUTY/SYM (those "
            "are only settable for SQUARE/PULSE and RAMP respectively, "
            "p.29-30), transcribed above verbatim for the default SINE "
            "channel. Fix wave 1 follow-up: the mock used to always emit "
            "DUTY,SYM and never HLEV,LLEV -- a shape the manual never shows "
            "for a SINE. The driver now parses this via "
            "'parse_key_value_response' and pulls out its own field "
            "(awg_output.py's '_read_basic_wave'). (Root pattern for every "
            "'get_*' BSWV/OUTP/ARWV entry below.)"
        ),
    ),
    # p.31 EXAMPLE: "Change the frequency of C1 to 2000 Hz: C1:BSWV FRQ,2000".
    WireForm(table="awg", variant="siglent_sdg", op="set_frequency", params={"ch": 1, "frequency": 2000}, request="C1:BSWV FRQ,2000", source=f"{SDG_GUIDE} p.31", mock_kwargs={"awg_mode": True}),
    WireForm(
        table="awg",
        variant="siglent_sdg",
        op="get_frequency",
        params={"ch": 1},
        request="C1:BSWV?",
        response="C1:BSWV WVTP,SINE,FRQ,1000HZ,PERI,0.001S,AMP,1V,OFST,0V,HLEV,0.5V,LLEV,-0.5V,PHSE,0",
        parsed=1000.0,
        source=f"{SDG_GUIDE} p.31",
        mock_kwargs={"awg_mode": True},
        note=("H5 fixed (Task 10). Same bare-query fix as get_function above ('C1:BSWV? FRQ' -> 'C1:BSWV?'); FRQ pulled out of the same whole-list response."),
    ),
    # p.31 EXAMPLE: "Set the amplitude of C1 to 3 Vpp: C1:BSWV AMP,3".
    WireForm(table="awg", variant="siglent_sdg", op="set_amplitude", params={"ch": 1, "amplitude": 3}, request="C1:BSWV AMP,3", source=f"{SDG_GUIDE} p.31", mock_kwargs={"awg_mode": True}),
    WireForm(
        table="awg",
        variant="siglent_sdg",
        op="get_amplitude",
        params={"ch": 1},
        request="C1:BSWV?",
        response="C1:BSWV WVTP,SINE,FRQ,1000HZ,PERI,0.001S,AMP,1V,OFST,0V,HLEV,0.5V,LLEV,-0.5V,PHSE,0",
        parsed=1.0,
        source=f"{SDG_GUIDE} p.31",
        mock_kwargs={"awg_mode": True},
        note=("H5 fixed (Task 10). Same bare-query fix as get_function above ('C1:BSWV? AMP' -> 'C1:BSWV?'); AMP pulled out of the same whole-list response."),
    ),
    # p.30 parameter table: "OFST <offset> := offset. The unit is volts 'V'.";
    # general COMMAND SYNTAX '<channel>:BaSic_WaVe <parameter>,<value>'
    # (p.29) instantiated with the documented OFST keyword; field spelling
    # confirmed by the get_function response example above ("...OFST,0V...").
    WireForm(table="awg", variant="siglent_sdg", op="set_offset", params={"ch": 1, "offset": 0.5}, request="C1:BSWV OFST,0.5", source=f"{SDG_GUIDE} p.29-30, p.31", mock_kwargs={"awg_mode": True}),
    WireForm(
        table="awg",
        variant="siglent_sdg",
        op="get_offset",
        params={"ch": 1},
        request="C1:BSWV?",
        response="C1:BSWV WVTP,SINE,FRQ,1000HZ,PERI,0.001S,AMP,1V,OFST,0V,HLEV,0.5V,LLEV,-0.5V,PHSE,0",
        parsed=0.0,
        source=f"{SDG_GUIDE} p.31",
        mock_kwargs={"awg_mode": True},
        note=("H5 fixed (Task 10). Same bare-query fix as get_function above ('C1:BSWV? OFST' -> 'C1:BSWV?'); OFST pulled out of the same whole-list response."),
    ),
    # p.30 parameter table: "PHSE <phase> := {0 to 360}. The unit is 'degree'.";
    # same general-syntax instantiation as set_offset above; field spelling
    # confirmed by the get_function response example ("...PHSE,0").
    WireForm(table="awg", variant="siglent_sdg", op="set_phase", params={"ch": 1, "phase": 90}, request="C1:BSWV PHSE,90", source=f"{SDG_GUIDE} p.29-30, p.31", mock_kwargs={"awg_mode": True}),
    WireForm(
        table="awg",
        variant="siglent_sdg",
        op="get_phase",
        params={"ch": 1},
        request="C1:BSWV?",
        response="C1:BSWV WVTP,SINE,FRQ,1000HZ,PERI,0.001S,AMP,1V,OFST,0V,HLEV,0.5V,LLEV,-0.5V,PHSE,0",
        parsed=0.0,
        source=f"{SDG_GUIDE} p.31",
        mock_kwargs={"awg_mode": True},
        note=("H5 fixed (Task 10). Same bare-query fix as get_function above ('C1:BSWV? PHSE' -> 'C1:BSWV?'); PHSE pulled out of the same whole-list response."),
    ),
    # p.30 parameter table: "DUTY <duty> := {0 to 100}. ... Only settable "
    # "when WVTP is SQUARE or PULSE."; same general-syntax instantiation.
    WireForm(table="awg", variant="siglent_sdg", op="set_pulse_duty", params={"ch": 1, "duty": 25}, request="C1:BSWV DUTY,25", source=f"{SDG_GUIDE} p.29-30", mock_kwargs={"awg_mode": True}),
    WireForm(
        table="awg",
        variant="siglent_sdg",
        op="get_pulse_duty",
        params={"ch": 1},
        request="C1:BSWV?",
        response="C1:BSWV WVTP,PULSE,FRQ,1000HZ,PERI,0.001S,AMP,1V,OFST,0V,HLEV,0.5V,LLEV,-0.5V,PHSE,0,DUTY,50",
        parsed=50.0,
        source=f"{SDG_GUIDE} p.31, p.29",
        mock_kwargs={
            "awg_mode": True,
            "awg_channels": {1: {"function": "PULSE", "frequency": 1000.0, "amplitude": 1.0, "offset": 0.0, "phase": 0.0, "enabled": False, "pulse_duty": 50.0, "ramp_symmetry": 50.0}},
        },
        note=(
            "H5 fixed (Task 10); fix wave 1 follow-up. Same bare-query fix "
            "as get_function above ('C1:BSWV? DUTY' -> 'C1:BSWV?'). DUTY is "
            "'Only settable when WVTP is SQUARE or PULSE' (p.29 parameter "
            "table) -- it does NOT appear in the p.31 SINE example, so the "
            "channel is configured PULSE via mock_kwargs to get a response "
            "shape the manual actually documents as containing DUTY. On the "
            "default SINE channel this getter now honestly raises "
            "CommandError (no DUTY field), matching real hardware."
        ),
    ),
    # p.29-30 parameter table: "SYM <symmetry> := {0 to 100}. Symmetry of "
    # "RAMP. ... Only settable when WVTP is RAMP."; same general-syntax
    # instantiation.
    WireForm(table="awg", variant="siglent_sdg", op="set_ramp_symmetry", params={"ch": 1, "symmetry": 50}, request="C1:BSWV SYM,50", source=f"{SDG_GUIDE} p.29-30", mock_kwargs={"awg_mode": True}),
    WireForm(
        table="awg",
        variant="siglent_sdg",
        op="get_ramp_symmetry",
        params={"ch": 1},
        request="C1:BSWV?",
        response="C1:BSWV WVTP,RAMP,FRQ,1000HZ,PERI,0.001S,AMP,1V,OFST,0V,HLEV,0.5V,LLEV,-0.5V,PHSE,0,SYM,50",
        parsed=50.0,
        source=f"{SDG_GUIDE} p.31, p.30",
        mock_kwargs={
            "awg_mode": True,
            "awg_channels": {1: {"function": "RAMP", "frequency": 1000.0, "amplitude": 1.0, "offset": 0.0, "phase": 0.0, "enabled": False, "pulse_duty": 50.0, "ramp_symmetry": 50.0}},
        },
        note=(
            "H5 fixed (Task 10); fix wave 1 follow-up. Same bare-query fix "
            "as get_function above ('C1:BSWV? SYM' -> 'C1:BSWV?'). SYM is "
            "'Symmetry of RAMP ... Only settable when WVTP is RAMP' (p.30 "
            "parameter table) -- it does NOT appear in the p.31 SINE "
            "example, so the channel is configured RAMP via mock_kwargs to "
            "get a response shape the manual actually documents as "
            "containing SYM. On the default SINE channel this getter now "
            "honestly raises CommandError (no SYM field), matching real "
            "hardware."
        ),
    ),
    # p.27 COMMAND SYNTAX: "<channel>:OUTPut ON|OFF,LOAD,<load>,PLRT,
    # <polarity>" -- but its own worked EXAMPLEs (p.28) show each field is
    # independently settable: "C1:OUTP ON" (bare state), "C1:OUTP LOAD,50",
    # "C1:OUTP PLRT,NOR".
    WireForm(table="awg", variant="siglent_sdg", op="set_output", params={"ch": 1, "state": "ON"}, request="C1:OUTP ON", source=f"{SDG_GUIDE} p.28", mock_kwargs={"awg_mode": True}),
    WireForm(
        table="awg",
        variant="siglent_sdg",
        op="get_output",
        params={"ch": 1},
        request="C1:OUTP?",
        response="C1:OUTP ON,LOAD,HZ,PLRT,NOR",
        parsed=True,
        source=f"{SDG_GUIDE} p.27-28",
        mock_kwargs={
            "awg_mode": True,
            "awg_channels": {1: {"function": "SINE", "frequency": 1000.0, "amplitude": 1.0, "offset": 0.0, "phase": 0.0, "enabled": True, "pulse_duty": 50.0, "ramp_symmetry": 50.0}},
        },
        note=(
            "H5 fixed (Task 10). REQUEST already matched the manual "
            "('<channel>:OUTPut?' is bare, p.27) -- the fix was the mock, "
            "which used to answer bare 'ON'/'OFF' instead of the documented "
            "'ON|OFF,LOAD,<load>,PLRT,<polarity>' worked EXAMPLE (p.27-28, "
            "transcribed above; channel state overridden to enabled=True so "
            "the mock reproduces this exact literal example). "
            "awg_output.py's 'enabled' property now parses via "
            '\'parse_key_value_response(response)["STATE"] == "ON"\'.'
        ),
    ),
    # p.28 EXAMPLE: "Set the load of CH1 to 50 ohms: C1:OUTP LOAD,50" --
    # matches exactly. Not mocked (no LOAD handler in connection/mock/base.py).
    WireForm(table="awg", variant="siglent_sdg", op="set_output_load", params={"ch": 1, "load": 50}, request="C1:OUTP LOAD,50", source=f"{SDG_GUIDE} p.28", mock_kwargs={"awg_mode": True}),
    WireForm(
        table="awg",
        variant="siglent_sdg",
        op="get_output_load",
        params={"ch": 1},
        request="C1:OUTP?",
        response="C1:OUTP ON,LOAD,HZ,PLRT,NOR",
        parsed="HZ",
        source=f"{SDG_GUIDE} p.27-28",
        mock_kwargs={
            "awg_mode": True,
            "awg_channels": {1: {"function": "SINE", "frequency": 1000.0, "amplitude": 1.0, "offset": 0.0, "phase": 0.0, "enabled": True, "pulse_duty": 50.0, "ramp_symmetry": 50.0}},
        },
        note=(
            "H5 fixed (Task 10). Same bare-query fix as get_output above "
            "('C1:OUTP? LOAD' -> 'C1:OUTP?'); there is no way to query just "
            "the load value, only the bare '<channel>:OUTPut?' returning ALL "
            "fields. Dead code: no caller anywhere in the repo invokes "
            "get_output_load -- there is no awg_output.py property to update, "
            "so this entry is verified at the command-table/mock level only."
        ),
    ),
    # p.28 EXAMPLE: "Set the polarity of CH1 to normal: C1:OUTP PLRT,NOR" --
    # matches exactly. Not mocked, dead code (no caller anywhere).
    WireForm(table="awg", variant="siglent_sdg", op="set_output_polarity", params={"ch": 1, "polarity": "NOR"}, request="C1:OUTP PLRT,NOR", source=f"{SDG_GUIDE} p.28", mock_kwargs={"awg_mode": True}),
    WireForm(
        table="awg",
        variant="siglent_sdg",
        op="get_output_polarity",
        params={"ch": 1},
        request="C1:OUTP?",
        response="C1:OUTP ON,LOAD,HZ,PLRT,NOR",
        parsed="NOR",
        source=f"{SDG_GUIDE} p.27-28",
        mock_kwargs={
            "awg_mode": True,
            "awg_channels": {1: {"function": "SINE", "frequency": 1000.0, "amplitude": 1.0, "offset": 0.0, "phase": 0.0, "enabled": True, "pulse_duty": 50.0, "ramp_symmetry": 50.0}},
        },
        note=(
            "H5 fixed (Task 10). Same bare-query fix as get_output_load "
            "above ('C1:OUTP? PLRT' -> 'C1:OUTP?'). Dead code: no caller "
            "anywhere in the repo invokes get_output_polarity -- there is no "
            "awg_output.py property to update, so this entry is verified at "
            "the command-table/mock level only."
        ),
    ),
    # p.62 Format2: "<channel>:ArbWaVe NAME,<name>"; the unquoted rendering
    # matches this guide's own Python code-sample appendix exactly (p.188:
    # dev.write("C1:ARWV NAME,wave1")) rather than the inline prose EXAMPLE's
    # quoted form (C1:ARWV NAME,"wave_1") -- both are the same documented
    # command, just with/without quotes around the name literal. Not mocked
    # (no ARWV handler), dead code (no caller anywhere in the repo).
    WireForm(
        table="awg", variant="siglent_sdg", op="set_arb_waveform", params={"ch": 1, "name": "wave1"}, request="C1:ARWV NAME,wave1", source=f"{SDG_GUIDE} p.62, p.188", mock_kwargs={"awg_mode": True}
    ),
    WireForm(
        table="awg",
        variant="siglent_sdg",
        op="get_arb_waveform",
        params={"ch": 1},
        request="C1:ARWV?",
        response="C1:ARWV INDEX,2,NAME,StairUp",
        parsed="StairUp",
        source=f"{SDG_GUIDE} p.62",
        mock_kwargs={"awg_mode": True},
        note=(
            "H5 fixed (Task 10). QUERY SYNTAX is bare '<channel>:ARbWaVe?' "
            "(p.62) -- the 'C1:ARWV? NAME' selector this entry used to "
            "record was invented. RESPONSE FORMAT always returns BOTH "
            "'INDEX,<index>,NAME,<name>' together (worked EXAMPLE "
            "transcribed above); connection/mock/base.py now answers this "
            "statically since arb waveform selection isn't tracked in "
            "awg_channels state. Dead code: no caller anywhere in the repo "
            "invokes get_arb_waveform -- there is no awg_output.py property "
            "to update, so this entry is verified at the command-table/mock "
            "level only."
        ),
    ),
    # p.36 EXAMPLE: "Set CH1 modulation state to on: C1:MDWV STATE,ON" --
    # matches exactly. Not mocked, dead code (no caller anywhere).
    WireForm(table="awg", variant="siglent_sdg", op="set_modulation", params={"ch": 1, "state": "ON"}, request="C1:MDWV STATE,ON", source=f"{SDG_GUIDE} p.33, p.36", mock_kwargs={"awg_mode": True}),
    WireForm(
        table="awg",
        variant="siglent_sdg",
        op="get_modulation",
        params={"ch": 1},
        request="C1:MDWV?",
        response=None,
        source=f"{SDG_GUIDE} p.36",
        mock_kwargs={"awg_mode": True},
        note=(
            "H5 fixed (Task 10) for the request only: QUERY SYNTAX is bare "
            "'<channel>:MoDulateWaVe?' (p.36) -- the 'C1:MDWV? STATE' "
            "selector this entry used to record was invented. Future-"
            "expansion command; no Python getter/mock/parser wired yet "
            "(no caller anywhere in the repo invokes get_modulation, and "
            "there is no MDWV handler in connection/mock/base.py), so this "
            "stays request-only rather than inventing a parser or mock "
            "response for code nothing exercises."
        ),
    ),
    # p.59-60 EXAMPLE: "Set CH1 burst state to ON C1:BTWV STATE,ON" --
    # matches exactly. Not mocked, dead code (no caller anywhere).
    WireForm(table="awg", variant="siglent_sdg", op="set_burst_state", params={"ch": 1, "state": "ON"}, request="C1:BTWV STATE,ON", source=f"{SDG_GUIDE} p.59-60", mock_kwargs={"awg_mode": True}),
    WireForm(
        table="awg",
        variant="siglent_sdg",
        op="get_burst_state",
        params={"ch": 1},
        request="C1:BTWV?",
        response=None,
        source=f"{SDG_GUIDE} p.60",
        mock_kwargs={"awg_mode": True},
        note=(
            "H5 fixed (Task 10) for the request only: QUERY SYNTAX is bare "
            "'<channel>:BTWV(BursTWaVe)?' (p.60) -- the 'C1:BTWV? STATE' "
            "selector this entry used to record was invented. Future-"
            "expansion command; no Python getter/mock/parser wired yet "
            "(no caller anywhere in the repo invokes get_burst_state, and "
            "there is no BTWV handler in connection/mock/base.py), so this "
            "stays request-only rather than inventing a parser or mock "
            "response for code nothing exercises."
        ),
    ),
    # p.37, p.39 EXAMPLE: "Set CH1 sweep state to ON: C1:SWWV STATE,ON" --
    # matches exactly. Not mocked, dead code (no caller anywhere).
    WireForm(table="awg", variant="siglent_sdg", op="set_sweep_state", params={"ch": 1, "state": "ON"}, request="C1:SWWV STATE,ON", source=f"{SDG_GUIDE} p.37, p.39", mock_kwargs={"awg_mode": True}),
    WireForm(
        table="awg",
        variant="siglent_sdg",
        op="get_sweep_state",
        params={"ch": 1},
        request="C1:SWWV?",
        response=None,
        source=f"{SDG_GUIDE} p.38",
        mock_kwargs={"awg_mode": True},
        note=(
            "H5 fixed (Task 10) for the request only: QUERY SYNTAX is bare "
            "'<channel>:SWeepWaVe?' (p.38) -- the 'C1:SWWV? STATE' selector "
            "this entry used to record was invented. Future-expansion "
            "command; no Python getter/mock/parser wired yet (no caller "
            "anywhere in the repo invokes get_sweep_state, and there is no "
            "SWWV handler in connection/mock/base.py), so this stays "
            "request-only rather than inventing a parser or mock response "
            "for code nothing exercises."
        ),
    ),
]
