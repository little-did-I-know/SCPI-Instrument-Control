"""GUI widgets for oscilloscope control and DAQ.

Widgets are exposed lazily (PEP 562). Importing them eagerly here meant that
importing *any* submodule -- including the pure numpy/matplotlib measurement
marker math, which needs no Qt at all -- executed this file and pulled in
PyQt6. CI installs `.[dev,web]` without the `gui` extra, so that made Qt-free
modules uncollectable there while dev machines with PyQt6 stayed green.

`from scpi_control.gui.widgets import ChannelControl` still works; the module is
imported on first attribute access instead of at package import.
"""

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - for type checkers and IDEs only
    from scpi_control.gui.widgets.channel_control import ChannelControl
    from scpi_control.gui.widgets.daq_ai_panel import DAQAIPanel
    from scpi_control.gui.widgets.daq_channel_config import DAQChannelConfig
    from scpi_control.gui.widgets.daq_data_view import DAQDataView
    from scpi_control.gui.widgets.daq_scan_config import DAQScanConfig
    from scpi_control.gui.widgets.data_logger_control import DataLoggerControl
    from scpi_control.gui.widgets.measurement_panel import MeasurementPanel
    from scpi_control.gui.widgets.timebase_control import TimebaseControl
    from scpi_control.gui.widgets.trigger_control import TriggerControl
    from scpi_control.gui.widgets.waveform_display import WaveformDisplay

# Public name -> submodule that defines it.
_LAZY_WIDGETS = {
    "ChannelControl": "channel_control",
    "MeasurementPanel": "measurement_panel",
    "TimebaseControl": "timebase_control",
    "TriggerControl": "trigger_control",
    "WaveformDisplay": "waveform_display",
    # DAQ/Data Logger widgets
    "DAQChannelConfig": "daq_channel_config",
    "DAQDataView": "daq_data_view",
    "DAQScanConfig": "daq_scan_config",
    "DAQAIPanel": "daq_ai_panel",
    "DataLoggerControl": "data_logger_control",
}

# Note: ScopeWebView not exposed here to avoid QtWebEngineWidgets initialization issues
# Import it explicitly when needed: from scpi_control.gui.widgets.scope_web_view import ScopeWebView

# Note: VectorGraphicsPanel not exposed here as it requires optional 'fun' extras
# Import it explicitly when needed: from scpi_control.gui.widgets.vector_graphics_panel import VectorGraphicsPanel

__all__ = [
    "WaveformDisplay",
    "ChannelControl",
    "TriggerControl",
    "MeasurementPanel",
    "TimebaseControl",
    # DAQ widgets
    "DAQChannelConfig",
    "DAQDataView",
    "DAQScanConfig",
    "DAQAIPanel",
    "DataLoggerControl",
]


def __getattr__(name: str):
    """Import and cache a widget on first access (PEP 562)."""
    module_name = _LAZY_WIDGETS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(f"{__name__}.{module_name}"), name)
    globals()[name] = value  # cache so __getattr__ runs once per name
    return value


def __dir__():
    return sorted(set(globals()) | set(_LAZY_WIDGETS))
