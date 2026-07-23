"""Documented SCPI request/response pairs, transcribed from vendor programming guides.

Every entry is a verbatim transcription of an EXAMPLE block in a vendor manual.
The manuals are NOT committed (see docs/development/vendor-manuals.md for sources
and .git/info/exclude for why), so `source` must always name document and page.

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
]
