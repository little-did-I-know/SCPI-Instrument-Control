"""Main window for Siglent oscilloscope control GUI."""

import logging
from typing import TYPE_CHECKING, Optional

import numpy as np

if TYPE_CHECKING:
    from siglent.gui.vnc_window import VNCWindow

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QFileDialog, QGroupBox, QHBoxLayout, QInputDialog, QMainWindow, QMessageBox, QProgressDialog, QPushButton, QSplitter, QStatusBar, QTabWidget, QVBoxLayout, QWidget

from siglent import Oscilloscope, PowerSupply
from siglent.exceptions import SiglentConnectionError, SiglentError

# Try to use PyQtGraph for high-performance plotting, fallback to matplotlib
try:
    from siglent.gui.widgets.waveform_display_pg import WaveformDisplayPG as WaveformDisplay

    USING_PYQTGRAPH = True
    logger = logging.getLogger(__name__)
    logger.info("Using PyQtGraph for waveform display (high performance mode)")
except ImportError:
    from siglent.gui.widgets.waveform_display import WaveformDisplay

    USING_PYQTGRAPH = False
    logger = logging.getLogger(__name__)
    logger.warning("PyQtGraph not available, using matplotlib (install with: pip install 'Siglent-Oscilloscope[gui]')")
from siglent.gui.connection_manager import ConnectionManager
from siglent.gui.live_view_worker import LiveViewWorker
from siglent.gui.waveform_capture_worker import WaveformCaptureWorker
from siglent.gui.widgets.channel_control import ChannelControl
from siglent.gui.widgets.cursor_panel import CursorPanel
from siglent.gui.widgets.error_dialog import DetailedErrorDialog
from siglent.gui.widgets.fft_display import FFTDisplay
from siglent.gui.widgets.math_panel import MathPanel
from siglent.gui.widgets.measurement_panel import MeasurementPanel
from siglent.gui.widgets.protocol_decode_panel import ProtocolDecodePanel
from siglent.gui.widgets.psu_control import PSUControl
from siglent.gui.widgets.reference_panel import ReferencePanel
from siglent.gui.widgets.terminal_widget import TerminalWidget
from siglent.gui.widgets.timebase_control import TimebaseControl
from siglent.gui.widgets.trigger_control import TriggerControl
from siglent.gui.widgets.visual_measurement_panel import VisualMeasurementPanel
from siglent.protocol_decoders import I2CDecoder, SPIDecoder, UARTDecoder
from siglent.reference_waveform import ReferenceWaveform

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window for oscilloscope control."""

    def __init__(self):
        """Initialize main window."""
        super().__init__()

        self.scope: Optional[Oscilloscope] = None
        self.psu: Optional[PowerSupply] = None
        self.is_live_view = False
        self.live_view_worker: Optional[LiveViewWorker] = None
        self.capture_worker: Optional[WaveformCaptureWorker] = None
        self.progress_dialog: Optional[QProgressDialog] = None

        # Connection manager
        self.connection_manager = ConnectionManager()

        # Reference waveform manager
        self.reference_manager = ReferenceWaveform()

        # Protocol decoders
        self.i2c_decoder = I2CDecoder()
        self.spi_decoder = SPIDecoder()
        self.uart_decoder = UARTDecoder()

        # Control widgets (initialized in _init_ui)
        self.channel_control: Optional[ChannelControl] = None
        self.trigger_control: Optional[TriggerControl] = None
        self.measurement_panel: Optional[MeasurementPanel] = None
        self.timebase_control: Optional[TimebaseControl] = None
        self.math_panel: Optional[MathPanel] = None
        self.fft_display: Optional[FFTDisplay] = None
        self.reference_panel: Optional[ReferencePanel] = None
        self.protocol_decode_panel: Optional[ProtocolDecodePanel] = None
        self.psu_control: Optional[PSUControl] = None
        self.terminal_widget: Optional[TerminalWidget] = None

        # VNC window (separate window)
        self.vnc_window: Optional[VNCWindow] = None

        self._init_ui()
        self._create_menus()
        self._create_toolbar()
        self._create_status_bar()

        logger.info("Main window initialized")

    def _init_ui(self):
        """Initialize user interface."""
        self.setWindowTitle("Siglent Oscilloscope Control")
        # Set wider rectangular window (1600x850) for better waveform display
        self.setGeometry(100, 100, 1600, 850)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout(central_widget)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # IMPORTANT: Create waveform display first, before control panel
        # because control panel needs to connect signals to it
        self.waveform_display = WaveformDisplay()

        # Left panel - Controls
        left_panel = self._create_control_panel()
        splitter.addWidget(left_panel)

        # Right panel - Waveform display
        right_panel = self._create_display_panel()
        splitter.addWidget(right_panel)

        # Set initial sizes (25% controls, 75% display)
        # With 1600px width: ~400px controls, ~1200px display
        splitter.setSizes([400, 1200])

        main_layout.addWidget(splitter)

    def _create_control_panel(self) -> QWidget:
        """Create the left control panel.

        Returns:
            Control panel widget
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Create tab widget for controls
        self.tabs = QTabWidget()

        # Channels tab
        self.channel_control = ChannelControl()
        self.tabs.addTab(self.channel_control, "Channels")

        # Trigger tab
        self.trigger_control = TriggerControl()
        self.tabs.addTab(self.trigger_control, "Trigger")

        # Timebase tab
        self.timebase_control = TimebaseControl()
        self.tabs.addTab(self.timebase_control, "Timebase")

        # Measurements tab
        self.measurement_panel = MeasurementPanel()
        self.tabs.addTab(self.measurement_panel, "Measurements")

        # Visual Measurements tab
        self.visual_measurement_panel = VisualMeasurementPanel(self.waveform_display)
        self.tabs.addTab(self.visual_measurement_panel, "Visual Measure")

        # Cursors tab
        self.cursor_panel = CursorPanel()
        self.tabs.addTab(self.cursor_panel, "Cursors")

        # Connect cursor panel signals to waveform display
        self.cursor_panel.cursor_mode_changed.connect(self.waveform_display.set_cursor_mode)
        self.cursor_panel.clear_cursors.connect(self.waveform_display._clear_all_cursors)

        # Set up timer to update cursor values periodically
        self.cursor_update_timer = QTimer()
        self.cursor_update_timer.timeout.connect(self._update_cursor_values)
        self.cursor_update_timer.start(100)  # Update every 100ms

        # Math tab
        self.math_panel = MathPanel()
        self.tabs.addTab(self.math_panel, "Math")

        # Connect math panel signals
        self.math_panel.math1_expression_changed.connect(self._on_math1_expression_changed)
        self.math_panel.math2_expression_changed.connect(self._on_math2_expression_changed)
        self.math_panel.math1_enabled_changed.connect(self._on_math1_enabled_changed)
        self.math_panel.math2_enabled_changed.connect(self._on_math2_enabled_changed)

        # FFT tab
        self.fft_display = FFTDisplay()
        self.tabs.addTab(self.fft_display, "FFT")

        # Connect FFT display signals
        self.fft_display.fft_compute_requested.connect(self._on_fft_compute_requested)

        # Reference tab
        self.reference_panel = ReferencePanel()
        self.tabs.addTab(self.reference_panel, "Reference")

        # Connect reference panel signals
        self.reference_panel.save_reference.connect(self._on_save_reference)
        self.reference_panel.load_reference.connect(self._on_load_reference)
        self.reference_panel.delete_reference.connect(self._on_delete_reference)
        self.reference_panel.show_difference.connect(self._on_toggle_reference_difference)

        # Load initial reference list
        self._refresh_reference_list()

        # Protocol Decode tab
        self.protocol_decode_panel = ProtocolDecodePanel()
        self.tabs.addTab(self.protocol_decode_panel, "Protocol")

        # Vector Graphics tab (optional - requires 'fun' extras)
        try:
            from siglent.gui.widgets.vector_graphics_panel import VectorGraphicsPanel

            self.vector_graphics_panel = VectorGraphicsPanel()
            self.tabs.addTab(self.vector_graphics_panel, "Vector Graphics")
        except ImportError:
            # 'fun' extras not installed - tab will show install message
            from siglent.gui.widgets.vector_graphics_panel import VectorGraphicsPanel

            self.vector_graphics_panel = VectorGraphicsPanel()
            self.tabs.addTab(self.vector_graphics_panel, "Vector Graphics 🎨")

        # Connect protocol decode panel signals
        self.protocol_decode_panel.decode_requested.connect(self._on_protocol_decode_requested)
        self.protocol_decode_panel.export_requested.connect(self._on_protocol_export_requested)

        # Terminal tab
        self.terminal_widget = TerminalWidget()
        self.tabs.addTab(self.terminal_widget, "Terminal")

        # Power Supply tab
        self.psu_control = PSUControl()
        self.tabs.addTab(self.psu_control, "Power Supply")

        layout.addWidget(self.tabs)

        return panel

    def _create_display_panel(self) -> QWidget:
        """Create the right display panel.

        Returns:
            Display panel widget
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        # Waveform display (already created in _init_ui)
        waveform_group = QGroupBox("Waveform Display")
        waveform_layout = QVBoxLayout(waveform_group)
        waveform_layout.setContentsMargins(0, 0, 0, 0)

        # Use the waveform_display already created in _init_ui
        waveform_layout.addWidget(self.waveform_display)

        layout.addWidget(waveform_group)

        return panel

    def _create_menus(self):
        """Create menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        connect_action = QAction("&Connect to Oscilloscope...", self)
        connect_action.setShortcut("Ctrl+O")
        connect_action.triggered.connect(self._on_connect)
        file_menu.addAction(connect_action)

        disconnect_action = QAction("&Disconnect Oscilloscope", self)
        disconnect_action.triggered.connect(self._on_disconnect)
        file_menu.addAction(disconnect_action)

        file_menu.addSeparator()

        # Power Supply menu items
        psu_connect_action = QAction("Connect to &Power Supply...", self)
        psu_connect_action.setShortcut("Ctrl+P")
        psu_connect_action.triggered.connect(self._on_psu_connect)
        file_menu.addAction(psu_connect_action)

        psu_disconnect_action = QAction("Disconnect Po&wer Supply", self)
        psu_disconnect_action.triggered.connect(self._on_psu_disconnect)
        file_menu.addAction(psu_disconnect_action)

        file_menu.addSeparator()

        # Recent connections submenu
        self.recent_connections_menu = file_menu.addMenu("&Recent Connections")
        self._update_recent_connections_menu()

        file_menu.addSeparator()

        save_waveform_action = QAction("Save &Waveform...", self)
        save_waveform_action.setShortcut("Ctrl+S")
        save_waveform_action.triggered.connect(self._on_save_waveform)
        file_menu.addAction(save_waveform_action)

        save_screenshot_action = QAction("Save S&creenshot...", self)
        save_screenshot_action.setShortcut("Ctrl+Shift+S")
        save_screenshot_action.triggered.connect(self._on_save_screenshot)
        file_menu.addAction(save_screenshot_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Acquisition menu
        acq_menu = menubar.addMenu("&Acquisition")

        run_action = QAction("&Run", self)
        run_action.setShortcut("F5")
        run_action.triggered.connect(self._on_run)
        acq_menu.addAction(run_action)

        stop_action = QAction("&Stop", self)
        stop_action.setShortcut("F6")
        stop_action.triggered.connect(self._on_stop)
        acq_menu.addAction(stop_action)

        single_action = QAction("S&ingle", self)
        single_action.setShortcut("F7")
        single_action.triggered.connect(self._on_single)
        acq_menu.addAction(single_action)

        acq_menu.addSeparator()

        capture_action = QAction("&Capture Waveform", self)
        capture_action.setShortcut("F8")
        capture_action.triggered.connect(self._on_capture_waveform)
        acq_menu.addAction(capture_action)

        live_view_action = QAction("&Live View", self)
        live_view_action.setCheckable(True)
        live_view_action.setShortcut("Ctrl+R")
        live_view_action.toggled.connect(self._on_toggle_live_view)
        acq_menu.addAction(live_view_action)
        self.live_view_action = live_view_action  # Store reference for external access

        # View menu
        view_menu = menubar.addMenu("&View")

        vnc_action = QAction("Open &Scope Display (VNC)...", self)
        vnc_action.setShortcut("Ctrl+D")
        vnc_action.triggered.connect(self._on_open_vnc_window)
        view_menu.addAction(vnc_action)

        view_menu.addSeparator()

        auto_setup_action = QAction("&Auto Setup", self)
        auto_setup_action.triggered.connect(self._on_auto_setup)
        view_menu.addAction(auto_setup_action)

        view_menu.addSeparator()

        toggle_grid_action = QAction("Toggle &Grid", self)
        toggle_grid_action.setShortcut("G")
        toggle_grid_action.triggered.connect(self._on_toggle_grid)
        view_menu.addAction(toggle_grid_action)

        toggle_cursors_action = QAction("Toggle &Cursors", self)
        toggle_cursors_action.setShortcut("C")
        toggle_cursors_action.triggered.connect(self._on_toggle_cursors)
        view_menu.addAction(toggle_cursors_action)

        reset_zoom_action = QAction("&Reset Zoom", self)
        reset_zoom_action.setShortcut("Home")
        reset_zoom_action.triggered.connect(self._on_reset_zoom)
        view_menu.addAction(reset_zoom_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        shortcuts_action = QAction("&Keyboard Shortcuts", self)
        shortcuts_action.setShortcut("F1")
        shortcuts_action.triggered.connect(self._on_show_shortcuts)
        help_menu.addAction(shortcuts_action)

        help_menu.addSeparator()

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _create_toolbar(self):
        """Create toolbar."""
        toolbar = self.addToolBar("Main Toolbar")

        # Add styled connect/disconnect buttons that stand out
        connect_btn = QPushButton("Connect")
        connect_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                font-size: 12pt;
                padding: 8px 16px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """
        )
        connect_btn.clicked.connect(self._on_connect)
        toolbar.addWidget(connect_btn)

        disconnect_btn = QPushButton("Disconnect")
        disconnect_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                font-size: 12pt;
                padding: 8px 16px;
                border-radius: 4px;
                border: none;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c1170a;
            }
        """
        )
        disconnect_btn.clicked.connect(self._on_disconnect)
        toolbar.addWidget(disconnect_btn)

        toolbar.addSeparator()

        run_action = QAction("Run", self)
        run_action.triggered.connect(self._on_run)
        toolbar.addAction(run_action)

        stop_action = QAction("Stop", self)
        stop_action.triggered.connect(self._on_stop)
        toolbar.addAction(stop_action)

        single_action = QAction("Single", self)
        single_action.triggered.connect(self._on_single)
        toolbar.addAction(single_action)

        toolbar.addSeparator()

        capture_action = QAction("Capture Waveform", self)
        capture_action.triggered.connect(self._on_capture_waveform)
        toolbar.addAction(capture_action)

        screenshot_action = QAction("Screenshot", self)
        screenshot_action.setToolTip("Save screenshot from oscilloscope display")
        screenshot_action.triggered.connect(self._on_save_screenshot)
        toolbar.addAction(screenshot_action)

        toolbar.addSeparator()

        vnc_action = QAction("Open Scope Display", self)
        vnc_action.triggered.connect(self._on_open_vnc_window)
        toolbar.addAction(vnc_action)

    def _create_status_bar(self):
        """Create status bar."""
        self.statusBar().showMessage("Not connected")

    def _update_recent_connections_menu(self):
        """Update the recent connections menu."""
        self.recent_connections_menu.clear()

        recent = self.connection_manager.get_recent_connections()

        if not recent:
            no_recent_action = QAction("(No recent connections)", self)
            no_recent_action.setEnabled(False)
            self.recent_connections_menu.addAction(no_recent_action)
        else:
            for connection in recent:
                display_text = self.connection_manager.format_connection_display(connection)
                action = QAction(display_text, self)
                action.triggered.connect(lambda checked, conn=connection: self._connect_to_recent(conn))
                self.recent_connections_menu.addAction(action)

            self.recent_connections_menu.addSeparator()

            clear_action = QAction("Clear Recent Connections", self)
            clear_action.triggered.connect(self._on_clear_recent_connections)
            self.recent_connections_menu.addAction(clear_action)

    def _connect_to_recent(self, connection: dict):
        """Connect to a recent connection.

        Args:
            connection: Connection dictionary with host and port
        """
        host = connection.get("host")
        port = connection.get("port", 5024)

        if host:
            self._connect_to_scope(host, port)

    def _on_clear_recent_connections(self):
        """Clear recent connections."""
        reply = QMessageBox.question(
            self,
            "Clear Recent Connections",
            "Are you sure you want to clear all recent connections?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.connection_manager.clear_recent_connections()
            self._update_recent_connections_menu()
            logger.info("Cleared recent connections")

    def _on_connect(self):
        """Handle connect action."""
        # Get default IP from last connection
        last_connection = self.connection_manager.get_last_connection()
        default_ip = last_connection.get("host", "192.168.1.100") if last_connection else "192.168.1.100"

        # Get IP address from user
        ip, ok = QInputDialog.getText(self, "Connect to Oscilloscope", "Enter oscilloscope IP address:", text=default_ip)

        if ok and ip:
            self._connect_to_scope(ip)

    def _connect_to_scope(self, ip: str, port: int = 5024):
        """Connect to oscilloscope at specified IP and port.

        Args:
            ip: IP address or hostname
            port: TCP port (default: 5024)
        """
        try:
            self.statusBar().showMessage(f"Connecting to {ip}...")
            self.scope = Oscilloscope(ip, port)
            self.scope.connect()

            device_info = self.scope.device_info
            model = device_info.get("model", "Unknown") if device_info else "Unknown"

            # Pass scope reference to all control widgets
            self.channel_control.set_scope(self.scope)
            self.trigger_control.set_scope(self.scope)
            self.measurement_panel.set_scope(self.scope)
            self.timebase_control.set_scope(self.scope)
            self.terminal_widget.set_oscilloscope(self.scope)
            if hasattr(self, "vector_graphics_panel"):
                self.vector_graphics_panel.set_scope(self.scope)

            # Update math panel and FFT display with available channels
            if self.scope.model_capability:
                num_channels = self.scope.model_capability.num_channels
                self.math_panel.update_available_channels(num_channels)
                self.fft_display.update_available_channels(num_channels)

            # Create detailed status message with model capability info
            if self.scope.model_capability:
                cap = self.scope.model_capability
                status_msg = f"Connected: {model} | {cap.series} | {cap.num_channels}ch | {cap.bandwidth_mhz}MHz | {ip}"
                info_msg = f"Successfully connected to:\n\n" f"Model: {model}\n" f"Series: {cap.series}\n" f"Channels: {cap.num_channels}\n" f"Bandwidth: {cap.bandwidth_mhz} MHz\n" f"IP Address: {ip}"
            else:
                status_msg = f"Connected to {model} at {ip}"
                info_msg = f"Successfully connected to {model}\nIP: {ip}"

            self.statusBar().showMessage(status_msg)
            QMessageBox.information(self, "Connected", info_msg)
            logger.info(f"Connected to oscilloscope at {ip}")

            # Add to recent connections
            self.connection_manager.add_connection(ip, port, model)
            self._update_recent_connections_menu()

        except (SiglentConnectionError, SiglentError) as e:
            self.statusBar().showMessage("Connection failed")
            QMessageBox.critical(self, "Connection Error", f"Failed to connect to oscilloscope:\n{str(e)}")
            logger.error(f"Connection failed: {e}")
            self.scope = None

    def _on_disconnect(self):
        """Handle disconnect action."""
        if self.scope:
            # Stop live view if running
            if self.is_live_view:
                self._on_toggle_live_view(False)
            elif self.live_view_worker:
                # Ensure worker is stopped
                self.live_view_worker.stop()
                self.live_view_worker = None

            self.scope.disconnect()
            self.scope = None

            # Clear scope reference from all control widgets
            self.channel_control.set_scope(None)
            self.trigger_control.set_scope(None)
            self.measurement_panel.set_scope(None)
            self.timebase_control.set_scope(None)
            self.terminal_widget.set_oscilloscope(None)
            if hasattr(self, "vector_graphics_panel"):
                self.vector_graphics_panel.set_scope(None)

            self.statusBar().showMessage("Disconnected")
            logger.info("Disconnected from oscilloscope")
        else:
            QMessageBox.warning(self, "Not Connected", "No oscilloscope connected")

    def _on_psu_connect(self):
        """Handle PSU connect action."""
        # Get IP address from user
        ip, ok = QInputDialog.getText(self, "Connect to Power Supply", "Enter power supply IP address:", text="192.168.1.200")

        if ok and ip:
            self._connect_to_psu(ip)

    def _connect_to_psu(self, ip: str, port: int = 5024):
        """Connect to power supply at specified IP and port.

        Args:
            ip: IP address or hostname
            port: TCP port (default: 5024)
        """
        try:
            self.statusBar().showMessage(f"Connecting to PSU at {ip}...")
            self.psu = PowerSupply(ip, port)
            self.psu.connect()

            device_info = self.psu.device_info
            model = device_info.get("model", "Unknown") if device_info else "Unknown"
            manufacturer = device_info.get("manufacturer", "Unknown") if device_info else "Unknown"

            # Pass PSU reference to control widget
            self.psu_control.set_psu(self.psu)

            # Create detailed status message with model capability info
            if self.psu.model_capability:
                cap = self.psu.model_capability
                status_msg = f"PSU Connected: {model} | " f"{cap.num_outputs} outputs | " f"{cap.scpi_variant} | {ip}"
                info_msg = (
                    f"Successfully connected to power supply:\n\n"
                    f"Manufacturer: {manufacturer}\n"
                    f"Model: {model}\n"
                    f"Outputs: {cap.num_outputs}\n"
                    f"SCPI Variant: {cap.scpi_variant}\n"
                    f"IP Address: {ip}"
                )
            else:
                status_msg = f"PSU Connected to {model} at {ip}"
                info_msg = f"Successfully connected to {model}\nIP: {ip}"

            self.statusBar().showMessage(status_msg)
            QMessageBox.information(self, "PSU Connected", info_msg)
            logger.info(f"Connected to power supply at {ip}")

            # Switch to Power Supply tab
            for i in range(self.tabs.count()):
                if self.tabs.tabText(i) == "Power Supply":
                    self.tabs.setCurrentIndex(i)
                    break

        except (SiglentConnectionError, SiglentError) as e:
            self.statusBar().showMessage("PSU connection failed")
            QMessageBox.critical(self, "PSU Connection Error", f"Failed to connect to power supply:\n{str(e)}")
            logger.error(f"PSU connection failed: {e}")
            self.psu = None

    def _on_psu_disconnect(self):
        """Handle PSU disconnect action."""
        if self.psu:
            self.psu.disconnect()
            self.psu = None

            # Clear PSU reference from control widget
            self.psu_control.set_psu(None)

            self.statusBar().showMessage("PSU Disconnected")
            logger.info("Disconnected from power supply")
        else:
            QMessageBox.warning(self, "Not Connected", "No power supply connected")

    def _on_run(self):
        """Handle run action."""
        if self.scope:
            try:
                self.scope.run()
                self.statusBar().showMessage("Acquisition running (AUTO trigger)")
                logger.info("Acquisition started")
            except SiglentError as e:
                QMessageBox.critical(self, "Error", f"Failed to start acquisition:\n{str(e)}")
        else:
            QMessageBox.warning(self, "Not Connected", "No oscilloscope connected")

    def _on_stop(self):
        """Handle stop action."""
        if self.scope:
            try:
                self.scope.stop()
                self.statusBar().showMessage("Acquisition stopped")
                logger.info("Acquisition stopped")
            except SiglentError as e:
                QMessageBox.critical(self, "Error", f"Failed to stop acquisition:\n{str(e)}")
        else:
            QMessageBox.warning(self, "Not Connected", "No oscilloscope connected")

    def _on_single(self):
        """Handle single trigger action."""
        if self.scope:
            try:
                self.scope.trigger_single()
                self.statusBar().showMessage("Single trigger armed")
                logger.info("Single trigger armed")
            except SiglentError as e:
                QMessageBox.critical(self, "Error", f"Failed to arm single trigger:\n{str(e)}")
        else:
            QMessageBox.warning(self, "Not Connected", "No oscilloscope connected")

    def _on_auto_setup(self):
        """Handle auto setup action."""
        if self.scope:
            try:
                self.statusBar().showMessage("Running auto setup...")
                self.scope.auto_setup()
                self.statusBar().showMessage("Auto setup complete")
                logger.info("Auto setup complete")
            except SiglentError as e:
                QMessageBox.critical(self, "Error", f"Auto setup failed:\n{str(e)}")
        else:
            QMessageBox.warning(self, "Not Connected", "No oscilloscope connected")

    def _on_open_vnc_window(self):
        """Handle opening VNC window."""
        # Lazy import to avoid QtWebEngineWidgets initialization issues
        try:
            from siglent.gui.vnc_window import VNCWindow
        except ImportError as e:
            QMessageBox.critical(
                self,
                "Missing Dependency",
                "The VNC viewer requires PyQt6-WebEngine to be installed.\n\n" "Please install it using:\n" "pip install PyQt6-WebEngine\n\n" f"Error: {str(e)}",
            )
            logger.error(f"Failed to import VNCWindow: {e}")
            return

        try:
            # Create VNC window if not already created
            if self.vnc_window is None:
                self.vnc_window = VNCWindow(self)

            # Set IP if we have a connected scope
            if self.scope and self.scope.host:
                self.vnc_window.set_scope_ip(self.scope.host)
            elif not self.vnc_window.scope_ip:
                # No scope connected and no IP previously set, show info
                QMessageBox.information(
                    self,
                    "VNC Viewer",
                    "Enter your oscilloscope's IP address in the toolbar to connect.\n\n" "The VNC viewer will display your oscilloscope's screen interface.",
                )

            # Show the window
            self.vnc_window.show()
            self.vnc_window.raise_()
            self.vnc_window.activateWindow()
            logger.info("Opened VNC window")

        except Exception as e:
            QMessageBox.critical(self, "VNC Window Error", f"Failed to open VNC window:\n{str(e)}")
            logger.error(f"Failed to open VNC window: {e}")

    def _on_save_screenshot(self):
        """Handle save screenshot action."""
        if not self.scope:
            QMessageBox.warning(self, "Not Connected", "No oscilloscope connected")
            return

        try:
            # Ask user for file location
            # Note: SCDP command returns BMP format regardless of extension
            file_filter = "BMP Image (*.bmp);;All Files (*.*)"
            filename, selected_filter = QFileDialog.getSaveFileName(self, "Save Screenshot", "screenshot.bmp", file_filter)

            if filename:
                self.statusBar().showMessage("Capturing screenshot using SCDP...")
                logger.info(f"Saving screenshot to {filename}")

                # Capture and save screenshot (SCDP returns BMP format)
                self.scope.screen_capture.save_screenshot(filename)

                self.statusBar().showMessage(f"Screenshot saved to {filename}")
                QMessageBox.information(
                    self,
                    "Screenshot Saved",
                    f"Screenshot successfully saved to:\n{filename}\n\n" f"Note: Image is in BMP format (from SCDP command).",
                )
                logger.info(f"Screenshot saved successfully to {filename}")

        except Exception as e:
            self.statusBar().showMessage("Screenshot capture failed")
            QMessageBox.critical(
                self,
                "Screenshot Error",
                f"Failed to capture screenshot:\n{str(e)}\n\n" f"The SCDP command is used per Siglent manual.\n" f"Ensure your oscilloscope supports this command.",
            )
            logger.error(f"Screenshot capture failed: {e}")

    def _on_capture_waveform(self):
        """Handle capture waveform action - uses background worker to prevent GUI freeze."""
        if not self.scope:
            QMessageBox.warning(self, "Not Connected", "No oscilloscope connected")
            return

        # Don't allow new capture while one is in progress
        if self.capture_worker and self.capture_worker.isRunning():
            QMessageBox.warning(self, "Capture in Progress", "Please wait for current capture to complete")
            return

        try:
            logger.info("=== Capture Waveform Started ===")

            # Get list of enabled channels
            enabled_channels = []
            supported_channels = self.scope.supported_channels if hasattr(self.scope, "supported_channels") else range(1, 5)

            for ch_num in supported_channels:
                try:
                    channel = getattr(self.scope, f"channel{ch_num}", None)
                    if channel:
                        is_enabled = channel.enabled
                        logger.info(f"Channel {ch_num} enabled: {is_enabled}")
                        if is_enabled:
                            enabled_channels.append(ch_num)
                except Exception as e:
                    logger.warning(f"Could not check channel {ch_num} status: {e}")

            logger.info(f"Enabled channels: {enabled_channels}")

            if not enabled_channels:
                # Ask user if they want to enable channel 1
                reply = QMessageBox.question(
                    self,
                    "No Channels Enabled",
                    "No channels are currently enabled.\n\nWould you like to enable Channel 1?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    try:
                        self.scope.channel1.enable()
                        # Wait a bit for scope to process
                        from PyQt6.QtCore import QThread

                        QThread.msleep(100)
                        enabled_channels = [1]
                        logger.info("Enabled channel 1 for capture")
                    except Exception as e:
                        QMessageBox.critical(self, "Error", f"Could not enable channel 1:\n{str(e)}")
                        logger.error(f"Failed to enable channel 1: {e}")
                        return
                else:
                    logger.info("User cancelled capture")
                    return

            # Create progress dialog
            self.progress_dialog = QProgressDialog("Initializing capture...", "Cancel", 0, 100, self)
            self.progress_dialog.setWindowTitle("Capturing Waveforms")
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.setAutoClose(True)
            self.progress_dialog.setMinimumDuration(0)  # Show immediately
            self.progress_dialog.canceled.connect(self._on_capture_cancelled)

            # Create and configure worker
            self.capture_worker = WaveformCaptureWorker(self.scope, enabled_channels, self)
            self.capture_worker.progress_update.connect(self._on_capture_progress)
            self.capture_worker.waveforms_ready.connect(self._on_capture_complete)
            self.capture_worker.capture_complete.connect(self._on_capture_finished)
            self.capture_worker.error_occurred.connect(self._on_capture_error)

            # Start capture in background thread
            logger.info(f"Starting background capture for channels: {enabled_channels}")
            self.statusBar().showMessage("Capturing waveforms...")
            self.capture_worker.start()

        except SiglentError as e:
            self.statusBar().showMessage("Capture failed")
            QMessageBox.critical(self, "Capture Error", f"Failed to start capture:\n{str(e)}")
            logger.error(f"Waveform capture failed: {e}", exc_info=True)

    def _on_capture_progress(self, message: str, percentage: int):
        """Handle progress updates from capture worker."""
        if self.progress_dialog:
            self.progress_dialog.setLabelText(message)
            self.progress_dialog.setValue(percentage)
        logger.debug(f"Capture progress: {percentage}% - {message}")

    def _on_capture_complete(self, waveforms):
        """Handle waveforms ready from capture worker."""
        # Close progress dialog BEFORE plotting to prevent signal race conditions
        self._close_progress_dialog()

        logger.info(f"Displaying {len(waveforms)} captured waveform(s)...")
        self.waveform_display.plot_multiple_waveforms(waveforms)
        self.statusBar().showMessage(f"Captured {len(waveforms)} waveform(s)")

    def _on_capture_finished(self, waveform_count: int):
        """Handle capture completion."""
        self._close_progress_dialog()
        logger.info(f"=== Capture Complete: {waveform_count} waveform(s) ===")

    def _on_capture_error(self, error_message: str):
        """Handle capture errors from worker."""
        self._close_progress_dialog()

        self.statusBar().showMessage("Capture failed")
        QMessageBox.warning(self, "Capture Failed", error_message)
        logger.error(f"Capture error: {error_message}")

    def _on_capture_cancelled(self):
        """Handle user cancelling the capture."""
        # Only cancel if worker is actually running (not already finished)
        if self.capture_worker and self.capture_worker.isRunning():
            logger.info("User cancelled capture")
            self.capture_worker.cancel()
            self.statusBar().showMessage("Capture cancelled")
            self._close_progress_dialog()

    def _close_progress_dialog(self):
        """Safely close progress dialog and disconnect signals to prevent race conditions."""
        if self.progress_dialog:
            # Disconnect canceled signal BEFORE closing to prevent spurious cancel events
            try:
                self.progress_dialog.canceled.disconnect(self._on_capture_cancelled)
            except TypeError:
                # Signal might not be connected, ignore
                pass

            self.progress_dialog.close()
            self.progress_dialog = None

    def _on_toggle_live_view(self, checked: bool):
        """Handle live view toggle.

        Args:
            checked: True to enable live view, False to disable
        """
        if not self.scope:
            QMessageBox.warning(self, "Not Connected", "No oscilloscope connected")
            # Uncheck the action since we can't enable live view
            self.live_view_action.blockSignals(True)
            self.live_view_action.setChecked(False)
            self.live_view_action.blockSignals(False)
            return

        self.is_live_view = checked

        if checked:
            try:
                logger.info("Starting live view...")

                # Ensure scope is running in AUTO mode for continuous acquisition
                logger.debug("Setting trigger mode to AUTO")
                self.scope.trigger.mode = "AUTO"
                self.scope.run()

                # Check if at least one channel is enabled
                any_enabled = False
                logger.debug("Checking for enabled channels...")

                for ch_num in range(1, 5):
                    try:
                        channel = getattr(self.scope, f"channel{ch_num}", None)
                        if channel is not None:
                            is_enabled = channel.enabled
                            logger.debug(f"Channel {ch_num} enabled: {is_enabled}")
                            if is_enabled:
                                any_enabled = True
                                break
                    except Exception as e:
                        logger.debug(f"Error checking channel {ch_num}: {e}")
                        pass

                if not any_enabled:
                    # Enable channel 1 by default if none are enabled
                    logger.warning("No channels enabled, attempting to enable channel 1")
                    try:
                        self.scope.channel1.enable()
                        logger.info("Auto-enabled channel 1 for live view")
                        QMessageBox.information(
                            self,
                            "Channel Enabled",
                            "Channel 1 has been automatically enabled for live view.",
                        )
                    except Exception as e:
                        logger.error(f"Could not enable channel 1: {e}")
                        raise RuntimeError(f"No channels are enabled and could not enable channel 1: {e}")

                # Start live view worker thread
                logger.info("Starting live view worker thread...")
                self.live_view_worker = LiveViewWorker(self.scope, self)
                self.live_view_worker.waveforms_ready.connect(self._on_waveforms_ready)
                self.live_view_worker.error_occurred.connect(self._on_live_view_error)
                self.live_view_worker.status_update.connect(self._on_live_view_status)
                self.live_view_worker.start()

                self.statusBar().showMessage("Live view enabled (AUTO mode)")
                logger.info("Live view worker thread started")

            except Exception as e:
                logger.error(f"Failed to start live view: {e}")
                QMessageBox.warning(
                    self,
                    "Live View Error",
                    f"Could not start live view:\n{str(e)}\n\n" f"Make sure the oscilloscope is connected and at least one channel is enabled.",
                )

                # Disable live view flag and uncheck the menu action
                self.is_live_view = False
                self.live_view_action.blockSignals(True)
                self.live_view_action.setChecked(False)
                self.live_view_action.blockSignals(False)
        else:
            # Stop live view
            if self.live_view_worker:
                logger.info("Stopping live view worker thread...")
                self.live_view_worker.stop()
                self.live_view_worker = None

            self.statusBar().showMessage("Live view disabled")
            logger.info("Live view disabled")

    def _on_waveforms_ready(self, waveforms):
        """Handle waveforms received from background worker thread.

        This runs on the main GUI thread, so it's safe to update the display.

        Args:
            waveforms: List of WaveformData objects
        """
        logger.info(f"Received {len(waveforms)} waveforms from worker thread")

        if waveforms:
            # Update display (this is fast with PyQtGraph)
            self.waveform_display.plot_multiple_waveforms(waveforms, fast_update=True)

            # Update status
            num_channels = len(waveforms)
            self.statusBar().showMessage(f"Live view: {num_channels} channel(s) updating")
        else:
            self.statusBar().showMessage("Live view: No enabled channels")

    def _on_live_view_error(self, error_info):
        """Handle errors from background worker thread.

        Args:
            error_info: Error information dictionary with details
        """
        # Log the full error
        error_msg = error_info.get("message", "Unknown error") if isinstance(error_info, dict) else str(error_info)
        logger.error(f"Live view worker error: {error_msg}")

        # Update status bar with brief message
        brief_msg = error_msg[:60] if len(error_msg) > 60 else error_msg
        self.statusBar().showMessage(f"Live view error: {brief_msg}", 5000)

        # Show detailed error dialog if we have structured error info
        if isinstance(error_info, dict):
            dialog = DetailedErrorDialog(error_info, self)
            dialog.exec()
        else:
            # Fallback for old-style string errors
            QMessageBox.warning(self, "Live View Error", str(error_info))

    def _on_live_view_status(self, status_msg):
        """Handle status updates from live view worker.

        Args:
            status_msg: Status message string
        """
        # Update status bar with worker status
        self.statusBar().showMessage(status_msg)
        logger.debug(f"Live view status: {status_msg}")

    def _on_save_waveform(self):
        """Handle save waveform action."""
        if not self.scope:
            QMessageBox.warning(self, "Not Connected", "No oscilloscope connected")
            return

        # Check if waveform display has data
        if not hasattr(self.waveform_display, "current_waveforms") or not self.waveform_display.current_waveforms:
            QMessageBox.information(
                self,
                "No Data",
                "No waveform data to save.\n\nCapture a waveform first using F8 or the Capture button.",
            )
            return

        try:
            # Ask user for file location and format
            file_filter = "CSV File (*.csv);;Enhanced CSV (*.csv);;NumPy Archive (*.npz);;MATLAB File (*.mat);;HDF5 File (*.h5);;All Files (*.*)"
            filename, selected_filter = QFileDialog.getSaveFileName(self, "Save Waveform", "waveform.csv", file_filter)

            if filename:
                # Determine format from filter
                format_map = {
                    "CSV File (*.csv)": "CSV",
                    "Enhanced CSV (*.csv)": "CSV_ENHANCED",
                    "NumPy Archive (*.npz)": "NPY",
                    "MATLAB File (*.mat)": "MAT",
                    "HDF5 File (*.h5)": "HDF5",
                }

                file_format = format_map.get(selected_filter)

                self.statusBar().showMessage("Saving waveform...")

                # Save all captured waveforms
                waveforms = self.waveform_display.current_waveforms
                if len(waveforms) == 1:
                    # Single waveform
                    self.scope.waveform.save_waveform(waveforms[0], filename, format=file_format)
                    msg = f"Waveform saved to {filename}"
                else:
                    # Multiple waveforms - save with channel suffix
                    import os

                    base, ext = os.path.splitext(filename)
                    for wf in waveforms:
                        ch_filename = f"{base}_CH{wf.channel}{ext}"
                        self.scope.waveform.save_waveform(wf, ch_filename, format=file_format)
                    msg = f"Saved {len(waveforms)} waveforms to {os.path.dirname(filename)}"

                self.statusBar().showMessage(msg)
                QMessageBox.information(self, "Waveform Saved", msg)
                logger.info(f"Waveform(s) saved successfully")

        except Exception as e:
            self.statusBar().showMessage("Save failed")
            QMessageBox.critical(self, "Save Error", f"Failed to save waveform:\n{str(e)}")
            logger.error(f"Waveform save failed: {e}")

    def _on_toggle_grid(self):
        """Toggle grid on waveform display."""
        if hasattr(self.waveform_display, "toggle_grid"):
            self.waveform_display.toggle_grid()
            logger.info("Toggled grid display")
        else:
            QMessageBox.information(
                self,
                "Grid Toggle",
                "Grid toggle will be available when waveform display is enhanced.",
            )

    def _on_reset_zoom(self):
        """Reset zoom on waveform display."""
        if hasattr(self.waveform_display, "reset_zoom"):
            self.waveform_display.reset_zoom()
            self.statusBar().showMessage("Zoom reset")
            logger.info("Reset zoom")
        else:
            QMessageBox.information(
                self,
                "Reset Zoom",
                "Zoom reset will be available when waveform display is enhanced.",
            )

    def _on_toggle_cursors(self):
        """Toggle cursor mode (cycle through off -> vertical -> both)."""
        current_mode = self.cursor_panel.current_mode

        # Cycle through modes: off -> vertical -> both -> off
        if current_mode == "off":
            self.cursor_panel.set_mode("vertical")
        elif current_mode == "vertical":
            self.cursor_panel.set_mode("both")
        else:
            self.cursor_panel.set_mode("off")

        logger.info(f"Toggled cursors to: {self.cursor_panel.current_mode}")

    def _update_cursor_values(self):
        """Update cursor value displays in cursor panel."""
        # Get cursor values from waveform display
        values = self.waveform_display.get_cursor_values()

        # Update cursor panel
        self.cursor_panel.update_cursor_values(x1=values.get("x1"), y1=values.get("y1"), x2=values.get("x2"), y2=values.get("y2"))

    def _on_math1_expression_changed(self, expression: str):
        """Handle Math1 expression change.

        Args:
            expression: New expression string
        """
        if self.scope and self.scope.math1:
            self.scope.math1.set_expression(expression)
            logger.info(f"Math1 expression set to: {expression}")

    def _on_math2_expression_changed(self, expression: str):
        """Handle Math2 expression change.

        Args:
            expression: New expression string
        """
        if self.scope and self.scope.math2:
            self.scope.math2.set_expression(expression)
            logger.info(f"Math2 expression set to: {expression}")

    def _on_math1_enabled_changed(self, enabled: bool):
        """Handle Math1 enable state change.

        Args:
            enabled: Enable state
        """
        if self.scope and self.scope.math1:
            if enabled:
                self.scope.math1.enable()
            else:
                self.scope.math1.disable()
            logger.info(f"Math1 {'enabled' if enabled else 'disabled'}")

    def _on_math2_enabled_changed(self, enabled: bool):
        """Handle Math2 enable state change.

        Args:
            enabled: Enable state
        """
        if self.scope and self.scope.math2:
            if enabled:
                self.scope.math2.enable()
            else:
                self.scope.math2.disable()
            logger.info(f"Math2 {'enabled' if enabled else 'disabled'}")

    def _on_fft_compute_requested(self, channel: str, window: str):
        """Handle FFT computation request.

        Args:
            channel: Channel name (C1, C2, C3, C4, M1, M2)
            window: Window function name
        """
        if not self.scope:
            QMessageBox.warning(self, "Not Connected", "No oscilloscope connected")
            return

        try:
            # Get waveform data
            waveform = None

            if channel.startswith("C"):
                # Hardware channel
                ch_num = int(channel[1])
                waveform = self.scope.get_waveform(ch_num)
            elif channel == "M1":
                # Math channel 1
                waveform = self._compute_math_waveform(self.scope.math1)
            elif channel == "M2":
                # Math channel 2
                waveform = self._compute_math_waveform(self.scope.math2)

            if waveform is None:
                QMessageBox.warning(self, "No Data", f"No waveform data available for {channel}")
                return

            # Compute FFT
            fft_result = self.scope.fft_analyzer.compute_fft(waveform, window=window, output_db=True)

            if fft_result:
                # Display FFT result
                self.fft_display.set_fft_result(fft_result)
                self.statusBar().showMessage(f"FFT computed for {channel} using {window} window")
                logger.info(f"FFT computed for {channel}")
            else:
                QMessageBox.warning(self, "FFT Error", "Failed to compute FFT")

        except Exception as e:
            QMessageBox.critical(self, "FFT Error", f"Error computing FFT:\n{str(e)}")
            logger.error(f"FFT computation error: {e}")

    def _compute_math_waveform(self, math_channel):
        """Compute math channel waveform.

        Args:
            math_channel: MathChannel instance

        Returns:
            Computed waveform or None
        """
        if not math_channel or not math_channel.enabled:
            return None

        # Get all available waveforms
        waveforms = {}
        for ch_num in self.scope.supported_channels:
            try:
                wf = self.scope.get_waveform(ch_num)
                if wf:
                    waveforms[f"C{ch_num}"] = wf
            except Exception as e:
                logger.warning(f"Failed to get waveform for C{ch_num}: {e}")

        # Compute math result
        return math_channel.compute(waveforms)

    def _on_save_reference(self):
        """Handle save reference request."""
        if not self.waveform_display.current_waveforms:
            QMessageBox.warning(self, "No Data", "No waveform data to save as reference")
            return

        # Ask for reference name
        name, ok = QInputDialog.getText(self, "Save Reference", "Enter reference name:")

        if ok and name:
            try:
                # Use first waveform
                waveform = self.waveform_display.current_waveforms[0]

                # Create metadata
                metadata = {
                    "source": "Live capture",
                    "model": (self.scope.device_info.get("model", "Unknown") if self.scope else "Unknown"),
                }

                # Save reference
                filepath = self.reference_manager.save_reference(waveform, name, metadata)

                QMessageBox.information(self, "Saved", f"Reference saved:\n{filepath}")
                logger.info(f"Reference saved: {name}")

                # Refresh list
                self._refresh_reference_list()

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save reference:\n{str(e)}")
                logger.error(f"Failed to save reference: {e}")

    def _on_load_reference(self, filepath: str):
        """Handle load reference request.

        Args:
            filepath: Path to reference file
        """
        try:
            # Load reference
            reference_data = self.reference_manager.load_reference(filepath)

            if reference_data:
                # Set reference in waveform display
                self.waveform_display.set_reference(reference_data)

                # Update reference panel
                self.reference_panel.set_loaded_reference(reference_data)

                # Calculate and display correlation if live waveform exists
                if self.waveform_display.current_waveforms:
                    waveform = self.waveform_display.current_waveforms[0]
                    correlation = self.reference_manager.calculate_correlation(waveform, reference_data)

                    # Calculate RMS difference
                    diff = self.reference_manager.calculate_difference(waveform, reference_data)
                    rms_diff = np.sqrt(np.mean(diff**2)) if diff is not None else None

                    self.reference_panel.update_comparison_stats(correlation, rms_diff)

                self.statusBar().showMessage("Reference loaded")
                logger.info(f"Reference loaded: {filepath}")
            else:
                QMessageBox.warning(self, "Error", "Failed to load reference")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load reference:\n{str(e)}")
            logger.error(f"Failed to load reference: {e}")

    def _on_delete_reference(self, filepath: str):
        """Handle delete reference request.

        Args:
            filepath: Path to reference file
        """
        try:
            # Delete reference
            success = self.reference_manager.delete_reference(filepath)

            if success:
                QMessageBox.information(self, "Deleted", "Reference deleted successfully")
                logger.info(f"Reference deleted: {filepath}")

                # Refresh list
                self._refresh_reference_list()

                # Clear if this was the loaded reference
                if self.waveform_display.get_reference_data():
                    ref_path = self.waveform_display.get_reference_data().get("filepath")
                    if ref_path == filepath:
                        self.waveform_display.clear_reference()
                        self.reference_panel._on_unload_reference()
            else:
                QMessageBox.warning(self, "Error", "Failed to delete reference")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete reference:\n{str(e)}")
            logger.error(f"Failed to delete reference: {e}")

    def _on_toggle_reference_difference(self, enabled: bool):
        """Handle toggle reference difference mode.

        Args:
            enabled: Whether difference mode is enabled
        """
        self.waveform_display.toggle_difference_mode(enabled)
        logger.info(f"Reference difference mode: {enabled}")

    def _refresh_reference_list(self):
        """Refresh the reference waveform list."""
        try:
            references = self.reference_manager.list_references()
            self.reference_panel.update_reference_list(references)
            logger.info(f"Reference list refreshed: {len(references)} references")
        except Exception as e:
            logger.error(f"Failed to refresh reference list: {e}")

    def _on_protocol_decode_requested(self, protocol: str, params: dict, channel_map: dict):
        """Handle protocol decode request.

        Args:
            protocol: Protocol name ('I2C', 'SPI', 'UART')
            params: Decode parameters
            channel_map: Channel mapping (signal_name -> channel_number)
        """
        if not self.scope:
            QMessageBox.warning(self, "Not Connected", "No oscilloscope connected")
            return

        try:
            # Get waveforms based on channel mapping
            waveforms = {}
            for signal_name, channel_str in channel_map.items():
                # Extract channel number
                ch_num = int(channel_str[1])  # 'C1' -> 1

                # Get waveform
                waveform = self.scope.get_waveform(ch_num)
                if waveform:
                    waveforms[signal_name] = waveform
                else:
                    QMessageBox.warning(self, "No Data", f"No waveform data available for channel {channel_str}")
                    return

            # Select decoder
            if protocol == "I2C":
                decoder = self.i2c_decoder
            elif protocol == "SPI":
                decoder = self.spi_decoder
            elif protocol == "UART":
                decoder = self.uart_decoder
            else:
                QMessageBox.warning(self, "Error", f"Unknown protocol: {protocol}")
                return

            # Decode
            self.statusBar().showMessage(f"Decoding {protocol}...")
            events = decoder.decode(waveforms, **params)

            # Display results
            self.protocol_decode_panel.display_events(events)

            self.statusBar().showMessage(f"{protocol} decode complete: {len(events)} events")
            logger.info(f"{protocol} decode complete: {len(events)} events")

        except Exception as e:
            QMessageBox.critical(self, "Decode Error", f"Error decoding protocol:\n{str(e)}")
            logger.error(f"Protocol decode error: {e}")
            self.statusBar().showMessage("Decode failed")

    def _on_protocol_export_requested(self):
        """Handle protocol event export request."""
        events = self.protocol_decode_panel.get_events()

        if not events:
            QMessageBox.warning(self, "No Data", "No events to export")
            return

        # Ask for filename
        filename, _ = QFileDialog.getSaveFileName(self, "Export Protocol Events", "", "CSV Files (*.csv);;All Files (*)")

        if filename:
            try:
                # Determine which decoder has the events
                # Use the first decoder that has events matching our list
                if self.i2c_decoder.events == events:
                    self.i2c_decoder.export_events_csv(filename)
                elif self.spi_decoder.events == events:
                    self.spi_decoder.export_events_csv(filename)
                elif self.uart_decoder.events == events:
                    self.uart_decoder.export_events_csv(filename)
                else:
                    # Fallback: export manually
                    import csv

                    with open(filename, "w", newline="") as f:
                        writer = csv.writer(f)
                        writer.writerow(["Timestamp", "Event Type", "Data", "Description", "Channel", "Valid"])
                        for event in events:
                            writer.writerow(
                                [
                                    f"{event.timestamp:.9f}",
                                    event.event_type.value,
                                    str(event.data),
                                    event.description,
                                    event.channel,
                                    "Yes" if event.valid else "No",
                                ]
                            )

                QMessageBox.information(self, "Export Complete", f"Events exported to:\n{filename}")
                logger.info(f"Protocol events exported: {filename}")

            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export events:\n{str(e)}")
                logger.error(f"Protocol export error: {e}")

    def _on_show_shortcuts(self):
        """Show keyboard shortcuts help dialog."""
        shortcuts_text = """
        <h3>Keyboard Shortcuts</h3>

        <h4>File Operations</h4>
        <table width="100%">
        <tr><td><b>Ctrl+O</b></td><td>Connect to oscilloscope</td></tr>
        <tr><td><b>Ctrl+S</b></td><td>Save waveform</td></tr>
        <tr><td><b>Ctrl+Shift+S</b></td><td>Save screenshot</td></tr>
        <tr><td><b>Ctrl+Q</b></td><td>Exit application</td></tr>
        </table>

        <h4>Acquisition</h4>
        <table width="100%">
        <tr><td><b>F5</b></td><td>Run (continuous acquisition)</td></tr>
        <tr><td><b>F6</b></td><td>Stop acquisition</td></tr>
        <tr><td><b>F7</b></td><td>Single trigger</td></tr>
        <tr><td><b>F8</b></td><td>Capture waveform</td></tr>
        <tr><td><b>Ctrl+R</b></td><td>Toggle live view</td></tr>
        </table>

        <h4>View</h4>
        <table width="100%">
        <tr><td><b>Ctrl+D</b></td><td>Open scope display (VNC)</td></tr>
        <tr><td><b>G</b></td><td>Toggle grid</td></tr>
        <tr><td><b>C</b></td><td>Toggle cursors</td></tr>
        <tr><td><b>Home</b></td><td>Reset zoom</td></tr>
        <tr><td><b>ESC</b></td><td>Clear all cursors</td></tr>
        </table>

        <h4>Help</h4>
        <table width="100%">
        <tr><td><b>F1</b></td><td>Show this help</td></tr>
        </table>
        """

        QMessageBox.about(self, "Keyboard Shortcuts", shortcuts_text)

    def _on_about(self):
        """Show about dialog."""
        about_text = """
        <h3>Siglent Oscilloscope Control</h3>
        <p><b>Version 0.1.0</b></p>
        <p>Advanced control application for Siglent oscilloscopes</p>

        <h4>Supported Models</h4>
        <ul>
        <li>SDS800X HD Series (SDS824X HD, SDS804X HD)</li>
        <li>SDS1000X-E Series (SDS1104X-E, SDS1204X-E, SDS1202X-E, SDS1102X-E)</li>
        <li>SDS2000X Plus Series (SDS2104X Plus, SDS2204X Plus, SDS2354X Plus)</li>
        <li>SDS5000X Series (SDS5104X, SDS5054X)</li>
        </ul>

        <p>Python package for programmatic and GUI-based oscilloscope control via Ethernet.</p>
        """
        QMessageBox.about(self, "About Siglent Oscilloscope Control", about_text)

    def closeEvent(self, event):
        """Handle window close event."""
        # Stop live view if running
        if self.is_live_view and self.live_view_worker:
            logger.info("Stopping live view worker on close...")
            self.live_view_worker.stop()
            self.live_view_worker = None

        # Disconnect from scope
        if self.scope:
            self.scope.disconnect()

        event.accept()
