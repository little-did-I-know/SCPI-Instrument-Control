"""Shared fixture helpers for dual-dialect tests."""

from unittest.mock import Mock

from scpi_control.scpi_commands import SCPICommandSet


def make_dialect_scope(dialect):
    scope = Mock()
    scope.dialect = dialect
    scope._get_command.side_effect = SCPICommandSet(dialect).get_command
    scope._has_command.side_effect = SCPICommandSet(dialect).has_command
    return scope
