"""Separate window for VNC oscilloscope display."""

import logging
from typing import Optional

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QAction
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QToolBar, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)


class VNCWindow(QMainWindow):
    """Separate window for displaying VNC oscilloscope interface."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize VNC window.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.scope_ip: Optional[str] = None
        self._init_ui()

    def _init_ui(self):
        """Initialize user interface."""
        self.setWindowTitle("Oscilloscope Display (VNC)")
        self.setGeometry(100, 100, 1024, 768)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create web view first (needed by toolbar)
        self.web_view = QWebEngineView()

        # Configure web engine settings
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)

        # Connect signals
        self.web_view.loadStarted.connect(self._on_load_started)
        self.web_view.loadFinished.connect(self._on_load_finished)

        # Create toolbar (after web_view is created)
        toolbar = self._create_toolbar()
        self.addToolBar(toolbar)

        layout.addWidget(self.web_view)

        # Status bar
        self.statusBar().showMessage("Ready")

    def _create_toolbar(self) -> QToolBar:
        """Create toolbar with controls.

        Returns:
            Toolbar widget
        """
        toolbar = QToolBar("VNC Controls")
        toolbar.setMovable(False)

        # IP input
        toolbar.addWidget(QLabel("Scope IP:"))

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("192.168.1.207")
        self.url_input.setMaximumWidth(150)
        self.url_input.returnPressed.connect(self._on_load_url)
        toolbar.addWidget(self.url_input)

        # Connect button
        connect_action = QAction("Connect", self)
        connect_action.triggered.connect(self._on_load_url)
        toolbar.addAction(connect_action)

        toolbar.addSeparator()

        # Reload button
        reload_action = QAction("Reload", self)
        reload_action.triggered.connect(self._on_reload)
        toolbar.addAction(reload_action)

        # Back button
        back_action = QAction("Back", self)
        back_action.triggered.connect(self.web_view.back)
        toolbar.addAction(back_action)

        # Forward button
        forward_action = QAction("Forward", self)
        forward_action.triggered.connect(self.web_view.forward)
        toolbar.addAction(forward_action)

        toolbar.addSeparator()

        # Fullscreen button
        fullscreen_action = QAction("Fullscreen", self)
        fullscreen_action.setCheckable(True)
        fullscreen_action.toggled.connect(self._on_fullscreen_toggled)
        toolbar.addAction(fullscreen_action)

        toolbar.addSeparator()

        # Help button
        help_action = QAction("Help", self)
        help_action.triggered.connect(self._show_help)
        toolbar.addAction(help_action)

        return toolbar

    def set_scope_ip(self, ip: str):
        """Set the oscilloscope IP address and load interface.

        Args:
            ip: Oscilloscope IP address
        """
        self.scope_ip = ip
        self.url_input.setText(ip)
        self._load_scope_interface()

    def _load_scope_interface(self):
        """Load the oscilloscope's web interface."""
        if not self.scope_ip:
            logger.warning("No scope IP address set")
            self.statusBar().showMessage("No IP address set")
            return

        # Construct the noVNC URL
        url = f"http://{self.scope_ip}/Instrument/novnc/vnc_auto.php"

        logger.info(f"Loading oscilloscope VNC interface: {url}")
        self.statusBar().showMessage(f"Loading {url}...")
        self.web_view.setUrl(QUrl(url))

    def _on_load_url(self):
        """Handle load URL button or enter key."""
        ip = self.url_input.text().strip()
        if ip:
            self.set_scope_ip(ip)
        else:
            logger.warning("No IP address entered")
            self.statusBar().showMessage("Please enter an IP address")

    def _on_reload(self):
        """Handle reload button."""
        self.web_view.reload()
        logger.info("Reloading VNC interface")
        self.statusBar().showMessage("Reloading...")

    def _on_fullscreen_toggled(self, checked: bool):
        """Handle fullscreen toggle.

        Args:
            checked: True for fullscreen, False for normal
        """
        if checked:
            self.showFullScreen()
            logger.info("Entered fullscreen mode")
        else:
            self.showNormal()
            logger.info("Exited fullscreen mode")

    def _on_load_started(self):
        """Handle load started event."""
        logger.debug("VNC interface loading started")
        self.statusBar().showMessage("Loading...")

    def _on_load_finished(self, success: bool):
        """Handle load finished event.

        Args:
            success: True if page loaded successfully
        """
        if success:
            logger.info("VNC interface loaded successfully")
            self.statusBar().showMessage("Connected to oscilloscope")
        else:
            logger.error("Failed to load VNC interface")
            self.statusBar().showMessage("Failed to load VNC interface - Check IP address and network connection")

            # Show helpful error message
            QMessageBox.warning(
                self,
                "Connection Failed",
                f"Failed to load the oscilloscope VNC interface.\n\n"
                f"Troubleshooting:\n"
                f"1. Verify the oscilloscope IP address is correct\n"
                f"2. Ensure the oscilloscope is powered on and connected to the network\n"
                f"3. Check that VNC/web interface is enabled on the oscilloscope\n"
                f"4. Verify your computer can ping the oscilloscope\n\n"
                f"Current URL: http://{self.scope_ip}/Instrument/novnc/vnc_auto.php",
            )

    def _show_help(self):
        """Show help dialog for VNC viewer."""
        help_text = """
        <h3>VNC Viewer Help</h3>

        <p>This window displays the oscilloscope's built-in screen interface using VNC.</p>

        <h4>How to Use:</h4>
        <ol>
        <li>Enter your oscilloscope's IP address in the toolbar</li>
        <li>Click "Connect" to load the interface</li>
        <li>Use the mouse and keyboard to interact with the oscilloscope display</li>
        </ol>

        <h4>Toolbar Buttons:</h4>
        <ul>
        <li><b>Connect</b> - Connect to the oscilloscope at the specified IP</li>
        <li><b>Reload</b> - Reload the current page</li>
        <li><b>Back/Forward</b> - Navigate browser history</li>
        <li><b>Fullscreen</b> - Toggle fullscreen mode (or press ESC to exit)</li>
        </ul>

        <h4>Requirements:</h4>
        <ul>
        <li>Oscilloscope must be connected to the network</li>
        <li>VNC/web interface must be enabled on the oscilloscope</li>
        <li>Firewall must allow HTTP connections to the oscilloscope</li>
        </ul>

        <h4>Keyboard Shortcuts:</h4>
        <ul>
        <li><b>ESC</b> - Exit fullscreen mode</li>
        <li><b>Enter</b> - Connect (when IP field is focused)</li>
        </ul>
        """

        QMessageBox.about(self, "VNC Viewer Help", help_text)

    def keyPressEvent(self, event):
        """Handle key press events.

        Args:
            event: Key event
        """
        # ESC key exits fullscreen
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.showNormal()
        else:
            super().keyPressEvent(event)
