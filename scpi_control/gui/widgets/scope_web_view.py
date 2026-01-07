"""Web view widget for embedded oscilloscope interface."""

import logging
from typing import Optional

from PyQt6.QtCore import QUrl
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

logger = logging.getLogger(__name__)


class ScopeWebView(QWidget):
    """Widget for displaying embedded oscilloscope web interface."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize scope web view widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.scope_ip: Optional[str] = None
        self._init_ui()

    def _init_ui(self):
        """Initialize user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Control bar
        control_bar = QHBoxLayout()
        control_bar.setContentsMargins(5, 5, 5, 5)

        # URL/IP input
        url_label = QLabel("Scope IP:")
        control_bar.addWidget(url_label)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("192.168.1.207")
        self.url_input.returnPressed.connect(self._on_load_url)
        control_bar.addWidget(self.url_input)

        # Load button
        load_btn = QPushButton("Connect to Web Interface")
        load_btn.clicked.connect(self._on_load_url)
        control_bar.addWidget(load_btn)

        # Reload button
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self._on_reload)
        control_bar.addWidget(reload_btn)

        # Fullscreen button
        fullscreen_btn = QPushButton("Fullscreen noVNC")
        fullscreen_btn.clicked.connect(self._on_fullscreen)
        control_bar.addWidget(fullscreen_btn)

        control_bar.addStretch()

        layout.addLayout(control_bar)

        # Web view
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

        layout.addWidget(self.web_view)

        # Info label
        info_label = QLabel(
            "<b>Oscilloscope Web Interface:</b><br>"
            "This displays the built-in web interface of your Siglent oscilloscope.<br>"
            "You can interact with it just like on the physical scope's touchscreen.<br>"
            "<i>Note: The web interface provides full VNC access to the scope.</i>"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("QLabel { font-size: 9pt; color: #888; padding: 5px; }")
        layout.addWidget(info_label)

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
            return

        # Construct the noVNC URL
        url = f"http://{self.scope_ip}/Instrument/novnc/vnc_auto.php"

        logger.info(f"Loading oscilloscope web interface: {url}")
        self.web_view.setUrl(QUrl(url))

    def _on_load_url(self):
        """Handle load URL button or enter key."""
        ip = self.url_input.text().strip()
        if ip:
            self.set_scope_ip(ip)
        else:
            logger.warning("No IP address entered")

    def _on_reload(self):
        """Handle reload button."""
        self.web_view.reload()
        logger.info("Reloading web interface")

    def _on_fullscreen(self):
        """Handle fullscreen button - inject JavaScript to click fullscreen."""
        # Try to trigger fullscreen in the noVNC viewer
        js_code = """
        // Try to find and click the fullscreen button in noVNC
        try {
            var buttons = document.querySelectorAll('button, input[type="button"]');
            for (var i = 0; i < buttons.length; i++) {
                if (buttons[i].title && buttons[i].title.toLowerCase().includes('fullscreen')) {
                    buttons[i].click();
                    break;
                }
            }
        } catch(e) {
            console.log('Could not trigger fullscreen:', e);
        }
        """
        self.web_view.page().runJavaScript(js_code)
        logger.info("Attempted to trigger fullscreen mode")

    def _on_load_started(self):
        """Handle load started event."""
        logger.debug("Web interface loading started")

    def _on_load_finished(self, success: bool):
        """Handle load finished event.

        Args:
            success: True if page loaded successfully
        """
        if success:
            logger.info("Web interface loaded successfully")
        else:
            logger.error("Failed to load web interface")
