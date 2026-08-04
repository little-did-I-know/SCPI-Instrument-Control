"""Public, string-compatible vocabulary for token-valued instrument parameters.

Every enum subclasses (str, Enum) with name == value, so members compare and
hash equal to the plain canonical strings the API has always spoken:
Coupling.DC == "DC". Setters accept either form; getters keep returning plain
strings (spec: "enums in, strings out").

This module is deliberately leaf-level: it imports nothing from the driver or
command-table modules, so those can import it without cycles. Which tokens a
CONNECTED dialect supports is the command layer's knowledge (scpi_commands.py
token maps); the enums here are the union vocabulary.
"""

from enum import Enum
from typing import Iterable, Literal, Mapping, Optional, Union

from scpi_control import exceptions

# Literal aliases for annotations. Kept alongside the enums so trigger.py and
# channel.py can re-export them from their historical locations.
TriggerModeType = Literal["AUTO", "NORM", "NORMAL", "SINGLE", "STOP"]
TriggerTypeType = Literal["EDGE", "SLEW", "GLIT", "INTV", "RUNT", "PATTERN"]
TriggerSlopeType = Literal["POS", "NEG", "WINDOW"]
TriggerCouplingType = Literal["DC", "AC", "HFREJ", "LFREJ"]
TriggerSourceType = Literal["C1", "C2", "C3", "C4", "EX", "EX5", "LINE"]
CouplingType = Literal["DC", "AC", "GND"]
BandwidthLimitType = Literal["OFF", "ON", "FULL"]
TrackingModeType = Literal["INDEPENDENT", "SERIES", "PARALLEL"]


class Coupling(str, Enum):
    """Channel coupling. Wire mapping is per-dialect (legacy speaks D1M/A1M)."""

    DC = "DC"
    AC = "AC"
    GND = "GND"


class TriggerMode(str, Enum):
    AUTO = "AUTO"
    NORM = "NORM"
    SINGLE = "SINGLE"
    STOP = "STOP"


class TriggerSlope(str, Enum):
    POS = "POS"
    NEG = "NEG"
    WINDOW = "WINDOW"


class TriggerCoupling(str, Enum):
    DC = "DC"
    AC = "AC"
    HFREJ = "HFREJ"
    LFREJ = "LFREJ"


class TriggerType(str, Enum):
    """Public trigger-type vocabulary (MAUI-descended naming: SLEW = slope
    trigger, GLIT = pulse/glitch trigger)."""

    EDGE = "EDGE"
    SLEW = "SLEW"
    GLIT = "GLIT"
    INTV = "INTV"
    RUNT = "RUNT"
    PATTERN = "PATTERN"


class TriggerSource(str, Enum):
    C1 = "C1"
    C2 = "C2"
    C3 = "C3"
    C4 = "C4"
    EX = "EX"
    EX5 = "EX5"
    LINE = "LINE"


class BandwidthLimit(str, Enum):
    OFF = "OFF"
    ON = "ON"
    FULL = "FULL"


class TrackingMode(str, Enum):
    INDEPENDENT = "INDEPENDENT"
    SERIES = "SERIES"
    PARALLEL = "PARALLEL"


def normalize_token(
    value: Union[str, Enum],
    *,
    parameter: str,
    valid: Iterable[str],
    aliases: Optional[Mapping[str, str]] = None,
    dialect: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """Uppercase, alias-fold, and validate a token; return the canonical string.

    Raises InvalidParameterError (also a ValueError) carrying the parameter
    name, the offending value, and the valid options for THIS instrument.
    """
    # Unwrap enum members explicitly: on Python < 3.12, str() of a (str, Enum)
    # member is "Coupling.DC", not "DC" -- .value is the canonical string.
    if isinstance(value, Enum):
        value = value.value
    original = str(value)
    token = original.strip().upper()
    if aliases:
        token = aliases.get(token, token)
    valid_set = set(valid)
    if token not in valid_set:
        raise exceptions.InvalidParameterError(parameter=parameter, value=original, valid_options=valid_set, dialect=dialect, model=model)
    return token
