"""GUI widgets for oscilloscope control."""

from siglent.gui.widgets.waveform_display import WaveformDisplay
from siglent.gui.widgets.channel_control import ChannelControl
from siglent.gui.widgets.trigger_control import TriggerControl
from siglent.gui.widgets.measurement_panel import MeasurementPanel
from siglent.gui.widgets.timebase_control import TimebaseControl
# Note: ScopeWebView not imported here to avoid QtWebEngineWidgets initialization issues
# Import it explicitly when needed: from siglent.gui.widgets.scope_web_view import ScopeWebView

__all__ = [
    "WaveformDisplay",
    "ChannelControl",
    "TriggerControl",
    "MeasurementPanel",
    "TimebaseControl",
]
