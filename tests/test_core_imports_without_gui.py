"""Ensure core modules import when GUI dependencies are unavailable."""

import builtins
import importlib


def test_core_imports_without_gui(monkeypatch):
    """Verify importing core modules does not require PyQt6."""

    real_import = builtins.__import__

    def _no_gui_import(name, *args, **kwargs):
        if name.startswith("PyQt6"):
            raise ModuleNotFoundError("PyQt6 not available in this environment")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_gui_import)

    modules = [
        "siglent",  # Test backward compatibility
        "scpi_control",
        "scpi_control.oscilloscope",
        "scpi_control.connection",
        "scpi_control.connection.base",
        "scpi_control.connection.socket",
        "scpi_control.scpi_commands",
        "scpi_control.waveform",
        "scpi_control.math_channel",
        "scpi_control.analysis",
        "scpi_control.protocol_decode",
        "scpi_control.protocol_decoders",
        "scpi_control.reference_waveform",
    ]

    for module in modules:
        importlib.import_module(module)
