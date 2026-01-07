"""GUI widgets for oscilloscope control."""

from scpi_control.gui.widgets.channel_control import ChannelControl
from scpi_control.gui.widgets.measurement_panel import MeasurementPanel
from scpi_control.gui.widgets.timebase_control import TimebaseControl
from scpi_control.gui.widgets.trigger_control import TriggerControl
from scpi_control.gui.widgets.waveform_display import WaveformDisplay

# Note: ScopeWebView not imported here to avoid QtWebEngineWidgets initialization issues
# Import it explicitly when needed: from scpi_control.gui.widgets.scope_web_view import ScopeWebView

# Note: VectorGraphicsPanel not imported here as it requires optional 'fun' extras
# Import it explicitly when needed: from scpi_control.gui.widgets.vector_graphics_panel import VectorGraphicsPanel

__all__ = [
    "WaveformDisplay",
    "ChannelControl",
    "TriggerControl",
    "MeasurementPanel",
    "TimebaseControl",
]
