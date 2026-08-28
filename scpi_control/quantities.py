"""Unit-aware quantities with optional measurement uncertainty.

Wraps `pint` (dimensional analysis: a Quantity carries its unit, and
mismatched-dimension arithmetic raises instead of silently producing a
meaningless number) and `uncertainties` (a `ufloat` magnitude propagates
value +/- error correctly through arithmetic). One module-level
UnitRegistry -- pint's own documentation is explicit that Quantity objects
from two different registries compare unequal to each other, so every
Quantity in this codebase must come from THIS registry, via `quantity()`.

Optional dependency: requires the `uncertainty` extra
(`pip install "SCPI-Instrument-Control[uncertainty]"`). Nothing else in this
package imports this module at top level -- every caller does a local
import, so installing scpi_control (or even scpi_control[report-generator])
does not pull in pint/uncertainties unless uncertainty features are
actually used.
"""

from typing import Optional

try:
    import pint
    from uncertainties import ufloat
except ImportError:
    raise ImportError("pint and uncertainties are required for measurement-uncertainty support. " 'Install with: pip install "SCPI-Instrument-Control[uncertainty]"')

_REGISTRY = pint.UnitRegistry()
Quantity = _REGISTRY.Quantity


def quantity(value: float, unit: str, uncertainty: Optional[float] = None) -> Quantity:
    """Build a Quantity, optionally carrying a symmetric 1-sigma uncertainty.

    Args:
        value: The nominal value, in `unit`.
        unit: A pint-recognized unit string, e.g. "V", "Hz", "s", "percent".
        uncertainty: 1-sigma uncertainty in the same `unit`, or None for an
            exact/unmeasured-spread value.

    Returns:
        A Quantity whose magnitude is a plain float (no uncertainty given)
        or an `uncertainties.ufloat` (uncertainty given).
    """
    magnitude = ufloat(value, uncertainty) if uncertainty is not None else value
    return _REGISTRY.Quantity(magnitude, unit)


def format_quantity(q: Quantity, precision: int = 3) -> str:
    """'1.23 +/- 0.012 V' (compact SI prefix) or '3 V' with no uncertainty.

    Args:
        q: A Quantity built by `quantity()`.
        precision: Significant figures for both the nominal value and the
            uncertainty (independently -- matches how each is individually
            meaningful, not a shared decimal-place count).
    """
    magnitude = q.magnitude
    if hasattr(magnitude, "nominal_value"):
        # pint's to_compact() internally does an implicit float() conversion
        # to pick a scale, which `uncertainties` deliberately forbids on a
        # ufloat. Compact using the plain nominal value only, then convert
        # the std_dev into whatever unit that picked -- never hand a ufloat
        # magnitude to to_compact() itself.
        nominal_compact = _REGISTRY.Quantity(magnitude.nominal_value, q.units).to_compact()
        unit_str = format(nominal_compact.units, "~")
        std_dev_converted = _REGISTRY.Quantity(magnitude.std_dev, q.units).to(nominal_compact.units)
        return f"{nominal_compact.magnitude:.{precision}g} ± {std_dev_converted.magnitude:.{precision}g} {unit_str}"
    compact = q.to_compact()
    unit_str = format(compact.units, "~")
    return f"{compact.magnitude:.{precision}g} {unit_str}"
