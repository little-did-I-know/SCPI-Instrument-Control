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
        "siglent",
        "siglent.oscilloscope",
        "siglent.connection",
        "siglent.connection.base",
        "siglent.connection.socket",
        "siglent.scpi_commands",
        "siglent.waveform",
        "siglent.math_channel",
        "siglent.analysis",
        "siglent.protocol_decode",
        "siglent.protocol_decoders",
        "siglent.reference_waveform",
    ]

    for module in modules:
        importlib.import_module(module)
