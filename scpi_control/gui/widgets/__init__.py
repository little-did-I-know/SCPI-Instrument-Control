"""GUI widgets for oscilloscope control and DAQ."""

from scpi_control.gui.widgets.channel_control import ChannelControl
from scpi_control.gui.widgets.measurement_panel import MeasurementPanel
from scpi_control.gui.widgets.timebase_control import TimebaseControl
from scpi_control.gui.widgets.trigger_control import TriggerControl
from scpi_control.gui.widgets.waveform_display import WaveformDisplay

# DAQ/Data Logger widgets
from scpi_control.gui.widgets.daq_channel_config import DAQChannelConfig
from scpi_control.gui.widgets.daq_data_view import DAQDataView
from scpi_control.gui.widgets.daq_scan_config import DAQScanConfig
from scpi_control.gui.widgets.daq_ai_panel import DAQAIPanel
from scpi_control.gui.widgets.data_logger_control import DataLoggerControl

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
    # DAQ widgets
    "DAQChannelConfig",
    "DAQDataView",
    "DAQScanConfig",
    "DAQAIPanel",
    "DataLoggerControl",
]
