"""Main window for Siglent oscilloscope control GUI."""

import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QStatusBar, QMessageBox, QInputDialog,
    QGroupBox, QTabWidget
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction

from siglent import Oscilloscope
from siglent.exceptions import ConnectionError, SiglentError
from siglent.gui.widgets.waveform_display import WaveformDisplay
from siglent.gui.widgets.channel_control import ChannelControl
from siglent.gui.widgets.trigger_control import TriggerControl
from siglent.gui.widgets.measurement_panel import MeasurementPanel
from siglent.gui.widgets.timebase_control import TimebaseControl
from siglent.gui.widgets.scope_web_view import ScopeWebView

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window for oscilloscope control."""

    def __init__(self):
        """Initialize main window."""
        super().__init__()

        self.scope: Optional[Oscilloscope] = None
        self.is_live_view = False
        self.live_timer = QTimer()
        self.live_timer.timeout.connect(self._update_live_view)

        # Control widgets (initialized in _init_ui)
        self.channel_control: Optional[ChannelControl] = None
        self.trigger_control: Optional[TriggerControl] = None
        self.measurement_panel: Optional[MeasurementPanel] = None
        self.timebase_control: Optional[TimebaseControl] = None
        self.scope_web_view: Optional[ScopeWebView] = None

        self._init_ui()
        self._create_menus()
        self._create_toolbar()
        self._create_status_bar()

        logger.info("Main window initialized")

    def _init_ui(self):
        """Initialize user interface."""
        self.setWindowTitle("Siglent Oscilloscope Control")
        self.setGeometry(100, 100, 1400, 800)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout(central_widget)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - Controls
        left_panel = self._create_control_panel()
        splitter.addWidget(left_panel)

        # Right panel - Waveform display
        right_panel = self._create_display_panel()
        splitter.addWidget(right_panel)

        # Set initial sizes (30% controls, 70% display)
        splitter.setSizes([400, 1000])

        main_layout.addWidget(splitter)

    def _create_control_panel(self) -> QWidget:
        """Create the left control panel.

        Returns:
            Control panel widget
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # Create tab widget for controls
        tabs = QTabWidget()

        # Channels tab
        self.channel_control = ChannelControl()
        tabs.addTab(self.channel_control, "Channels")

        # Trigger tab
        self.trigger_control = TriggerControl()
        tabs.addTab(self.trigger_control, "Trigger")

        # Timebase tab
        self.timebase_control = TimebaseControl()
        tabs.addTab(self.timebase_control, "Timebase")

        # Measurements tab
        self.measurement_panel = MeasurementPanel()
        tabs.addTab(self.measurement_panel, "Measurements")

        layout.addWidget(tabs)

        return panel

    def _create_display_panel(self) -> QWidget:
        """Create the right display panel.

        Returns:
            Display panel widget
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create tab widget for display views
        display_tabs = QTabWidget()

        # Waveform display tab
        self.waveform_display = WaveformDisplay()
        display_tabs.addTab(self.waveform_display, "Waveform Plot")

        # Web interface tab
        self.scope_web_view = ScopeWebView()
        display_tabs.addTab(self.scope_web_view, "Scope Display (VNC)")

        layout.addWidget(display_tabs)

        return panel

    def _create_menus(self):
        """Create menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        connect_action = QAction("&Connect...", self)
        connect_action.setShortcut("Ctrl+O")
        connect_action.triggered.connect(self._on_connect)
        file_menu.addAction(connect_action)

        disconnect_action = QAction("&Disconnect", self)
        disconnect_action.triggered.connect(self._on_disconnect)
        file_menu.addAction(disconnect_action)

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
        live_view_action.toggled.connect(self._on_toggle_live_view)
        acq_menu.addAction(live_view_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        auto_setup_action = QAction("&Auto Setup", self)
        auto_setup_action.triggered.connect(self._on_auto_setup)
        view_menu.addAction(auto_setup_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_about)
        help_menu.addAction(about_action)

    def _create_toolbar(self):
        """Create toolbar."""
        toolbar = self.addToolBar("Main Toolbar")

        # Add actions to toolbar
        connect_action = QAction("Connect", self)
        connect_action.triggered.connect(self._on_connect)
        toolbar.addAction(connect_action)

        disconnect_action = QAction("Disconnect", self)
        disconnect_action.triggered.connect(self._on_disconnect)
        toolbar.addAction(disconnect_action)

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

    def _create_status_bar(self):
        """Create status bar."""
        self.statusBar().showMessage("Not connected")

    def _on_connect(self):
        """Handle connect action."""
        # Get IP address from user
        ip, ok = QInputDialog.getText(
            self, "Connect to Oscilloscope",
            "Enter oscilloscope IP address:",
            text="192.168.1.100"
        )

        if ok and ip:
            try:
                self.statusBar().showMessage(f"Connecting to {ip}...")
                self.scope = Oscilloscope(ip)
                self.scope.connect()

                device_info = self.scope.device_info
                model = device_info.get('model', 'Unknown') if device_info else 'Unknown'

                # Pass scope reference to all control widgets
                self.channel_control.set_scope(self.scope)
                self.trigger_control.set_scope(self.scope)
                self.measurement_panel.set_scope(self.scope)
                self.timebase_control.set_scope(self.scope)

                # Set IP address for web view
                self.scope_web_view.set_scope_ip(ip)

                self.statusBar().showMessage(f"Connected to {model} at {ip}")
                QMessageBox.information(
                    self, "Connected",
                    f"Successfully connected to {model}\nIP: {ip}"
                )
                logger.info(f"Connected to oscilloscope at {ip}")

            except (ConnectionError, SiglentError) as e:
                self.statusBar().showMessage("Connection failed")
                QMessageBox.critical(
                    self, "Connection Error",
                    f"Failed to connect to oscilloscope:\n{str(e)}"
                )
                logger.error(f"Connection failed: {e}")
                self.scope = None

    def _on_disconnect(self):
        """Handle disconnect action."""
        if self.scope:
            # Stop live view if running
            if self.is_live_view:
                self._on_toggle_live_view(False)

            self.scope.disconnect()
            self.scope = None

            # Clear scope reference from all control widgets
            self.channel_control.set_scope(None)
            self.trigger_control.set_scope(None)
            self.measurement_panel.set_scope(None)
            self.timebase_control.set_scope(None)

            self.statusBar().showMessage("Disconnected")
            logger.info("Disconnected from oscilloscope")
        else:
            QMessageBox.warning(self, "Not Connected", "No oscilloscope connected")

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

    def _on_capture_waveform(self):
        """Handle capture waveform action."""
        if not self.scope:
            QMessageBox.warning(self, "Not Connected", "No oscilloscope connected")
            return

        try:
            # Check if at least one channel is enabled
            any_enabled = False
            for ch_num in range(1, 5):
                try:
                    channel = getattr(self.scope, f"channel{ch_num}")
                    if channel.enabled:
                        any_enabled = True
                        break
                except Exception:
                    pass

            if not any_enabled:
                # Ask user if they want to enable channel 1
                reply = QMessageBox.question(
                    self, "No Channels Enabled",
                    "No channels are currently enabled.\n\nWould you like to enable Channel 1?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    try:
                        self.scope.channel1.enable()
                        logger.info("Enabled channel 1 for capture")
                    except Exception as e:
                        QMessageBox.critical(
                            self, "Error",
                            f"Could not enable channel 1:\n{str(e)}"
                        )
                        return
                else:
                    return

            self.statusBar().showMessage("Capturing waveforms...")

            # Capture waveforms from all enabled channels
            waveforms = []
            errors = []
            for ch_num in range(1, 5):  # Channels 1-4
                try:
                    channel = getattr(self.scope, f"channel{ch_num}")
                    if channel.enabled:
                        waveform = self.scope.get_waveform(ch_num)
                        waveforms.append(waveform)
                        logger.info(f"Captured waveform from channel {ch_num}")
                except Exception as e:
                    errors.append(f"CH{ch_num}: {str(e)}")
                    logger.warning(f"Could not capture from channel {ch_num}: {e}")

            if waveforms:
                # Display waveforms
                self.waveform_display.plot_multiple_waveforms(waveforms)
                self.statusBar().showMessage(f"Captured {len(waveforms)} waveform(s)")
            else:
                self.statusBar().showMessage("Capture failed - no data")
                error_msg = "Could not capture waveforms."
                if errors:
                    error_msg += "\n\nErrors:\n" + "\n".join(errors[:3])  # Show first 3 errors
                QMessageBox.warning(self, "Capture Failed", error_msg)

        except SiglentError as e:
            self.statusBar().showMessage("Capture failed")
            QMessageBox.critical(self, "Capture Error", f"Failed to capture waveforms:\n{str(e)}")
            logger.error(f"Waveform capture failed: {e}")

    def _on_toggle_live_view(self, checked: bool):
        """Handle live view toggle.

        Args:
            checked: True to enable live view, False to disable
        """
        if not self.scope:
            QMessageBox.warning(self, "Not Connected", "No oscilloscope connected")
            return

        self.is_live_view = checked

        if checked:
            try:
                # Ensure scope is running in AUTO mode for continuous acquisition
                self.scope.trigger.mode = "AUTO"
                self.scope.run()

                # Check if at least one channel is enabled
                any_enabled = False
                for ch_num in range(1, 5):
                    try:
                        channel = getattr(self.scope, f"channel{ch_num}")
                        if channel.enabled:
                            any_enabled = True
                            break
                    except Exception:
                        pass

                if not any_enabled:
                    # Enable channel 1 by default if none are enabled
                    try:
                        self.scope.channel1.enable()
                        logger.info("Auto-enabled channel 1 for live view")
                        QMessageBox.information(
                            self, "Channel Enabled",
                            "Channel 1 has been automatically enabled for live view."
                        )
                    except Exception as e:
                        logger.error(f"Could not enable channel 1: {e}")

                # Start live view
                self.live_timer.start(200)  # Update every 200ms
                self.statusBar().showMessage("Live view enabled (AUTO mode)")
                logger.info("Live view enabled")

            except Exception as e:
                logger.error(f"Failed to start live view: {e}")
                QMessageBox.warning(
                    self, "Live View Error",
                    f"Could not start live view:\n{str(e)}\n\nMake sure the oscilloscope is connected."
                )
                self.is_live_view = False
        else:
            # Stop live view
            self.live_timer.stop()
            self.statusBar().showMessage("Live view disabled")
            logger.info("Live view disabled")

    def _update_live_view(self):
        """Update waveform display for live view."""
        if not self.scope or not self.scope.is_connected:
            self.live_timer.stop()
            self.is_live_view = False
            return

        try:
            # Acquire waveforms from enabled channels
            waveforms = []
            errors = []

            for ch_num in range(1, 5):  # Channels 1-4
                try:
                    channel = getattr(self.scope, f"channel{ch_num}")
                    if channel.enabled:
                        waveform = self.scope.get_waveform(ch_num)
                        waveforms.append(waveform)
                except Exception as e:
                    errors.append(f"CH{ch_num}: {str(e)}")
                    logger.debug(f"Could not acquire waveform from channel {ch_num}: {e}")

            # Update display
            if waveforms:
                self.waveform_display.plot_multiple_waveforms(waveforms)
                # Update status with success info
                num_channels = len(waveforms)
                self.statusBar().showMessage(
                    f"Live view: {num_channels} channel(s) updating"
                )
            else:
                # No waveforms acquired
                if errors:
                    logger.warning(f"Live view errors: {'; '.join(errors)}")
                    self.statusBar().showMessage(
                        f"Live view: No data (check signal and trigger)"
                    )
                else:
                    logger.debug("No enabled channels for live view")
                    self.statusBar().showMessage("Live view: No enabled channels")

        except Exception as e:
            logger.error(f"Error updating live view: {e}")
            self.statusBar().showMessage(f"Live view error: {str(e)[:50]}")
            # Don't stop live view on error, just skip this update

    def _on_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self, "About",
            "<h3>Siglent Oscilloscope Control</h3>"
            "<p>Version 0.1.0</p>"
            "<p>Control application for Siglent SD824x HD oscilloscopes</p>"
            "<p>Python package for programmatic and GUI-based oscilloscope control</p>"
        )

    def closeEvent(self, event):
        """Handle window close event."""
        # Stop live view if running
        if self.is_live_view:
            self.live_timer.stop()

        # Disconnect from scope
        if self.scope:
            self.scope.disconnect()

        event.accept()
