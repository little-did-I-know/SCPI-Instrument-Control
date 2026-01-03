"""
LLM settings dialog for configuring AI features.

Allows users to configure Ollama, LM Studio, or OpenAI connections.
"""

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
    QLabel,
    QComboBox,
    QGroupBox,
    QMessageBox,
    QTabWidget,
    QWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
from pathlib import Path

from siglent.report_generator.llm.client import LLMClient, LLMConfig


class LLMSettingsDialog(QDialog):
    """Dialog for configuring LLM settings."""

    settings_saved = pyqtSignal(LLMConfig)

    def __init__(self, current_config: LLMConfig = None, parent=None):
        """
        Initialize LLM settings dialog.

        Args:
            current_config: Current LLM configuration
            parent: Parent widget
        """
        super().__init__(parent)
        self.config = current_config or LLMConfig()

        self.setWindowTitle("LLM Settings")
        self.setModal(True)
        self.resize(500, 400)

        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout()

        # Tabs for different presets
        tabs = QTabWidget()

        # Ollama tab
        ollama_tab = self._create_ollama_tab()
        tabs.addTab(ollama_tab, "Ollama")

        # LM Studio tab
        lm_studio_tab = self._create_lm_studio_tab()
        tabs.addTab(lm_studio_tab, "LM Studio")

        # OpenAI tab
        openai_tab = self._create_openai_tab()
        tabs.addTab(openai_tab, "OpenAI")

        # Custom tab
        custom_tab = self._create_custom_tab()
        tabs.addTab(custom_tab, "Custom")

        layout.addWidget(tabs)

        # Advanced settings
        advanced_group = QGroupBox("Advanced Settings")
        advanced_layout = QFormLayout()

        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(0.7)
        advanced_layout.addRow("Temperature:", self.temperature_spin)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 8000)
        self.max_tokens_spin.setSingleStep(100)
        self.max_tokens_spin.setValue(2000)
        advanced_layout.addRow("Max Tokens:", self.max_tokens_spin)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(10, 300)
        self.timeout_spin.setSuffix(" seconds")
        self.timeout_spin.setValue(60)
        advanced_layout.addRow("Timeout:", self.timeout_spin)

        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)

        # Buttons
        button_layout = QHBoxLayout()

        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self._test_connection)
        button_layout.addWidget(test_btn)

        button_layout.addStretch()

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _create_ollama_tab(self) -> QWidget:
        """Create Ollama configuration tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        info_label = QLabel(
            "Ollama runs locally on your machine providing privacy and no API costs.\n"
            "Download from: https://ollama.com"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        form = QFormLayout()

        self.ollama_port_spin = QSpinBox()
        self.ollama_port_spin.setRange(1, 65535)
        self.ollama_port_spin.setValue(11434)
        form.addRow("Port:", self.ollama_port_spin)

        self.ollama_model_edit = QLineEdit("llama3.2")
        form.addRow("Model:", self.ollama_model_edit)

        layout.addLayout(form)

        use_btn = QPushButton("Use Ollama Settings")
        use_btn.clicked.connect(self._use_ollama)
        layout.addWidget(use_btn)

        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _create_lm_studio_tab(self) -> QWidget:
        """Create LM Studio configuration tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        info_label = QLabel(
            "LM Studio provides a local LLM server with a user-friendly interface.\n"
            "Download from: https://lmstudio.ai"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        form = QFormLayout()

        self.lm_studio_port_spin = QSpinBox()
        self.lm_studio_port_spin.setRange(1, 65535)
        self.lm_studio_port_spin.setValue(1234)
        form.addRow("Port:", self.lm_studio_port_spin)

        self.lm_studio_model_edit = QLineEdit("local-model")
        form.addRow("Model:", self.lm_studio_model_edit)

        layout.addLayout(form)

        use_btn = QPushButton("Use LM Studio Settings")
        use_btn.clicked.connect(self._use_lm_studio)
        layout.addWidget(use_btn)

        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _create_openai_tab(self) -> QWidget:
        """Create OpenAI configuration tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        info_label = QLabel(
            "OpenAI provides cloud-based GPT models (requires API key and internet).\n"
            "Get API key from: https://platform.openai.com/api-keys"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        form = QFormLayout()

        self.openai_api_key_edit = QLineEdit()
        self.openai_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_api_key_edit.setPlaceholderText("sk-...")
        form.addRow("API Key:", self.openai_api_key_edit)

        self.openai_model_combo = QComboBox()
        self.openai_model_combo.addItems(["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"])
        form.addRow("Model:", self.openai_model_combo)

        layout.addLayout(form)

        use_btn = QPushButton("Use OpenAI Settings")
        use_btn.clicked.connect(self._use_openai)
        layout.addWidget(use_btn)

        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _create_custom_tab(self) -> QWidget:
        """Create custom configuration tab."""
        widget = QWidget()
        layout = QVBoxLayout()

        info_label = QLabel(
            "Configure a custom OpenAI-compatible endpoint."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        form = QFormLayout()

        self.custom_endpoint_edit = QLineEdit()
        self.custom_endpoint_edit.setPlaceholderText("http://localhost:8000/v1")
        form.addRow("Endpoint:", self.custom_endpoint_edit)

        self.custom_model_edit = QLineEdit()
        form.addRow("Model:", self.custom_model_edit)

        self.custom_api_key_edit = QLineEdit()
        self.custom_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.custom_api_key_edit.setPlaceholderText("(optional)")
        form.addRow("API Key:", self.custom_api_key_edit)

        layout.addLayout(form)

        use_btn = QPushButton("Use Custom Settings")
        use_btn.clicked.connect(self._use_custom)
        layout.addWidget(use_btn)

        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _use_ollama(self):
        """Use Ollama settings."""
        port = self.ollama_port_spin.value()
        model = self.ollama_model_edit.text()

        self.custom_endpoint_edit.setText(f"http://localhost:{port}/v1")
        self.custom_model_edit.setText(model)
        self.custom_api_key_edit.clear()

    def _use_lm_studio(self):
        """Use LM Studio settings."""
        port = self.lm_studio_port_spin.value()
        model = self.lm_studio_model_edit.text()

        self.custom_endpoint_edit.setText(f"http://localhost:{port}/v1")
        self.custom_model_edit.setText(model)
        self.custom_api_key_edit.clear()

    def _use_openai(self):
        """Use OpenAI settings."""
        api_key = self.openai_api_key_edit.text()
        model = self.openai_model_combo.currentText()

        self.custom_endpoint_edit.setText("https://api.openai.com/v1")
        self.custom_model_edit.setText(model)
        self.custom_api_key_edit.setText(api_key)

    def _use_custom(self):
        """Custom settings are already in the fields."""
        pass

    def _load_config(self):
        """Load current configuration into UI."""
        self.custom_endpoint_edit.setText(self.config.endpoint)
        self.custom_model_edit.setText(self.config.model)
        if self.config.api_key:
            self.custom_api_key_edit.setText(self.config.api_key)

        self.temperature_spin.setValue(self.config.temperature)
        self.max_tokens_spin.setValue(self.config.max_tokens)
        self.timeout_spin.setValue(self.config.timeout)

    def get_config(self) -> LLMConfig:
        """
        Get the configured LLM settings.

        Returns:
            LLMConfig object
        """
        endpoint = self.custom_endpoint_edit.text().strip()
        model = self.custom_model_edit.text().strip()
        api_key = self.custom_api_key_edit.text().strip() or None

        return LLMConfig(
            endpoint=endpoint,
            model=model,
            api_key=api_key,
            temperature=self.temperature_spin.value(),
            max_tokens=self.max_tokens_spin.value(),
            timeout=self.timeout_spin.value(),
        )

    def _test_connection(self):
        """Test the LLM connection."""
        config = self.get_config()

        if not config.endpoint or not config.model:
            QMessageBox.warning(
                self,
                "Invalid Configuration",
                "Please configure endpoint and model before testing.",
            )
            return

        try:
            client = LLMClient(config)

            # Show progress
            QMessageBox.information(
                self,
                "Testing Connection",
                "Testing connection to LLM service...\nThis may take a few seconds.",
            )

            success = client.test_connection()

            if success:
                QMessageBox.information(
                    self,
                    "Connection Successful",
                    f"Successfully connected to {config.model} at {config.endpoint}",
                )
            else:
                QMessageBox.warning(
                    self,
                    "Connection Failed",
                    "Failed to connect to LLM service.\n"
                    "Please check your settings and ensure the service is running.",
                )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Connection Error",
                f"Error testing connection:\n{str(e)}",
            )

    def accept(self):
        """Save settings and close dialog."""
        config = self.get_config()

        if not config.endpoint or not config.model:
            QMessageBox.warning(
                self,
                "Invalid Configuration",
                "Please configure endpoint and model.",
            )
            return

        self.config = config
        self.settings_saved.emit(config)
        super().accept()
