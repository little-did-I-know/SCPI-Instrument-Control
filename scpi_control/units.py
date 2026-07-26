"""Parse human-written SI quantity strings into floats.

`batch_capture` documents its scales as strings ("1us", "500mV") and its own
example copies them verbatim, but applied them unparsed -- so the documented
call raised TypeError. This module is that parser.

Deliberately separate from `waveform._SI_MAGNITUDES`, which decodes magnitude
letters in legacy Siglent *instrument responses* (K/M/G, upper case, no small
prefixes -- RC01020-E01C p.117). This one parses *user input*, where "m" is
milli and "M" is mega. Two grammars that happen to share three letters; merging
them would make one of the two wrong.
"""

import re
from decimal import Decimal, InvalidOperation
from typing import Union

from scpi_control import exceptions

# Decimal EXPONENTS, not float multipliers. Multiplying by a float scale is not
# correctly rounded -- float("10") * 1e-6 is 9.999999999999999e-06, while the
# literal 10e-6 is 1e-05 -- and the difference reaches the wire, because the
# parsed value is formatted straight into a SCPI command. Shifting the decimal
# exponent and converting once gives the canonical float.
#
# Case-SENSITIVE on purpose: "m" is milli, "M" is mega. A case-insensitive table
# turns a 1 mV scale into a 1 MV scale with no error at all. "K" is accepted
# alongside "k" because instrument front panels commonly print it that way;
# there is no conflicting lower-case meaning to lose.
_PREFIX_EXPONENTS = {
    "f": -15,
    "p": -12,
    "n": -9,
    "u": -6,
    "µ": -6,  # U+00B5 MICRO SIGN
    "μ": -6,  # U+03BC GREEK SMALL LETTER MU -- both appear in the wild
    "m": -3,
    "k": 3,
    "K": 3,
    "M": 6,
    "G": 9,
}

# Leading number (with optional sign and exponent), then optional whitespace,
# then whatever suffix remains. The suffix is NOT anchored to a known unit --
# see the module note on why units are unvalidated.
_QUANTITY = re.compile(r"^\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)\s*(\S*)\s*$")


def parse_si_value(value: Union[str, float], quantity: str) -> float:
    """Convert an SI quantity string (or a plain number) to a float.

    Args:
        value: "1us", "500mV", "2.5V", "1e-6", or an int/float, which is
            returned unchanged. Accepting numbers is what keeps callers that
            already pass floats working.
        quantity: Human-readable name of what is being parsed, used in the
            error message (e.g. "timebase scale").

    Returns:
        The value in base SI units.

    Raises:
        exceptions.InvalidParameterError: If no leading number can be found, or
            the value is not a string or number.

    The suffix rule: if its FIRST character is a known prefix, that prefix is
    applied and the rest is ignored as a unit ("500mV" -> 0.5). Otherwise the
    whole suffix is treated as a unit and ignored ("2.5V" -> 2.5). Units are not
    validated, so "1x" parses to 1.0 -- validating them would mean maintaining a
    list of every unit an instrument might print, for no benefit to any caller.
    A bare prefix is still a prefix: "1m" is 1e-3, not 1 metre. The returned
    float is the same one a decimal literal with that exponent would produce
    (e.g. "10us" -> 1e-05, not 9.999999999999999e-06).
    """
    # bool before int: bool subclasses int, so True would otherwise sail through
    # as 1.0 and hide whatever mistake produced it.
    if isinstance(value, bool):
        raise exceptions.InvalidParameterError(f"{quantity} must be a number or an SI string, not a bool: {value!r}")
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        raise exceptions.InvalidParameterError(f"{quantity} must be a number or an SI string: {value!r}")
    match = _QUANTITY.match(value)
    if not match:
        raise exceptions.InvalidParameterError(f"Could not parse {quantity} from {value!r}. Expected a number with an optional SI prefix and unit, e.g. '1us', '500mV', '2.5V' or 1e-06.")
    number, suffix = match.group(1), match.group(2)
    exponent = _PREFIX_EXPONENTS.get(suffix[0]) if suffix else None
    if exponent is None:
        return float(number)
    try:
        # Decimal handles a number that ALREADY carries an exponent -- "1e6m" is
        # 1e3, where naive string composition would build the invalid "1e6e-3".
        return float(Decimal(number).scaleb(exponent))
    except InvalidOperation:
        raise exceptions.InvalidParameterError(f"Could not scale {quantity} from {value!r}: the value is out of range.") from None
