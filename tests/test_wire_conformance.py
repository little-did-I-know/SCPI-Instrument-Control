"""Conformance: driver and mock are each checked against the vendor manual.

The point of this module is that NOTHING here compares the driver to the mock.
Both are compared to a transcription of the manual, so they cannot co-validate
an invented command the way they did before 2026-07-23 (audit theme 2).
"""

import pytest

from scpi_control.awg_scpi_commands import AWGSCPICommandSet
from scpi_control.connection.mock import MockConnection
from scpi_control.daq_scpi_commands import DAQSCPICommandSet
from scpi_control.psu_scpi_commands import PSUSCPICommandSet
from scpi_control.scpi_commands import SCPICommandSet
from tests.wire_forms import MISMATCH_DEFERRED, UNCITED, VERIFIED, WIRE_FORMS


def command_set_for(wf):
    """Return the command set that owns `wf.op`."""
    if wf.table == "scope":
        return SCPICommandSet(wf.dialect, wf.variant)
    if wf.table == "psu":
        return PSUSCPICommandSet(wf.variant)
    if wf.table == "awg":
        return AWGSCPICommandSet(wf.variant)
    if wf.table == "daq":
        return DAQSCPICommandSet(wf.variant)
    raise ValueError(f"unknown table {wf.table!r}")


def _ident(wf):
    return f"{wf.table}:{wf.dialect}:{wf.op}"


VERIFIED_FORMS = [wf for wf in WIRE_FORMS if wf.status == VERIFIED]
RESPONSE_FORMS = [wf for wf in VERIFIED_FORMS if wf.response is not None]


@pytest.mark.parametrize("wf", VERIFIED_FORMS, ids=[_ident(wf) for wf in VERIFIED_FORMS])
def test_driver_renders_documented_request(wf):
    """The command table must produce exactly what the manual documents."""
    rendered = command_set_for(wf).get_command(wf.op, **wf.params)
    assert rendered == wf.request, f"{_ident(wf)}: manual says {wf.request!r} ({wf.source})"


@pytest.mark.parametrize("wf", RESPONSE_FORMS, ids=[_ident(wf) for wf in RESPONSE_FORMS])
def test_mock_answers_documented_response(wf):
    """The mock must answer exactly what the manual documents."""
    conn = MockConnection(**wf.mock_kwargs)
    conn.connect()
    assert conn.query(wf.request) == wf.response, f"{_ident(wf)}: manual says {wf.response!r} ({wf.source})"


def test_every_entry_cites_a_source():
    """An entry with no citation is an assumption wearing a test's clothes."""
    for wf in WIRE_FORMS:
        if wf.status == UNCITED:
            assert wf.note, f"{_ident(wf)}: UNCITED entries must say why in `note`"
        else:
            assert " p." in wf.source, f"{_ident(wf)}: source must name document and page, got {wf.source!r}"


def test_deferred_entries_explain_themselves():
    """MISMATCH_DEFERRED without a reason becomes invisible debt."""
    for wf in WIRE_FORMS:
        if wf.status == MISMATCH_DEFERRED:
            assert wf.note, f"{_ident(wf)}: deferred entries must record the audit ID and why"


COVERED_TABLES = {
    ("scope", "legacy"): SCPICommandSet("legacy").LEGACY_COMMANDS,
    ("scope", "modern"): SCPICommandSet("modern").MODERN_COMMANDS,
    ("psu", "siglent_spd"): PSUSCPICommandSet("siglent_spd").SIGLENT_SPD_OVERRIDES,
    ("awg", "siglent_sdg"): AWGSCPICommandSet("siglent_sdg").SIGLENT_SDG_OVERRIDES,
}


@pytest.mark.parametrize("key", sorted(COVERED_TABLES, key=str), ids=str)
def test_every_command_has_a_corpus_entry(key):
    """A new command with no citation must fail the suite.

    This is the recurrence prevention. Audit theme 2 appeared in the 2026-07-13
    audit, was not fixed, and reappeared on 2026-07-22 -- because nothing forced
    a new wire form to justify itself.
    """
    table, variant_or_dialect = key
    documented = {
        wf.op
        for wf in WIRE_FORMS
        if wf.table == table and (wf.dialect == variant_or_dialect or wf.variant == variant_or_dialect)
    }
    missing = sorted(set(COVERED_TABLES[key]) - documented)
    assert not missing, (
        f"{table}/{variant_or_dialect}: no corpus entry for {missing}. "
        f"Add one citing the manual, or mark it UNCITED with a reason."
    )
