"""Pluggable instrument accuracy-spec registry.

Ships with zero populated entries by design (see the design spec's
Non-goals -- only programming guides, not datasheets, are in this repo, and
this project does not fabricate accuracy numbers). This tests the plumbing:
register, look up, and the "no spec on file" honest-None path.

Pure-CPU. No pint/uncertainties dependency -- this module doesn't need them.
"""

import pytest

from scpi_control.exceptions import InvalidParameterError
from scpi_control.instrument_specs import AccuracySpec, lookup_accuracy_spec, register_accuracy_spec


def test_lookup_with_no_registered_spec_returns_none():
    assert lookup_accuracy_spec("Nonexistent Co", "Model X", "voltage") is None


def test_register_and_look_up_round_trip():
    spec = AccuracySpec(
        formula=lambda reading, full_scale: abs(reading) * 0.03 + full_scale * 0.005,
        source="Test Datasheet p.1, vertical accuracy table",
    )
    register_accuracy_spec("Siglent", "SDS824X HD", "voltage", spec)
    try:
        found = lookup_accuracy_spec("Siglent", "SDS824X HD", "voltage")
        assert found is spec
        assert found.formula(1.0, 10.0) == pytest.approx(0.08)
    finally:
        # Test isolation: the registry is module-level global state.
        from scpi_control import instrument_specs

        instrument_specs._REGISTRY.pop(("Siglent", "SDS824X HD", "voltage"), None)


def test_accuracy_spec_requires_a_source():
    with pytest.raises(TypeError):
        AccuracySpec(formula=lambda reading, full_scale: 0.0)  # missing required `source`


def test_register_rejects_an_empty_source():
    spec = AccuracySpec(formula=lambda reading, full_scale: 0.0, source="")
    with pytest.raises(InvalidParameterError):
        register_accuracy_spec("Siglent", "SDS824X HD", "voltage", spec)
