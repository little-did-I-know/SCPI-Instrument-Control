"""Derived, queryable capabilities for a connected oscilloscope.

Everything here is DERIVED from the per-dialect command tables and token maps
in scpi_commands.py (a feature exists iff its command is in the resolved
table; token sets come from the maps) plus the model registry for hardware
facts the tables cannot express (max_channels). Nothing is guessed: building
requires a resolved dialect, which requires a live connection.
"""

from dataclasses import dataclass

from scpi_control.models import ModelCapability
from scpi_control.scpi_commands import (
    SCPICommandSet,
    supported_badge_types,
    supported_couplings,
    supported_measurement_types,
    supported_trigger_couplings,
    supported_trigger_modes,
    supported_trigger_slopes,
    supported_trigger_sources,
    supported_trigger_types,
)


@dataclass(frozen=True)
class ScopeCapabilities:
    """What the connected scope's dialect + variant + model can express.

    Token-set fields hold PUBLIC vocabulary strings; vocabulary enums compare
    and hash equal to them, so `TriggerType.GLIT in caps.trigger_types` works.
    """

    dialect: str
    scpi_variant: str
    model_name: str
    max_channels: int
    trigger_modes: frozenset
    trigger_types: frozenset
    trigger_slopes: frozenset
    trigger_couplings: frozenset
    trigger_sources: frozenset
    channel_couplings: frozenset
    measurement_types: frozenset
    has_trigger_holdoff: bool
    has_probe_ratio: bool
    has_channel_unit: bool
    has_math_display: bool
    has_screen_dump: bool
    has_measurement_statistics: bool


def build_scope_capabilities(commands: SCPICommandSet, model: ModelCapability) -> ScopeCapabilities:
    dialect = commands.dialect
    if dialect == "tektronix":
        # Measurement vocabulary is family-split: TBS speaks MEASUrement:IMMed
        # (tek_tbs override), the MSO families speak MEAS<x> badges (tek_mso
        # override); a plain base table has neither.
        if commands.has_command("get_meas_immed_value"):
            measurement_types = supported_measurement_types(dialect)
        elif commands.has_command("get_badge_value"):
            measurement_types = supported_badge_types(dialect)
        else:
            measurement_types = frozenset()
    else:
        measurement_types = supported_measurement_types(dialect)

    return ScopeCapabilities(
        dialect=dialect,
        scpi_variant=commands.scpi_variant,
        model_name=model.model_name,
        max_channels=model.num_channels,
        trigger_modes=supported_trigger_modes(dialect),
        trigger_types=supported_trigger_types(dialect),
        trigger_slopes=supported_trigger_slopes(dialect),
        trigger_couplings=supported_trigger_couplings(dialect),
        trigger_sources=supported_trigger_sources(dialect),
        channel_couplings=supported_couplings(dialect),
        measurement_types=measurement_types,
        has_trigger_holdoff=commands.has_command("set_trigger_holdoff"),
        has_probe_ratio=commands.has_command("set_probe_ratio"),
        has_channel_unit=commands.has_command("set_channel_unit"),
        has_math_display=commands.has_command("set_math_display"),
        has_screen_dump=commands.has_command("screen_dump"),
        has_measurement_statistics=commands.has_command("set_statistics"),
    )
