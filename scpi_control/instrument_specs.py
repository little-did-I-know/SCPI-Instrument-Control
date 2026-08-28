"""Pluggable per-instrument measurement-accuracy formulas.

Ships with an empty registry. This repo does not fabricate accuracy numbers
it hasn't verified against a real datasheet (see AUDIT.md C1/C2 for what
happens when it did, historically, for other computed metrics) -- only
programming guides, not datasheets, are downloaded in docs/. Populate real
entries via `register_accuracy_spec` once you have a real datasheet citation.
"""

from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

from scpi_control.exceptions import InvalidParameterError


@dataclass(frozen=True)
class AccuracySpec:
    """One documented accuracy formula.

    e.g. "+/-(3% of reading + 0.5% of full scale)" becomes
    `lambda reading, full_scale: abs(reading) * 0.03 + full_scale * 0.005`.

    Attributes:
        formula: (reading, full_scale) -> absolute uncertainty, in the
            reading's own unit.
        source: Where this formula came from -- required, not optional, so
            an entry cannot be registered without a citation (e.g.
            "SDS824X HD datasheet DS0503X-E01B, p.4, vertical accuracy
            table").
    """

    formula: Callable[[float, float], float]
    source: str


_REGISTRY: Dict[Tuple[str, str, str], AccuracySpec] = {}


def register_accuracy_spec(manufacturer: str, model: str, measurement_type: str, spec: AccuracySpec) -> None:
    """Register a real, cited accuracy formula for one instrument + measurement type."""
    if not spec.source.strip():
        raise InvalidParameterError("AccuracySpec.source must cite where the formula came from, not be empty")
    _REGISTRY[(manufacturer, model, measurement_type)] = spec


def lookup_accuracy_spec(manufacturer: str, model: str, measurement_type: str) -> Optional[AccuracySpec]:
    """The registered spec, or None if nothing is on file -- never a guess."""
    return _REGISTRY.get((manufacturer, model, measurement_type))
