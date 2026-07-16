"""Shared fixture helpers for dual-dialect tests."""

from unittest.mock import Mock

from scpi_control.scpi_commands import SCPICommandSet


def make_dialect_scope(dialect, variant="standard", num_channels=4):
    scope = Mock()
    scope.dialect = dialect
    # An int (not a Mock) so models.validate_channel binds the channel range
    # instead of falling back to MAX_SUPPORTED_CHANNELS.
    scope.model_capability.num_channels = num_channels
    scope._get_command.side_effect = SCPICommandSet(dialect, variant).get_command
    scope._has_command.side_effect = SCPICommandSet(dialect, variant).has_command
    return scope
